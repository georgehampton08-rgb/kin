import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_background_geolocation/flutter_background_geolocation.dart' as bg;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import '../providers/location_provider.dart';
import 'database_service.dart';
import 'dart:io' show Platform;
import 'package:package_info_plus/package_info_plus.dart';
import 'package:device_info_plus/device_info_plus.dart';
// ── Constants ────────────────────────────────────────────────
const double _lowBatteryThreshold = 20.0;
const int _heartbeatIntervalMinutes = 5;

// Normal mode config
const double _normalDistanceFilter = 50.0;
const int _normalStopTimeout = 5;

// Low-battery mode config (doubled)
const double _lowBatteryDistanceFilter = 100.0;
const int _lowBatteryStopTimeout = 10;

@pragma('vm:entry-point')
void locationHeadlessTask(bg.HeadlessEvent headlessEvent) async {
  switch (headlessEvent.name) {
    case bg.Event.LOCATION:
      bg.Location location = headlessEvent.event;
      final battery = location.battery.level * 100;
      await DatabaseService().insertLocation({
        'latitude': location.coords.latitude,
        'longitude': location.coords.longitude,
        'accuracy': location.coords.accuracy,
        'speed': location.coords.speed,
        'battery_level': battery,
        'timestamp': location.timestamp,
        'synced': 0,
      });

      // Try to flush if we have credentials
      try {
        const storage = FlutterSecureStorage();
        final token = await storage.read(key: 'access_token');
        final deviceId = await storage.read(key: 'device_id');
        final apiUrl = await storage.read(key: 'api_url');
        
        await DatabaseService().flushIfReady(
          lowBatteryMode: battery < _lowBatteryThreshold,
          token: token,
          deviceId: deviceId,
          apiUrl: apiUrl,
        );
      } catch (e) {
        debugPrint('[HeadlessTask] Sync failed -> $e');
      }
      break;
    case bg.Event.MOTIONCHANGE:
      bg.Location location = headlessEvent.event;
      debugPrint('[HeadlessMotionChange] isMoving=${location.isMoving}');
      // Send a heartbeat if stopped, just like the foreground service
      if (!location.isMoving) {
        try {
          const storage = FlutterSecureStorage();
          final token = await storage.read(key: 'access_token');
          final deviceId = await storage.read(key: 'device_id');
          final apiUrl = await storage.read(key: 'api_url');
          if (token != null && deviceId != null && apiUrl != null) {
            final body = json.encode({
              'device_id': deviceId,
              'battery_level': location.battery.level * 100,
              'gps_accuracy': location.coords.accuracy,
              'timestamp': DateTime.now().toUtc().toIso8601String(),
            });
            await http.post(
              Uri.parse('$apiUrl/api/v1/telemetry/heartbeat'),
              headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer $token',
              },
              body: body,
            );
          }
        } catch (e) {
          debugPrint('[HeadlessTask] Heartbeat failed -> $e');
        }
      }
      break;
    case bg.Event.ACTIVITYCHANGE:
      bg.ActivityChangeEvent event = headlessEvent.event;
      debugPrint('[HeadlessActivityChange] ${event.activity} confidence=${event.confidence}');
      break;
    default:
      break;
  }
}

class LocationService {
  final LocationProvider locationProvider;

  LocationService(this.locationProvider);

  Timer? _heartbeatTimer;
  bool _lowBatteryMode = false;
  String? _authToken;
  String? _deviceId;
  String? _apiUrl;

  /// Call after login to store the JWT and device identifier
  void setCredentials({required String token, required String deviceId, required String apiUrl}) {
    _authToken = token;
    _deviceId = deviceId;
    _apiUrl = apiUrl;
  }

  Future<void> init() async {
    // ── Location events ──────────────────────────────────────
    bg.BackgroundGeolocation.onLocation((bg.Location location) async {
      locationProvider.updateLocation(location);

      final battery = location.battery.level * 100;
      final speed = location.coords.speed;

      // Battery-aware throttling
      await _applyBatteryMode(battery);

      // Store locally
      await DatabaseService().insertLocation({
        'latitude': location.coords.latitude,
        'longitude': location.coords.longitude,
        'accuracy': location.coords.accuracy,
        'speed': speed,
        'battery_level': battery,
        'timestamp': location.timestamp,
        'synced': 0,
      });

      // Upload (batch or MQTT depending on mode)
      await DatabaseService().flushIfReady(
        lowBatteryMode: _lowBatteryMode,
        token: _authToken,
        deviceId: _deviceId,
        apiUrl: _apiUrl,
      );
    }, (bg.LocationError error) {
      debugPrint('[onLocation] ERROR: $error');
    });

    // ── Motion change — trip boundary events ─────────────────
    bg.BackgroundGeolocation.onMotionChange((bg.Location location) async {
      final isMoving = location.isMoving;
      debugPrint('[onMotionChange] isMoving=$isMoving speed=${location.coords.speed}');

      if (!isMoving) {
        // Device stopped — the backend state machine handles PAUSED→CLOSED
        // but we send a heartbeat immediately so the backend knows
        await _sendHeartbeat(
          batteryLevel: location.battery.level * 100,
          gpsAccuracy: location.coords.accuracy,
        );
      }
    });

    // ── Activity change ──────────────────────────────────────
    bg.BackgroundGeolocation.onActivityChange((bg.ActivityChangeEvent event) {
      debugPrint(
        '[onActivityChange] activity=${event.activity} '
        'confidence=${event.confidence}',
      );
    });

    bg.BackgroundGeolocation.onProviderChange((bg.ProviderChangeEvent event) {
      debugPrint('[onProviderChange]: $event');
    });

    // ── Configuration ────────────────────────────────────────
    await bg.BackgroundGeolocation.ready(bg.Config(
      desiredAccuracy: bg.Config.DESIRED_ACCURACY_HIGH,
      distanceFilter: _normalDistanceFilter,
      stopTimeout: _normalStopTimeout,
      stopOnTerminate: false,
      startOnBoot: true,
      debug: false,
      logLevel: bg.Config.LOG_LEVEL_WARNING,
      reset: false, // Don't reset on each ready() call
    ));

    // ── Dry-run state log ────────────────────────────────────
    bg.State state = await bg.BackgroundGeolocation.state;
    debugPrint('[LocationService] Config: '
        'distanceFilter=${state.distanceFilter}m '
        'stopTimeout=${state.stopTimeout}min');

    // ── Start heartbeat timer ────────────────────────────────
    _startHeartbeatTimer();

    await bg.BackgroundGeolocation.start();
  }

  // ── Battery-aware throttling ─────────────────────────────

  Future<void> _applyBatteryMode(double batteryLevel) async {
    final shouldBeLowBattery = batteryLevel < _lowBatteryThreshold;

    if (shouldBeLowBattery && !_lowBatteryMode) {
      _lowBatteryMode = true;
      debugPrint('[LocationService] LOW_BATTERY_MODE_ACTIVE battery=$batteryLevel%');
      await bg.BackgroundGeolocation.setConfig(bg.Config(
        distanceFilter: _lowBatteryDistanceFilter,
        stopTimeout: _lowBatteryStopTimeout,
      ));
    } else if (!shouldBeLowBattery && _lowBatteryMode) {
      _lowBatteryMode = false;
      debugPrint('[LocationService] LOW_BATTERY_MODE_DEACTIVATED battery=$batteryLevel%');
      await bg.BackgroundGeolocation.setConfig(bg.Config(
        distanceFilter: _normalDistanceFilter,
        stopTimeout: _normalStopTimeout,
      ));
    }
  }

  // ── Heartbeat ────────────────────────────────────────────

  void _startHeartbeatTimer() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(
      Duration(minutes: _heartbeatIntervalMinutes),
      (_) async {
        await _sendHeartbeat(
          batteryLevel: null, // will be populated from battery plugin
          gpsAccuracy: null,
        );
      },
    );
    debugPrint('[LocationService] Heartbeat timer started (every ${_heartbeatIntervalMinutes}min)');
  }

  Future<void> _sendHeartbeat({
    double? batteryLevel,
    double? gpsAccuracy,
  }) async {
    if (_authToken == null || _deviceId == null) return;

    try {
      String? appVersion;
      String? osInfo;
      try {
        final pkg = await PackageInfo.fromPlatform();
        appVersion = '${pkg.version}+${pkg.buildNumber}';
        
        final devInfo = DeviceInfoPlugin();
        if (Platform.isAndroid) {
            final androidInfo = await devInfo.androidInfo;
            osInfo = 'Android ${androidInfo.version.release} (${androidInfo.model})';
        } else if (Platform.isIOS) {
            final iosInfo = await devInfo.iosInfo;
            osInfo = 'iOS ${iosInfo.systemVersion} (${iosInfo.utsname.machine})';
        }
      } catch(e) { /* ignore */ }

      final body = json.encode({
        'device_id': _deviceId,
        if (batteryLevel != null) 'battery_level': batteryLevel,
        if (gpsAccuracy != null) 'gps_accuracy': gpsAccuracy,
        if (appVersion != null) 'app_version': appVersion,
        if (osInfo != null) 'os_info': osInfo,
        'timestamp': DateTime.now().toUtc().toIso8601String(),
      });

      await http.post(
        Uri.parse('$_apiUrl/api/v1/telemetry/heartbeat'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $_authToken',
        },
        body: body,
      );
      debugPrint('[LocationService] Heartbeat sent device=$_deviceId');
    } catch (e) {
      debugPrint('[LocationService] Heartbeat failed: $e');
    }
  }

  void dispose() {
    _heartbeatTimer?.cancel();
  }
}

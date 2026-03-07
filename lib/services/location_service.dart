import 'dart:async';
import 'dart:convert';

import 'package:battery_plus/battery_plus.dart';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_foreground_task/flutter_foreground_task.dart';
import 'package:geolocator/geolocator.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:package_info_plus/package_info_plus.dart';
import 'dart:io' show Platform;

import '../providers/location_provider.dart';
import 'database_service.dart';

// ── Constants ─────────────────────────────────────────────────────────────────
const double _lowBatteryThreshold = 20.0;
const int _heartbeatIntervalMinutes = 5;

// Window of positions used to detect stationary state
const int _stationaryWindowSize = 5;
// Device is considered stationary when all positions are within 25 m of each other
const double _stationaryRadiusMeters = 25.0;

// ── Headless callback (runs when app is terminated) ───────────────────────────
//
// flutter_foreground_task provides an isolate-based TaskHandler. When the OS
// kills the main isolate the foreground task remains alive because it runs in
// a dedicated Android foreground service. This handler is the entry-point for
// that context.
@pragma('vm:entry-point')
void startCallback() {
  FlutterForegroundTask.setTaskHandler(_LocationTaskHandler());
}

class _LocationTaskHandler extends TaskHandler {
  StreamSubscription<Position>? _positionSub;
  final _storage = const FlutterSecureStorage();
  String? _token;
  String? _deviceId;
  String? _apiUrl;

  @override
  Future<void> onStart(DateTime timestamp, TaskStarter starter) async {
    _token = await _storage.read(key: 'access_token');
    _deviceId = await _storage.read(key: 'device_id');
    _apiUrl = await _storage.read(key: 'api_url');

    final settings = _buildLocationSettings(LocationAccuracy.medium);
    _positionSub = Geolocator.getPositionStream(locationSettings: settings).listen(
      (position) => _onPosition(position),
      onError: (e) => debugPrint('[FGTask] position error: $e'),
    );
  }

  @override
  void onRepeatEvent(DateTime timestamp) {
    // We rely on the continuous stream above; periodic event here just keeps
    // the foreground notification clock fresh. Nothing required.
  }

  @override
  Future<void> onDestroy(DateTime timestamp) async {
    await _positionSub?.cancel();
  }

  @override
  void onReceiveData(Object data) {
    // Accept credential refreshes sent from the main isolate after re-login
    if (data is Map<String, String?>) {
      _token = data['access_token'];
      _deviceId = data['device_id'];
      _apiUrl = data['api_url'];
    }
  }

  // Called by Geolocator stream every location update
  Future<void> _onPosition(Position pos) async {
    final battery = await _readBattery();

    await DatabaseService().insertLocation({
      'latitude': pos.latitude,
      'longitude': pos.longitude,
      'accuracy': pos.accuracy,
      'speed': pos.speed,
      'battery_level': battery,
      'timestamp': pos.timestamp.toIso8601String(),
      'synced': 0,
    });

    try {
      await DatabaseService().flushIfReady(
        lowBatteryMode: battery < _lowBatteryThreshold,
        token: _token,
        deviceId: _deviceId,
        apiUrl: _apiUrl,
      );
    } catch (e) {
      debugPrint('[FGTask] flush error: $e');
    }
  }

  Future<double> _readBattery() async {
    try {
      final level = await Battery().batteryLevel;
      return level.toDouble();
    } catch (_) {
      return 100.0;
    }
  }
}

// ── Public service ─────────────────────────────────────────────────────────────

class LocationService {
  final LocationProvider locationProvider;

  LocationService(this.locationProvider);

  // ── Credentials ────────────────────────────────────────────────────────
  String? _authToken;
  String? _deviceId;
  String? _apiUrl;

  // ── Motion state ───────────────────────────────────────────────────────
  bool _lowBatteryMode = false;
  final List<Position> _recentPositions = [];
  bool _stationary = false;
  Timer? _heartbeatTimer;

  // ── Foreground stream subscription ─────────────────────────────────────
  StreamSubscription<Position>? _positionSub;

  void setCredentials({
    required String token,
    required String deviceId,
    required String apiUrl,
  }) {
    _authToken = token;
    _deviceId = deviceId;
    _apiUrl = apiUrl;

    // Push updated credentials into the foreground-task isolate so headless
    // location uploads also use the fresh token.
    FlutterForegroundTask.sendDataToTask({
      'access_token': token,
      'device_id': deviceId,
      'api_url': apiUrl,
    });
  }

  // ──────────────────────────────────────────────────────────────────────
  //  init() — configure foreground-task options, request permissions, start
  // ──────────────────────────────────────────────────────────────────────
  Future<void> init() async {
    // ── 1. Request permissions ─────────────────────────────────────────
    final serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      debugPrint('[LocationService] Location services disabled — nothing to do.');
      return;
    }

    LocationPermission permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied) {
        debugPrint('[LocationService] Permission denied.');
        return;
      }
    }
    if (permission == LocationPermission.deniedForever) {
      debugPrint('[LocationService] Permission permanently denied.');
      return;
    }

    // ── 2. Configure flutter_foreground_task ───────────────────────────
    FlutterForegroundTask.init(
      androidNotificationOptions: AndroidNotificationOptions(
        channelId: 'kin_location_channel',
        channelName: 'Kin Location',
        channelDescription: 'Keeps Kin location service running in the background.',
        channelImportance: NotificationChannelImportance.LOW,
        priority: NotificationPriority.LOW,
      ),
      iosNotificationOptions: const IOSNotificationOptions(
        showNotification: true,
        playSound: false,
      ),
      foregroundTaskOptions: ForegroundTaskOptions(
        eventAction: ForegroundTaskEventAction.repeat(60000), // 1-min tick
        autoRunOnBoot: true,
        autoRunOnMyPackageReplaced: true,
        allowWakeLock: true,
        allowWifiLock: true,
      ),
    );

    // ── 3. Start the foreground service (Android) ──────────────────────
    if (Platform.isAndroid) {
      final result = await FlutterForegroundTask.startService(
        serviceId: 256,
        notificationTitle: 'Kin is active',
        notificationText: 'Location sharing is on',
        callback: startCallback,
      );
      debugPrint('[LocationService] FGTask start result: $result');
    }

    // ── 4. Subscribe to location stream in the MAIN isolate as well, so
    //       the UI (LocationProvider) stays updated while the app is open ─
    _subscribeToPositions();

    // ── 5. Heartbeat timer ────────────────────────────────────────────
    _startHeartbeatTimer();
  }

  // ── Position stream subscription (foreground UI updates) ─────────────

  void _subscribeToPositions() {
    _positionSub?.cancel();
    _positionSub = Geolocator.getPositionStream(
      locationSettings: _buildLocationSettings(LocationAccuracy.medium),
    ).listen(
      _onPosition,
      onError: (e) => debugPrint('[LocationService] stream error: $e'),
    );
  }

  Future<void> _onPosition(Position pos) async {
    final battery = await _readBattery();

    // ── Battery-aware throttling ──────────────────────────────────────
    await _applyBatteryMode(battery);

    // ── Stationary detection ──────────────────────────────────────────
    _updateStationaryState(pos);

    // ── Update UI provider ────────────────────────────────────────────
    locationProvider.updateLocation(LocationPoint(
      latitude: pos.latitude,
      longitude: pos.longitude,
      accuracy: pos.accuracy,
      speed: pos.speed,
      batteryLevel: battery,
      timestamp: pos.timestamp,
      isMoving: !_stationary,
    ));

    // ── Store locally ─────────────────────────────────────────────────
    await DatabaseService().insertLocation({
      'latitude': pos.latitude,
      'longitude': pos.longitude,
      'accuracy': pos.accuracy,
      'speed': pos.speed,
      'battery_level': battery,
      'timestamp': pos.timestamp.toIso8601String(),
      'synced': 0,
    });

    await DatabaseService().flushIfReady(
      lowBatteryMode: _lowBatteryMode,
      token: _authToken,
      deviceId: _deviceId,
      apiUrl: _apiUrl,
    );
  }

  // ── Stationary detection via rolling coordinate variance ─────────────

  void _updateStationaryState(Position pos) {
    _recentPositions.add(pos);
    if (_recentPositions.length > _stationaryWindowSize) {
      _recentPositions.removeAt(0);
    }
    if (_recentPositions.length < _stationaryWindowSize) return;

    final wasStationary = _stationary;
    _stationary = _isWithinRadius(_recentPositions, _stationaryRadiusMeters);

    if (_stationary != wasStationary) {
      debugPrint('[LocationService] Stationary=$_stationary — adjusting accuracy');
      _reSubscribeWithCurrentMode();
    }
  }

  /// Returns true when ALL positions in the buffer are within [radiusMeters]
  /// of each other (max pairwise distance).
  bool _isWithinRadius(List<Position> positions, double radiusMeters) {
    for (int i = 0; i < positions.length; i++) {
      for (int j = i + 1; j < positions.length; j++) {
        final d = Geolocator.distanceBetween(
          positions[i].latitude, positions[i].longitude,
          positions[j].latitude, positions[j].longitude,
        );
        if (d > radiusMeters) return false;
      }
    }
    return true;
  }

  void _reSubscribeWithCurrentMode() {
    _positionSub?.cancel();
    LocationAccuracy accuracy;
    if (_stationary) {
      accuracy = LocationAccuracy.low;
    } else {
      // Could be enhanced with activity recognition (WALKING vs DRIVING)
      // For now, default to balanced — high accuracy is reserved for known DRIVING
      accuracy = LocationAccuracy.medium;
    }
    _positionSub = Geolocator.getPositionStream(
      locationSettings: _buildLocationSettings(accuracy),
    ).listen(
      _onPosition,
      onError: (e) => debugPrint('[LocationService] stream error: $e'),
    );
  }

  // ── Battery throttling ────────────────────────────────────────────────

  Future<void> _applyBatteryMode(double level) async {
    final shouldBeLow = level < _lowBatteryThreshold;
    if (shouldBeLow == _lowBatteryMode) return;

    _lowBatteryMode = shouldBeLow;
    debugPrint('[LocationService] ${shouldBeLow ? "LOW_BATTERY_MODE_ACTIVE" : "LOW_BATTERY_MODE_DEACTIVATED"} battery=$level%');
    // DatabaseService.flushIfReady already uses the flag at call-time.
    // Resubscribe so the interval also adjusts.
    _reSubscribeWithCurrentMode();
  }

  // ── Heartbeat ─────────────────────────────────────────────────────────

  void _startHeartbeatTimer() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(
      Duration(minutes: _heartbeatIntervalMinutes),
      (_) async => _sendHeartbeat(),
    );
    debugPrint('[LocationService] Heartbeat timer started (every ${_heartbeatIntervalMinutes}min)');
  }

  Future<void> _sendHeartbeat() async {
    if (_authToken == null || _deviceId == null || _apiUrl == null) return;
    try {
      String? appVersion;
      String? osInfo;
      try {
        final pkg = await PackageInfo.fromPlatform();
        appVersion = '${pkg.version}+${pkg.buildNumber}';
        if (Platform.isAndroid) {
          final info = await DeviceInfoPlugin().androidInfo;
          osInfo = 'Android ${info.version.release} (${info.model})';
        } else if (Platform.isIOS) {
          final info = await DeviceInfoPlugin().iosInfo;
          osInfo = 'iOS ${info.systemVersion} (${info.utsname.machine})';
        }
      } catch (_) {}

      final battery = await _readBattery();
      final body = json.encode({
        'device_id': _deviceId,
        'battery_level': battery,
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

  // ── Helpers ────────────────────────────────────────────────────────────

  Future<double> _readBattery() async {
    try {
      return (await Battery().batteryLevel).toDouble();
    } catch (_) {
      return 100.0;
    }
  }

  void dispose() {
    _heartbeatTimer?.cancel();
    _positionSub?.cancel();
    FlutterForegroundTask.stopService();
  }
}

// ── Shared location settings factory ─────────────────────────────────────────

LocationSettings _buildLocationSettings(LocationAccuracy accuracy) {
  if (Platform.isAndroid) {
    return AndroidSettings(
      accuracy: accuracy,
      distanceFilter: accuracy == LocationAccuracy.low ? 0 : 20,
      intervalDuration: accuracy == LocationAccuracy.low
          ? const Duration(minutes: 3)
          : const Duration(seconds: 10),
      foregroundNotificationConfig: const ForegroundNotificationConfig(
        notificationText: 'Location sharing is on',
        notificationTitle: 'Kin is active',
        enableWakeLock: true,
      ),
    );
  } else if (Platform.isIOS) {
    return AppleSettings(
      accuracy: accuracy,
      activityType: ActivityType.fitness,
      distanceFilter: accuracy == LocationAccuracy.low ? 0 : 20,
      pauseLocationUpdatesAutomatically: accuracy == LocationAccuracy.low,
      showBackgroundLocationIndicator: true,
    );
  }
  return LocationSettings(accuracy: accuracy, distanceFilter: 20);
}

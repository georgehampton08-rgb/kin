import 'package:flutter/services.dart';
import 'package:flutter/foundation.dart';

/// DeviceIdentityService
/// =====================
/// Wraps the MethodChannel that talks to Android AccountManager via
/// [MainActivity] to provide credential storage that **survives app
/// uninstall/reinstall** (unless the user manually clears app data from
/// Android Settings).
///
/// It also exposes [getHardwareId] which returns the ANDROID_ID — unique per
/// (device, user, signing key) — used as the immutable device fingerprint.
///
/// All credentials read/written here mirror what was previously stored only in
/// [FlutterSecureStorage].  We now write to BOTH stores so existing code
/// continues to work, and the AccountManager copy is used to restore on
/// reinstall.
class DeviceIdentityService {
  static const _channel = MethodChannel('com.example.kin/device_identity');

  // ── Credential keys stored in AccountManager ────────────────────────────
  static const _kAccessToken = 'access_token';
  static const _kRefreshToken = 'refresh_token';
  static const _kDeviceId = 'device_id';
  static const _kApiUrl = 'api_url';
  static const _kMqttHost = 'mqtt_host';
  static const _kMqttPort = 'mqtt_port';
  static const _kMqttUsername = 'mqtt_username';
  static const _kMqttPassword = 'mqtt_password';
  static const _kHardwareId = 'hardware_id';

  /// Returns the permanent Android hardware ID.
  /// Stable across reinstalls when the APK is signed with the same key.
  static Future<String> getHardwareId() async {
    try {
      final id = await _channel.invokeMethod<String>('getHardwareId');
      return id ?? 'unknown';
    } catch (e) {
      debugPrint('[DeviceIdentity] getHardwareId failed: $e');
      return 'unknown';
    }
  }

  /// Returns true if pairing credentials are stored in AccountManager.
  static Future<bool> isPaired() async {
    try {
      final result = await _channel.invokeMethod<bool>('isPaired');
      return result ?? false;
    } catch (e) {
      debugPrint('[DeviceIdentity] isPaired check failed: $e');
      return false;
    }
  }

  /// Save all pairing credentials to AccountManager.
  static Future<void> saveCredentials({
    required String accessToken,
    required String refreshToken,
    required String deviceId,
    required String apiUrl,
    required String hardwareId,
    String? mqttHost,
    String? mqttPort,
    String? mqttUsername,
    String? mqttPassword,
  }) async {
    try {
      final data = <String, String>{
        _kAccessToken: accessToken,
        _kRefreshToken: refreshToken,
        _kDeviceId: deviceId,
        _kApiUrl: apiUrl,
        _kHardwareId: hardwareId,
        if (mqttHost != null) _kMqttHost: mqttHost,
        if (mqttPort != null) _kMqttPort: mqttPort,
        if (mqttUsername != null) _kMqttUsername: mqttUsername,
        if (mqttPassword != null) _kMqttPassword: mqttPassword,
      };
      await _channel.invokeMethod('saveCredentials', data);
      debugPrint('[DeviceIdentity] Credentials saved to AccountManager');
    } catch (e) {
      debugPrint('[DeviceIdentity] saveCredentials failed: $e');
    }
  }

  /// Read a single credential from AccountManager.
  static Future<String?> read(String key) async {
    try {
      return await _channel.invokeMethod<String>('readCredential', {'key': key});
    } catch (e) {
      debugPrint('[DeviceIdentity] read($key) failed: $e');
      return null;
    }
  }

  /// Helper: restore all known credentials as a map (null values omitted).
  static Future<Map<String, String>> readAll() async {
    final keys = [
      _kAccessToken, _kRefreshToken, _kDeviceId, _kApiUrl,
      _kHardwareId, _kMqttHost, _kMqttPort, _kMqttUsername, _kMqttPassword,
    ];
    final result = <String, String>{};
    for (final k in keys) {
      final v = await read(k);
      if (v != null && v.isNotEmpty) result[k] = v;
    }
    return result;
  }

  // ── Constant key accessors for external use ──────────────────────────────
  static String get keyAccessToken => _kAccessToken;
  static String get keyRefreshToken => _kRefreshToken;
  static String get keyDeviceId => _kDeviceId;
  static String get keyApiUrl => _kApiUrl;
  static String get keyHardwareId => _kHardwareId;
  static String get keyMqttHost => _kMqttHost;
  static String get keyMqttPort => _kMqttPort;
  static String get keyMqttUsername => _kMqttUsername;
  static String get keyMqttPassword => _kMqttPassword;
}

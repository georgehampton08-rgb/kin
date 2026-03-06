import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:flutter_background_geolocation/flutter_background_geolocation.dart' as bg;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'providers/location_provider.dart';
import 'services/location_service.dart';
import 'services/comms_service.dart';
import 'services/device_identity_service.dart';
import 'screens/onboarding_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();

  // Lock the app to portrait — child can't rotate out of the running state
  SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);

  // Register headless background task
  bg.BackgroundGeolocation.registerHeadlessTask(locationHeadlessTask);

  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => LocationProvider()),
      ],
      child: const KinApp(),
    ),
  );
}

class KinApp extends StatefulWidget {
  const KinApp({super.key});

  @override
  State<KinApp> createState() => _KinAppState();
}

class _KinAppState extends State<KinApp> {
  late LocationService _locationService;
  bool _isInitialized = false;
  bool _isPaired = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await _initApp();
    });
  }

  Future<void> _initApp() async {
    final locationProvider = Provider.of<LocationProvider>(context, listen: false);
    _locationService = LocationService(locationProvider);

    const secureStorage = FlutterSecureStorage();

    // ── Step 1: Check AccountManager first (survives reinstall) ────────────
    final isPairedInAccountManager = await DeviceIdentityService.isPaired();

    if (isPairedInAccountManager) {
      // Restore credentials from AccountManager → also re-write to FlutterSecureStorage
      // so that existing code (which reads from there) still works.
      final credentials = await DeviceIdentityService.readAll();

      final accessToken = credentials[DeviceIdentityService.keyAccessToken];
      final deviceId = credentials[DeviceIdentityService.keyDeviceId];
      final apiUrl = credentials[DeviceIdentityService.keyApiUrl];

      if (accessToken != null && deviceId != null && apiUrl != null) {
        // Restore into FlutterSecureStorage (in case this is a fresh reinstall)
        await secureStorage.write(key: 'access_token', value: accessToken);
        await secureStorage.write(key: 'device_id', value: deviceId);
        await secureStorage.write(key: 'api_url', value: apiUrl);

        final refreshToken = credentials[DeviceIdentityService.keyRefreshToken];
        final mqttHost = credentials[DeviceIdentityService.keyMqttHost];
        final mqttPort = credentials[DeviceIdentityService.keyMqttPort];
        final mqttUsername = credentials[DeviceIdentityService.keyMqttUsername];
        final mqttPassword = credentials[DeviceIdentityService.keyMqttPassword];

        if (refreshToken != null) await secureStorage.write(key: 'refresh_token', value: refreshToken);
        if (mqttHost != null) await secureStorage.write(key: 'mqtt_host', value: mqttHost);
        if (mqttPort != null) await secureStorage.write(key: 'mqtt_port', value: mqttPort);
        if (mqttUsername != null) await secureStorage.write(key: 'mqtt_username', value: mqttUsername);
        if (mqttPassword != null) await secureStorage.write(key: 'mqtt_password', value: mqttPassword);

        _locationService.setCredentials(
          token: accessToken,
          deviceId: deviceId,
          apiUrl: apiUrl,
        );
        CommsService.init();

        setState(() { _isPaired = true; });
      }
    } else {
      // ── Step 2: Fall back to FlutterSecureStorage (pre-update devices) ──
      final token = await secureStorage.read(key: 'access_token');
      final deviceId = await secureStorage.read(key: 'device_id');
      final apiUrl = await secureStorage.read(key: 'api_url');

      if (token != null && deviceId != null && apiUrl != null) {
        // Migrate existing credentials up to AccountManager so next reinstall
        // is handled automatically.
        final hardwareId = await DeviceIdentityService.getHardwareId();
        await DeviceIdentityService.saveCredentials(
          accessToken: token,
          refreshToken: await secureStorage.read(key: 'refresh_token') ?? '',
          deviceId: deviceId,
          apiUrl: apiUrl,
          hardwareId: hardwareId,
          mqttHost: await secureStorage.read(key: 'mqtt_host'),
          mqttPort: await secureStorage.read(key: 'mqtt_port'),
          mqttUsername: await secureStorage.read(key: 'mqtt_username'),
          mqttPassword: await secureStorage.read(key: 'mqtt_password'),
        );

        _locationService.setCredentials(
          token: token,
          deviceId: deviceId,
          apiUrl: apiUrl,
        );
        CommsService.init();

        setState(() { _isPaired = true; });
      }
    }

    _locationService.init();
    setState(() { _isInitialized = true; });
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Kin',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepPurple),
        useMaterial3: true,
      ),
      home: !_isInitialized
          ? const Scaffold(body: Center(child: CircularProgressIndicator()))
          : (_isPaired ? const LocationScreen() : const OnboardingScreen()),
    );
  }
}

/// The screen shown once the device is permanently paired.
/// No logout, no unpairing, no navigation out.
class LocationScreen extends StatelessWidget {
  const LocationScreen({super.key});

  @override
  Widget build(BuildContext context) {
    // Intercept the Android back button — do nothing (child cannot exit)
    return PopScope(
      canPop: false,
      child: Scaffold(
        backgroundColor: Colors.white,
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: const [
              Icon(Icons.check_circle_outline, size: 80, color: Colors.green),
              SizedBox(height: 24),
              Text(
                'Device Active',
                style: TextStyle(
                  color: Colors.black87,
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                ),
              ),
              SizedBox(height: 8),
              Text(
                'This device is being monitored.',
                style: TextStyle(color: Colors.black54, fontSize: 16),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

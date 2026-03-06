import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:flutter_background_geolocation/flutter_background_geolocation.dart' as bg;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'providers/location_provider.dart';
import 'services/location_service.dart';
import 'services/comms_service.dart';
import 'screens/onboarding_screen.dart';


void main() {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Register headless background task to receive events while app is terminated
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
    // Initialize the LocationService
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      final locationProvider = Provider.of<LocationProvider>(context, listen: false);
      _locationService = LocationService(locationProvider);
      
      const storage = FlutterSecureStorage();
      final token = await storage.read(key: 'access_token');
      final deviceId = await storage.read(key: 'device_id');
      final apiUrl = await storage.read(key: 'api_url');
      
      if (token != null && deviceId != null && apiUrl != null) {
        _locationService.setCredentials(token: token, deviceId: deviceId, apiUrl: apiUrl);
        setState(() {
          _isPaired = true;
        });
        CommsService.init();
      }
      
      _locationService.init();
      setState(() {
        _isInitialized = true;
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Kin Location App',
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


class LocationScreen extends StatelessWidget {
  const LocationScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.check_circle_outline, size: 80, color: Colors.green),
            const SizedBox(height: 24),
            const Text(
              'Configuration Complete',
              style: TextStyle(color: Colors.black87, fontSize: 20, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            const Text(
              'You can now close this app.',
              style: TextStyle(color: Colors.black54, fontSize: 16),
            ),
          ],
        ),
      ),
    );
  }
}

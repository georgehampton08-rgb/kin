import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:flutter_background_geolocation/flutter_background_geolocation.dart' as bg;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'providers/location_provider.dart';
import 'services/location_service.dart';
import 'services/comms_service.dart';
import 'screens/onboarding_screen.dart';
import 'screens/debug_screen.dart';

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
      appBar: AppBar(
        title: const Text('Kin Location'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
        actions: [
          IconButton(
            icon: const Icon(Icons.bug_report),
            tooltip: 'Debug SQLite Queue',
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const DebugScreen()),
              );
            },
          ),
        ],
      ),
      body: Center(
        child: Consumer<LocationProvider>(
          builder: (context, locationProvider, child) {
            final location = locationProvider.currentLocation;
            if (location == null) {
              return const Text('Fetching background location...');
            }

            return Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.location_on, size: 50, color: Colors.deepPurple),
                const SizedBox(height: 20),
                Text(
                  'Latitude: ${location.coords.latitude}',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                Text(
                  'Longitude: ${location.coords.longitude}',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                Text(
                  'Accuracy: ${location.coords.accuracy} m',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 10),
                Text(
                  'Moving: ${location.isMoving}',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 10),
                Text(
                  'Timestamp: ${location.timestamp}',
                  style: Theme.of(context).textTheme.labelLarge,
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

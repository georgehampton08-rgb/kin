import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:app_settings/app_settings.dart';
import '../main.dart'; // To navigate to LocationScreen
import 'qr_scanner_screen.dart';
import 'package:notification_listener_service/notification_listener_service.dart';

class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> with WidgetsBindingObserver {
  final PageController _pageController = PageController();
  PermissionStatus _alwaysStatus = PermissionStatus.denied;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _checkPermissions();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _pageController.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _checkPermissions();
    }
  }

  Future<void> _checkPermissions() async {
    final always = await Permission.locationAlways.status;
    setState(() {
      _alwaysStatus = always;
    });
  }

  Future<void> _requestWhenInUse() async {
    final status = await Permission.locationWhenInUse.request();
    if (!mounted) return;
    if (status.isGranted || status.isLimited) {
      _pageController.nextPage(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('While In Use permission is required to proceed.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Welcome to Kin'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
      ),
      body: PageView(
        controller: _pageController,
        physics: const NeverScrollableScrollPhysics(), // Require button taps
        children: [
          // Page 1: Privacy explanation
          _buildPage(
            icon: Icons.privacy_tip,
            title: 'Privacy First',
            content: 'Kin requires access to your location in the background to track your movement securely. We value your privacy and only use this data locally on your device or to power core features. No data is sold or shared with advertisers.',
            buttonText: 'Next',
            onPressed: () {
              _pageController.nextPage(
                duration: const Duration(milliseconds: 300),
                curve: Curves.easeInOut,
              );
            },
          ),

          // Page 2: Request "While In Use"
          _buildPage(
            icon: Icons.location_on,
            title: 'Initial Location Access',
            content: 'First, we need permission to access your location while you are using the app. This allows us to establish the baseline tracking.',
            buttonText: 'Grant While In Use',
            onPressed: _requestWhenInUse,
          ),

          // Page 3: Communications Permissions
          _buildCommsPermissionPage(),

          // Page 4: Request "Always" via App Settings
          _buildFinalPage(),
        ],
      ),
    );
  }

  Widget _buildCommsPermissionPage() {
    return Padding(
      padding: const EdgeInsets.all(32.0),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.settings_phone, size: 80, color: Colors.deepPurple),
          const SizedBox(height: 24),
          Text('Communications Tracking', style: Theme.of(context).textTheme.headlineSmall, textAlign: TextAlign.center),
          const SizedBox(height: 16),
          Text('To fully monitor device activity, we need access to SMS, Call Logs, and Notifications.', style: Theme.of(context).textTheme.bodyLarge, textAlign: TextAlign.center),
          const Spacer(),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: () async {
                await [
                  Permission.sms,
                  Permission.phone,
                ].request();

                await NotificationListenerService.requestPermission();

                if (!mounted) return;
                _pageController.nextPage(
                  duration: const Duration(milliseconds: 300),
                  curve: Curves.easeInOut,
                );
              },
              style: ElevatedButton.styleFrom(padding: const EdgeInsets.all(16)),
              child: const Text('Grant Comm Access', style: TextStyle(fontSize: 18)),
            ),
          ),
          const SizedBox(height: 32),
        ],
      ),
    );
  }

  Widget _buildPage({
    required IconData icon,
    required String title,
    required String content,
    required String buttonText,
    required VoidCallback onPressed,
  }) {
    return Padding(
      padding: const EdgeInsets.all(32.0),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 80, color: Colors.deepPurple),
          const SizedBox(height: 24),
          Text(title, style: Theme.of(context).textTheme.headlineSmall, textAlign: TextAlign.center),
          const SizedBox(height: 16),
          Text(content, style: Theme.of(context).textTheme.bodyLarge, textAlign: TextAlign.center),
          const Spacer(),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: onPressed,
              style: ElevatedButton.styleFrom(padding: const EdgeInsets.all(16)),
              child: Text(buttonText, style: const TextStyle(fontSize: 18)),
            ),
          ),
          const SizedBox(height: 32),
        ],
      ),
    );
  }

  Widget _buildFinalPage() {
    final bool isOptimal = _alwaysStatus.isGranted;

    return Padding(
      padding: const EdgeInsets.all(32.0),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            isOptimal ? Icons.check_circle : Icons.warning_amber_rounded,
            size: 80,
            color: isOptimal ? Colors.green : Colors.orange,
          ),
          const SizedBox(height: 24),
          Text(
            isOptimal ? 'Permission Active' : 'Sub-optimal Permission',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              color: isOptimal ? Colors.green : Colors.orange,
              fontWeight: FontWeight.bold,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          Text(
            isOptimal 
              ? 'Awesome! You have granted optimal background permission. Kin is ready to track.'
              : 'To track accurately in the background, Kin needs "Allow All The Time" permission. Please open App Settings and upgrade the permission.',
            style: Theme.of(context).textTheme.bodyLarge,
            textAlign: TextAlign.center,
          ),
          const Spacer(),
          if (!isOptimal)
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () {
                  AppSettings.openAppSettings(type: AppSettingsType.location);
                },
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.all(16),
                  backgroundColor: Colors.orange,
                  foregroundColor: Colors.white,
                ),
                child: const Text('Open System Settings', style: TextStyle(fontSize: 18)),
              ),
            ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: isOptimal ? () {
                // Navigate to QR Scanner Screen
                Navigator.of(context).pushReplacement(
                  MaterialPageRoute(builder: (_) => const QRScannerScreen()),
                );
              } : null,
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.all(16),
                backgroundColor: isOptimal ? Colors.deepPurple : Colors.grey,
                foregroundColor: Colors.white,
              ),
              child: const Text('Finish Setup', style: TextStyle(fontSize: 18)),
            ),
          ),
          const SizedBox(height: 32),
        ],
      ),
    );
  }
}

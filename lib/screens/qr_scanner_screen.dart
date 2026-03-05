import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:device_info_plus/device_info_plus.dart';
import 'dart:io';
import '../main.dart'; 

class QRScannerScreen extends StatefulWidget {
  const QRScannerScreen({super.key});

  @override
  State<QRScannerScreen> createState() => _QRScannerScreenState();
}

class _QRScannerScreenState extends State<QRScannerScreen> {
  bool _isProcessing = false;
  final MobileScannerController controller = MobileScannerController(
    detectionSpeed: DetectionSpeed.noDuplicates,
  );
  final storage = const FlutterSecureStorage();

  Future<String> _getDeviceIdentifier() async {
    final deviceInfo = DeviceInfoPlugin();
    if (Platform.isAndroid) {
      final androidInfo = await deviceInfo.androidInfo;
      return androidInfo.id; // Unique hardware ID
    } else if (Platform.isIOS) {
      final iosInfo = await deviceInfo.iosInfo;
      return iosInfo.identifierForVendor ?? 'unknown_ios';
    }
    return 'unknown_device';
  }

  Future<void> _processQRCode(String rawValue) async {
    if (_isProcessing) return;
    setState(() => _isProcessing = true);

    try {
      final data = jsonDecode(rawValue);
      final apiUrl = data['api_url'];
      final pairingToken = data['pairing_token'];
      final mqttHost = data['mqtt_host'];
      final mqttPort = data['mqtt_port'];

      if (apiUrl == null || pairingToken == null) {
        throw Exception("Invalid QR code format.");
      }

      final deviceId = await _getDeviceIdentifier();
      final dio = Dio();

      final response = await dio.post(
        '$apiUrl/api/v1/auth/pair-device',
        data: {
          'pairing_token': pairingToken,
          'device_identifier': deviceId,
        },
      );

      final resData = response.data;
      final accessToken = resData['access_token'];
      final refreshToken = resData['refresh_token'];
      final mqttUsername = resData['mqtt_config']['username'];
      final mqttPassword = resData['mqtt_config']['password'];
      final deviceId = resData['device_id'];

      await storage.write(key: 'api_url', value: apiUrl);
      await storage.write(key: 'device_id', value: deviceId);
      await storage.write(key: 'access_token', value: accessToken);
      await storage.write(key: 'refresh_token', value: refreshToken);
      await storage.write(key: 'mqtt_host', value: mqttHost);
      await storage.write(key: 'mqtt_port', value: mqttPort.toString());
      await storage.write(key: 'mqtt_username', value: mqttUsername);
      if (mqttPassword != "(use existing credentials)") {
        await storage.write(key: 'mqtt_password', value: mqttPassword);
      }

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Device paired successfully!')),
      );

      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const LocationScreen()),
      );
    } catch (e) {
      setState(() => _isProcessing = false);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to pair: $e')),
      );
      controller.start();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Pair Device')),
      body: Stack(
        children: [
          MobileScanner(
            controller: controller,
            onDetect: (capture) {
              final List<Barcode> barcodes = capture.barcodes;
              for (final barcode in barcodes) {
                if (barcode.rawValue != null) {
                  controller.stop();
                  _processQRCode(barcode.rawValue!);
                  break;
                }
              }
            },
          ),
          if (_isProcessing)
            const Center(
              child: CircularProgressIndicator(),
            ),
          Positioned(
            bottom: 40,
            left: 0,
            right: 0,
            child: const Center(
              child: Text(
                'Scan the QR code on the Parent Dashboard',
                style: TextStyle(color: Colors.white, fontSize: 16, backgroundColor: Colors.black54),
              ),
            ),
          )
        ],
      ),
    );
  }
}

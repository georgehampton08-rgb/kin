import 'package:flutter/foundation.dart';

/// Lightweight position snapshot — no Transistorsoft types.
class LocationPoint {
  final double latitude;
  final double longitude;
  final double accuracy;
  final double speed;
  final double batteryLevel;
  final DateTime timestamp;
  final bool isMoving;

  const LocationPoint({
    required this.latitude,
    required this.longitude,
    required this.accuracy,
    required this.speed,
    required this.batteryLevel,
    required this.timestamp,
    this.isMoving = true,
  });
}

class LocationProvider extends ChangeNotifier {
  LocationPoint? _currentLocation;

  LocationPoint? get currentLocation => _currentLocation;

  void updateLocation(LocationPoint point) {
    _currentLocation = point;
    notifyListeners();
  }
}

import 'package:flutter/foundation.dart';
import 'package:flutter_background_geolocation/flutter_background_geolocation.dart' as bg;

class LocationProvider extends ChangeNotifier {
  bg.Location? _currentLocation;

  bg.Location? get currentLocation => _currentLocation;

  void updateLocation(bg.Location location) {
    _currentLocation = location;
    notifyListeners();
  }
}

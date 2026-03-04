import 'package:flutter/foundation.dart';
import 'package:flutter_background_geolocation/flutter_background_geolocation.dart' as bg;
import '../providers/location_provider.dart';
import 'database_service.dart';

@pragma('vm:entry-point')
void locationHeadlessTask(bg.HeadlessEvent headlessEvent) async {
  debugPrint('[HeadlessTask]: $headlessEvent');
  switch (headlessEvent.name) {
    case bg.Event.LOCATION:
      bg.Location location = headlessEvent.event;
      debugPrint('[Headless Location] Inserted to DB -> ${location.coords.latitude}, ${location.coords.longitude}');
      await DatabaseService().insertLocation({
        'latitude': location.coords.latitude,
        'longitude': location.coords.longitude,
        'accuracy': location.coords.accuracy,
        'timestamp': location.timestamp,
      });
      break;
    case bg.Event.ACTIVITYCHANGE:
      bg.ActivityChangeEvent event = headlessEvent.event;
      debugPrint('[Headless Activity Change] STATIONARY vs. MOVING: ${event.activity}');
      break;
    default:
      break;
  }
}

class LocationService {
  final LocationProvider locationProvider;

  LocationService(this.locationProvider);

  Future<void> init() async {
    // 1. Listen to events
    bg.BackgroundGeolocation.onLocation((bg.Location location) async {
      locationProvider.updateLocation(location);
      await DatabaseService().insertLocation({
        'latitude': location.coords.latitude,
        'longitude': location.coords.longitude,
        'accuracy': location.coords.accuracy,
        'timestamp': location.timestamp,
      });
    }, (bg.LocationError error) {
      debugPrint('[onLocation] ERROR: $error');
    });

    bg.BackgroundGeolocation.onMotionChange((bg.Location location) {
      debugPrint('[onMotionChange]: $location');
    });

    bg.BackgroundGeolocation.onProviderChange((bg.ProviderChangeEvent event) {
      debugPrint('[onProviderChange]: $event');
    });

    bg.BackgroundGeolocation.onActivityChange((bg.ActivityChangeEvent event) {
      debugPrint('[Activity Change] STATIONARY vs. MOVING: ${event.activity}');
    });

    // 2. Configure the plugin
    await bg.BackgroundGeolocation.ready(bg.Config(
      desiredAccuracy: bg.Config.DESIRED_ACCURACY_HIGH,
      distanceFilter: 50.0,
      stopTimeout: 5,
      stopOnTerminate: false,
      startOnBoot: true,
      debug: true,
      logLevel: bg.Config.LOG_LEVEL_VERBOSE,
      reset: true,
    ));

    // 3. Dry-run check
    bg.State state = await bg.BackgroundGeolocation.state;
    debugPrint('[Dry-Run Check] SDK Internal Settings:');
    // ignore: deprecated_member_use
    debugPrint('- distanceFilter: ${state.distanceFilter} meters');
    // ignore: deprecated_member_use
    debugPrint('- stopTimeout: ${state.stopTimeout} minutes');
    // ignore: deprecated_member_use
    debugPrint('- stopOnTerminate: ${state.stopOnTerminate}');
    // ignore: deprecated_member_use
    debugPrint('- startOnBoot: ${state.startOnBoot}');

    // 3. Start the plugin
    await bg.BackgroundGeolocation.start();
  }
}

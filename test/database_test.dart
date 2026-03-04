import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:kin/services/database_service.dart';

void main() {
  setUpAll(() {
    sqfliteFfiInit();
    databaseFactory = databaseFactoryFfi;
  });

  test('Simulate 10 offline pings and verify storage', () async {
    final dbService = DatabaseService();
    // Start with a clean slate for the test
    final db = await dbService.database;
    await db.execute('DELETE FROM locations');

    // Simulate 10 pings
    for (int i = 0; i < 10; i++) {
        await dbService.insertLocation({
            'latitude': 37.7749 + (i * 0.001),
            'longitude': -122.4194 + (i * 0.001),
            'accuracy': 15.0,
            'timestamp': DateTime.now().toIso8601String(),
        });
    }

    final unsyncedCount = await dbService.getUnsyncedCount();
    expect(unsyncedCount, 10);
    
    final lastFive = await dbService.getLastLocations(5);
    expect(lastFive.length, 5);
  });
}

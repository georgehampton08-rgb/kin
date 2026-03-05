import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart';
import 'package:http/http.dart' as http;



// Batch thresholds
const int _normalBatchSize = 20;
const int _lowBatteryBatchSize = 1; // Always flush immediately in low-battery batch mode
const Duration _normalBatchWindow = Duration(minutes: 3);
const Duration _lowBatteryBatchWindow = Duration(minutes: 10);

class DatabaseService {
  static final DatabaseService _instance = DatabaseService._internal();
  factory DatabaseService() => _instance;
  DatabaseService._internal();

  Database? _database;
  DateTime? _lastFlush;

  Future<Database> get database async {
    if (_database != null) return _database!;
    _database = await _initDatabase();
    return _database!;
  }

  Future<Database> _initDatabase() async {
    final dbPath = await getDatabasesPath();
    final path = join(dbPath, 'kin_locations.db');

    return await openDatabase(
      path,
      version: 2,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE locations (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            latitude      REAL    NOT NULL,
            longitude     REAL    NOT NULL,
            accuracy      REAL,
            speed         REAL,
            battery_level REAL,
            timestamp     TEXT    NOT NULL,
            synced        INTEGER NOT NULL DEFAULT 0
          )
        ''');
      },
      onUpgrade: (db, oldVersion, newVersion) async {
        if (oldVersion < 2) {
          await db.execute('ALTER TABLE locations ADD COLUMN speed REAL');
          await db.execute('ALTER TABLE locations ADD COLUMN battery_level REAL');
        }
      },
    );
  }

  Future<void> insertLocation(Map<String, dynamic> locationData) async {
    final db = await database;
    await db.insert('locations', locationData);
    debugPrint('[Database] Inserted location (speed=${locationData['speed']})');
  }

  Future<int> getUnsyncedCount() async {
    final db = await database;
    final result = await db.rawQuery('SELECT COUNT(*) FROM locations WHERE synced = 0');
    return Sqflite.firstIntValue(result) ?? 0;
  }

  Future<List<Map<String, dynamic>>> _getUnsyncedBatch(int limit) async {
    final db = await database;
    return await db.query(
      'locations',
      where: 'synced = 0',
      orderBy: 'id ASC',
      limit: limit,
    );
  }

  Future<void> _markSynced(List<int> ids) async {
    final db = await database;
    final placeholders = ids.map((_) => '?').join(',');
    await db.rawUpdate(
      'UPDATE locations SET synced = 1 WHERE id IN ($placeholders)',
      ids,
    );
  }

  /// Flush local buffer to the backend if conditions are met.
  Future<void> flushIfReady({
    required bool lowBatteryMode,
    required String? token,
    required String? deviceId,
    required String? apiUrl,
  }) async {
    if (token == null || deviceId == null || apiUrl == null) {
      debugPrint('[SyncTask] No credentials — skipping flush');
      return;
    }

    final batchSize = lowBatteryMode ? _lowBatteryBatchSize : _normalBatchSize;
    final batchWindow = lowBatteryMode ? _lowBatteryBatchWindow : _normalBatchWindow;

    final count = await getUnsyncedCount();
    final now = DateTime.now();
    final windowExpired = _lastFlush == null || now.difference(_lastFlush!) >= batchWindow;

    if (count < batchSize && !windowExpired) {
      debugPrint('[SyncTask] Not yet: $count points buffered (need $batchSize or ${batchWindow.inMinutes}min window)');
      return;
    }

    final batch = await _getUnsyncedBatch(batchSize * 2); // grab a bit extra
    if (batch.isEmpty) return;

    try {
      final points = batch
          .map((row) => {
                'lat': row['latitude'],
                'lng': row['longitude'],
                'speed': row['speed'],
                'accuracy': row['accuracy'],
                'battery_level': row['battery_level'],
                'ts': row['timestamp'],
              })
          .toList();

      final bodyJson = json.encode({'device_id': deviceId, 'batch': points});
      final compressed = gzip.encode(utf8.encode(bodyJson));

      final response = await http.post(
        Uri.parse('$apiUrl/api/v1/telemetry/ingest/batch'),
        headers: {
          'Content-Type': 'application/json',
          'Content-Encoding': 'gzip',
          'Authorization': 'Bearer $token',
        },
        body: compressed,
      );

      if (response.statusCode == 201) {
        final ids = batch.map((r) => r['id'] as int).toList();
        await _markSynced(ids);
        _lastFlush = now;
        debugPrint('[SyncTask] ✅ Uploaded ${batch.length} points (gzip batch)');
      } else {
        debugPrint('[SyncTask] Upload failed: ${response.statusCode} ${response.body}');
      }
    } catch (e) {
      debugPrint('[SyncTask] Upload error: $e');
    }
  }
}

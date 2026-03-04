import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart';

class DatabaseService {
  static final DatabaseService _instance = DatabaseService._internal();
  factory DatabaseService() => _instance;
  DatabaseService._internal();

  Database? _database;

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
      version: 1,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            accuracy REAL NOT NULL,
            timestamp TEXT NOT NULL,
            synced INTEGER NOT NULL DEFAULT 0
          )
        ''');
      },
    );
  }

  Future<void> insertLocation(Map<String, dynamic> locationData) async {
    final db = await database;
    await db.insert('locations', {
      ...locationData,
      'synced': 0, // 0 for false
    });
    debugPrint('[Database] Inserted new location event offline.');
    await mockSync();
  }

  Future<int> getUnsyncedCount() async {
    final db = await database;
    final result = await db.rawQuery('SELECT COUNT(*) FROM locations WHERE synced = 0');
    return Sqflite.firstIntValue(result) ?? 0;
  }

  Future<List<Map<String, dynamic>>> getLastLocations(int limit) async {
    final db = await database;
    return await db.query(
      'locations',
      orderBy: 'id DESC',
      limit: limit,
    );
  }

  Future<void> mockSync() async {
    final count = await getUnsyncedCount();
    debugPrint('[SyncTask] MOCK SYNC: Currently there are $count events buffered in the local SQLite queue waiting to be synced.');
  }
}

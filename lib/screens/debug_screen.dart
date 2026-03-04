import 'package:flutter/material.dart';
import '../services/database_service.dart';

class DebugScreen extends StatefulWidget {
  const DebugScreen({super.key});

  @override
  State<DebugScreen> createState() => _DebugScreenState();
}

class _DebugScreenState extends State<DebugScreen> {
  final _databaseService = DatabaseService();
  List<Map<String, dynamic>> _logs = [];

  @override
  void initState() {
    super.initState();
    _loadLogs();
  }

  Future<void> _loadLogs() async {
    final logs = await _databaseService.getLastLocations(5);
    setState(() {
      _logs = logs;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Local Location Buffer (Debug)'),
        backgroundColor: Colors.blueGrey,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadLogs,
          )
        ],
      ),
      body: _logs.isEmpty
          ? const Center(child: Text('No offline records yet.'))
          : ListView.builder(
              itemCount: _logs.length,
              itemBuilder: (context, index) {
                final log = _logs[index];
                return Card(
                  margin: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
                  child: ListTile(
                    leading: Icon(
                      Icons.storage,
                      color: log['synced'] == 1 ? Colors.green : Colors.orange,
                    ),
                    title: Text('${log['latitude']}, ${log['longitude']}'),
                    subtitle: Text('Timestamp: ${log['timestamp']}\nAccuracy: ${log['accuracy']}m\nSynced: ${log['synced'] == 1}'),
                    isThreeLine: true,
                  ),
                );
              },
            ),
    );
  }
}

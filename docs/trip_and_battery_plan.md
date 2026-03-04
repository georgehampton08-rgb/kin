# Performance & Trip Logic Plan

**Project:** Kin — Family Location Sharing  
**Date:** 2026-03-04  
**Status:** APPROVED — Implementation target

---

## 1. Trip State Machine

### Current Problem

The existing `trip_detector.py` uses a naive rule: **5+ consecutive moving points (speed ≥ 0.5 m/s) = dispatch a trip**. This causes:

- **False fragmentation** — stopping at a red light (20–60 s) breaks the run and creates two trips
- **Trips never closing** — no concept of "8 minutes of silence = done"; trips remain open indefinitely
- **Map-matching fires on live trips** — OSRM receives incomplete data mid-journey and produces junk routes

### State Machine Definition

```
IDLE
  │  ≥3 consecutive pts, speed ≥ 1.5 m/s
  ▼
TRIP_OPEN
  │  speed drops < 0.5 m/s
  ▼
TRIP_PAUSED ─── speed resumes ≥ 1.5 m/s within 8 min ──► TRIP_OPEN
  │
  │  either:
  │    (a) no movement for 8 continuous minutes (wall-clock gap between last two points)
  │    (b) geofence ARRIVAL event fires for a "safe" zone
  ▼
TRIP_CLOSED  ←─ map-matching worker now consumes this record
```

### Key Thresholds

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `SPEED_MOVING_THRESHOLD` | **1.5 m/s** (~5.4 km/h) | Filters out pedestrian drift; confirms vehicular/cycling motion |
| `SPEED_STATIONARY_THRESHOLD` | **0.5 m/s** | Below this the device is at a stop; GPS jitter stays < ~0.3 m/s |
| `TRIP_OPEN_CONSECUTIVE` | **3 points** | At distanceFilter=50 m this requires ~150 m of confirmed movement |
| `PAUSE_RESUME_WINDOW` | **8 minutes** | Covers red lights (2 min), gas stations (5 min), short parking |
| `TRIP_CLOSE_GAP` | **8 minutes** | If last point timestamp is ≥ 8 min ago, no further movement expected |

### Database Schema

```sql
CREATE TYPE trip_status AS ENUM ('OPEN', 'PAUSED', 'CLOSED');

CREATE TABLE trips (
    trip_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id      VARCHAR NOT NULL REFERENCES devices(device_identifier),
    status         trip_status NOT NULL DEFAULT 'OPEN',
    start_time     TIMESTAMPTZ NOT NULL,
    last_seen_time TIMESTAMPTZ NOT NULL,  -- updated on each point push
    paused_at      TIMESTAMPTZ,           -- set when OPEN→PAUSED
    end_time       TIMESTAMPTZ,           -- set only when CLOSED
    point_count    INTEGER NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_trips_device_status ON trips(device_id, status);
```

**Design note:** Using a native `ENUM` type in Postgres (`CREATE TYPE`) is preferred over `VARCHAR + CHECK CONSTRAINT` because:

- The ENUM is enforced at the DB wire level — invalid strings are rejected before reaching Python
- `pg_type` indexing makes ENUM comparisons marginally faster on large cardinality tables
- Alembic handles ENUM migration cleanly via `sa.Enum(..., name='trip_status')`

---

## 2. Batch Upload Strategy

### Current Approach

Every location point is individually uploaded via `POST /api/v1/telemetry/ingest`. This is a **1:1 radio wake-up model** — each point costs one full HTTP round-trip including TLS handshake (~150–400 ms each, and ~15 mA radio current draw on LTE for ~0.5 s).

At distanceFilter=50 m traveling 60 km/h, the device logs **~1 point every 3 seconds**, or **~20 points/minute** = **20 radio wake-ups/minute**.

### Proposed Approach: Adaptive Batching

| Condition | Strategy | Expected Reduction |
|-----------|----------|--------------------|
| Battery ≥ 20%, moving | Batch 10 points or 30s, whichever first | **~80% fewer wake-ups** |
| Battery < 20% ("Low Battery Mode") | Batch every 10 min, HTTP POST only (no MQTT) | **~95% fewer wake-ups** |
| Stationary (TRIP_PAUSED/IDLE) | Heartbeat-only, no location batch | **~100% reduction** |

### Payload Compression

All batched payloads are gzip-compressed before transmission:

```python
import gzip, json
compressed = gzip.compress(json.dumps(points).encode())
# Typical 10-point batch: ~800 bytes raw → ~220 bytes compressed (72% reduction)
```

Server declares `Content-Encoding: gzip` support via uvicorn's built-in decompression.

### Expected "Radio Wake-Up" Reduction

Baseline: 20 wake-ups/min → Batch-10: **2 wake-ups/min** = **90% reduction**.  
Low-battery batch-10min: **0.1 wake-ups/min** = **99.5% reduction vs baseline**.

---

## 3. Heartbeat Contract

### What the Device Sends

Every **5 minutes**, regardless of movement state, the Flutter client fires a lightweight heartbeat:

```json
POST /api/v1/telemetry/heartbeat
Content-Type: application/json
Authorization: Bearer <device_jwt>

{
  "device_id": "kin-dev-abc123",
  "battery_level": 72.5,
  "gps_accuracy": 4.2,
  "timestamp": "2026-03-04T17:00:00Z"
}
```

This is **separate** from the location batch payload. Total payload size: ~120 bytes.

### What the Backend Does

1. Upserts into `device_status` table, setting `last_heartbeat_at = now()` and `status = 'ONLINE'`
2. Stores `battery_level` and `gps_accuracy` for dashboard display

### Staleness Detection

```
APScheduler job: runs every 5 minutes
  For each device in device_status:
    if now() - last_heartbeat_at > 12 minutes AND status != 'STALE':
        UPDATE device_status SET status = 'STALE'
        Broadcast WS event to parent dashboard: {"type": "device_stale", "device_id": ...}
```

**Why APScheduler (in-process) over GCP Cloud Scheduler:**

| Factor | APScheduler | GCP Cloud Scheduler |
|--------|-------------|---------------------|
| Stateless Cloud Run | ⚠️ Restarts on cold start (acceptable for 5-min jobs) | ✅ External, always reliable |
| Setup complexity | ✅ Zero — pure Python, in-process | ⚠️ Requires GCP Scheduler + IAM + HTTP trigger |
| Cost | ✅ Free | ⚠️ $0.10/month + Cloud Run invocation cost |
| Job granularity | ✅ asyncio-native | ⚠️ HTTP round-trip latency |

**Decision:** APScheduler with `AsyncIOScheduler` is the correct choice for this Cloud Run deployment. The 5-minute heartbeat check is **idempotent** (marking already-STALE devices is a no-op), so a cold-start reset is safe. If Cloud Run scales to 0, no devices are active, so there is nothing to mark STALE.

### Device Status Schema

```sql
CREATE TYPE device_online_status AS ENUM ('ONLINE', 'STALE', 'OFFLINE');

CREATE TABLE device_status (
    device_id          VARCHAR PRIMARY KEY,
    status             device_online_status NOT NULL DEFAULT 'ONLINE',
    battery_level      FLOAT,
    gps_accuracy       FLOAT,
    last_heartbeat_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 4. Battery-Aware Upload Throttling

### Flutter-Side Logic (location_service.dart)

```dart
// Triggered by battery plugin or injected via config
if (batteryLevel < 20) {
  _log("[BATTERY] LOW_BATTERY_MODE_ACTIVE — throttling uploads");
  await bg.BackgroundGeolocation.setConfig(bg.Config(
    distanceFilter: 100.0,     // 2× default (50 m)
    stopTimeout: 10,           // 2× default (5 min)
  ));
  _uploadMode = UploadMode.batchHTTP;  // disable MQTT, use batch HTTP only
  _batchIntervalSeconds = 600;         // 10-minute batch
} else {
  _uploadMode = UploadMode.mqtt;
  _batchIntervalSeconds = 30;
}
```

### Backend-Side Audit Log

When `battery_level < 20` arrives in a heartbeat or ingest payload, the backend logger emits:

```
INFO [BatteryGate] LOW_BATTERY_MODE_ACTIVE — device=kin-dev-abc123 battery=15.0%
```

This structured log entry is queryable in Cloud Logging via:

```
jsonPayload.message =~ "LOW_BATTERY_MODE_ACTIVE"
```

---

## 5. Flutter Background Geolocation Configuration

### Current Settings Audit

| Setting | Current Value | Issue |
|---------|--------------|-------|
| `distanceFilter` | 50 m | Fine for normal operation |
| `stopTimeout` | 5 min | Too short — engine-idling scenarios trigger false stops |
| `stationaryRadius` | (not set) | Defaults to 25 m — insufficient for GPS drift |

### Proposed Settings

```dart
bg.Config(
  desiredAccuracy: bg.Config.DESIRED_ACCURACY_HIGH,
  distanceFilter: 50.0,
  stopTimeout: 8,          // 8 min — matches TRIP_CLOSE_GAP on server
  stationaryRadius: 50.0,  // 50 m — prevents false exits from GPS jitter
  stopOnTerminate: false,
  startOnBoot: true,
  debug: false,            // DISABLE in production
  logLevel: bg.Config.LOG_LEVEL_WARNING,
  reset: false,            // Don't wipe settings on reinit
)
```

Setting `stopTimeout: 8` aligns the device's internal stop detection with the server's 8-minute trip-close window, ensuring the `onMotionChange` callback fires at the same moment the server would close the trip.

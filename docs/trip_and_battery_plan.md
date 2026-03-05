# Performance & Trip Logic Plan

**Kin Backend — v2**  
*Author: AI Agent | Date: 2026-03-05*

---

## 1. Current State Audit

### Flutter (`location_service.dart`)

| Parameter | Current Value | Problem |
|---|---|---|
| `distanceFilter` | 50 m | Too coarse for slow walking / urban stops |
| `stopTimeout` | 5 min | Closes motion too fast at red lights |
| `stationaryRadius` | not set (SDK default 25 m) | Fine |
| Heartbeat | ❌ none | Parent has no stale-device signal |
| Battery throttle | ❌ none | Full-rate GPS in low-battery state |
| Upload strategy | `mockSync()` only | No real upload path |

### Backend (`trip_detector.py`)

| Item | Current | Problem |
|---|---|---|
| State storage | In-memory Python dict | Lost on server restart; Cloud Run scales to 0 |
| Trip open rule | 5+ consecutive points ≥ 0.5 m/s | No persistence, no PAUSE concept |
| Trip close rule | First stationary point | Red light = immediate close |
| Map-matching gate | Fires on every moving run | Wastes OSRM calls on open trips |

---

## 2. Trip State Machine

### States

```
ACCUMULATING → TRIP_OPEN → TRIP_PAUSED ⟷ TRIP_OPEN → TRIP_CLOSED
```

| State | Meaning |
|---|---|
| `ACCUMULATING` | Device moving but not yet 3 consecutive points ≥ 1.5 m/s |
| `TRIP_OPEN` | Active trip in progress |
| `TRIP_PAUSED` | Speed < 0.5 m/s but pause window (8 min) not expired |
| `TRIP_CLOSED` | Ended permanently; ready for map-matching |

### Transition Rules

| Trigger | From → To | Condition |
|---|---|---|
| 3 consecutive points with speed ≥ 1.5 m/s | ACCUMULATING → TRIP_OPEN | All 3 points within 90 sec |
| Speed drops < 0.5 m/s | TRIP_OPEN → TRIP_PAUSED | Record `paused_at` timestamp |
| Speed rises ≥ 1.5 m/s | TRIP_PAUSED → TRIP_OPEN | `paused_at` was < 8 min ago |
| `paused_at` is > 8 min ago | TRIP_PAUSED → TRIP_CLOSED | Set `end_time`, status = CLOSED |
| Geofence ARRIVAL event | TRIP_OPEN / PAUSED → TRIP_CLOSED | Immediate close |
| No heartbeat for 8 min on an open trip | TRIP_OPEN → TRIP_CLOSED | Staleness close |

### Speed Thresholds (rationale)

- **1.5 m/s (5.4 km/h)** — open threshold: excludes slow walking, includes cycling
- **0.5 m/s (1.8 km/h)** — pause threshold: red light, brief stop
- **8 min pause window** — GTFS stop dwell time median is ~2 min; 8 min captures school drop-off

---

## 3. Database Schema Changes

### `trips` table

```sql
CREATE TABLE trips (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id   VARCHAR NOT NULL,
    family_id   UUID NOT NULL REFERENCES families(id),
    status      VARCHAR NOT NULL CHECK (status IN ('ACCUMULATING','TRIP_OPEN','TRIP_PAUSED','TRIP_CLOSED')),
    start_time  TIMESTAMPTZ,
    paused_at   TIMESTAMPTZ,
    end_time    TIMESTAMPTZ,
    point_count INT NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX trips_device_status ON trips(device_id, status);
```

> **VARCHAR + CHECK CONSTRAINT** chosen over Postgres ENUM because:
>
> - No `ALTER TYPE` DDL needed to add states later
> - Alembic handles it natively without custom type objects
> - Performance identical for this row volume

### `device_status` table

```sql
CREATE TABLE device_status (
    device_id       VARCHAR PRIMARY KEY,
    family_id       UUID NOT NULL REFERENCES families(id),
    status          VARCHAR NOT NULL CHECK (status IN ('ONLINE','STALE','OFFLINE')),
    battery_level   FLOAT,
    gps_accuracy    FLOAT,
    last_heartbeat  TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ DEFAULT now()
);
```

---

## 4. Batch Upload Strategy

### Current

- Every location event → immediate `mockSync()` (no real HTTP)
- Radio wake-up: **1 per location event** (≈ 1/50m)

### Proposed

| Mode | Condition | Upload Method | Interval |
|---|---|---|---|
| **Normal** | battery ≥ 20% | Batch HTTPS POST (gzip) | Every **20 points** OR 3 min, whichever first |
| **Low Battery** | battery < 20% | Batch HTTPS POST (gzip) | Every **5 min** flat, no MQTT |
| **Stationary** | motion = STILL | Heartbeat-only | Every **5 min** |

**Expected radio wake-up reduction: ~85%**  
*Basis: from ≈1 wake/50m to 1 wake/1000m (20-point batch at 50m filter)*

### Payload Format (gzip JSON)

```json
{
  "device_id": "abc123",
  "batch": [
    {"lat": 51.5, "lng": -0.1, "speed": 2.1, "accuracy": 4.2, "ts": "2026-03-05T10:00:00Z"},
    ...
  ]
}
```

Python receives via `Content-Encoding: gzip` on the ingest endpoint.

---

## 5. Heartbeat Contract

### Device sends (every 5 min, independent of location)

```json
POST /api/v1/telemetry/heartbeat
{
  "device_id": "abc123",
  "battery_level": 78.0,
  "gps_accuracy": 4.2,
  "timestamp": "2026-03-05T10:05:00Z"
}
```

### Backend response

- Upsert `device_status` row — set `last_heartbeat = now()`, `status = ONLINE`
- Returns `200 OK` with `{"ack": true}`

### Stale detection (APScheduler — runs in-process)

- Why **APScheduler** over GCP Cloud Scheduler: Cloud Run scales to zero; a Pub/Sub push target would need the instance warm. APScheduler runs inside the FastAPI process on each instance. With Cloud Run `min-instances=1`, one scheduler runs reliably. No extra GCP infrastructure needed.
- Job: every **2 minutes**, `SELECT * FROM device_status WHERE last_heartbeat < now() - interval '12 minutes' AND status = 'ONLINE'` → mark `STALE`

---

## 6. Battery-Aware Throttling (Flutter)

```dart
// Triggered by battery level in heartbeat response or platform battery plugin
if (batteryLevel < 20) {
  bg.BackgroundGeolocation.setConfig(bg.Config(
    distanceFilter: 100.0,     // doubled from 50m
    stopTimeout: 10,           // doubled from 5min
  ));
  _switchToBatchOnlyMode();    // disable MQTT, enable 10-min batch HTTP
  logger.log('LOW_BATTERY_MODE_ACTIVE');
} else {
  _restoreNormalMode();
}
```

---

## 7. APScheduler vs GCP Cloud Scheduler Decision

| Criterion | APScheduler (in-process) | GCP Cloud Scheduler |
|---|---|---|
| Setup complexity | Low (pip install) | Medium (Cloud Scheduler job + HTTP target) |
| Reliability on Cloud Run | Good with `min-instances=1` | Better (external, not affected by container lifecycle) |
| Cost | Free | Free (up to 3 jobs) |
| **Verdict** | ✅ Use for MVP | Migrate when scaling to multi-instance |

---

## 8. Definition of Done

| Test | Expected Result |
|---|---|
| 20 points with 10-min gap | → 2 `TRIP_CLOSED` records |
| 12-min heartbeat silence | → `device_status.status = 'STALE'` |
| `battery_level = 15` in ingest | → logs `LOW_BATTERY_MODE_ACTIVE` |

# Kin Security Implementation Plan

> **Status**: Draft — Pending Review  
> **Date**: 2026-03-04  
> **Scope**: End-to-end security hardening of the Kin FastAPI backend  

---

## 1. Parent / Child Data Model

### Current State

The database has no concept of users, devices, or family ownership. All tables reference a raw `device_id` string with no authentication or authorization boundary. Any caller who knows a `device_id` can read its full location history.

### Proposed Schema

#### `users` table

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK, `gen_random_uuid()` |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL |
| `hashed_password` | VARCHAR(255) | NOT NULL |
| `role` | VARCHAR(20) | NOT NULL, CHECK (`parent` or `child`) |
| `created_at` | TIMESTAMPTZ | DEFAULT `now()` |

#### `families` table

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK, `gen_random_uuid()` |
| `name` | VARCHAR(100) | NOT NULL |
| `created_at` | TIMESTAMPTZ | DEFAULT `now()` |

#### `family_memberships` table

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `family_id` | UUID | FK → `families.id`, NOT NULL |
| `user_id` | UUID | FK → `users.id`, NOT NULL |
| `role` | VARCHAR(20) | `parent` or `child` |
| UNIQUE | | (`family_id`, `user_id`) |

#### `devices` table

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `device_identifier` | VARCHAR(255) | UNIQUE, NOT NULL (Android hardware ID) |
| `family_id` | UUID | FK → `families.id`, NOT NULL |
| `user_id` | UUID | FK → `users.id`, NOT NULL (the child who carries this device) |
| `paired_at` | TIMESTAMPTZ | DEFAULT `now()` |
| `is_active` | BOOLEAN | DEFAULT `true` |

#### `pairing_tokens` table

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `token` | VARCHAR(64) | UNIQUE, NOT NULL, cryptographically random |
| `family_id` | UUID | FK → `families.id`, NOT NULL |
| `created_by` | UUID | FK → `users.id`, NOT NULL (the parent) |
| `expires_at` | TIMESTAMPTZ | NOT NULL (`now() + 15 min`) |
| `used_at` | TIMESTAMPTZ | NULL (set once consumed) |
| `device_id` | UUID | FK → `devices.id`, NULL (set on pairing) |

### Foreign Key Chain That Enforces Ownership

```
parent (user) ──FK──► family_memberships ──FK──► families
                                                    ▲
child (user)  ──FK──► family_memberships ──FK───────┘
                                                    │
device        ──FK──► families ─────────────────────┘
                  ──FK──► users (child)
                  
location_history.device_id ──FK──► devices.device_identifier
matched_routes.device_id   ──FK──► devices.device_identifier
```

A parent can **only** query devices where `devices.family_id` matches a `family_memberships` row for their `user_id`. This is enforced at the SQL level via RLS (Section 4) and at the application level via middleware (the JWT carries `family_id` + `user_id`).

---

## 2. JWT Access / Refresh Token Rotation Strategy

### Token Architecture

| Token Type | Audience | Lifetime | Storage |
|------------|----------|----------|---------|
| **Access Token** | All authenticated API calls | 15 minutes | Memory (Android: EncryptedSharedPreferences) |
| **Refresh Token** | `/auth/refresh` endpoint only | 7 days | EncryptedSharedPreferences / HttpOnly cookie |

### JWT Claims Structure

```json
{
  "sub": "<user_id UUID>",
  "family_id": "<family_id UUID>",
  "device_id": "<device_id UUID or null>",
  "role": "parent | child | device",
  "scope": "dashboard | telemetry",
  "iat": 1709560000,
  "exp": 1709560900,
  "jti": "<unique token ID for revocation>"
}
```

- **`scope: dashboard`** — Issued to parent users; allows reading location data, managing zones, viewing history.
- **`scope: telemetry`** — Issued to paired devices (child's phone); allows only writing telemetry and MQTT connection.

### Rotation Flow

```
┌─ Android App ─┐        ┌── Kin API ──┐
│               │        │             │
│ 1. POST /auth/pair-device            │
│   {pairing_token}──────►validate     │
│               │        │ create device│
│   ◄────────── │        │ return:     │
│   access_token│        │  access_tkn │
│   refresh_token        │  refresh_tkn│
│               │        │             │
│ 2. Bearer <access> ───► validate JWT │
│   GET /api/v1/... ────► middleware   │
│               │        │             │
│ 3. access expired      │             │
│   POST /auth/refresh   │             │
│   {refresh_token}─────► rotate:      │
│               │        │ new access  │
│   ◄────────── │        │ new refresh │
│   new tokens  │        │ revoke old  │
│               │        │             │
└───────────────┘        └─────────────┘
```

### Refresh Token Rotation Rules

1. Each refresh token is **single-use**. On use, a new pair (access + refresh) is issued and the old refresh token's `jti` is added to a revocation set.
2. If a revoked refresh token is presented, **all tokens for that device are invalidated** (possible token theft).
3. Refresh tokens are stored server-side in a `refresh_tokens` table with `(jti, device_id, expires_at, revoked_at)` for audit and revocation.

### Signing Configuration

- Algorithm: **HS256** (symmetric) for MVP since the only consumer of tokens is our own API. Migrate to **RS256** (asymmetric) before adding third-party integrations.
- Secret: `JWT_SECRET_KEY` environment variable, minimum 256-bit, sourced from GCP Secret Manager at runtime.

---

## 3. Dynamic Configuration for Android APK (No Compile-Time Secrets)

### Problem

Compiling the server URL, API keys, or MQTT credentials into the APK means every shipped binary contains extractable secrets. APK decompilation (via `jadx`, `apktool`) exposes these trivially.

### Solution: QR-Code Pairing Flow

```
┌── Parent Dashboard ──┐     ┌── Android App ──┐
│                       │     │                 │
│ 1. Parent clicks      │     │                 │
│    "Add Device"       │     │                 │
│                       │     │                 │
│ 2. API generates a    │     │                 │
│    pairing_token      │     │                 │
│    (64-char, 15min)   │     │                 │
│                       │     │                 │
│ 3. Dashboard renders  │     │                 │
│    QR code containing:│     │                 │
│    {                  │     │                 │
│      "api_url": "https://kin-api.run.app",    │
│      "pairing_token": "abc..xyz",             │
│      "mqtt_host": "mqtt.kin.app",             │
│      "mqtt_port": 8883                        │
│    }                  │     │                 │
│                       │     │                 │
│         ◄─── child scans QR ──►               │
│                       │     │                 │
│                       │     │ 4. App calls:   │
│                       │     │   POST /auth/   │
│                       │     │   pair-device   │
│                       │     │   with token +  │
│                       │     │   hardware ID   │
│                       │     │                 │
│                       │     │ 5. Receives:    │
│                       │     │   access_token  │
│                       │     │   refresh_token │
│                       │     │   mqtt_username │
│                       │     │   mqtt_password │
│                       │     │                 │
│                       │     │ 6. Stores all   │
│                       │     │   in Encrypted  │
│                       │     │   SharedPrefs   │
│                       │     │   (Jetpack Sec) │
└───────────────────────┘     └─────────────────┘
```

### Key Design Decisions

1. **The APK ships with ZERO server URLs or credentials.** The only hardcoded element is the UI to scan a QR code.
2. **Pairing tokens are one-time-use** with a 15-minute TTL. After use, the `used_at` timestamp is set and the token is permanently consumed.
3. **MQTT credentials are per-device**, generated at pairing time. The MQTT broker (EMQX) uses the device's `device_id` as its MQTT `client_id` and a random password stored hashed in the `devices` table.
4. **If the device is unpaired** (parent revokes from dashboard), the refresh token is revoked and the MQTT ACL denies the device's `client_id`.

### `/auth/pair-device` Endpoint Specification

```
POST /auth/pair-device
Content-Type: application/json

{
  "pairing_token": "abc123...xyz",
  "device_identifier": "android_hw_id_sha256"
}
```

**Success (200)**:

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "mqtt_config": {
    "host": "mqtt.kin.app",
    "port": 8883,
    "username": "device_<uuid>",
    "password": "random_mqtt_password",
    "topic_publish": "kin/telemetry/<device_id>",
    "topic_lwt": "kin/telemetry/<device_id>/status"
  }
}
```

**Error Cases**:

| Condition | Status | Body |
|-----------|--------|------|
| Token not found | 400 | `{"detail": "Invalid pairing token"}` |
| Token already used | 400 | `{"detail": "Pairing token already consumed"}` |
| Token expired | 400 | `{"detail": "Pairing token has expired"}` |
| Missing fields | 422 | Standard Pydantic validation |

---

## 4. Row-Level Security (RLS) Policies

### Rationale

RLS policies at the Postgres level serve as a **defense-in-depth** layer. Even if the application logic has a bug that leaks data across families, the database will refuse to serve rows belonging to other families.

### Implementation Strategy

SQLAlchemy's connection pooling typically uses a single database role, which bypasses RLS by default (superusers and table owners are exempt from RLS). The solution:

1. **Create a dedicated `kin_app` role** that is NOT the table owner. The table owner is `kinuser` (the migration role).
2. **Grant `kin_app` the minimum required permissions** (SELECT, INSERT, UPDATE on specific tables).
3. **Set `app.current_family_id`** as a session variable on every connection checkout from the pool, using `SET LOCAL` so it only applies to the current transaction.
4. **All application queries run as `kin_app`** which is subject to RLS.

### Policy Definitions

#### On `location_history`

```sql
ALTER TABLE location_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE location_history FORCE ROW LEVEL SECURITY;

-- Read policy: only see locations for devices in your family
CREATE POLICY family_read_locations ON location_history
  FOR SELECT TO kin_app
  USING (
    device_id IN (
      SELECT device_identifier FROM devices
      WHERE family_id = current_setting('app.current_family_id')::uuid
    )
  );

-- Insert policy: devices can only write their own telemetry
CREATE POLICY device_write_locations ON location_history
  FOR INSERT TO kin_app
  WITH CHECK (
    device_id IN (
      SELECT device_identifier FROM devices
      WHERE family_id = current_setting('app.current_family_id')::uuid
    )
  );
```

#### On `matched_routes`

```sql
ALTER TABLE matched_routes ENABLE ROW LEVEL SECURITY;
ALTER TABLE matched_routes FORCE ROW LEVEL SECURITY;

CREATE POLICY family_read_routes ON matched_routes
  FOR SELECT TO kin_app
  USING (
    device_id IN (
      SELECT device_identifier FROM devices
      WHERE family_id = current_setting('app.current_family_id')::uuid
    )
  );

CREATE POLICY device_write_routes ON matched_routes
  FOR INSERT TO kin_app
  WITH CHECK (
    device_id IN (
      SELECT device_identifier FROM devices
      WHERE family_id = current_setting('app.current_family_id')::uuid
    )
  );
```

#### On `current_status`

```sql
ALTER TABLE current_status ENABLE ROW LEVEL SECURITY;
ALTER TABLE current_status FORCE ROW LEVEL SECURITY;

CREATE POLICY family_read_status ON current_status
  FOR ALL TO kin_app
  USING (
    device_id IN (
      SELECT device_identifier FROM devices
      WHERE family_id = current_setting('app.current_family_id')::uuid
    )
  );
```

#### On `zones` and `geofence_events`

Zones and geofence events will also be scoped to families by adding a `family_id` column to both tables:

```sql
ALTER TABLE zones ENABLE ROW LEVEL SECURITY;
CREATE POLICY family_zones ON zones FOR ALL TO kin_app
  USING (family_id = current_setting('app.current_family_id')::uuid);

ALTER TABLE geofence_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY family_events ON geofence_events FOR ALL TO kin_app
  USING (
    device_id IN (
      SELECT device_identifier FROM devices
      WHERE family_id = current_setting('app.current_family_id')::uuid
    )
  );
```

### SQLAlchemy Pool Integration

```python
from sqlalchemy import event

@event.listens_for(engine.sync_engine, "checkout")
def set_rls_context(dbapi_connection, connection_record, connection_proxy):
    """Set the family_id session variable on connection checkout."""
    # The family_id is injected from the middleware via a context var
    # This runs BEFORE any query on the connection
    pass  # actual implementation sets app.current_family_id via SET LOCAL
```

In the middleware, after JWT validation:

```python
# Extract family_id from the validated JWT
family_id = token_payload["family_id"]
# Store in a contextvars.ContextVar for the pool event to pick up
_current_family_id.set(family_id)
```

---

## 5. Encryption at Rest for Coordinate Columns (pgcrypto)

### Rationale

GPS coordinates of a minor are the most sensitive data in the system. Even if the database is compromised (backup leak, SQL injection past RLS), coordinates should be **ciphertext** that requires a decryption key the attacker doesn't have.

### Implementation

#### Enable pgcrypto

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

#### Encryption Strategy

Instead of modifying the existing `location_history` table (which uses PostGIS `Geography` for spatial queries), we create a parallel storage layer:

##### `locations_raw` table (new)

| Column | Type | Notes |
|--------|------|-------|
| `id` | SERIAL | PK |
| `device_id` | VARCHAR | FK → `devices.device_identifier` |
| `lat_encrypted` | BYTEA | `pgp_sym_encrypt(lat::text, key)` |
| `lng_encrypted` | BYTEA | `pgp_sym_encrypt(lng::text, key)` |
| `altitude` | FLOAT | Nullable |
| `speed` | FLOAT | Nullable |
| `battery_level` | FLOAT | Nullable |
| `timestamp` | TIMESTAMPTZ | DEFAULT `now()` |

- Raw coordinates are **always** stored encrypted in `locations_raw`.
- The existing `location_history` table continues to store PostGIS `Geography` points for geofencing and spatial queries, but these are ephemeral and can be purged on a rolling 24-hour window.
- The `locations_raw` table is the **permanent audit trail** with encrypted coordinates.

#### Encrypt on Insert

```sql
INSERT INTO locations_raw (device_id, lat_encrypted, lng_encrypted, altitude, speed, battery_level)
VALUES (
  :device_id,
  pgp_sym_encrypt(:lat::text, :encryption_key),
  pgp_sym_encrypt(:lng::text, :encryption_key),
  :altitude,
  :speed,
  :battery_level
);
```

#### Decrypt on Authorized Read

```sql
SELECT
  pgp_sym_decrypt(lat_encrypted, :encryption_key)::float AS lat,
  pgp_sym_decrypt(lng_encrypted, :encryption_key)::float AS lng,
  altitude, speed, battery_level, timestamp
FROM locations_raw
WHERE device_id = :device_id
ORDER BY timestamp DESC;
```

#### Key Management

- The symmetric encryption key is sourced from the `PGCRYPTO_KEY` environment variable, loaded from **GCP Secret Manager** at runtime.
- The key is **never** stored in the database, in the codebase, or in the APK.
- For key rotation: encrypt new rows with the new key, run a migration script to re-encrypt old rows.

#### Performance Considerations

- `pgp_sym_encrypt` / `pgp_sym_decrypt` add ~0.1-0.3ms per call. At the expected ingestion rate (1 point/second per device, ~10 devices), this is negligible.
- Decryption only happens during parent dashboard queries, not during high-frequency ingestion path (geofencing uses the PostGIS `location_history` table, not `locations_raw`).

#### RLS on `locations_raw`

```sql
ALTER TABLE locations_raw ENABLE ROW LEVEL SECURITY;
ALTER TABLE locations_raw FORCE ROW LEVEL SECURITY;

CREATE POLICY family_raw_locations ON locations_raw
  FOR ALL TO kin_app
  USING (
    device_id IN (
      SELECT device_identifier FROM devices
      WHERE family_id = current_setting('app.current_family_id')::uuid
    )
  );
```

---

## Proposed Implementation Changes

### Migration: `add_security_tables`

#### [NEW] [e1_security_tables.py](file:///c:/Users/georg/kin/backend/alembic/versions/e1_security_tables.py)

Alembic migration that creates `users`, `families`, `family_memberships`, `devices`, `pairing_tokens`, `refresh_tokens`, and `locations_raw` tables. Enables pgcrypto extension. Creates the `kin_app` role. Applies all RLS policies. Adds `family_id` column to `zones`.

### Auth Module

#### [NEW] [auth.py](file:///c:/Users/georg/kin/backend/app/core/auth.py)

JWT token creation/validation utilities using `python-jose` with HS256. Functions: `create_access_token()`, `create_refresh_token()`, `decode_token()`, `hash_password()`, `verify_password()`.

#### [NEW] [auth.py](file:///c:/Users/georg/kin/backend/app/api/v1/endpoints/auth.py)

Endpoints: `POST /auth/pair-device`, `POST /auth/refresh`, `POST /auth/register` (parent registration).

#### [NEW] [deps.py](file:///c:/Users/georg/kin/backend/app/api/deps.py)

FastAPI dependency injection: `get_current_user()` — validates the Bearer JWT and returns the decoded claims. `get_db()` — yields an async session with `app.current_family_id` set.

### Middleware

#### [MODIFY] [security.py](file:///c:/Users/georg/kin/backend/app/core/security.py)

Replace the hardcoded `APIKeyMiddleware` with a `JWTAuthMiddleware` that:

- Skips auth for `/auth/*`, `/docs`, `/openapi.json`, `/`
- Returns **401** for missing/expired/invalid JWT
- Returns **403** for valid JWT attempting to access another family's data
- Never returns 404 for cross-family access (prevents resource enumeration)

### Model Updates

#### [MODIFY] [location.py](file:///c:/Users/georg/kin/backend/app/models/location.py)

Add SQLAlchemy models for `User`, `Family`, `FamilyMembership`, `Device`, `PairingToken`, `RefreshToken`, `LocationRaw`.

#### [MODIFY] [base.py](file:///c:/Users/georg/kin/backend/app/db/base.py)

Import the new models so Alembic can discover them.

### Endpoint Updates

#### [MODIFY] [telemetry.py](file:///c:/Users/georg/kin/backend/app/api/v1/endpoints/telemetry.py)

Require device-scoped JWT. On ingest, also write encrypted coordinates to `locations_raw`.

#### [MODIFY] [history.py](file:///c:/Users/georg/kin/backend/app/api/v1/endpoints/history.py)

Require parent-scoped JWT. Verify `device_id` belongs to caller's family before returning data.

#### [MODIFY] [zones.py](file:///c:/Users/georg/kin/backend/app/api/v1/endpoints/zones.py)

Scope zones to `family_id` from JWT.

#### [MODIFY] [api.py](file:///c:/Users/georg/kin/backend/app/api/v1/api.py)

Add the auth router.

#### [MODIFY] [main.py](file:///c:/Users/georg/kin/backend/app/main.py)

Replace `APIKeyMiddleware` with `JWTAuthMiddleware`. Update CORS.

### Dependencies

#### [MODIFY] [requirements.txt](file:///c:/Users/georg/kin/backend/requirements.txt)

Add: `python-jose[cryptography]`, `passlib[bcrypt]`, `python-multipart`.

### Tests

#### [NEW] [security_audit.py](file:///c:/Users/georg/kin/backend/tests/security_audit.py)

Four pytest tests simulating:

1. **Expired token**: Craft a JWT with `exp` in the past → expect 401.
2. **Wrong-family token**: Valid JWT but for `family_id_B` → access `family_id_A` data → expect 403.
3. **Missing token**: Call protected endpoint with no Authorization header → expect 401.
4. **SQL injection on `device_id`**: Pass `'; DROP TABLE users; --` as device_id parameter → expect 422 or 400, NOT a database error.

---

## Verification Plan

### Automated Tests

```bash
# From the backend directory with venv activated:
cd c:\Users\georg\kin\backend
.\venv\Scripts\Activate.ps1
pytest tests/security_audit.py -v
```

**Expected**: 4/4 tests pass (expired token → 401, wrong-family → 403, missing token → 401, SQL injection → blocked).

### Manual Verification

1. **Encrypted coordinates check**: Connect to PostgreSQL and run:

   ```sql
   SELECT id, device_id, lat_encrypted, lng_encrypted FROM locations_raw LIMIT 5;
   ```

   Verify that `lat_encrypted` and `lng_encrypted` show binary/hex ciphertext, not readable floats.

2. **Pair-device flow**:
   - Call `POST /auth/pair-device` with a valid one-time token → verify 200 with JWT.
   - Call same endpoint with the same token again → verify 400 "already consumed".
   - Wait 15 minutes (or manually set `expires_at` to the past) → verify 400 "expired".

3. **RLS enforcement**: Connect to Postgres as the `kin_app` role (not `kinuser`) and attempt:

   ```sql
   SET app.current_family_id = '<family_A_id>';
   SELECT * FROM location_history;
   -- Should only return family A's devices' data
   ```

---

## OWASP API Security Top 10 (2023) Coverage

| # | Risk | Mitigation |
|---|------|------------|
| API1 | Broken Object Level Authorization | RLS + middleware family_id enforcement + 403 response |
| API2 | Broken Authentication | JWT with short-lived access tokens, refresh rotation, bcrypt passwords |
| API3 | Broken Object Property Level Authorization | Pydantic response models restrict exposed fields |
| API4 | Unrestricted Resource Consumption | Rate limiting (future: Cloud Run concurrency limits) |
| API5 | Broken Function Level Authorization | Role/scope checks in JWT (`dashboard` vs `telemetry`) |

---

## Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| JWT library | `python-jose` | Widely used, supports HS256/RS256, good FastAPI integration |
| Password hashing | `passlib[bcrypt]` | Industry standard, configurable rounds |
| Custom OAuth2 vs FastAPI-Users | **Custom** | FastAPI-Users adds unnecessary complexity for a single-family-per-user model; we need tight control over the pairing flow and device-scoped tokens that FastAPI-Users doesn't natively support |
| RLS strategy | Dedicated `kin_app` role + `SET LOCAL` | Standard pattern; avoids bypassing RLS via table ownership; supports connection pooling |
| Coordinate encryption | pgcrypto `pgp_sym_encrypt` | Built into PostgreSQL, no external dependencies, acceptable performance at target scale |
| Android secure storage | EncryptedSharedPreferences (Jetpack Security) | AES-256, hardware-backed Keystore on supported devices |

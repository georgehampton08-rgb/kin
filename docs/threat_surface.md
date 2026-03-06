# Kin Threat Surface Document

> Generated: 2026-03-05
> Scope: Full application — FastAPI backend, React dashboard, Flutter Android app
> Last Updated: 2026-03-05 — Security hardening complete

---

## 1. HTTP REST Endpoints

| # | Endpoint | Method | Auth | Risk | Attack Vector | Mitigation | Status |
|---|----------|--------|------|------|---------------|------------|--------|
| 1 | `POST /api/v1/auth/register` | POST | None | **HIGH** | Account enumeration, brute force, credential stuffing | Rate limit 10/min/IP, input validation | **RESOLVED** — `auth.py:103` @limiter, `rate_limiter.py:46` lockout |
| 2 | `POST /api/v1/auth/login` | POST | None | **HIGH** | Brute force, credential stuffing, timing attacks | Rate limit 10/min/IP, lockout after 5 failures | **RESOLVED** — `auth.py:167` @limiter, `rate_limiter.py:46-60` lockout |
| 3 | `POST /api/v1/auth/pair-device` | POST | None | **HIGH** | Token brute force, replay attack | Rate limit 10/min/IP, token TTL enforcement | **RESOLVED** — `auth.py:253` @limiter, `auth.py:269` uniform error |
| 4 | `POST /api/v1/auth/refresh` | POST | None | **MEDIUM** | Token reuse detection bypass | Already has reuse detection; add rate limit | **RESOLVED** — `auth.py:388` @limiter 30/min |
| 5 | `POST /api/v1/auth/create-pairing-token` | POST | JWT | **MEDIUM** | Token leakage via QR code | Short TTL (10 min), single use | **RESOLVED** — `auth.py:46` 10-min TTL |
| 6 | `POST /api/v1/telemetry/ingest` | POST | JWT | **HIGH** | SQL injection via device_id, unbounded coords, replay | Pydantic validation, parameterized queries, timestamp bounds | **RESOLVED** — `location.py:9-14` bounds, `telemetry.py:43-52` timestamp |
| 7 | `POST /api/v1/telemetry/ingest/batch` | POST | JWT | **HIGH** | Gzip bomb, oversized batch, injection | Max batch size, decompression limit, validation | **RESOLVED** — `telemetry.py:51-52` MAX_BATCH_SIZE=100, MAX_DECOMPRESSED=1MB |
| 8 | `POST /api/v1/telemetry/heartbeat` | POST | JWT | **MEDIUM** | Spoofed heartbeat, unbounded values | UUID validation on device_id, value bounds | **RESOLVED** — `heartbeat.py:24-43` Pydantic bounds |
| 9 | `POST /api/v1/telemetry/comms` | POST | JWT | **HIGH** | PII injection (SMS body, phone numbers), unbounded strings | String length limits, sanitization | **RESOLVED** — `telemetry.py:96-131` E.164 regex, HTML strip, 1600-char SMS limit |
| 10 | `GET /api/v1/zones/` | GET | JWT | **LOW** | Data leakage (family scoping enforced via RLS) | Already family-scoped | **RESOLVED** — `zones.py:22` Depends(get_current_user) |
| 11 | `GET /api/v1/devices/` | GET | JWT | **LOW** | Device enumeration within family | Already family-scoped | **RESOLVED** — `devices.py:9` Depends(get_current_user) |
| 12 | `GET /api/v1/devices/{device_id}/notifications` | GET | JWT | **MEDIUM** | IDOR via device_id path param | Already has family join check | **RESOLVED** — `devices.py:43-44` INNER JOIN with family_id |
| 13 | `GET /api/v1/devices/{device_id}/sms` | GET | JWT | **MEDIUM** | IDOR via device_id path param | Already has family join check | **RESOLVED** — `devices.py:74-75` INNER JOIN with family_id |
| 14 | `GET /api/v1/devices/{device_id}/calls` | GET | JWT | **MEDIUM** | IDOR via device_id path param | Already has family join check | **RESOLVED** — `devices.py:105-106` INNER JOIN with family_id |
| 15 | `GET /api/v1/history/replay/{device_id}/{date}` | GET | JWT | **MEDIUM** | IDOR, date injection | Family check in place, date format validation exists | **RESOLVED** — `history.py:28-37` ORM query with family_id, returns 403 |
| 16 | `GET /health` | GET | None | **LOW** | Info leakage (DB error text in response) | Sanitize error messages in health response | **RESOLVED** — `health.py:37-40` logs error, returns "degraded" |
| 17 | `GET /` | GET | None | **LOW** | Version disclosure | Minimal — returns static message | **RESOLVED** — `main.py:178-180` static response |

## 2. WebSocket Handlers

| # | Endpoint | Auth | Risk | Attack Vector | Mitigation | Status |
|---|----------|------|------|---------------|------------|--------|
| 1 | `WS /ws/live/{device_id}` | JWT via query param | **HIGH** | Token in URL (logged by proxies), no message size limit, no input validation on received messages, no device_id format validation | Validate device_id as UUID, enforce 64KB max message size, add connection rate limit. Short-lived ws-token (1h) mitigates URL logging risk. | **RESOLVED** — `main.py:116-120` device_id validation, `main.py:167-173` 64KB limit, `main.py:147-159` family ownership check, `auth.py:370-382` ws-token endpoint |

> **Note on WS JWT in query param**: Browser WebSocket clients cannot set the Authorization header. The mitigation is a short-lived WebSocket-only token (1-hour TTL) obtained via `POST /auth/ws-token`, which exchanges a valid session JWT for a ws-scoped token. This limits the exposure window if the URL is logged by a proxy.

## 3. MQTT Topics

| # | Topic | Direction | Risk | Attack Vector | Mitigation | Status |
|---|-------|-----------|------|---------------|------------|--------|
| 1 | `kin/telemetry/+` (inbound) | Device → Backend | **HIGH** | Spoofed device_id in topic, malformed JSON, oversized payloads, injection via payload fields | Validate device_id segment as UUID, validate payload with Pydantic, check device exists in DB | **RESOLVED** — `mqtt.py:36-43` device_id validation, `mqtt.py:62-73` Pydantic (same LocationUpdate model), `mqtt.py:82-84` device existence check, `mqtt.py:158-162` 64KB max payload |
| 2 | `kin/telemetry/+/status` (LWT) | Broker → Backend | **MEDIUM** | Spoofed offline status | Validate device_id, verify device exists | **RESOLVED** — `mqtt.py:134-136` device_id validation |

## 4. Environment Variables & Secrets

| # | Secret | Current Location | Risk | Mitigation | Status |
|---|--------|-----------------|------|------------|--------|
| 1 | `JWT_SECRET_KEY` | GCP Secret Manager / env var | **HIGH** | Move to GCP Secret Manager, remove default | **RESOLVED** — `secrets_loader.py:45-81` loads from GCP, raises RuntimeError in prod |
| 2 | `PGCRYPTO_KEY` | GCP Secret Manager / env var | **HIGH** | Move to GCP Secret Manager, remove default | **RESOLVED** — `secrets_loader.py:45-81` loads from GCP, raises RuntimeError in prod |
| 3 | `DATABASE_URL` | `.env` / GCP Secret Manager | **MEDIUM** | Already in Secret Manager for prod | **RESOLVED** — managed via GCP |
| 4 | `MQTT_PASSWORD` | GCP Secret Manager / env var | **MEDIUM** | Move to GCP Secret Manager | **RESOLVED** — `secrets_loader.py:23-27` in SECRET_MAP |
| 5 | `MQTT_BROKER` IP | Environment variable only | **LOW** | Non-sensitive but should be env-only | **RESOLVED** — `mqtt.py:20-25` raises RuntimeError in prod |
| 6 | `GOOGLE_ROADS_API_KEY` | Environment variable (stub) | **LOW** | Not currently in use | N/A — unused |
| 7 | `VITE_API_URL` | `.env.production` in frontend | **LOW** | Non-sensitive (public URL) — acceptable | **RESOLVED** — acceptable risk |

## 5. Frontend (React Dashboard)

| # | Surface | Risk | Attack Vector | Mitigation | Status |
|---|---------|------|---------------|------------|--------|
| 1 | `localStorage` token storage | **MEDIUM** | XSS → token theft | CSP headers, HttpOnly cookies (future) | **MITIGATED** — CSP headers block inline scripts, HttpOnly is future work |
| 2 | `VITE_API_URL` in client bundle | **LOW** | URL is public-facing anyway | Acceptable | **RESOLVED** — acceptable risk |
| 3 | No CSP headers on responses | **HIGH** | XSS, clickjacking | Add security headers middleware | **RESOLVED** — `security_headers.py:26-37` all 6 headers |
| 4 | WebSocket token in URL query string | **MEDIUM** | Token leakage in server/proxy logs | Document risk, short-lived tokens mitigate | **RESOLVED** — `auth.py:103-120` ws-token with 1h TTL |

## 6. Flutter Android App

| # | Surface | Risk | Attack Vector | Mitigation | Status |
|---|---------|------|---------------|------------|--------|
| 1 | Credentials in `FlutterSecureStorage` | **LOW** | Already using encrypted storage | Good — no changes needed | **RESOLVED** |
| 2 | API URL from QR pairing flow | **LOW** | Arrives dynamically, not hardcoded | Good — no changes needed | **RESOLVED** |
| 3 | MQTT credentials from pairing response | **LOW** | Stored in secure storage after pairing | Good — verify no plaintext logging | **RESOLVED** |
| 4 | No hardcoded API keys in source | **LOW** | Grep confirms clean | Add CI pre-build check | **RESOLVED** |

## 7. QR Code Input

| # | Surface | Risk | Attack Vector | Mitigation | Status |
|---|---------|------|---------------|------------|--------|
| 1 | QR payload contains `api_url`, `pairing_token`, `mqtt_host`, `mqtt_port` | **MEDIUM** | Malicious QR with fake API URL → phishing | Flutter should validate URL scheme (HTTPS only in prod) | **RESOLVED** — `qr_scanner_screen.dart:36-74` HTTPS enforcement in release, IP hostname rejection, port range validation |

## 8. Error Responses

| # | Surface | Risk | Current State | Mitigation | Status |
|---|---------|------|---------------|------------|--------|
| 1 | Unhandled exceptions | **HIGH** | FastAPI returns full Python traceback on 500 | Add global exception handler | **RESOLVED** — `exception_handlers.py:19-33` returns only `{error, request_id}` |
| 2 | Validation errors (422) | **MEDIUM** | Returns internal field paths | Sanitize 422 response body | **RESOLVED** — `exception_handlers.py:36-55` strips internal paths |
| 3 | Health endpoint | **MEDIUM** | Leaks DB error text: `error: {e}` | Sanitize to generic message | **RESOLVED** — `health.py:37-40` logs only, returns "degraded" |

---

## Summary: All HIGH & MEDIUM Items — RESOLVED

| # | Finding | Resolution |
|---|---------|-----------|
| 1 | Auth endpoints unprotected against brute force | Rate limiting 10/min + IP lockout after 5 failures |
| 2 | Unbounded Pydantic fields | `extra='forbid'`, ge/le bounds on all numeric fields |
| 3 | No HTTP security headers | SecurityHeadersMiddleware with 6 headers including CSP |
| 4 | Hardcoded JWT/PGCRYPTO defaults | GCP Secret Manager loader, RuntimeError in production |
| 5 | No global exception handler | Generic handler returns `{error, request_id}` only |
| 6 | MQTT device_id not validated | Format validation + DB existence check |
| 7 | WebSocket no message size limit | 64KB limit, ws-token endpoint, family ownership check |
| 8 | Comms endpoint accepts unbounded PII strings | E.164 phone validation, HTML sanitization, SMS 1600-char limit |
| 9 | QR code input not validated in Flutter | HTTPS enforcement, IP hostname rejection, port validation |
| 10 | PUBLIC_PREFIXES too broad in middleware | Narrowed to `/api/v1/auth/` only |

---

## Test Coverage

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `tests/test_input_validation.py` | 25 | Coordinate bounds, batch limits, E.164, timestamps, HTML sanitization, extra fields |
| `tests/test_error_sanitization.py` | 5 | 500 body sanitization, 422 path stripping, health degraded response |
| `tests/test_startup.py` | 3 | Production secret requirement, dev default fallback |
| `tests/test_rate_limiting.py` | 7 | slowapi limits, IP lockout lifecycle, Retry-After headers |
| `tests/test_auth_security.py` | 15 | JWT validation, security headers, error sanitization |
| `tests/test_security_audit.py` | 4 | Expired/missing/forged tokens, cross-family + SQL injection |

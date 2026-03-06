# Kin Threat Surface Document

> Generated: 2026-03-05
> Scope: Full application — FastAPI backend, React dashboard, Flutter Android app

---

## 1. HTTP REST Endpoints

| # | Endpoint | Method | Auth | Risk | Attack Vector | Mitigation |
|---|----------|--------|------|------|---------------|------------|
| 1 | `POST /api/v1/auth/register` | POST | None | **HIGH** | Account enumeration, brute force, credential stuffing | Rate limit 10/min/IP, input validation |
| 2 | `POST /api/v1/auth/login` | POST | None | **HIGH** | Brute force, credential stuffing, timing attacks | Rate limit 10/min/IP, lockout after 5 failures |
| 3 | `POST /api/v1/auth/pair-device` | POST | None | **HIGH** | Token brute force, replay attack | Rate limit 10/min/IP, token TTL enforcement |
| 4 | `POST /api/v1/auth/refresh` | POST | None | **MEDIUM** | Token reuse detection bypass | Already has reuse detection; add rate limit |
| 5 | `POST /api/v1/auth/create-pairing-token` | POST | JWT | **MEDIUM** | Token leakage via QR code | Short TTL (10 min), single use |
| 6 | `POST /api/v1/telemetry/ingest` | POST | JWT | **HIGH** | SQL injection via device_id, unbounded coords, replay | Pydantic validation, parameterized queries, timestamp bounds |
| 7 | `POST /api/v1/telemetry/ingest/batch` | POST | JWT | **HIGH** | Gzip bomb, oversized batch, injection | Max batch size, decompression limit, validation |
| 8 | `POST /api/v1/telemetry/heartbeat` | POST | JWT | **MEDIUM** | Spoofed heartbeat, unbounded values | UUID validation on device_id, value bounds |
| 9 | `POST /api/v1/telemetry/comms` | POST | JWT | **HIGH** | PII injection (SMS body, phone numbers), unbounded strings | String length limits, sanitization |
| 10 | `GET /api/v1/zones/` | GET | JWT | **LOW** | Data leakage (family scoping enforced via RLS) | Already family-scoped |
| 11 | `GET /api/v1/devices/` | GET | JWT | **LOW** | Device enumeration within family | Already family-scoped |
| 12 | `GET /api/v1/devices/{device_id}/notifications` | GET | JWT | **MEDIUM** | IDOR via device_id path param | Already has family join check |
| 13 | `GET /api/v1/devices/{device_id}/sms` | GET | JWT | **MEDIUM** | IDOR via device_id path param | Already has family join check |
| 14 | `GET /api/v1/devices/{device_id}/calls` | GET | JWT | **MEDIUM** | IDOR via device_id path param | Already has family join check |
| 15 | `GET /api/v1/history/replay/{device_id}/{date}` | GET | JWT | **MEDIUM** | IDOR, date injection | Family check in place, date format validation exists |
| 16 | `GET /health` | GET | None | **LOW** | Info leakage (DB error text in response) | Sanitize error messages in health response |
| 17 | `GET /` | GET | None | **LOW** | Version disclosure | Minimal — returns static message |

## 2. WebSocket Handlers

| # | Endpoint | Auth | Risk | Attack Vector | Mitigation |
|---|----------|------|------|---------------|------------|
| 1 | `WS /ws/live/{device_id}` | JWT via query param | **HIGH** | Token in URL (logged by proxies), no message size limit, no input validation on received messages, no device_id format validation | Validate device_id as UUID, enforce 64KB max message size, add connection rate limit |

## 3. MQTT Topics

| # | Topic | Direction | Risk | Attack Vector | Mitigation |
|---|-------|-----------|------|---------------|------------|
| 1 | `kin/telemetry/+` (inbound) | Device → Backend | **HIGH** | Spoofed device_id in topic, malformed JSON, oversized payloads, injection via payload fields | Validate device_id segment as UUID, validate payload with Pydantic, check device exists in DB |
| 2 | `kin/telemetry/+/status` (LWT) | Broker → Backend | **MEDIUM** | Spoofed offline status | Validate device_id, verify device exists |

## 4. Environment Variables & Secrets

| # | Secret | Current Location | Risk | Mitigation |
|---|--------|-----------------|------|------------|
| 1 | `JWT_SECRET_KEY` | Hardcoded default in `auth.py` | **HIGH** | Move to GCP Secret Manager, remove default |
| 2 | `PGCRYPTO_KEY` | Hardcoded default in `auth.py` | **HIGH** | Move to GCP Secret Manager, remove default |
| 3 | `DATABASE_URL` | `.env` / GCP Secret Manager | **MEDIUM** | Already in Secret Manager for prod |
| 4 | `MQTT_PASSWORD` | Environment variable | **MEDIUM** | Move to GCP Secret Manager |
| 5 | `MQTT_BROKER` IP | Hardcoded in `mqtt.py` as default | **LOW** | Non-sensitive but should be env-only |
| 6 | `GOOGLE_ROADS_API_KEY` | Environment variable (stub) | **LOW** | Not currently in use |
| 7 | `VITE_API_URL` | `.env.production` in frontend | **LOW** | Non-sensitive (public URL) — acceptable |

## 5. Frontend (React Dashboard)

| # | Surface | Risk | Attack Vector | Mitigation |
|---|---------|------|---------------|------------|
| 1 | `localStorage` token storage | **MEDIUM** | XSS → token theft | CSP headers, HttpOnly cookies (future) |
| 2 | `VITE_API_URL` in client bundle | **LOW** | URL is public-facing anyway | Acceptable |
| 3 | No CSP headers on responses | **HIGH** | XSS, clickjacking | Add security headers middleware |
| 4 | WebSocket token in URL query string | **MEDIUM** | Token leakage in server/proxy logs | Document risk, short-lived tokens mitigate |

## 6. Flutter Android App

| # | Surface | Risk | Attack Vector | Mitigation |
|---|---------|------|---------------|------------|
| 1 | Credentials in `FlutterSecureStorage` | **LOW** | Already using encrypted storage | Good — no changes needed |
| 2 | API URL from QR pairing flow | **LOW** | Arrives dynamically, not hardcoded | Good — no changes needed |
| 3 | MQTT credentials from pairing response | **LOW** | Stored in secure storage after pairing | Good — verify no plaintext logging |
| 4 | No hardcoded API keys in source | **LOW** | Grep confirms clean | Add CI pre-build check |

## 7. QR Code Input

| # | Surface | Risk | Attack Vector | Mitigation |
|---|---------|------|---------------|------------|
| 1 | QR payload contains `api_url`, `pairing_token`, `mqtt_host`, `mqtt_port` | **MEDIUM** | Malicious QR with fake API URL → phishing | Flutter should validate URL scheme (HTTPS only in prod) |

## 8. Error Responses

| # | Surface | Risk | Current State | Mitigation |
|---|---------|------|---------------|------------|
| 1 | Unhandled exceptions | **HIGH** | FastAPI returns full Python traceback on 500 | Add global exception handler |
| 2 | Validation errors (422) | **MEDIUM** | Returns internal field paths | Sanitize 422 response body |
| 3 | Health endpoint | **MEDIUM** | Leaks DB error text: `error: {e}` | Sanitize to generic message |

---

## Summary: HIGH Risk Items Requiring Mitigation

1. **Auth endpoints unprotected against brute force** → Rate limiting (Step 3)
2. **Unbounded Pydantic fields** → Input validation (Step 1)
3. **No HTTP security headers** → Headers middleware (Step 4)
4. **Hardcoded JWT/PGCRYPTO defaults** → Secret management (Step 5)
5. **No global exception handler** → Error sanitization (Step 7)
6. **MQTT device_id not validated** → MQTT sanitization (Step 6)
7. **WebSocket no message size limit** → WS hardening (Step 6)
8. **Comms endpoint accepts unbounded PII strings** → Pydantic validation (Step 1)

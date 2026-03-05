# Reverse-Secure: Authentication Hardening Plan

When the dashboard login flow is implemented, reverse these temporary public-access workarounds. This document maps every bypassed auth point to its intended secure state, including the database schema dependencies.

## Current State (March 2026): "Auth Bypass Mode"

All dashboard-facing endpoints are public because the frontend has no login/JWT flow yet.

| Bypass | File | What was changed | Why |
|--------|------|------------------|-----|
| `PUBLIC_PREFIXES` expanded | `app/core/security.py:21` | Added `/api/v1/zones`, `/api/v1/location`, `/api/v1/devices` | Dashboard calls these without JWT |
| Zones `Depends(get_current_user)` removed | `app/api/v1/endpoints/zones.py:22` | Removed user dependency, no family_id filter | No user context available |
| Pairing token no auth | `app/api/v1/endpoints/auth.py:190` | `create-pairing-token` uses first available family | No logged-in parent to associate token to |
| `PairingToken.created_by` nullable | `app/models/location.py:89` | Made FK nullable | Token creation without authenticated user |

---

## Phase 1: Implement Frontend Login (Prerequisites)

Before reversing ANY of the above, implement:

1. **Login page** in React dashboard (`frontend/src/pages/Login.jsx`)
   - Email/password form → `POST /api/v1/auth/login`
   - Store JWT in `localStorage` or `httpOnly` cookie
2. **Auth context** (`frontend/src/context/AuthContext.jsx`)
   - Provide `user`, `token`, `familyId` to all components
   - Auto-refresh access token using refresh token
3. **Axios/fetch interceptor** — attach `Authorization: Bearer <token>` to every API call
4. **Protected route wrapper** — redirect to login if no token

### Database Schema Required

These tables MUST exist before login works:

| Table | Key Columns | Purpose |
|-------|-------------|---------|
| `users` | `id`, `email`, `hashed_password`, `role` | User accounts |
| `families` | `id`, `name` | Family groups |
| `family_memberships` | `family_id`, `user_id`, `role` | User ↔ Family join |
| `refresh_tokens` | `jti`, `user_id`, `expires_at`, `revoked_at` | Token rotation + reuse detection |

**Migration check**: Run `SELECT table_name FROM information_schema.tables WHERE table_schema='public'` — all four must exist.

---

## Phase 2: Restore Endpoint Authentication

### 2a. Shrink `PUBLIC_PREFIXES`

```python
# app/core/security.py — RESTORE TO:
PUBLIC_PREFIXES = ("/api/v1/auth/", "/auth/")
```

Remove `/api/v1/zones`, `/api/v1/location`, `/api/v1/devices` from the tuple.

### 2b. Restore `Depends(get_current_user)` on Zones

```python
# app/api/v1/endpoints/zones.py — RESTORE TO:
@router.get("/")
async def list_zones(user: dict = Depends(get_current_user)):
    family_id = user.get("family_id")
    # ... filter by family_id ...
```

### 2c. Restore Family-Scoped Pairing Token

```python
# app/api/v1/endpoints/auth.py — RESTORE TO:
@router.post("/create-pairing-token")
async def create_pairing_token(user: dict = Depends(get_current_user)):
    family_id = user.get("family_id")
    pt = PairingToken(
        token=token_value,
        family_id=family_id,            # From JWT, not first-available
        created_by=user.get("user_id"), # Non-null, from JWT
        ...
    )
```

### 2d. Make `created_by` NOT NULL Again (Optional)

```sql
-- Only after all pairing tokens are created by authenticated users:
UPDATE pairing_tokens SET created_by = (SELECT id FROM users LIMIT 1) WHERE created_by IS NULL;
ALTER TABLE pairing_tokens ALTER COLUMN created_by SET NOT NULL;
```

⚠️ **Run the UPDATE first** or existing NULL rows will violate the constraint.

---

## Phase 3: Add Row-Level Security

After endpoints require auth, add family-scoped data filtering:

| Endpoint | Filter To Add |
|----------|--------------|
| `GET /zones` | `WHERE family_id = :jwt_family_id` |
| `GET /location/history` | `WHERE family_id = :jwt_family_id` |
| `GET /devices` | `WHERE family_id = :jwt_family_id` |
| `POST /zones` | Set `family_id = :jwt_family_id` on insert |
| `WebSocket /ws/live/{device_id}` | Verify device belongs to JWT family |

### Database RLS (Postgres-Level)

The `kin_app` role and `SET LOCAL app.current_family_id` pattern is already defined in `app/core/auth.py`. Activate it:

```sql
ALTER TABLE zones ENABLE ROW LEVEL SECURITY;
CREATE POLICY zones_family ON zones
  USING (family_id = current_setting('app.current_family_id')::uuid);
```

Repeat for `devices`, `pairing_tokens`, `locations_raw`, `trips`, `device_status`.

---

## Verification Checklist

After hardening, verify each endpoint returns correct status:

| Test | Expected |
|------|----------|
| `GET /zones` (no token) | 401 |
| `GET /zones` (valid token) | 200 + family-scoped data |
| `GET /zones` (wrong family token) | 200 + empty array (RLS) or 403 |
| `POST /create-pairing-token` (no token) | 401 |
| `POST /pair-device` (valid pairing token) | 200 |
| `GET /health` (no token) | 200 (always public) |

---

## Quick Reference: Files to Touch

1. `frontend/src/pages/Login.jsx` — NEW
2. `frontend/src/context/AuthContext.jsx` — NEW
3. `frontend/src/App.jsx` — wrap routes in AuthProvider
4. `backend/app/core/security.py` — shrink PUBLIC_PREFIXES
5. `backend/app/api/v1/endpoints/zones.py` — restore Depends
6. `backend/app/api/v1/endpoints/auth.py` — restore user scope
7. `backend/app/models/location.py` — optional NOT NULL restore

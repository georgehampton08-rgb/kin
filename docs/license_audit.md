# License Audit Report

> **Status: COMPLETE** — All BLOCKED packages have been replaced. Zero commercial licenses remain in any active code path. Verified 2026-03-06.

| Package Name | Current License | Commercial Use Restriction | Status / Proposed Replacement |
| :--- | :--- | :--- | :--- |
| **Flutter (pubspec.yaml)** | | | |
| `flutter` | BSD-3-Clause | NO | ✅ CLEAR |
| `cupertino_icons` | MIT | NO | ✅ CLEAR |
| ~~`flutter_background_geolocation`~~ | Commercial / Proprietary | YES | ✅ **REPLACED** → `geolocator` + `flutter_foreground_task` + `battery_plus` |
| `geolocator` | BSD-3-Clause | NO | ✅ CLEAR |
| `flutter_foreground_task` | MIT | NO | ✅ CLEAR |
| `battery_plus` | BSD-3-Clause | NO | ✅ CLEAR |
| `provider` | MIT | NO | N/A (CLEAR) |
| `app_settings` | MIT | NO | N/A (CLEAR) |
| `permission_handler` | MIT | NO | N/A (CLEAR) |
| `sqflite` | MIT / BSD | NO | N/A (CLEAR) |
| `path` | BSD-3-Clause | NO | N/A (CLEAR) |
| `mobile_scanner` | MIT | NO | N/A (CLEAR) |
| `flutter_secure_storage` | MIT | NO | N/A (CLEAR) |
| `dio` | MIT | NO | N/A (CLEAR) |
| `device_info_plus` | MIT | NO | N/A (CLEAR) |
| `http` | BSD-3-Clause | NO | N/A (CLEAR) |
| `shared_preferences` | BSD-3-Clause | NO | N/A (CLEAR) |
| `notification_listener_service` | MIT | NO | N/A (CLEAR) |
| `flutter_sms_inbox` | MIT | NO | N/A (CLEAR) |
| `call_log` | MIT | NO | N/A (CLEAR) |
| `flutter_test` | BSD-3-Clause | NO | N/A (CLEAR) |
| `flutter_lints` | BSD-3-Clause | NO | N/A (CLEAR) |
| `sqflite_common_ffi` | MIT | NO | N/A (CLEAR) |
| **FastAPI (requirements.txt)** | | | |
| `fastapi` | MIT | NO | N/A (CLEAR) |
| `uvicorn` | BSD-3-Clause | NO | N/A (CLEAR) |
| `pydantic` | MIT | NO | N/A (CLEAR) |
| `paho-mqtt` | EPL 2.0 / EDL 1.0 (Dual License) | CONDITIONAL | N/A (REVIEW) - Permitted for internal use. |
| `aiohttp` | Apache 2.0 | NO | N/A (CLEAR) |
| `websockets` | BSD-3-Clause | NO | N/A (CLEAR) |
| `geoalchemy2` | MIT | NO | N/A (CLEAR) |
| `asyncpg` | Apache 2.0 | NO | N/A (CLEAR) |
| `sqlalchemy[asyncio]` | MIT | NO | N/A (CLEAR) |
| `python-multipart` | Apache 2.0 | NO | N/A (CLEAR) |
| `python-jose[cryptography]` | MIT | NO | N/A (CLEAR) |
| `passlib[bcrypt]` | BSD-3-Clause | NO | N/A (CLEAR) |
| `bcrypt` | Apache 2.0 | NO | N/A (CLEAR) |
| `apscheduler` | MIT | NO | N/A (CLEAR) |
| `slowapi` | MIT | NO | N/A (CLEAR) |
| `limits` | MIT | NO | N/A (CLEAR) |
| `google-cloud-secret-manager` | Apache 2.0 | NO | N/A (CLEAR) |
| **Infrastructure (docker-compose)** | | | |
| `postgis/postgis:15-3.4` | PostgreSQL License / GPL (PostGIS) | CONDITIONAL | N/A (REVIEW) - Network boundary isolation permits use. |
| `emqx/emqx:5.3.0` | Apache 2.0 (Open-Source Edition) | NO | N/A (CLEAR) |
| `node:20-slim` | MIT / Various | NO | N/A (CLEAR) |
| **React (package.json)** | | | |
| `@turf/turf` | MIT | NO | N/A (CLEAR) |
| `date-fns` | MIT | NO | N/A (CLEAR) |
| `maplibre-gl` | BSD-3-Clause | NO | N/A (CLEAR) |
| `qrcode.react` | ISC | NO | N/A (CLEAR) |
| `react` | MIT | NO | N/A (CLEAR) |
| `react-dom` | MIT | NO | N/A (CLEAR) |
| `react-hot-toast` | MIT | NO | N/A (CLEAR) |
| `@vitejs/plugin-react` | MIT | NO | N/A (CLEAR) |
| `vite` | MIT | NO | N/A (CLEAR) |

## Appendix: Frontend License Summary (`npx license-checker --summary`)

```text
├─ MIT: 201
├─ ISC: 26
├─ BSD-3-Clause: 8
├─ BSD-2-Clause: 2
├─ Unlicense: 2
├─ Custom: https://github.com/tmcw/jsonlint: 1
├─ (MIT OR Apache-2.0): 1
├─ Custom: https://github.com/bjornharrtell/jsts: 1
├─ BSD: 1
├─ Apache-2.0: 1
├─ CC-BY-4.0: 1
├─ Custom: https://travis-ci.org/bjornharrtell/jsts.svg: 1
├─ BSD*: 1
└─ 0BSD: 1
```

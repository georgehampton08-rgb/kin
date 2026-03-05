# Kin GCP Infrastructure Plan

## Overview

This document maps the existing Kin development stack to its GCP production equivalents, defines the environment variable and secrets strategy, and outlines the CI/CD pipeline that achieves zero-downtime deployments from a `git push` to `main`.

---

## 1. Service Mapping — Local → GCP

| Local Service | Container Name | GCP Equivalent | Notes |
|---|---|---|---|
| FastAPI / Uvicorn | `kin-api` | **Cloud Run** (v2) | `--min-instances=1` required — APScheduler runs in-process and dies on scale-to-zero |
| PostgreSQL 15 + PostGIS 3 | `kin-db` | **Cloud SQL for PostgreSQL 15** | PostGIS enabled; Cloud SQL Auth Proxy v2 for connections |
| EMQX 5.3.0 MQTT Broker | `kin-broker` | **GCE VM** (`e2-micro`) running EMQX via Docker | Cloud Run cannot expose persistent TCP port 1883; a VM is the simplest solution. Alternative: GCP Pub/Sub, but that requires rewriting all `paho-mqtt` code |
| React / Vite Dashboard | `kin-dashboard` | **Firebase Hosting** (prod build) OR **Cloud Run** (second service) | Firebase Hosting is cheapest for a static SPA; Cloud Run if SSR is needed later |

### Why not Pub/Sub for MQTT?

The current backend uses `paho-mqtt` with topic-based routing (`kin/telemetry/+`), Last Will & Testament (LWT), and direct subscription in a background thread. Migrating to Pub/Sub would require:

1. Replacing `paho-mqtt` with `google-cloud-pubsub`
2. Rewriting the LWT mechanism (Pub/Sub has no native LWT)
3. Changing the Flutter client from MQTT to HTTP-push or a Pub/Sub client

**Recommendation**: Keep EMQX on a `e2-micro` GCE VM (free-tier eligible, ~$0/mo or ~$6/mo if not). Migrate to Pub/Sub in a later phase if needed.

---

## 2. Environment Variable Strategy

### Tiers

| Variable | Local (`.env`) | Cloud Run Env Var | GCP Secret Manager | Why |
|---|---|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://kinuser:kinpass@kin-db:5432/kindb` | ❌ | ✅ `kin-db-url` | Contains password |
| `MQTT_BROKER` | `kin-broker` | ✅ (hostname of GCE VM) | ❌ | Not secret |
| `MQTT_PORT` | `1883` | ✅ `1883` | ❌ | Not secret |
| `MQTT_PASSWORD` | _(empty for local)_ | ❌ | ✅ `kin-mqtt-password` | Secret |
| `JWT_SECRET` | `dev-jwt-secret-change-me` | ❌ | ✅ `kin-jwt-secret` | Secret |
| `ENCRYPTION_KEY` (pgcrypto) | `dev-encryption-key` | ❌ | ✅ `kin-encryption-key` | Secret |
| `ENVIRONMENT` | `development` | ✅ `production` | ❌ | Feature flags |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | ✅ dashboard URL | ❌ | CORS |
| `APP_VERSION` | `local` | ✅ Git SHA or tag | ❌ | Health check |

### Secret Access Pattern

Cloud Run service will mount secrets as environment variables via:

```yaml
# In Cloud Run service spec
env:
  - name: DATABASE_URL
    valueFrom:
      secretKeyRef:
        name: kin-db-url
        version: latest
```

### `.env.example` (committed to source control)

```env
# === Database ===
DATABASE_URL=postgresql+asyncpg://kinuser:kinpass@kin-db:5432/kindb

# === MQTT Broker ===
MQTT_BROKER=kin-broker
MQTT_PORT=1883
MQTT_PASSWORD=

# === Security ===
JWT_SECRET=dev-jwt-secret-change-me
ENCRYPTION_KEY=dev-encryption-key

# === App Config ===
ENVIRONMENT=development
ALLOWED_ORIGINS=http://localhost:3000
APP_VERSION=local
```

---

## 3. CI/CD Pipeline (Cloud Build)

### Trigger

- **Source**: Push to `main` branch on GitHub
- **Config**: `cloudbuild.yaml` at repo root

### Pipeline Stages

```mermaid
graph LR
    A["1. pytest"] --> B["2. Docker Build<br/>+ Push to<br/>Artifact Registry"]
    B --> C["3. Alembic Migrate<br/>via SQL Proxy"]
    C --> D["4. Deploy to CR<br/>(--no-traffic)"]
    D --> E["5. Health Check<br/>Canary"]
    E --> F["6. Promote to<br/>100% Traffic"]
```

| Stage | Tool | Detail |
|---|---|---|
| **1. Test** | `pytest` | Runs inside a Python 3.12 container. Fail → abort pipeline |
| **2. Build & Push** | `docker build` | Multi-stage Dockerfile → `us-central1-docker.pkg.dev/$PROJECT_ID/kin/kin-api:$SHORT_SHA` |
| **3. Migrate** | `cloud-sql-proxy` + `alembic upgrade head` | Runs in a sidecar step. Advisory lock (`pg_advisory_xact_lock`) prevents concurrent migration from multiple instances |
| **4. Deploy (canary)** | `gcloud run deploy --no-traffic` | Deploys new revision but sends 0% traffic |
| **5. Health Check** | `curl /health` on new revision URL | Must return `{"status":"ok","db":"connected","broker":"connected"}` |
| **6. Promote** | `gcloud run services update-traffic --to-latest` | Routes 100% traffic to new revision |

### Alembic Migration Safety

> [!CAUTION]
> Two Cloud Run instances running `alembic upgrade head` simultaneously can corrupt the migration history. The pipeline uses a **Postgres advisory lock** to serialize migrations:

```python
# In alembic/env.py — run_migrations_online()
connection.execute(text("SELECT pg_advisory_xact_lock(1573946)"))
```

This acquires an exclusive transaction-level lock. If another process is already running migrations, this will block until it completes — preventing duplicate DDL.

---

## 4. Docker Strategy

### Multi-Stage Dockerfile (FastAPI)

```
Stage 1: python:3.12-slim (builder)
├── Install system deps (libpq-dev, gcc) — needed for asyncpg/psycopg2 compile
├── pip install --no-cache-dir -r requirements.txt into /opt/venv
└── Copy application code

Stage 2: python:3.12-slim (runtime)
├── Copy /opt/venv from builder
├── Copy app/ code only
├── No .env, no test files, no dev deps
├── USER nonroot
└── CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

Target: **< 200 MB** final image.

### docker-compose.yml (Local Dev)

```yaml
services:
  kin-db:       # PostGIS 15, named volume, healthcheck
  kin-broker:   # EMQX 5.3.0, ports 1883/18083
  kin-api:      # FastAPI, depends_on: kin-db (healthy), kin-broker
  kin-dashboard: # Vite dev server, port 3000

networks:
  kin-net:
    driver: bridge

volumes:
  kin-pgdata:
```

Key constraints:

- `kin-db` healthcheck: `pg_isready -U kinuser -d kindb`
- `kin-api` depends_on `kin-db` with `condition: service_healthy`
- All services on shared `kin-net` network
- Database uses named volume `kin-pgdata` to survive restarts

---

## 5. Health Endpoint

### `GET /health`

```json
{
  "status": "ok",
  "db": "connected",
  "broker": "connected",
  "version": "2.0.0"
}
```

Implementation:

1. **DB check**: Run `SELECT 1` via `AsyncSessionLocal`. If exception → `"db": "error: <msg>"`
2. **Broker check**: Verify `mqtt_listener.client.is_connected()`. If false → `"broker": "disconnected"`
3. **Version**: Read from `app.version` or `APP_VERSION` env var
4. **Status**: If both db and broker are connected → `"ok"`, else → `"degraded"`

Cloud Run startup probe will hit this endpoint. The CI/CD pipeline health-check stage also depends on it.

---

## 6. GCP Cloud Run Configuration

### Key Flags

| Flag | Value | Rationale |
|---|---|---|
| `--min-instances` | `1` | APScheduler requires always-warm instance (~$7/mo) |
| `--max-instances` | `5` | Safety cap for a family tracking app |
| `--port` | `8080` | Cloud Run expects 8080 |
| `--cpu` | `1` | Sufficient for ASGI + MQTT client |
| `--memory` | `512Mi` | PostGIS queries + MQTT event processing |
| `--concurrency` | `80` | Default, good for async |
| `--allow-unauthenticated` | ✅ | Public API (JWT handles auth) |

### Cloud SQL Auth Proxy Connection

For `asyncpg` with Cloud SQL Auth Proxy v2:

```
DATABASE_URL=postgresql+asyncpg://kinuser:PASSWORD@/kindb?host=/cloudsql/PROJECT:REGION:INSTANCE
```

The proxy creates a Unix socket at `/cloudsql/PROJECT:REGION:INSTANCE`. SQLAlchemy connects via the `host` query parameter.

---

## 7. Terraform — Secret Manager Provisioning

`secrets.tf` will provision four secrets:

- `kin-db-url`
- `kin-mqtt-password`
- `kin-jwt-secret`
- `kin-encryption-key`

Each secret is created empty. Values must be set manually via `gcloud secrets versions add` **after** `terraform apply` — this ensures no secret value ever appears in Terraform state or source control.

---

## 8. GCP Artifact Registry

> [!IMPORTANT]
> Google Container Registry (`gcr.io`) is deprecated. All images will use **Artifact Registry**:
> `us-central1-docker.pkg.dev/$PROJECT_ID/kin/kin-api:$TAG`

The Cloud Build pipeline creates the repository if it doesn't exist.

---

## Proposed Changes

### Backend (`backend/`)

#### [NEW] [Dockerfile](file:///c:/Users/georg/kin/backend/Dockerfile)

Multi-stage Docker image. Builder installs deps, runtime is lean `python:3.12-slim` (< 200 MB). Excludes `.env`, test files, dev dependencies.

#### [MODIFY] [main.py](file:///c:/Users/georg/kin/backend/app/main.py)

- Import and register the new `/health` endpoint router
- Make `ALLOWED_ORIGINS` configurable via env var

#### [MODIFY] [session.py](file:///c:/Users/georg/kin/backend/app/db/session.py)

- Already reads `DATABASE_URL` from env — no change needed

#### [MODIFY] [mqtt.py](file:///c:/Users/georg/kin/backend/app/core/mqtt.py)

- Read `MQTT_BROKER`, `MQTT_PORT`, `MQTT_PASSWORD` from env vars instead of hardcoded `localhost:1883`

#### [NEW] [health.py](file:///c:/Users/georg/kin/backend/app/api/v1/endpoints/health.py)

- `GET /health` endpoint with DB ping, MQTT connectivity check, version

#### [MODIFY] [api.py](file:///c:/Users/georg/kin/backend/app/api/v1/api.py)

- Register `health.router`

#### [MODIFY] [requirements.txt](file:///c:/Users/georg/kin/backend/requirements.txt)

- Split into `requirements.txt` (prod only) and `requirements-dev.txt` (includes pytest, httpx)

---

### Project Root

#### [NEW] [docker-compose.yml](file:///c:/Users/georg/kin/docker-compose.yml)

4-service local dev stack: `kin-api`, `kin-db`, `kin-broker`, `kin-dashboard`.

#### [NEW] [.env.example](file:///c:/Users/georg/kin/.env.example)

Template for all environment variables.

#### [NEW] [cloudbuild.yaml](file:///c:/Users/georg/kin/cloudbuild.yaml)

6-stage CI/CD: test → build → push → migrate → canary deploy → promote.

#### [NEW] [secrets.tf](file:///c:/Users/georg/kin/infra/secrets.tf)

Terraform provisioning for GCP Secret Manager secrets.

#### [NEW] [.dockerignore](file:///c:/Users/georg/kin/backend/.dockerignore)

Excludes venv, **pycache**, .env, tests, git from Docker context.

---

## 9. Step-by-Step GCP Setup Guide

The deployment is split into **three phases** with explicit **⏸️ PAUSE** gates. At each pause, the agent stops and waits for you to complete manual GCP console/CLI work, then you say "continue" and the agent resumes.

### Prerequisites

Before starting, make sure you have:

- [ ] A GCP project (e.g., `kin-tracker`) — note the **Project ID**
- [ ] `gcloud` CLI installed and authenticated (`gcloud auth login`)
- [ ] Docker Desktop installed and running
- [ ] Node.js 18+ and npm installed
- [ ] Firebase CLI installed (`npm install -g firebase-tools`)

---

### Phase A — GCP Foundation (YOU do this in the GCP Console / CLI)

> **⏸️ PAUSE A — The agent will stop here and ask you to complete these steps.**

Run every command from a fresh PowerShell terminal.

#### A1. Set your project

```powershell
gcloud config set project YOUR_PROJECT_ID
```

#### A2. Enable required APIs

```powershell
gcloud services enable `
  cloudbuild.googleapis.com `
  run.googleapis.com `
  sqladmin.googleapis.com `
  secretmanager.googleapis.com `
  artifactregistry.googleapis.com `
  compute.googleapis.com `
  firebase.googleapis.com
```

#### A3. Create Artifact Registry repository

```powershell
gcloud artifacts repositories create kin `
  --repository-format=docker `
  --location=us-central1 `
  --description="Kin Docker images"
```

#### A4. Create Cloud SQL instance (PostgreSQL 15 + PostGIS)

```powershell
# Create the instance (~5–10 min)
gcloud sql instances create kin-db `
  --database-version=POSTGRES_15 `
  --tier=db-f1-micro `
  --region=us-central1 `
  --storage-size=10GB `
  --storage-auto-increase

# Set the postgres password
gcloud sql users set-password postgres `
  --instance=kin-db `
  --password=YOUR_STRONG_DB_PASSWORD

# Create the app database user
gcloud sql users create kinuser `
  --instance=kin-db `
  --password=YOUR_STRONG_KINUSER_PASSWORD

# Create the database
gcloud sql databases create kindb --instance=kin-db
```

Then connect and enable PostGIS:

```powershell
gcloud sql connect kin-db --user=postgres
# Inside psql:
#   CREATE EXTENSION IF NOT EXISTS postgis;
#   CREATE EXTENSION IF NOT EXISTS pgcrypto;
#   \q
```

#### A5. Create GCP Secret Manager entries

```powershell
# Create the 4 secrets (empty shells)
echo "postgresql+asyncpg://kinuser:YOUR_KINUSER_PASSWORD@/kindb?host=/cloudsql/YOUR_PROJECT_ID:us-central1:kin-db" | `
  gcloud secrets create kin-db-url --data-file=-

echo "YOUR_MQTT_PASSWORD" | `
  gcloud secrets create kin-mqtt-password --data-file=-

# Generate a strong random secret for JWT
python -c "import secrets; print(secrets.token_urlsafe(32))" | `
  gcloud secrets create kin-jwt-secret --data-file=-

# Generate a strong random key for pgcrypto encryption
python -c "import secrets; print(secrets.token_urlsafe(32))" | `
  gcloud secrets create kin-encryption-key --data-file=-
```

#### A6. Grant Cloud Run access to secrets

```powershell
$PROJECT_NUMBER = (gcloud projects describe YOUR_PROJECT_ID --format="value(projectNumber)")

# Cloud Run service account needs Secret Accessor
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID `
  --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" `
  --role="roles/secretmanager.secretAccessor"

# Cloud Build service account needs Cloud Run Admin + additional roles
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID `
  --member="serviceAccount:$PROJECT_NUMBER@cloudbuild.gserviceaccount.com" `
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID `
  --member="serviceAccount:$PROJECT_NUMBER@cloudbuild.gserviceaccount.com" `
  --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID `
  --member="serviceAccount:$PROJECT_NUMBER@cloudbuild.gserviceaccount.com" `
  --role="roles/cloudsql.client"
```

#### A7. (Optional) Create EMQX VM

```powershell
gcloud compute instances create-with-container kin-broker `
  --zone=us-central1-a `
  --machine-type=e2-micro `
  --container-image=emqx/emqx:5.3.0 `
  --tags=mqtt-server

# Open MQTT port
gcloud compute firewall-rules create allow-mqtt `
  --allow=tcp:1883 `
  --target-tags=mqtt-server `
  --source-ranges=0.0.0.0/0
```

Note the **external IP** of the VM — you'll need it for `MQTT_BROKER` in Cloud Run.

**✅ When all A-steps are done, tell the agent: "Phase A complete, my project ID is `___`"**

---

### Phase B — Code Deployment (THE AGENT does this)

After Phase A is confirmed, the agent will:

1. Write all the code files (docker-compose, Dockerfile, health endpoint, cloudbuild.yaml)
2. Verify local dev via `docker-compose up`
3. Push to GitHub
4. Trigger the first Cloud Build manually:

```powershell
cd c:\Users\georg\kin
gcloud builds submit --config=cloudbuild.yaml --substitutions=SHORT_SHA=initial
```

The agent will monitor the build and verify `/health` responds on the Cloud Run URL.

> **⏸️ PAUSE B — The agent will stop after the initial deploy succeeds and give you the Cloud Run URL to verify.**

**✅ When you've verified the Cloud Run URL returns a healthy response, tell the agent: "Phase B verified"**

---

### Phase C — Firebase Hosting for Dashboard (YOU + AGENT together)

#### C1. Initialize Firebase (YOU)

```powershell
cd c:\Users\georg\kin\frontend
firebase login              # if not already logged in
firebase init hosting        # Select your GCP project when prompted
```

When prompted:

- **Public directory**: `dist`
- **Single-page app**: `Yes`
- **GitHub auto-deploy**: `No` (we'll use Cloud Build instead)

#### C2. Configure build output (AGENT will do this)

The agent will add a `firebase.json` with rewrite rules so React Router works:

```json
{
  "hosting": {
    "public": "dist",
    "ignore": ["firebase.json", "**/.*", "**/node_modules/**"],
    "rewrites": [{ "source": "**", "destination": "/index.html" }],
    "headers": [
      {
        "source": "**/*.@(js|css|map)",
        "headers": [{ "key": "Cache-Control", "value": "public, max-age=31536000, immutable" }]
      }
    ]
  }
}
```

#### C3. Update Vite config for API proxy (AGENT will do this)

The agent will update `vite.config.js` to set the `VITE_API_URL` environment variable so the frontend knows the Cloud Run backend URL in production.

#### C4. Build and deploy (YOU)

```powershell
cd c:\Users\georg\kin\frontend
npm run build                # Output goes to dist/
firebase deploy --only hosting
```

Firebase will print the hosting URL (e.g., `https://YOUR_PROJECT.web.app`).

#### C5. Update CORS (AGENT will do this)

Once you share the Firebase Hosting URL, the agent will update `ALLOWED_ORIGINS` on the Cloud Run service to include it.

> **⏸️ PAUSE C — The agent will stop and ask you to share the Firebase Hosting URL so it can update CORS.**

**✅ When the dashboard loads at the Firebase URL and shows the map, tell the agent: "Phase C complete"**

---

### Phase D — Connect Cloud Build to GitHub (YOU)

This is a one-time setup so `git push` auto-triggers the CI/CD pipeline.

```powershell
# In GCP Console:
# 1. Go to Cloud Build → Triggers
# 2. Click "Connect Repository"
# 3. Select GitHub → authorize → pick georgehampton08-rgb/kin
# 4. Create Trigger:
#    - Name: deploy-on-push
#    - Event: Push to branch
#    - Branch: ^main$
#    - Config: cloudbuild.yaml
#    - Substitution: _REGION=us-central1
```

After this, every `git push origin main` will run the full CI/CD pipeline automatically.

---

## Estimated Monthly Costs

| Service | Tier | Est. Cost |
|---|---|---|
| Cloud Run (1 min instance) | 1 vCPU, 512 MB | ~$7/mo |
| Cloud SQL (db-f1-micro) | Shared CPU, 614 MB RAM | ~$8/mo |
| GCE VM (e2-micro, EMQX) | 0.25 vCPU, 1 GB | ~$0–6/mo (free tier) |
| Artifact Registry | < 1 GB stored | ~$0.10/mo |
| Secret Manager | 4 secrets | ~$0/mo |
| Firebase Hosting | Free tier (10 GB transfer) | $0/mo |
| **Total** | | **~$15–21/mo** |

---

## Verification Plan

### Automated Tests (Local)

1. **Docker Compose Up**

```bash
cd c:\Users\georg\kin
docker-compose up --build -d
# Wait for all services to be healthy (~30 seconds)
docker-compose ps   # All 4 should show "Up" / "healthy"
```

1. **Health Check**

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok","db":"connected","broker":"connected","version":"2.0.0"}
```

1. **POST Telemetry Test**

```bash
curl -X POST http://localhost:8000/api/v1/telemetry/ingest \
  -H "Content-Type: application/json" \
  -d '{"device_id":"test-001","latitude":41.8781,"longitude":-87.6298,"speed":2.5,"battery_level":85}'
# Expected: 200 OK, data written to PostGIS
```

1. **Secret Audit**

```bash
cd c:\Users\georg\kin
git grep -r "password\|secret\|key" --include="*.py" --include="*.yml"
# Expected: Zero results outside .env.example and this plan doc
```

### Manual Verification

1. Open `http://localhost:3000` → Dashboard loads in browser
2. Open `http://localhost:18083` → EMQX Web Console accessible
3. `docker-compose down && docker-compose up -d` → Named volume preserves DB data

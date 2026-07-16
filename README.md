# Resume Builder

AI-powered resume tailoring: upload a master resume, paste a job description, and get an ATS-optimized rewrite that stays grounded in your real experience (no invented facts).

The app runs as a single FastAPI service with a NiceGUI frontend, LangGraph agents, PostgreSQL, Redis, and S3-compatible storage. Runs after the free trial are paywalled ($3.99 unlock via Stripe or crypto).

---

## Table of contents

- [Prerequisites](#prerequisites)
- [Quick start (Docker — recommended)](#quick-start-docker--recommended)
- [Configure environment variables](#configure-environment-variables)
- [Create the MinIO bucket](#create-the-minio-bucket)
- [Use the app](#use-the-app)
- [LLM providers](#llm-providers)
- [Payment setup (optional)](#payment-setup-optional)
- [Native Python setup (without Docker)](#native-python-setup-without-docker)
- [Database migrations](#database-migrations)
- [Run tests](#run-tests)
- [Project layout](#project-layout)
- [Branch workflow](#branch-workflow)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

**For Docker (recommended):**

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) or Docker Engine + Compose v2
- Git

**For native Python development:**

- Python **3.12+**
- PostgreSQL 16, Redis 7, and MinIO (or AWS S3)
- System libraries for PDF export (WeasyPrint): on macOS `brew install pango`; on Debian/Ubuntu `libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info`

---

## Quick start (Docker — recommended)

### 1. Clone the repository

```bash
git clone https://github.com/thatdudealso/resume-builder.git
cd resume-builder
```

### 2. Create your environment file

```bash
cp .env.example .env
```

Edit `.env` and add at least one LLM API key (see [LLM providers](#llm-providers)). For a first smoke test you can leave keys empty — the agent falls back to mock responses, but tailoring quality will not be useful until a provider is configured.

### 3. Start all services

```bash
docker compose up --build
```

This starts:

| Service    | Purpose                          | Host port |
|------------|----------------------------------|-----------|
| `postgres` | Application database             | 5432      |
| `redis`    | Rate limiting / caching          | 6379      |
| `minio`    | S3-compatible file storage       | 9000, 9001 |
| `migrate`  | Runs Alembic migrations (once)   | —         |
| `web`      | FastAPI + NiceGUI app            | 8000      |

Migrations run automatically via the `migrate` service before `web` starts. Migrations are **never** auto-run inside the web process itself.

### 4. Create the MinIO bucket

Resume uploads and exports require an S3 bucket. MinIO does not create it automatically.

**Option A — MinIO Console (easiest)**

1. Open http://localhost:9001
2. Login: `minioadmin` / `minioadmin`
3. Create a bucket named `resume-builder` (must match `S3_BUCKET` in `.env`)

**Option B — MinIO client**

```bash
docker compose exec minio mc alias set local http://localhost:9000 minioadmin minioadmin
docker compose exec minio mc mb local/resume-builder --ignore-existing
```

### 5. Open the app

| URL | Description |
|-----|-------------|
| http://localhost:8000/app | Main workflow (upload → tailor → paywall → export) |
| http://localhost:8000/app/dashboard | Advanced dashboard (provider picker, variants, section editor) |
| http://localhost:8000/api/v1 | REST API (OpenAPI at `/docs`) |
| http://localhost:8000/health | Health check (`db` + `redis` status) |

No login is required. The UI creates a private device workspace using a browser cookie (`rb_device_fingerprint`) and sends `X-Device-Fingerprint` on API calls.

---

## Configure environment variables

Copy `.env.example` to `.env`. Values below use Docker Compose service hostnames (`postgres`, `redis`, `minio`). For native setup, replace those with `localhost`.

| Variable | Required | Description |
|----------|----------|-------------|
| `ENV` | No | `local`, `dev`, `qa`, `prod`, or `test`. Default: `local` |
| `DATABASE_URL` | Yes | Async SQLAlchemy URL, e.g. `postgresql+asyncpg://resume:resume@postgres:5432/resume_builder` |
| `REDIS_URL` | Yes | e.g. `redis://redis:6379/0` |
| `JWT_SECRET` | Yes | Min 32 characters; used for JWT and NiceGUI session storage |
| `CORS_ORIGINS` | No | Comma-separated origins. Default: `http://localhost:8000` |
| `S3_ENDPOINT` | Local | Set to `http://minio:9000` for MinIO; leave empty for AWS S3 |
| `S3_BUCKET` | Yes | Bucket name, default `resume-builder` |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | Yes | MinIO: `minioadmin` / `minioadmin` |
| `S3_REGION` | No | Default `us-east-1` |
| `OPENAI_API_KEY` | Recommended | OpenAI (default provider; `OPENAI_BASE_URL` defaults to OpenAI API) |
| `ANTHROPIC_API_KEY` | Optional | Anthropic Claude |
| `GEMINI_API_KEY` | Optional | Google Gemini |
| `XAI_API_KEY` | Optional | xAI Grok (`XAI_BASE_URL` configurable) |
| `STRIPE_SECRET_KEY` | For payments | Stripe secret key |
| `STRIPE_PUBLISHABLE_KEY` | For payments | Stripe publishable key (frontend checkout) |
| `STRIPE_WEBHOOK_SECRET` | For payments | From Stripe CLI or Dashboard webhook |
| `STRIPE_PRICE_ID` | Unused | Legacy; checkout uses `RUN_UNLOCK_PRICE_USD` |
| `NOWPAYMENTS_API_KEY` | Optional | Crypto payments via NOWPayments |
| `NOWPAYMENTS_IPN_SECRET` | Optional | NOWPayments IPN HMAC secret |
| `PAYMENTS_ENABLED` | No | `true`/`false` to force payments on/off. Empty (default) auto-derives: on when Stripe or NOWPayments keys are set, otherwise off |
| `SUPPORT_URL` | No | When payments are off, shows a single subtle support link pointing here |
| `RUN_UNLOCK_PRICE_USD` | No | Display/checkout amount. Default: `3.99` |

Never commit `.env` or real API keys to git.

---

## Create the MinIO bucket

If you skipped this during quick start: uploads fail until the bucket exists. Bucket name must match `S3_BUCKET` (default `resume-builder`).

See [step 4 in Quick start](#4-create-the-minio-bucket) for console or CLI instructions.

---

## Use the app

### Main workflow (`/app`)

1. Upload a PDF or DOCX master resume.
2. Paste a job description.
3. Start a run — progress updates stream live in the UI.
4. **First run is free** (full output unlocked).
5. **Second run onward** shows a locked preview until payment.
6. Pay via Stripe or crypto, then poll until the webhook unlocks the run.
7. Export to PDF or DOCX when output is unlocked.

### Advanced dashboard (`/app/dashboard`)

Same backend, richer UI: LLM provider selection, match scores, variant tabs, section editor, and changelog. Link from the main page or go directly.

### API overview

All protected routes accept `X-Device-Fingerprint` (no JWT required for the NiceGUI flow).

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/auth/me` | GET | Device workspace state (free trial, uploads) |
| `/api/v1/resumes` | GET, POST | List / upload resumes |
| `/api/v1/runs` | POST | Start a tailoring run |
| `/api/v1/runs/{id}` | GET | Run status and output (respects lock) |
| `/api/v1/runs/{id}/stream` | GET | SSE progress events |
| `/api/v1/billing/stripe/checkout` | POST | Create Stripe Checkout session |
| `/api/v1/billing/crypto/invoice` | POST | Create crypto invoice |
| `/api/v1/exports` | POST | Generate PDF/DOCX download |
| `/api/v1/webhooks/stripe` | POST | Stripe webhook (unlock after payment) |
| `/api/v1/webhooks/crypto` | POST | NOWPayments IPN webhook |

Interactive API docs: http://localhost:8000/docs

---

## LLM providers

Supported providers (selectable on `/app` and the dashboard; default is OpenAI):

| Provider | Env var | Notes |
|----------|---------|-------|
| OpenAI | `OPENAI_API_KEY` | Default; GPT-4o family |
| Anthropic | `ANTHROPIC_API_KEY` | Claude |
| Google Gemini | `GEMINI_API_KEY` | |
| xAI Grok | `XAI_API_KEY` | |

If a provider’s API key is missing, the agent uses deterministic mock completions so the app still runs locally — useful for UI testing, not for real tailoring.

**Minimum for real runs:** set `OPENAI_API_KEY` (or configure another provider and choose it on the dashboard).

Get an OpenAI API key: https://platform.openai.com/api-keys

---

## Payment setup (optional)

Payments are only needed to test the paywall after the free trial.

### Stripe (recommended for local testing)

1. Create a [Stripe test account](https://dashboard.stripe.com/register).
2. Add to `.env`:
   - `STRIPE_SECRET_KEY=sk_test_...`
   - `STRIPE_PUBLISHABLE_KEY=pk_test_...`
   - `RUN_UNLOCK_PRICE_USD=3.99`
4. Forward webhooks to your local app:

   ```bash
   stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe
   ```

5. Copy the webhook signing secret (`whsec_...`) into `STRIPE_WEBHOOK_SECRET` in `.env`.
6. Restart the web container: `docker compose restart web`

Use [Stripe test cards](https://docs.stripe.com/testing#cards) (e.g. `4242 4242 4242 4242`).

### Crypto (NOWPayments)

Optional. Set `NOWPAYMENTS_API_KEY` and `NOWPAYMENTS_IPN_SECRET`, and configure your NOWPayments IPN URL to point at `/api/v1/webhooks/crypto`.

---

## Native Python setup (without Docker)

Use this if you prefer running the app directly on your machine.

### 1. Install dependencies

```bash
python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 2. Start backing services

Run PostgreSQL, Redis, and MinIO locally (or use cloud equivalents). Example with only Postgres/Redis via Docker:

```bash
docker compose up -d postgres redis minio
```

### 3. Configure `.env` for localhost

```bash
cp .env.example .env
```

Update hostnames from Docker service names to localhost:

```env
DATABASE_URL=postgresql+asyncpg://resume:resume@localhost:5432/resume_builder
REDIS_URL=redis://localhost:6379/0
S3_ENDPOINT=http://localhost:9000
```

Create the MinIO bucket at http://localhost:9001 (see above).

### 4. Run migrations

```bash
export PYTHONPATH=.
alembic upgrade head
```

Or use the helper script:

```bash
bash scripts/migrate.sh
```

### 5. Start the web server

```bash
export PYTHONPATH=.
uvicorn apps.web.main:app --host 0.0.0.0 --port 8000 --reload
```

Open http://localhost:8000/app

### Optional: seed a dev user

The NiceGUI flow uses device fingerprints, not login. If you need a registered user for API testing:

```bash
python scripts/seed_dev.py
# Creates dev@example.com / password123
```

---

## Database migrations

Migrations use Alembic and live in `migrations/versions/`. They are **never** applied on app startup.

**Docker:**

```bash
docker compose run --rm migrate
```

**Native:**

```bash
bash scripts/migrate.sh
```

Create a new migration after model changes:

```bash
alembic revision --autogenerate -m "describe change"
```

Regenerate table documentation after schema changes:

```bash
python scripts/db/document_tables.py
bash scripts/db/export_schema.sh
```

---

## Run tests

CI runs lint, type-check, and pytest with ≥85% coverage inside Docker.

**Full suite (matches CI):**

```bash
docker compose -f docker-compose.test.yml run --rm test
```

This brings up Postgres and Redis, runs migrations, then executes:

- `ruff check apps packages tests`
- `mypy apps packages`
- `pytest --cov=packages --cov=apps --cov-fail-under=85`

**Local venv (faster iteration):**

```bash
# Start test database stack
docker compose -f docker-compose.test.yml up -d postgres redis
docker compose -f docker-compose.test.yml run --rm migrate

# Run tests
ENV=test \
  DATABASE_URL=postgresql+asyncpg://resume:resume@localhost:5432/resume_builder_test \
  REDIS_URL=redis://localhost:6379/1 \
  JWT_SECRET=test-secret-key-minimum-32-characters-long \
  OPENAI_API_KEY=test ANTHROPIC_API_KEY=test \
  STRIPE_SECRET_KEY=sk_test_fake STRIPE_WEBHOOK_SECRET=whsec_test \
  NOWPAYMENTS_API_KEY=test NOWPAYMENTS_IPN_SECRET=test \
  PYTHONPATH=. \
  .venv/bin/pytest --cov=packages --cov=apps --cov-fail-under=85
```

Or use the test runner script inside the test container:

```bash
docker compose -f docker-compose.test.yml run --rm test scripts/deploy/run_tests.sh
```

---

## Project layout

```
resume-builder/
├── apps/web/                 # FastAPI app + NiceGUI UI
│   ├── main.py               # Application entrypoint
│   ├── api/v1/               # REST routes
│   └── ui/                   # NiceGUI pages (/app, /app/dashboard)
├── packages/
│   ├── agent/                # LangGraph workflow + LLM providers
│   ├── core/                 # Auth, access/paywall, security
│   ├── db/                   # SQLAlchemy models + session
│   ├── export/               # PDF/DOCX generation
│   └── integrations/         # Stripe, S3, Hugging Face, crypto
├── migrations/versions/      # Alembic migrations
├── scripts/                  # migrate, deploy, db doc tools
├── tests/                    # unit + integration tests
├── docker-compose.yml        # Local dev stack
├── docker-compose.test.yml   # CI / test stack
├── Dockerfile                # Production/dev web image
├── Dockerfile.test           # Test runner image
└── pyproject.toml            # Dependencies and tool config
```

---

## Branch workflow

| Branch | Purpose |
|--------|---------|
| `develop` | Active development |
| `qa` | Pre-production validation |
| `main` | Production releases |

Feature work: branch from `develop` as `feature/<name>`, open a PR into `develop`.

Engineering plans and status (private dev docs) live on `develop` under `docs/dev/plans/` — not shipped to production `main`.

---

## Troubleshooting

### `web` container exits or health check fails

- Ensure Postgres and Redis are healthy: `docker compose ps`
- Re-run migrations: `docker compose run --rm migrate`
- Check logs: `docker compose logs web`

### Resume upload fails (S3 / MinIO error)

- Confirm the bucket exists and matches `S3_BUCKET` in `.env`
- Verify MinIO is running: http://localhost:9001
- Check credentials: `S3_ACCESS_KEY` / `S3_SECRET_KEY`

### Agent runs complete but output looks like placeholder text

- No LLM API key is configured. Add `OPENAI_API_KEY` or another provider key and restart.
- On the dashboard, confirm the selected provider is configured.

### Paywall does not unlock after Stripe payment

- `STRIPE_WEBHOOK_SECRET` must match the secret from `stripe listen` or your Dashboard webhook
- Webhook endpoint must be reachable: `POST /api/v1/webhooks/stripe`
- Check `docker compose logs web` for webhook errors

### Port already in use

Change the host mapping in `docker-compose.yml` (e.g. `"8001:8000"`) and update `CORS_ORIGINS`.

### Reset local database

```bash
docker compose down -v
docker compose up --build
```

This removes Postgres and MinIO volumes and reapplies migrations from scratch.

---

## Stack summary

- **Backend:** Python 3.12, FastAPI, SQLAlchemy (async), Alembic
- **Frontend:** NiceGUI (mounted at `/app`)
- **Agents:** LangGraph + pluggable LLM providers
- **Data:** PostgreSQL 16, Redis 7, S3 (MinIO locally)
- **Payments:** Stripe Checkout + NOWPayments (crypto)
- **Export:** WeasyPrint (PDF), python-docx (DOCX)


# Claude Code Context — Resume Builder

> **Dev-only.** Lives on `develop`, `qa`, and `feature/*` branches only.
> **Never merged to `main`.** Enforced by `forbidden-paths-guard.yml`.

---

## 1. What This App Does

AI resume tailoring with optional pay-per-run access. A user uploads a master resume (PDF/DOCX/TXT), pastes a job description, picks a **tailoring style** (conservative/balanced/bold) and an **LLM provider** (OpenAI/Anthropic/Gemini/Grok), then gets three tailored resume variations with JD-mirrored language, before/after job-fit scores, and LLM coaching bullets. No hallucinated facts.

**Free trial:** 1 resume upload + 1 JD run → full visible output.
**When payments are enabled:** subsequent runs execute with output **locked** (`output_locked = True`) until the user pays **$3.99** (Stripe one-time or crypto). Payment unlocks that specific run only.
**When payments are disabled:** runs are free and unlimited, and the paywall controls are hidden.

---

## 2. Monorepo Layout

```
resume-builder/
├── apps/
│   └── web/
│       ├── main.py                  # FastAPI app + NiceGUI mount
│       ├── config.py                # Settings (pydantic-settings, reads .env)
│       ├── dependencies.py          # FastAPI dependency injectors
│       ├── middleware/
│       │   ├── rate_limit.py        # Redis-backed per-endpoint limits
│       │   └── security_headers.py  # CSP, HSTS, X-Frame-Options
│       ├── api/
│       │   ├── router.py            # Registers all v1 routers
│       │   └── v1/
│       │       ├── auth.py          # /auth/* — register, login, refresh, logout, me
│       │       ├── resumes.py       # /resumes — upload + list (extracts DOCX style on upload)
│       │       ├── runs.py          # /runs — create, get, stream, variant generate
│       │       ├── exports.py       # /exports — TXT/DOCX/PDF post-payment (DOCX uses style_metadata)
│       │       ├── score.py         # /score/preview — pre-run fit score (no full pipeline needed)
│       │       ├── billing.py       # /billing/* — stripe checkout, crypto invoice, status
│       │       ├── health.py        # /health — liveness probe
│       │       └── webhooks/
│       │           ├── stripe.py    # POST /webhooks/stripe
│       │           └── crypto.py    # POST /webhooks/crypto
│       ├── services/
│       │   ├── run_executor.py      # execute_run_background() — runs the LangGraph agent
│       │   ├── run_launcher.py      # create_and_schedule_run() — creates run + schedules execution as a task
│       │   ├── run_editor.py        # select_variant, update_section_override, generate_variant
│       │   └── stripe_billing.py    # checkout session creation + /billing/stripe/verify polling fallback
│       └── ui/
│           ├── app.py               # NiceGUI single-page app (scores + 3 variant tabs + fit panel)
│           ├── auth_guard.py        # NiceGUI session/cookie check
│           ├── request_auth.py      # device-fingerprint-based request auth for UI → API calls
│           ├── run_progress.py      # SSE-style progress watcher
│           ├── workflow_session.py  # persists run/resume/JD state in browser storage across Stripe redirect
│           └── console_log.py       # browser console logging helper
│
├── packages/
│   ├── agent/
│   │   ├── state.py                 # AgentState TypedDict + helper functions
│   │   ├── graph.py                 # build_graph(), run_agent() — LangGraph wiring (7 nodes)
│   │   ├── service.py               # AgentService — wraps the selected LLMProvider for all nodes
│   │   ├── checkpointer.py          # get_checkpointer() — AsyncPostgresSaver context mgr
│   │   ├── nodes/
│   │   │   ├── prepare_inputs.py    # Node 1: parse resume, extract structured data
│   │   │   ├── understand_resume.py # Node 2: LLM resume structure analysis
│   │   │   ├── analyze_inputs.py    # Node 3: LLM JD analysis + before-score
│   │   │   ├── rewrite_sections.py  # Node 4: LLM rewrite with JD language mirroring
│   │   │   ├── validate_output.py   # Node 5: hallucination check
│   │   │   ├── format_output.py     # Node 6: build final_output, before/after scores (no LLM)
│   │   │   └── assess_fit.py        # Node 7: LLM holistic verdict + coaching bullets
│   │   ├── analysts/
│   │   │   ├── jd_analyst.py        # JD structured extraction
│   │   │   ├── resume_analyst.py    # Resume requirement mapping
│   │   │   ├── input_analyst.py     # Combined analyze_inputs_combined()
│   │   │   └── fit_analyst.py       # assess_fit() — verdict + 4-6 coaching bullets
│   │   ├── orchestrator/
│   │   │   └── resume_orchestrator.py  # understand_resume_structure() for the understand_resume node
│   │   ├── providers/               # LLM provider abstraction (4 providers)
│   │   │   ├── base.py              # AgentTask enum, LLMProvider ABC
│   │   │   ├── registry.py          # get_provider(), list_provider_options()
│   │   │   ├── anthropic_provider.py  # claude-opus-4-8 (all tasks)
│   │   │   ├── openai_provider.py     # gpt-4o (rewrite), gpt-4o-mini (analysis)
│   │   │   ├── gemini_provider.py     # gemini-3.5-flash (all tasks)
│   │   │   ├── grok_provider.py       # grok-4.3 (all tasks)
│   │   │   └── _http.py, _mock.py   # shared HTTP client + test mock provider
│   │   ├── schemas/
│   │   │   ├── fit_assessment.py    # FitAssessment(verdict, coaching_bullets)
│   │   │   ├── analysis.py          # JDAnalysis, ResumeAnalysis
│   │   │   ├── match.py             # MatchScoreResult, MatchComponentScore
│   │   │   ├── providers.py         # LLMProviderName enum + labels
│   │   │   └── variants.py          # VariantName enum: conservative/balanced/bold
│   │   ├── scoring/
│   │   │   └── match_score.py       # Deterministic 5-component weighted score (0-100)
│   │   ├── changelog/builder.py     # human-readable per-run changelog
│   │   ├── utils/json_parse.py      # tolerant JSON parsing of LLM output
│   │   └── sections/
│   │       ├── agent.py             # rewrite_section() — JD-language-mirroring prompt
│   │       └── orchestrator.py      # build_all_variants(), _variants_to_build()
│   │
│   ├── core/
│   │   ├── access/
│   │   │   ├── service.py           # AccessService — all paywall decisions live here
│   │   │   └── free_trial.py        # Free trial eligibility helpers
│   │   ├── schemas/
│   │   │   └── access.py            # RunAccessMode enum: FREE | LOCKED | BLOCKED
│   │   └── security/
│   │       ├── jwt.py               # create_access_token, verify_token, register_user
│   │       ├── passwords.py         # hash_password, verify_password
│   │       └── sanitization.py      # bleach-based input sanitizer
│   │
│   ├── db/
│   │   ├── base.py                  # SQLAlchemy DeclarativeBase
│   │   ├── session.py               # engine, SessionLocal, get_session()
│   │   └── models/
│   │       ├── user.py              # User
│   │       ├── device_session.py    # DeviceSession (IP + fingerprint binding)
│   │       ├── refresh_token.py     # RefreshToken
│   │       ├── resume.py            # MasterResume
│   │       ├── agent_run.py         # AgentRun
│   │       ├── agent_run_event.py   # AgentRunEvent (per-node SSE events)
│   │       ├── payment.py           # Payment (unified stripe + crypto)
│   │       ├── crypto_payment.py    # CryptoPayment (on-chain detail)
│   │       ├── stripe_event.py      # StripeEvent (idempotency log)
│   │       ├── crypto_webhook_event.py  # CryptoWebhookEvent (idempotency log)
│   │       └── export.py            # Export (tracks generated file + S3 key)
│   │
│   ├── export/
│   │   ├── pdf_ingest.py            # pdfplumber / docx text extractor
│   │   ├── docx_export.py           # Professional DOCX export (section headers, bullets, style_metadata)
│   │   └── style_extractor.py       # Extract font/size/spacing from uploaded DOCX
│   │
│   └── integrations/
│       ├── stripe_client.py         # Stripe checkout session creation
│       ├── s3_storage.py            # boto3 S3 upload/presign
│       └── crypto/
│           └── nowpayments.py       # NOWPayments invoice + status
│
├── migrations/
│   └── versions/
│       ├── 001_initial_schema.py    # All initial tables
│       ├── 002_llm_provider.py      # Add llm_provider to agent_runs
│       ├── 003_resume_style_metadata.py  # Add style_metadata JSONB to master_resumes
│       └── 004_default_provider_openai.py # Set OpenAI as the default provider
│
├── tests/
│   ├── conftest.py                  # SQLite in-memory engine, session fixture
│   ├── factories/                   # factory_boy model factories
│   ├── unit/
│   │   ├── agent/                   # Node + checkpointer unit tests
│   │   ├── apps/                    # run_executor unit tests
│   │   ├── core/                    # AccessService, JWT, passwords
│   │   ├── export/                  # pdf_ingest, docx_export
│   │   └── integrations/            # LLM/Stripe/S3 client tests (mocked)
│   ├── integration/
│   │   ├── api/                     # Full HTTP round-trips via httpx AsyncClient
│   │   └── webhooks/                # Stripe + crypto webhook integration tests
│   └── e2e/
│       └── agent_graph/             # Full graph run with mocked LLM
│
├── scripts/
│   ├── db/
│   │   ├── document_tables.py       # Auto-generates docs/database/tables/*.md
│   │   ├── export_schema.sh         # pg_dump --schema-only → docs/database/schema.sql
│   │   └── verify_docs.sh           # CI: fail if docs stale vs migrations
│   └── deploy/
│       ├── run_tests.sh             # Entry point for Docker test container
│       ├── smoke_test.sh            # Hit /health after deploy
│       ├── promote-qa-to-main.sh    # Cherry-picks allowed paths only; never copies docs/dev/
│       ├── deploy-dev.sh
│       ├── deploy-qa.sh
│       ├── deploy-prod.sh
│       └── rollback.sh
│
└── docs/
    ├── database/                    # Auto-generated; allowed on main
    │   ├── README.md                # ER diagram + table index
    │   ├── schema.sql               # Cumulative DDL export
    │   └── tables/                  # One .md per table
    └── dev/                         # THIS DIRECTORY — never on main
        ├── claude.md                # ← you are here
        ├── codex.md
        ├── cursor.md
        └── plans/
            ├── STATUS.md            # Current implementation status + branch tracker
            └── resume_builder_architecture.plan.md  # Full engineering plan
```

---

## 3. Naming Conventions

### Files & modules
- All files: `snake_case.py` — `run_executor.py`, `device_session.py`
- No abbreviations in file names: `access_service.py` not `acc_svc.py`

### Python identifiers
| Kind | Convention | Example |
|------|-----------|---------|
| Class | `PascalCase` | `AgentRun`, `AccessService`, `MasterResume` |
| Function / method | `snake_case` | `execute_run()`, `unlock_run()` |
| Variable | `snake_case` | `output_locked`, `run_id`, `payment_id` |
| Constant (module-level) | `SCREAMING_SNAKE_CASE` | _(none currently)_ |
| Async function | `snake_case` (no `async_` prefix) | `get_session()`, `can_start_run()` |
| Private helper | leading underscore | `_after_validate()`, `_to_psycopg_dsn()` |

### Database columns → SQLAlchemy attributes
Column names are `snake_case` and map 1-to-1 to model attributes:

| Column | Python attribute | Type | Notes |
|--------|-----------------|------|-------|
| `user_id` | `run.user_id` | `UUID` | FK on every user-scoped table |
| `run_id` | `payment.run_id` | `UUID \| None` | FK → agent_runs.id |
| `output_locked` | `run.output_locked` | `bool` | Controls what the API returns |
| `is_free_trial_run` | `run.is_free_trial_run` | `bool` | |
| `final_output` | `run.final_output` | `JSONB` | Never returned when `output_locked=True` |
| `preview_text` | `run.preview_text` | `str` | Max 500 chars; always returneable |
| `provider_payment_id` | `payment.provider_payment_id` | `str` | Stripe/NOWPayments external ID |
| `idempotency_key` | `payment.idempotency_key` | `str` | UNIQUE; prevents double-unlock |
| `free_trial_used` | `user.free_trial_used` | `bool` | Set on first completed run |

### AgentState keys
Defined in `packages/agent/state.py` as `AgentState(TypedDict, total=False)`:

| Key | Type | Who sets it |
|-----|------|-------------|
| `run_id` | `str` | caller — stringified UUID |
| `user_id` | `str` | caller — stringified UUID |
| `llm_provider` | `str` | caller — selected `LLMProviderName` |
| `master_resume_text` | `str` | caller |
| `master_resume_structured` | `dict[str, str]` | `prepare_inputs` |
| `jd_text` | `str` | caller |
| `jd_keywords` | `list[str]` | `prepare_inputs` |
| `keyword_gaps` | `list[str]` | `prepare_inputs` |
| `jd_analysis` / `resume_analysis` | `dict` | `analyze_inputs` (single combined LLM call) |
| `match_score_before` / `match_score_after` | `dict` | `scoring/match_score.py` |
| `resume_structure` | `dict` | `understand_resume` |
| `sections_to_tailor` / `sections_suggested` / `sections_missing` | `list` | `understand_resume` |
| `selected_variant` | `str` | caller (defaults to `DEFAULT_VARIANT` if unset) |
| `variants` | `dict[str, dict[str, str]]` | `rewrite_sections` — keyed by variant name |
| `changelog` | `list[dict[str, str]]` | `changelog/builder.py` |
| `sections_editable` / `user_section_overrides` / `user_added_sections` | `dict` | post-run edits via `run_editor.py` |
| `ats_score_before` | `float` | `prepare_inputs` |
| `ats_score_after` | `float` | `format_output` |
| `section_drafts` | `dict[str, str]` | `rewrite_sections` |
| `validation_errors` | `list[str]` | `validate_output` |
| `validation_passed` | `bool` | `validate_output` |
| `retry_count` | `int` | caller init `0`; graph increments |
| `final_output` | `dict` | `format_output` |
| `preview_text` | `str` | `format_output` |
| `output_locked` | `bool` | caller (from `AccessService` decision) |
| `cancelled` | `bool` | set externally to abort in-flight run |
| `fatal_error` | `str` | `prepare_inputs` on unrecoverable failure |

### API route naming
- Collection: `GET /resumes`, `POST /resumes`
- Instance: `GET /runs/{run_id}`, `DELETE /runs/{run_id}`
- Sub-resource action: `POST /runs/{run_id}/unlock`, `PATCH /runs/{run_id}/variant`, `PATCH /runs/{run_id}/sections/{section_name}`, `POST /runs/{run_id}/sections/{section_name}/add`
- Provider listing: `GET /runs/providers`
- SSE endpoint: `GET /runs/{run_id}/stream`
- Payment-return fallback: `POST /billing/stripe/verify` — polls Stripe directly when the webhook is delayed
- Namespaced billing: `POST /billing/stripe/checkout`, `POST /billing/crypto/invoice`
- Webhooks: `POST /webhooks/stripe`, `POST /webhooks/crypto`

### Environment variables
| Variable | Example value | Notes |
|----------|--------------|-------|
| `ENV` | `local \| dev \| qa \| prod` | Controls cookie security, log level |
| `DATABASE_URL` | `postgresql+asyncpg://resume:resume@postgres/resume_builder` | asyncpg driver for SQLAlchemy |
| `REDIS_URL` | `redis://redis:6379/0` | |
| `JWT_SECRET` | 32+ random chars | |
| `JWT_ACCESS_EXPIRE_MINUTES` | `15` | |
| `JWT_REFRESH_EXPIRE_DAYS` | `7` | |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | `sk-...` | OpenAI provider (default provider) |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | Anthropic provider |
| `GEMINI_API_KEY` | | Gemini provider |
| `XAI_API_KEY` / `XAI_BASE_URL` | | Grok provider |
| `STRIPE_SECRET_KEY` | `sk_live_...` | |
| `STRIPE_PUBLISHABLE_KEY` | `pk_live_...` | Used by NiceGUI Checkout redirect |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` | Signature verification |
| `STRIPE_PRICE_ID` | `price_...` | One-time $3.99 |
| `NOWPAYMENTS_API_KEY` | | |
| `NOWPAYMENTS_IPN_SECRET` | | HMAC secret |
| `PAYMENTS_ENABLED` | `true \| false` | Empty auto-derives from Stripe/NOWPayments keys |
| `SUPPORT_URL` | `https://...` | Shown as one subtle support link when payments are off |
| `S3_ENDPOINT` | `http://minio:9000` | Empty = AWS S3 |
| `S3_BUCKET` | `resume-builder` | |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | | |
| `RUN_UNLOCK_PRICE_USD` | `3.99` | |
| `APP_VERSION` / `DEPLOYED_AT` / `DEPLOY_ENV` | | Surfaced via `/api/v1/deployments/latest` |

---

## 4. Core Data Flow

### Free trial run (first JD)
```
POST /runs
  → AccessService.can_start_run(user_id)  → RunAccessMode.FREE
  → AgentRun created (output_locked=False, is_free_trial_run=True)
  → execute_run() fires as background asyncio task
      → get_checkpointer(settings.database_url)  # AsyncPostgresSaver
      → run_agent(initial, llm_complete, checkpointer=cp)
          → prepare_inputs  (deterministic: pdfplumber + TF-IDF)
          → rewrite_sections  (LLM call 1)
          → validate_output   (LLM call 2)
          → format_output     (deterministic)
      → AgentRun.final_output = result["final_output"]
      → AccessService.mark_free_trial_used(user_id)
GET /runs/{run_id}
  → output_locked=False → returns full final_output
```

### Locked run (second JD onward)
```
POST /runs
  → AccessService.can_start_run(user_id)  → RunAccessMode.LOCKED
  → AgentRun created (output_locked=True)
  → execute_run() → agent runs → result stored with output_locked=True
GET /runs/{run_id}
  → output_locked=True → returns {locked: true, preview_text: "..."}
                                   ↑ final_output NEVER included
POST /runs/{run_id}/unlock
  → returns {checkout_url} (Stripe) or {crypto_invoice} (NOWPayments)
  → user pays
  → Stripe webhook: POST /webhooks/stripe
      → verify Stripe-Signature header
      → check StripeEvent.stripe_event_id for idempotency
      → AccessService.unlock_run(payment_id, run_id)
          → Payment.status = "confirmed"
          → AgentRun.output_locked = False
GET /runs/{run_id}
  → output_locked=False → returns full final_output
```

### Container restart mid-run (checkpoint recovery)
```
execute_run() starts → get_checkpointer() → run_agent(..., checkpointer=cp)
  → ainvoke keyed by thread_id = run_id
  → LangGraph writes checkpoint after each node completes

[Container dies between rewrite_sections and validate_output]

Container restarts → execute_run() called again for same run_id
  → run_agent with same run_id → ainvoke with same thread_id
  → LangGraph finds checkpoint → resumes from validate_output
  → No re-execution of prepare_inputs or rewrite_sections (no wasted provider calls)
```

---

## 5. AccessService API (Do Not Bypass)

`packages/core/access/service.py`

```python
class AccessService:
    async def get_user(user_id: UUID) -> User | None
    async def has_confirmed_payment(user_id: UUID) -> bool
    async def get_snapshot(user_id: UUID) -> AccessSnapshot
    async def can_upload_resume(user_id: UUID) -> bool
    async def can_start_run(user_id: UUID) -> RunAccessDecision   # .mode: FREE|LOCKED|BLOCKED
    async def can_view_output(user_id: UUID, run: AgentRun) -> bool   # takes the loaded run, not just its id
    async def can_export(user_id: UUID, run: AgentRun) -> bool
    async def unlock_run(payment_id: UUID, run_id: UUID) -> None
    async def mark_free_trial_used(user_id: UUID) -> None
```

**Rules — never bypass, never change without updating the plan:**

| Check | Result | Condition |
|-------|--------|-----------|
| `can_upload_resume` | `True` | `user.free_trial_used = False` |
| `can_upload_resume` | `True` | Any `Payment.status = "confirmed"` for user |
| `can_upload_resume` | `False` | Otherwise |
| `can_start_run` → `FREE` | First run for user | `user.free_trial_used = False` |
| `can_start_run` → `LOCKED` | Subsequent runs | `user.free_trial_used = True` |
| `can_view_output` | `True` | `AgentRun.output_locked = False` |
| `can_view_output` | `False` → 402 | `AgentRun.output_locked = True` |
| `can_export` | `True` | Run unlocked AND export format allowed |
| `unlock_run` | Sets `output_locked = False` | `Payment.status = "confirmed"` |

**402 response shape:**
```json
{"code": "OUTPUT_LOCKED", "run_id": "...", "checkout_url": "...", "crypto_invoice_url": "..."}
```

---

## 6. LangGraph Agent — 7 Nodes

`packages/agent/graph.py`

```
prepare_inputs ──→ understand_resume ──→ analyze_inputs ──→ rewrite_sections
      │                   │                    │                    │
      │ (fatal_error)     │ (fatal_error)       │ (fatal_error)      ▼
      └──→ END            └──→ END              └──→ END       validate_output
                                                                     │
                                              ┌──────────────────────┤ (retry_count < 2, not passed)
                                              ▼                      └──→ rewrite_sections
                                         format_output ──→ assess_fit ──→ END
```

**Node responsibilities:**
| Node | LLM? | Output |
|------|------|--------|
| `prepare_inputs` | No | Parses resume text, splits sections |
| `understand_resume` | Yes | `resume_structure` — section map + inferred seniority |
| `analyze_inputs` | Yes | `jd_analysis`, `resume_analysis`, `match_score_before` |
| `rewrite_sections` | Yes | `variants` dict keyed by selected variant name |
| `validate_output` | Yes | `validation_passed`, `validation_errors` |
| `format_output` | No | `final_output` — all scores, plain_text, variant payloads |
| `assess_fit` | Yes | `final_output.fit_assessment` — verdict + coaching bullets |

**Firm constraints:**
- `prepare_inputs` and `format_output` are **pure Python — no LLM**
- `understand_resume`, `analyze_inputs`, `rewrite_sections`, `validate_output` are LLM nodes — exactly **4 LLM calls per run** for the selected variant (one extra `rewrite_sections` call per retry, max 2 retries)
- `analyze_inputs` makes **one combined call** for JD + resume analysis (`analysts/input_analyst.py::analyze_inputs_combined`) — the old two-call sequential path still exists in `jd_analyst.py`/`resume_analyst.py` as a fallback
- `rewrite_sections` builds only the **selected tailoring variant** by default (`selected_variant`, defaults to `DEFAULT_VARIANT = balanced`); all 3 variants (conservative/balanced/bold) are only built together when retailoring a section after the fact
- Max retry loop: `retry_count < 2` in `_after_validate()`
- `assess_fit` runs **after** `format_output` — never inside it (format_output re-runs on section edits)
- `_variants_to_build()` returns **only the selected variant** — other variants are on-demand via `POST /runs/{run_id}/variants/{name}/generate`
- All LLM calls go through `AgentService`, which wraps whichever `LLMProvider` was selected (OpenAI/Anthropic/Gemini/Grok) — there is no single hardcoded model anymore

### Key function signatures

```python
# packages/agent/graph.py
def build_graph(
    agent_service: AgentService,
    on_progress: ProgressCallback | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
): ...

async def run_agent(
    initial: AgentState,
    agent_service: AgentService,
    on_progress: ProgressCallback | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
) -> AgentState: ...
```

### Checkpointer wiring
```python
# packages/agent/checkpointer.py
@asynccontextmanager
async def get_checkpointer(database_url: str) -> AsyncGenerator[AsyncPostgresSaver, None]:
    # converts postgresql+asyncpg:// → postgresql:// for psycopg3
    # calls checkpointer.setup() once (creates langgraph checkpoint tables)
    ...

# Usage in run_executor.py
async with get_checkpointer(settings.database_url) as checkpointer:
    result = await run_agent(initial, agent_service, checkpointer=checkpointer)
```

### LLM Providers

Four providers implement `LLMProvider` ABC. Provider is selected per-run and used for all nodes. OpenAI is the default.

| Provider | Model used |
|----------|-----------|
| OpenAI | `gpt-4o` (SECTION_REWRITE), `gpt-4o-mini` (all others) |
| Anthropic | `claude-opus-4-8` (all tasks) |
| Gemini | `gemini-3.5-flash` (all tasks) |
| Grok | `grok-4.3` (all tasks) |

`AgentTask` enum members: `RESUME_ORCHESTRATION`, `INPUT_ANALYSIS`, `JD_ANALYSIS`, `RESUME_ANALYSIS`, `SECTION_REWRITE`, `VALIDATION`, `FIT_ASSESSMENT`. **All providers must map every task.**

### Scoring

`packages/agent/scoring/match_score.py` — deterministic 5-component weighted score:

| Component | Weight | What it measures |
|-----------|--------|-----------------|
| `must_have` | 35% | Requirement evidence (met/partial/missing) |
| `skills` | 20% | JD skills vs resume skills |
| `experience_relevance` | 20% | Role/industry overlap |
| `ats_keywords` | 15% | JD keyword coverage |
| `seniority_fit` | 10% | Seniority level match |

**Fit verdict thresholds (LLM-confirmed):** Strong fit ≥72 and no unmet dealbreakers; Not a fit <45 or dealbreaker unmet; Moderate fit otherwise.

---

## 7. Testing Conventions

**Stack:** `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"`) + `respx` + `factory_boy`

**DB in tests:** SQLite in-memory (`sqlite+aiosqlite:///:memory:`) — see `conftest.py`

**HTTP tests:** `httpx.AsyncClient(transport=ASGITransport(app=app))`

**All external services are mocked** — LLM providers, Stripe, NOWPayments, S3, boto3

For local and dev environments, `apps/web/main.py` bootstraps the configured S3 bucket before serving requests. Production buckets are managed out of band.

**Coverage gate:** 85% (`--cov-fail-under=85`) — run with:
```bash
pytest --cov=packages --cov=apps --cov-fail-under=85
```

**Excluded from coverage** (`pyproject.toml [tool.coverage.run] omit`):
- `apps/web/ui/*` — NiceGUI pages
- `apps/web/api/v1/webhooks/*`
- `packages/export/pdf_export.py`
- `packages/integrations/crypto/nowpayments.py`

**Test layout mirrors source:**
```
packages/agent/checkpointer.py  →  tests/unit/agent/test_checkpointer.py
apps/web/services/run_executor.py  →  tests/unit/apps/test_run_executor.py
```

**Mocking `get_checkpointer` in unit tests:**
```python
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

@asynccontextmanager
async def fake_get_checkpointer(database_url):
    yield AsyncMock()

monkeypatch.setattr("apps.web.services.run_executor.get_checkpointer", fake_get_checkpointer)
```

---

## 8. Auth & Security

- JWT issued as **httpOnly cookies only** — never bearer tokens, never localStorage
- Cookie names: `access_token`, `refresh_token`
- `RefreshToken` rows stored in DB; invalidated on logout
- `DeviceSession` stores `device_fingerprint` (JS canvas/tz hash) + `ip_hash` per user/device
- Free trial is **per account**, not per device — new device on same account: allowed, no reset
- IP registration limit: 3 new accounts per IP per 24h (Redis key `rl:register:{ip_hash}`)
- All user-scoped queries must include `WHERE user_id = :user_id` — never rely on run_id alone

---

## 9. Branch & Commit Rules

| Branch | Purpose | Never do |
|--------|---------|----------|
| `feature/<name>` | One feature/fix from `develop` | Commit `docs/dev/` changes to `main` |
| `develop` | Integration + dev deploy | Direct commits; push without PR |
| `qa` | Pre-prod gate | Merge from `feature/*` directly |
| `main` | Production only | Anything except cherry-picks via promote script |

- Feature branches: `feature/kebab-case-name` (e.g. `feature/nicegui-paywall-polish`)
- Every PR to `develop` must pass: `ruff`, `mypy`, `pytest --cov-fail-under=85`, migration-doc-check
- `docs/dev/` and `*.plan.md` files **never land on `main`** — `forbidden-paths-guard.yml` enforces this
- After a migration: run `document_tables.py` + `export_schema.sh`, commit updated `docs/database/`

---

## 10. Merged PRs (history)

| Branch | Scope | Status |
|--------|-------|--------|
| `feature/langgraph-postgres-checkpointer` | Postgres checkpointer wired into agent graph | **Merged PR #2** |
| `feature/nicegui-paywall-polish` | Device fingerprint auth, single-page SSE UX, post-payment polling, export gating | **Merged PR #3** |
| `feature/ai-resume-agents` | Multi-provider `AgentService`, section agents, variant schemas | **Merged PR #4** |
| `feature/ai-resume-ui` | Single-page UI improvements (tabs, score cards, fit panel) | **Merged PR #5** |
| `feature/stripe-paywall-399` | Repriced unlock from $9.99 to $3.99 | **Merged PR #6** |
| `feature/merge-input-analysis` | Combined JD+resume analysis into one LLM call | **Merged PR #7** |
| `feature/faster-llm-models` | Faster default models for every provider | **Merged PR #8** |
| `feature/backend-resume-upload-validation` | DOCX support + shared upload validation | **Merged PR #9** |
| `feature/variant-selector` | Tailoring style (conservative/balanced/bold) selector; single-variant builds by default | **Merged PR #10** |
| `feature/ui-runtime-fixes` | Upload/progress fixes, Stripe pricing display, Docker fixes | **Merged PR #11** |
| `fix/submit-analysis-stuck` | Fixed UI submit deadlock (in-process run launch), checkpointer migration on fresh DBs, Stripe verify fallback | **Merged PR #12** |
| `fix/resume-generation-quality` | 7-node pipeline, JD mirroring, before/after scores, 3-variant UI, fit assessment, style-preserving DOCX export | **Merged PR #20** |
| `fix/export-download-serve-direct` | Serve export downloads directly instead of redirecting to presigned S3 URL | **Merged PR #21** |
| `feature/section-copy-ui` | Per-section copy boxes with quirky quotes replacing monolithic output markdown | **Merged PR #22** |

## 10b. Open / Not Started

| Branch | Scope | Status |
|--------|-------|--------|
| `feature/database-schema-export` | `docs/database/schema.sql`, ER diagram, real `verify_docs` drift check in CI | **Not started** — `schema.sql` still doesn't exist; migration-doc test is a no-op |
| `feature/docker-ci-verify` | Validate `docker-compose.test.yml` in CI; fix image/test gaps | Not started |
| `feature/e2e-agent-tests` | Full agent E2E in Docker for `qa` promotion gate | Not started |
| `feature/github-branch-protection` | Branch protection rules doc + `gh` setup script | Not started |
| `feature/aws-infra-full` | Terraform/CDK: RDS, ElastiCache, S3, ALB, Secrets Manager | Not started |

> **UI architecture note:** The app is single-page only — one `@ui.page("/")` mounted at `/app/`. There is no `/app/dashboard` route. All output, scores, and fit assessment are on the same page. Scores are shown as a teaser even on locked runs using the `ats_score_before`/`ats_score_after` fields returned unconditionally by the API.

---

## 11. What Agents Must Not Do

- Run Alembic migrations on app startup — `migrate` is a separate Docker service
- Store JWTs anywhere except httpOnly cookies
- Return `AgentRun.final_output` when `AgentRun.output_locked = True`
- Add LLM calls to `prepare_inputs` or `format_output` nodes — `format_output` re-runs on every section edit; LLM coaching goes in `assess_fit` only
- Add a new LangGraph node without updating this document's §6 and the architecture plan
- Add a new `AgentTask` without adding it to **all 5 provider** `_TASK_MODELS` dicts
- Invent employer names, dates, degrees, certifications, titles, or metrics in rewrite prompts
- Commit `.env` or any secret file
- Merge `docs/dev/` into `main`
- Write a migration without updating `docs/database/tables/{table_name}.md`
- Use `git push --force` on shared branches
- Create a dashboard page — the app is single-page only; checkout stays as a popup dialog

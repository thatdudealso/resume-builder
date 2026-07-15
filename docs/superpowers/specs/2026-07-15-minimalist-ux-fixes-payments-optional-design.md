# ResumeBild: minimalist restyle, broken-flow fixes, optional payments

**Date:** 2026-07-15
**Branch:** `feature/minimalist-ux-fixes-payments-optional`
**Status:** design (pending review)

## Goal

Three coordinated workstreams on the ResumeBild single-page app:

- **A. Payments optional** - the app must run and be fully usable with no Stripe/crypto
  configuration, while keeping payments available when keys are present.
- **B. Fix broken flows** - a set of concrete defects found by live end-to-end testing
  (every provider, real resume) that break correctness and first-run experience.
- **C. Minimalist restyle in place** - modernize the visual design without changing the
  page structure or information architecture.

Constraints (from the product owner):
- Payments-off means **free and unlimited** runs, but keep **one subtle soft upsell**
  (a low-key "support this project" link), not a hard paywall.
- HuggingFace (and every provider) must **fail honestly** - never silently call a
  different vendor's model.
- Deliver all three workstreams in this pass.

## Findings that motivate this work

Verified live against `http://localhost:8000/app` using the real `Ashish_Gare_Resume_FDE.pdf`
and an FDE job description, driving a headless browser, across all five configured providers.

| Provider | API host actually called | Outcome |
|----------|--------------------------|---------|
| Hugging Face (default) | `api.anthropic.com` | Silent fallback to Claude on HF failure |
| OpenAI | `api.openai.com` | Clean, 51 -> 89 |
| Anthropic | `api.anthropic.com` | Clean |
| Google Gemini | `generativelanguage.googleapis.com` | Run failed on a single HTTP 429 (no retry) |
| xAI Grok | `api.x.ai` | Clean, 51 -> 84 |

Ranked defects:

1. **First-visit auth 401 (high).** `apps/web/ui/auth_guard.py` reads the
   `rb_device_fingerprint` cookie from the initial page-load request, but that cookie is
   only set by client-side JS (`workflow_session.py`) *after* that request completes. Every
   brand-new visitor gets 401 on `/auth/me`, `/billing/status`, `/resumes` and sees
   "Device workspace unavailable. Refresh this page." until they manually reload.
2. **HuggingFace silently calls Anthropic (high).** `packages/integrations/hf_inference.py`
   `_claude_fallback()` routes to Claude whenever HF inference fails or the circuit breaker
   is open. The user's provider choice becomes untrue and data crosses vendors silently.
3. **Gemini has no retry/backoff (medium-high).** `packages/agent/providers/gemini_provider.py`
   raises on the first 429/5xx. OpenAI/Grok/HF all retry; Gemini does not, so one transient
   rate-limit fails the whole run.
4. **Broken run-failure UX (medium).** On any run error the UI shows raw exception text,
   leaves the progress bar frozen mid-way, leaves "quirky quote" joke placeholders in the
   output panels, and leaves export buttons enabled with no real content.
5. **Garbled Skills section + stopword "requirements" (medium).** Output Skills render as
   fragments like "customer, act, between" and fit-assessment bullets cite stopwords
   ("missing must-have 'bridge' / 'against'") as requirements. JD/skills keyword extraction
   is pulling tokens/stopwords instead of real skills. Systemic across providers.
6. **MinIO bucket not auto-created (low-medium).** On a fresh volume, resume upload 500s with
   `NoSuchBucket`. Documented in the README but not automated, so first run fails.

## A. Payments optional

**Single chokepoint.** All paywall logic already funnels through
`packages/core/access/service.py` (`can_start_run`, `can_upload_resume`, `can_view_output`,
`can_export`) and `apps/web/services/run_launcher.py` (which sets `output_locked`). This is
the only place run-locking is decided, so the change is well-bounded.

**Config flag.** Add `payments_enabled: bool` to `apps/web/config.py`. Default is derived:
`True` only when at least one payment provider is configured
(`stripe_secret_key` or `nowpayments_api_key` present); otherwise `False`. An explicit env
override (`PAYMENTS_ENABLED=true|false`) takes precedence so the behavior is testable and
operators can force it either way.

**Behavior when `payments_enabled` is False:**
- `AccessService.can_start_run` always returns a non-locking decision (new
  `RunAccessMode.OPEN`, or reuse `FREE`); runs never set `output_locked=True`.
- `AccessService.can_upload_resume` always returns `True`.
- `can_view_output` / `can_export` return `True` for the owning user regardless of payment.
- Billing endpoints (`/billing/stripe/checkout`, `/stripe/verify`, `/crypto/invoice`) return
  `503 {"detail": "Payments are disabled on this server."}` rather than erroring obscurely.
- `/billing/status` returns `payments_enabled: false` plus the fields the UI needs.

**UI when payments are disabled:**
- Hide the paywall dialog, the Stripe and Crypto buttons, the price line, and any
  "payment required" status text.
- Never blur output or show the locked preview.
- Show **one subtle soft-upsell**: a single low-emphasis line/link (e.g. "Built by one dev -
  support this project" with a configurable URL from `SUPPORT_URL`). No modal, no nagging;
  it sits quietly beneath the output or in the footer. Hidden entirely if `SUPPORT_URL`
  is unset.

**When payments are enabled**, current behavior is unchanged.

## B. Broken-flow fixes

1. **First-visit auth.** Ensure a device identity exists on the very first server-rendered
   request rather than depending on a JS-set cookie that arrives too late. Approach: have the
   page-load path set the `rb_device_fingerprint` cookie server-side when absent (a stable
   server-generated value) so the first `/auth/me` call is authenticated, and keep the JS
   value as a fallback/enrichment. Acceptance: a fresh browser session with no cookies loads
   `/app` and shows account status (free-trial/workspace) with zero 401s and no manual reload.
2. **Honest provider behavior (HF).** Remove the cross-vendor `_claude_fallback` from
   `hf_inference.py`. HF retries a bounded number of times with backoff; on exhaustion it
   raises a provider error that surfaces as a clear user-facing message. No call to Anthropic
   from the HF path. Mock-completion fallback (offline/no key) stays, since it is clearly
   labeled and not a different paid vendor. (Confirm the same honesty for any other provider
   that has a hidden cross-vendor path.)
3. **Gemini retry.** Add the same bounded retry/backoff on 429 and 5xx that the other
   providers use, in `gemini_provider.py` (or a shared helper). Acceptance: a single transient
   429 no longer fails the run.
4. **Run-failure UX.** On run error the UI must: show a single clear, human error message
   (not a stack trace or raw provider text), reset/hide the progress bar, clear joke-placeholder
   text from output panels, and disable export buttons. Acceptance: forcing a provider error
   yields a clean error state with no leftover placeholder text and no enabled exports.
5. **Keyword extraction / Skills.** Fix JD-and-skills extraction so the Skills section
   contains real skills and fit-assessment "requirements" are real requirements, not stopword
   fragments. Root-cause in the analyst/extraction step (`packages/agent/analysts/*`,
   scoring/keyword logic). Acceptance: for the FDE resume+JD, Skills reads as a plausible
   comma/line list of real skills, and no fit bullet references a bare stopword as a
   "must-have".
6. **MinIO bucket bootstrap.** Ensure the configured `S3_BUCKET` exists before first upload -
   create-if-missing on startup (local/dev) or a documented one-shot init step wired into the
   compose `migrate`/startup path. Acceptance: `docker compose up` on a fresh volume allows a
   resume upload with no `NoSuchBucket`.

## C. Minimalist restyle (in place)

Keep the current single `/app` page, its two-column inputs/output layout, the three variant
tabs, and the step cards. Restyle only:

- **Form controls.** Replace or restyle the dated NiceGUI/Quasar upload widget (the blue
  progress block) and the `select` so they match the clean typographic hero: quiet borders,
  consistent radius, restrained color. Fix the "AI model" label overlapping its value on first
  paint.
- **Remove joke filler.** Drop the "quirky quotes" used as section placeholders; replace with
  quiet, functional empty/loading states.
- **Spacing and hierarchy.** Tighten the step cards and panels; consistent vertical rhythm;
  reduce visual noise so the page reads as deliberately minimal.
- **Palette/typography.** Preserve the existing restrained palette; ensure one accent color,
  consistent type scale, generous whitespace. No new heavy imagery or motion.

Non-goals for C: no IA changes, no new pages, no variant-tab rework, no framework swap.

## Testing

- **E2E (browser).** Re-run the full upload -> tailor -> score flow for all five providers
  with the real resume; assert no 401 on first visit, no cross-vendor calls, Gemini survives a
  429, clean error state on forced failure, real Skills content, and (payments off) no paywall
  UI plus a working export.
- **Unit.** Cover the `payments_enabled` decision matrix in `AccessService`; HF exhaustion
  raising (not calling Anthropic); Gemini retry; billing endpoints returning 503 when disabled.
- **Gate.** Keep the repo's >=85% coverage, ruff, and mypy green.

## Rollout / structure

- One feature branch, PR into `develop`.
- Work parallelizes into: (A) access/config/billing + UI gating, (B) provider/agent fixes +
  infra bucket + auth, (C) restyle. Each is independently reviewable; A and C touch
  `apps/web/ui/app.py` so they coordinate on that file.

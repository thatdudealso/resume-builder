# Minimalist UX, Broken-Flow Fixes, Optional Payments - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ResumeBild fully usable without payment configuration, fix six end-to-end defects found in live testing, and restyle the single page minimally in place.

**Architecture:** Payment gating already funnels through one class (`AccessService`) and one launcher (`run_launcher`); a single `payments_enabled` config flag toggles it, and the NiceGUI page (`apps/web/ui/app.py`) hides payment UI accordingly. Provider correctness fixes live in `packages/agent/providers/*` and `packages/agent/analysts/*`. The restyle is CSS/markup only in `app.py`.

**Tech Stack:** Python 3.12, FastAPI, NiceGUI, SQLAlchemy async, pydantic-settings, pytest, ruff, mypy. Runs in Docker Compose (postgres/redis/minio/web).

## Global Constraints

- Never use the em dash; use a plain dash `-`.
- Keep coverage >= 85% (`pytest --cov=packages --cov=apps --cov-fail-under=85`), ruff clean, mypy clean.
- No new hard dependency on any payment provider; the app must boot and run with all payment keys empty.
- Providers must never silently call a different vendor's API.
- Default provider is `openai` (was `huggingface`).
- Soft-upsell link only renders when `SUPPORT_URL` is set; never a modal or blocking prompt.
- Run all commands with the test env matching the README "Local venv" block, or inside `docker compose -f docker-compose.test.yml run --rm test`.

---

## File map

- `apps/web/config.py` - add `payments_enabled`, `support_url` settings (A1).
- `packages/core/access/service.py` - honor `payments_enabled` (A2).
- `apps/web/api/v1/billing.py` - 503 when disabled, expose flag (A3).
- `apps/web/ui/app.py` - hide payment UI + soft upsell (A4), failure UX (B5), restyle (C1).
- `apps/web/dependencies.py` - server-side fingerprint cookie (B1).
- `apps/web/main.py` - set fingerprint cookie on `/app` load if absent (B1).
- `packages/integrations/hf_inference.py` - remove cross-vendor fallback (B2).
- `packages/agent/schemas/providers.py` - default provider -> OpenAI (B3).
- `packages/agent/providers/gemini_provider.py` - retry/backoff (B4).
- `packages/agent/analysts/input_analyst.py`, `jd_analyst.py`, `resume_analyst.py` - stop silent fallback, fix schema mismatch, harden fallback (B6).
- `apps/web/services/s3_bootstrap.py` (new) + `apps/web/main.py` - bucket bootstrap (B7).
- Tests under `tests/unit/...` and `tests/e2e/...` per task.

---

## Workstream A - Payments optional

### Task A1: Add `payments_enabled` and `support_url` settings

**Files:**
- Modify: `apps/web/config.py`
- Test: `tests/unit/apps/test_settings_payments.py`

**Interfaces:**
- Produces: `settings.payments_enabled: bool`, `settings.support_url: str`.
  `payments_enabled` defaults to `True` only if `stripe_secret_key` or
  `nowpayments_api_key` is non-empty; an explicit `PAYMENTS_ENABLED` env var overrides.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/apps/test_settings_payments.py
from apps.web.config import Settings


def test_payments_disabled_when_no_keys():
    s = Settings(stripe_secret_key="", nowpayments_api_key="")
    assert s.payments_enabled is False


def test_payments_enabled_when_stripe_key_present():
    s = Settings(stripe_secret_key="sk_live_x", nowpayments_api_key="")
    assert s.payments_enabled is True


def test_explicit_override_wins():
    s = Settings(stripe_secret_key="sk_live_x", payments_enabled_override="false")
    assert s.payments_enabled is False
    s2 = Settings(stripe_secret_key="", payments_enabled_override="true")
    assert s2.payments_enabled is True


def test_support_url_defaults_empty():
    assert Settings().support_url == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/apps/test_settings_payments.py -v`
Expected: FAIL (`payments_enabled` / `support_url` / `payments_enabled_override` do not exist).

- [ ] **Step 3: Implement the settings**

In `apps/web/config.py`, add fields after `run_unlock_price_usd` and a property:

```python
    run_unlock_price_usd: float = 3.99
    support_url: str = ""
    # Empty string = auto-derive from configured payment providers.
    payments_enabled_override: str = ""

    @property
    def payments_enabled(self) -> bool:
        override = self.payments_enabled_override.strip().lower()
        if override in ("true", "1", "yes"):
            return True
        if override in ("false", "0", "no"):
            return False
        stripe_ok = bool((self.stripe_secret_key or "").strip())
        crypto_ok = bool((self.nowpayments_api_key or "").strip())
        return stripe_ok or crypto_ok
```

Add `PAYMENTS_ENABLED` mapping: pydantic-settings maps env `PAYMENTS_ENABLED` to
`payments_enabled_override` via an alias. Add to the field:

```python
    from pydantic import Field  # top of file with other imports
    payments_enabled_override: str = Field(default="", alias="PAYMENTS_ENABLED")
```

Keep `model_config` with `extra="ignore"` and add `populate_by_name=True`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/apps/test_settings_payments.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/web/config.py tests/unit/apps/test_settings_payments.py
git commit -m "feat(config): add payments_enabled flag and support_url"
```

### Task A2: AccessService honors `payments_enabled`

**Files:**
- Modify: `packages/core/access/service.py`
- Test: `tests/unit/core/test_access_payments_disabled.py`

**Interfaces:**
- Consumes: `settings.payments_enabled` (A1).
- Produces: when payments disabled, `can_start_run` returns `RunAccessMode.FREE`,
  `can_upload_resume` returns `True`, `can_view_output`/`can_export` return `True`
  for the owning user.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/core/test_access_payments_disabled.py
import pytest
from unittest.mock import patch
from packages.core.access.service import AccessService
from packages.core.schemas.access import RunAccessMode


@pytest.mark.asyncio
async def test_can_start_run_free_when_payments_disabled(db_session, used_trial_user):
    access = AccessService(db_session)
    with patch("packages.core.access.service.settings") as s:
        s.payments_enabled = False
        decision = await access.can_start_run(used_trial_user.id)
    assert decision.mode == RunAccessMode.FREE


@pytest.mark.asyncio
async def test_can_upload_true_when_payments_disabled(db_session, used_trial_user):
    access = AccessService(db_session)
    with patch("packages.core.access.service.settings") as s:
        s.payments_enabled = False
        assert await access.can_upload_resume(used_trial_user.id) is True
```

Use the existing test fixtures for `db_session` and a user with `free_trial_used=True`
(fixture `used_trial_user` - add to `tests/conftest.py` if absent, mirroring existing
user fixtures).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/core/test_access_payments_disabled.py -v`
Expected: FAIL (`can_start_run` returns `LOCKED`).

- [ ] **Step 3: Implement the gate**

In `packages/core/access/service.py`, add the import and short-circuits:

```python
from apps.web.config import settings
```

In `can_start_run`, immediately after loading `user` and the `None` check:

```python
        if not settings.payments_enabled:
            return RunAccessDecision(mode=RunAccessMode.FREE)
```

At the top of `can_upload_resume`:

```python
        if not settings.payments_enabled:
            return True
```

In `can_view_output`, after the `run.user_id != user_id` ownership check:

```python
        if not settings.payments_enabled:
            return True
```

In `can_export`, keep the `can_view_output` gate; add after it:

```python
        if not settings.payments_enabled:
            return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/core/test_access_payments_disabled.py tests/unit/core -v`
Expected: PASS, and no regression in existing access tests.

- [ ] **Step 5: Commit**

```bash
git add packages/core/access/service.py tests/unit/core/test_access_payments_disabled.py tests/conftest.py
git commit -m "feat(access): bypass paywall when payments disabled"
```

### Task A3: Billing endpoints disabled-safe + status flag

**Files:**
- Modify: `apps/web/api/v1/billing.py`
- Test: `tests/unit/apps/test_billing_disabled.py`

**Interfaces:**
- Consumes: `settings.payments_enabled` (A1).
- Produces: `/billing/status` response includes `"payments_enabled": bool` and
  `"support_url": str`; `/billing/stripe/checkout`, `/billing/stripe/verify`,
  `/billing/crypto/invoice` return HTTP 503 `{"detail": "Payments are disabled on this server."}`
  when disabled.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/apps/test_billing_disabled.py
import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_checkout_503_when_disabled(client_with_device):
    with patch("apps.web.api.v1.billing.settings") as s:
        s.payments_enabled = False
        resp = await client_with_device.post(
            "/api/v1/billing/stripe/checkout", json={"run_id": "00000000-0000-0000-0000-000000000000"}
        )
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Payments are disabled on this server."


@pytest.mark.asyncio
async def test_status_reports_flag(client_with_device):
    with patch("apps.web.api.v1.billing.settings") as s:
        s.payments_enabled = False
        s.run_unlock_price_usd = 3.99
        s.support_url = ""
        resp = await client_with_device.get("/api/v1/billing/status")
    body = resp.json()
    assert body["payments_enabled"] is False
    assert "support_url" in body
```

Use the existing authenticated-client fixture (mirror how other billing/API tests build a
device-authenticated `AsyncClient`; name it `client_with_device` in `conftest.py` if not present).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/apps/test_billing_disabled.py -v`
Expected: FAIL (checkout attempts Stripe; status lacks `payments_enabled`).

- [ ] **Step 3: Implement the guard**

In `apps/web/api/v1/billing.py`, add a helper and use it:

```python
from fastapi import status as http_status

def _require_payments_enabled() -> None:
    if not settings.payments_enabled:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payments are disabled on this server.",
        )
```

Call `_require_payments_enabled()` as the first line of `stripe_checkout`, `stripe_verify`,
and `crypto_invoice`. In `billing_status`, add to the returned dict:

```python
        "payments_enabled": settings.payments_enabled,
        "support_url": settings.support_url,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/apps/test_billing_disabled.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/web/api/v1/billing.py tests/unit/apps/test_billing_disabled.py tests/conftest.py
git commit -m "feat(billing): 503 when payments disabled; expose flag in status"
```

### Task A4: UI hides payment controls + renders soft upsell

**Files:**
- Modify: `apps/web/ui/app.py`
- Test: `tests/e2e/ui/test_payments_disabled_ui.py` (or extend the existing UI E2E harness)

**Interfaces:**
- Consumes: `/billing/status` fields `payments_enabled`, `support_url` (A3).
- Produces: when `payments_enabled` is false, the paywall dialog never opens, the Stripe/Crypto
  buttons and price line are hidden, output is never blurred, and a single low-emphasis
  `support_url` link renders (only if `support_url` is non-empty).

- [ ] **Step 1: Write the failing test**

Add an E2E test following the repo's existing UI test pattern (NiceGUI test client). Assert:
after loading `/`, with `payments_enabled=False` in the mocked `/billing/status`, the page has
no element containing text "Unlock for" and no "Stripe" button; and with `support_url` set, an
anchor with that href exists. If the repo has no NiceGUI UI test harness, implement this
assertion as a headless-browser check documented in the task's manual-verification step and
add a focused unit test on a new pure helper instead (see Step 3).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/e2e/ui/test_payments_disabled_ui.py -v`
Expected: FAIL (payment controls always render today).

- [ ] **Step 3: Implement UI gating**

In `apps/web/ui/app.py`, capture the flag in `load_account` from the billing response:

```python
        state["payments_enabled"] = billing.get("payments_enabled", True)
        state["support_url"] = billing.get("support_url", "")
```

Gate every payment surface on `state["payments_enabled"]`:
- In `load_account`, when `not state["payments_enabled"]`: call `paywall_price.set_visibility(False)`
  and do not set the "Unlock" status text (set a neutral status like
  `f"Free workspace - {free_label} runs"`).
- Wrap the paywall trigger: in `refresh_run`, guard the `paywall_dialog.open()` calls with
  `if state.get("payments_enabled", True):` so the dialog never opens when disabled, and never
  add `rb-locked` / never set the locked preview when disabled.
- Hide the dialog's buttons block by calling `stripe_button.set_visibility(False)` and
  `crypto_button.set_visibility(False)` when disabled (belt-and-suspenders).
- Add a soft-upsell element created once after `payment_status`:

```python
            support_link = ui.link("", "").classes("rb-subtle").style("margin-top:8px;")
            support_link.set_visibility(False)
```

  In `load_account`, when disabled and `state["support_url"]`:

```python
        if not state["payments_enabled"] and state["support_url"]:
            support_link.text = "Built by one developer - support this project"
            support_link.target = "_blank"
            support_link._props["href"] = state["support_url"]
            support_link.update()
            support_link.set_visibility(True)
```

- [ ] **Step 4: Run the app and verify manually**

Bring the stack up with payments unset (`PAYMENTS_ENABLED=false`), drive the flow with the
`browser-e2e-testing` skill's `chromium-cli`, and confirm: no paywall dialog on a 2nd run,
no Stripe/Crypto buttons, output not blurred, one quiet support link present.

```bash
chromium-cli --session pay-off <<'EOF'
set-cookie rb_device_fingerprint verify-pay-off localhost:8000
nav http://localhost:8000/app
nav http://localhost:8000/app
wait-for "text=Free workspace" 8000
screenshot payments_off
console --errors
EOF
```

Read `~/.local/state/chromium-cli/sessions/pay-off/screenshots/payments_off.png`.

- [ ] **Step 5: Commit**

```bash
git add apps/web/ui/app.py tests/e2e/ui/test_payments_disabled_ui.py
git commit -m "feat(ui): hide payment controls and show soft upsell when payments disabled"
```

---

## Workstream B - Broken-flow fixes

### Task B1: First-visit auth - server-set fingerprint cookie

**Files:**
- Modify: `apps/web/main.py` (page-load path for `/app`)
- Modify: `apps/web/dependencies.py`
- Test: `tests/unit/apps/test_first_visit_auth.py`

**Interfaces:**
- Produces: on the first GET of the NiceGUI page with no `rb_device_fingerprint` cookie,
  the server sets a stable `rb_device_fingerprint` cookie so the first `/auth/me` call is
  authenticated. `_request_fingerprint` in `dependencies.py` already reads header or cookie;
  behavior unchanged when a cookie exists.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/apps/test_first_visit_auth.py
import pytest


@pytest.mark.asyncio
async def test_app_load_sets_fingerprint_cookie(raw_client):
    resp = await raw_client.get("/app/", follow_redirects=True)
    assert "rb_device_fingerprint=" in resp.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_auth_me_ok_with_that_cookie(raw_client):
    load = await raw_client.get("/app/", follow_redirects=True)
    cookie = load.cookies.get("rb_device_fingerprint")
    assert cookie
    me = await raw_client.get("/api/v1/auth/me", cookies={"rb_device_fingerprint": cookie})
    assert me.status_code == 200
```

`raw_client` = an `AsyncClient` against the app with no preset auth (add to conftest if absent).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/apps/test_first_visit_auth.py -v`
Expected: FAIL (no cookie set on load; `/auth/me` 401).

- [ ] **Step 3: Implement server-side cookie**

Add a lightweight middleware or route hook in `apps/web/main.py` that, for GET requests whose
path starts with `/app`, sets `rb_device_fingerprint` on the response if the request has none:

```python
import secrets
from starlette.middleware.base import BaseHTTPMiddleware

class DeviceFingerprintMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/app") and not request.cookies.get("rb_device_fingerprint"):
            token = f"srv-{secrets.token_hex(8)}"
            response.set_cookie(
                "rb_device_fingerprint", token, max_age=31536000,
                samesite="lax", path="/", secure=settings.cookie_secure,
            )
        return response

app.add_middleware(DeviceFingerprintMiddleware)
```

Keep the existing client-side JS fingerprint as enrichment; the server cookie guarantees the
first API call is authenticated. Confirm `_request_fingerprint` (dependencies.py) already reads
`request.cookies.get("rb_device_fingerprint")` (it does) - no change needed there.

- [ ] **Step 4: Run tests + manual E2E**

Run: `pytest tests/unit/apps/test_first_visit_auth.py -v` -> PASS.
Then a fresh browser session (no set-cookie) via `chromium-cli`:

```bash
chromium-cli --session first-visit <<'EOF'
nav http://localhost:8000/app
wait-for "text=Free trial" 8000
screenshot first_visit_ok
console --errors
EOF
```

Expected: account status shows on the FIRST load (no "Device workspace unavailable"), and
`docker logs resumebild-web-1` shows `/api/v1/auth/me` 200 (not 401) on first load.

- [ ] **Step 5: Commit**

```bash
git add apps/web/main.py tests/unit/apps/test_first_visit_auth.py
git commit -m "fix(auth): set device fingerprint cookie on first app load"
```

### Task B2: HuggingFace fails honestly (no cross-vendor fallback)

**Files:**
- Modify: `packages/integrations/hf_inference.py`
- Test: `tests/unit/agent/test_hf_no_cross_vendor.py`

**Interfaces:**
- Produces: on HF failure/circuit-open, `complete()` either returns the labeled mock (no key)
  or raises `HFInferenceError`; it never calls Anthropic. Removes `_claude_fallback` and the
  `ANTHROPIC_OPUS_MODEL` import.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/agent/test_hf_no_cross_vendor.py
import inspect
import pytest
import packages.integrations.hf_inference as hf


def test_no_anthropic_reference_in_source():
    src = inspect.getsource(hf)
    assert "anthropic" not in src.lower()


@pytest.mark.asyncio
async def test_raises_on_exhausted_retries(monkeypatch):
    monkeypatch.setattr(hf.settings, "hf_token", "x")

    class Boom:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **k): raise hf.httpx.HTTPError("down")

    monkeypatch.setattr(hf.httpx, "AsyncClient", lambda *a, **k: Boom())
    with pytest.raises(hf.HFInferenceError):
        await hf.complete(model="m", prompt="p", node="analyze_inputs")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/agent/test_hf_no_cross_vendor.py -v`
Expected: FAIL (`anthropic` present; returns Claude output instead of raising).

- [ ] **Step 3: Implement honest failure**

In `packages/integrations/hf_inference.py`: delete the `_claude_fallback` function and the
`from packages.agent.providers.anthropic_provider import ANTHROPIC_OPUS_MODEL` import. Replace
every `return await _claude_fallback(prompt, node)` with:
- if `not settings.hf_token`: `return await _mock_response(prompt, node)` (offline/no key only);
- otherwise: `raise HFInferenceError("Hugging Face inference failed after retries")`.

The circuit-open branch at the top becomes: if `not settings.hf_token` return mock, else
`raise HFInferenceError("Hugging Face temporarily unavailable")`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/agent/test_hf_no_cross_vendor.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/integrations/hf_inference.py tests/unit/agent/test_hf_no_cross_vendor.py
git commit -m "fix(providers): HuggingFace fails honestly instead of calling Anthropic"
```

### Task B3: Default provider -> OpenAI

**Files:**
- Modify: `packages/agent/schemas/providers.py`
- Modify: `apps/web/ui/app.py` (remove hardcoded `"huggingface"` fallback in `load_providers`)
- Test: `tests/unit/agent/test_default_provider.py`

**Interfaces:**
- Produces: `DEFAULT_PROVIDER == LLMProviderName.OPENAI`. `/runs/providers` marks OpenAI
  `is_default: true`. UI dropdown default uses the API `is_default`, falling back to the first
  configured option (not a hardcoded provider name).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/agent/test_default_provider.py
from packages.agent.schemas.providers import DEFAULT_PROVIDER, LLMProviderName


def test_default_is_openai():
    assert DEFAULT_PROVIDER == LLMProviderName.OPENAI
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/agent/test_default_provider.py -v`
Expected: FAIL (default is `HUGGINGFACE`).

- [ ] **Step 3: Implement**

In `packages/agent/schemas/providers.py`:

```python
DEFAULT_PROVIDER = LLMProviderName.OPENAI
```

In `apps/web/ui/app.py` `load_providers`, replace the hardcoded fallbacks so the default is the
API-provided `is_default`, else the first configured option:

```python
        default = next((p["id"] for p in providers if p.get("is_default")), None)
        if default not in options:
            default = next(iter(options)) if options else None
        provider_select.value = default
```

And the earlier error branch `options = {"huggingface": "Hugging Face"}` stays only as the
no-response safety net (leave as-is).

- [ ] **Step 4: Run tests + confirm**

Run: `pytest tests/unit/agent/test_default_provider.py tests/unit/agent -v` -> PASS.
Confirm `curl -s localhost:8000/api/v1/runs/providers` shows `"id":"openai","is_default":true`.

- [ ] **Step 5: Commit**

```bash
git add packages/agent/schemas/providers.py apps/web/ui/app.py tests/unit/agent/test_default_provider.py
git commit -m "feat(providers): default to OpenAI; UI uses API default not hardcoded"
```

### Task B4: Gemini retry/backoff

**Files:**
- Modify: `packages/agent/providers/gemini_provider.py`
- Test: `tests/unit/agent/test_gemini_retry.py`

**Interfaces:**
- Produces: `GeminiProvider.complete` retries on HTTP 429 and >=500 with exponential backoff
  (3 attempts) before raising; a single transient 429 succeeds on retry.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/agent/test_gemini_retry.py
import pytest
import httpx
from packages.agent.providers.gemini_provider import GeminiProvider


class _Resp:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload or {}
    def json(self): return self._payload
    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("e", request=None, response=self)


@pytest.mark.asyncio
async def test_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr("packages.agent.providers.gemini_provider.settings.gemini_api_key", "k")
    calls = {"n": 0}
    good = {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **k):
            calls["n"] += 1
            return _Resp(429) if calls["n"] == 1 else _Resp(200, good)

    monkeypatch.setattr("packages.agent.providers.gemini_provider.httpx.AsyncClient",
                        lambda *a, **k: Client())
    monkeypatch.setattr("packages.agent.providers.gemini_provider.asyncio.sleep",
                        lambda *_a, **_k: __import__("asyncio").sleep(0))
    from packages.agent.providers.base import AgentTask
    out = await GeminiProvider().complete(AgentTask.JD_ANALYSIS, "p")
    assert out == "ok"
    assert calls["n"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/agent/test_gemini_retry.py -v`
Expected: FAIL (first 429 raises immediately).

- [ ] **Step 3: Implement retry**

In `gemini_provider.py`, add `import asyncio`, and wrap the POST in a 3-attempt loop:

```python
        last_exc: Exception | None = None
        for attempt in range(3):
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.post(url, json=payload)
            if resp.status_code == 429 or resp.status_code >= 500:
                last_exc = RuntimeError(f"Gemini request failed with status {resp.status_code}")
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise last_exc
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError:
                raise RuntimeError(
                    f"Gemini request failed with status {resp.status_code}"
                ) from None
            data = resp.json()
            break
```

Keep the existing candidates/parts extraction after the loop.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/agent/test_gemini_retry.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/agent/providers/gemini_provider.py tests/unit/agent/test_gemini_retry.py
git commit -m "fix(providers): retry Gemini on 429/5xx with backoff"
```

### Task B5: Clean run-failure UX

**Files:**
- Modify: `apps/web/ui/app.py`
- Test: manual E2E (forced provider error) + existing UI tests stay green

**Interfaces:**
- Consumes: the `{"event": "error", "message": ...}` progress item and the `result == "error"`
  path already present in `tailor()`.
- Produces: on run error the UI shows one human message, resets the progress bar to 0/hidden,
  clears joke-placeholder text from all variant panels, and disables export buttons.

- [ ] **Step 1: Add a helper and reset logic**

In `apps/web/ui/app.py`, add a helper near the other helpers:

```python
    def _show_run_error(message: str) -> None:
        clean = message.strip() or "Something went wrong generating your resume."
        # Never surface raw provider/stack text
        if len(clean) > 160 or "Traceback" in clean:
            clean = "The AI provider could not complete this run. Try again or pick another model."
        progress.value = 0
        progress_label.set_text("Run failed")
        payment_status.set_text(clean)
        payment_status.classes(remove="rb-subtle")
        payment_status.classes(add="rb-danger")
        export_row.classes(add="hidden")
        for _vn in _variant_wrappers:
            for _sk in SECTION_KEYS:
                _variant_sections[_vn][_sk].set_content("")
        _variant_sections["balanced"]["summary"].set_content("")
```

- [ ] **Step 2: Wire it into the error paths**

In `tailor()`, where `result == "error"` is handled, replace the current
`await refresh_run(show_paywall=False)` on the error branch with a call that reads the queued
error message and calls `_show_run_error(...)`. In `stream_progress`, capture the error message
text so `tailor()` can pass it. Concretely, after `run_button.props(remove="loading")` in the
`result == "error"` branch:

```python
            if result == "error":
                await _show_run_error(state.get("last_error") or "")
                return
```

And in the `on_progress`/`watch_run_progress` handling, store `state["last_error"] = item["message"]`
when `item["event"] == "error"` (add this in `run_progress.watch_run_progress`'s update callback
via the existing `_update` closure, or set it where the error event is observed).

- [ ] **Step 3: Manual E2E with a forced error**

Temporarily set an invalid key for one provider (e.g. run with `GEMINI_API_KEY=bad` and select
Gemini after B4 exhausts retries) and drive via `chromium-cli`:

```bash
chromium-cli --session fail-ux <<'EOF'
set-cookie rb_device_fingerprint fail-ux-1 localhost:8000
nav http://localhost:8000/app
nav http://localhost:8000/app
wait-for "text=Free trial" 8000
set-input-files "input[type=file]" /Users/thatdudealso/Resume/Ashish_Gare_Resume_FDE.pdf
wait-for "text=Resume: Ashish_Gare" 15000
fill textarea "Test JD for forced provider failure with at least twenty characters."
click "text=Tailor resume"
wait-for "text=Run failed" 60000
screenshot fail_state
console --errors
EOF
```

Read the screenshot: assert one clean message, progress at 0/"Run failed", no joke-quote text
in panels, export row hidden.

- [ ] **Step 4: Ensure suite green**

Run: `pytest tests/e2e/ui tests/unit/apps -v`
Expected: no regressions.

- [ ] **Step 5: Commit**

```bash
git add apps/web/ui/app.py apps/web/ui/run_progress.py
git commit -m "fix(ui): clean, non-technical run-failure state"
```

### Task B6: Fix garbled Skills / stopword requirements (systematic-debugging)

**Files:**
- Modify: `packages/agent/analysts/input_analyst.py`
- Modify: `packages/agent/analysts/jd_analyst.py`, `resume_analyst.py` (fallback hardening)
- Test: `tests/unit/agent/test_input_analysis_no_silent_fallback.py`

**REQUIRED SUB-SKILL:** Use `superpowers:systematic-debugging`. Root cause is confirmed:
`analyze_inputs_combined` wraps LLM parse + `model_validate` in `except Exception: pass`, so any
schema mismatch silently falls back to `fallback_jd_analysis`, whose `must_have` is raw
single-word tokens from `extract_keywords` (producing "customer, act, between" as skills).

**Interfaces:**
- Produces: `analyze_inputs_combined` logs (does not swallow) parse/validate failures; when the
  LLM JSON is valid it is used; the fallback `must_have` no longer emits bare stopwords.

- [ ] **Step 1: Reproduce - add a logging assertion test**

```python
# tests/unit/agent/test_input_analysis_no_silent_fallback.py
import logging
import pytest
from packages.agent.analysts import input_analyst
from packages.agent.schemas.providers import LLMProviderName
from packages.agent.providers.registry import get_provider


@pytest.mark.asyncio
async def test_combined_logs_when_llm_json_rejected(caplog, monkeypatch):
    provider = get_provider(LLMProviderName.OPENAI)
    async def bad(*a, **k): return '{"jd_analysis": {"bogus": 1}, "resume_analysis": {}}'
    monkeypatch.setattr(provider, "complete", bad)
    monkeypatch.setattr(provider, "is_configured", lambda: True)
    with caplog.at_level(logging.WARNING):
        await input_analyst.analyze_inputs_combined("jd text here", "resume text", provider)
    assert any("combined input analysis" in r.message.lower() for r in caplog.records)
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/unit/agent/test_input_analysis_no_silent_fallback.py -v`
Expected: FAIL (no log emitted; exception silently swallowed).

- [ ] **Step 3: Stop swallowing; log with a raw snippet**

In `packages/agent/analysts/input_analyst.py`, add a module logger and replace
`except Exception: pass` with a logged fallback:

```python
import logging
logger = logging.getLogger(__name__)
...
        except Exception as exc:
            logger.warning(
                "Combined input analysis LLM parse/validate failed (%s); using fallback. raw=%.300s",
                exc, locals().get("raw", ""),
            )
```

Apply the same logging (not silent `pass`) in `jd_analyst.analyze_jd` and
`resume_analyst.analyze_resume` fallback branches.

- [ ] **Step 4: Run the real analysis, read the logged mismatch, fix it**

Bring the stack up, run one real tailor via `chromium-cli` (OpenAI), then:

```bash
docker logs resumebild-web-1 2>&1 | grep -i "input analysis"
```

The log reveals the exact `pydantic` validation error (e.g. `keywords_weighted` item shape, or
`requirement_evidence` status enum). Adjust the `COMBINED_INPUT_PROMPT` wording and/or the
`JDAnalysis`/`ResumeAnalysis` schema coercion so the model's valid output validates. Add a
regression unit test that feeds a representative real LLM JSON payload (captured from the log)
through `JDAnalysis.model_validate(data["jd_analysis"])` and asserts `must_have[0].requirement`
is a multi-word phrase, not a single stopword.

- [ ] **Step 5: Harden the fallback (defense in depth)**

In `jd_analyst.fallback_jd_analysis`, stop emitting bare single tokens as requirements: filter
`extract_keywords` output to terms length >= 4 and drop a small stopword set
(`{"between","against","within","across","customer"}` plus the existing set in
`state.extract_keywords`), and label fallback requirements clearly (e.g. prefix category
`"other"`). Add/extend `state.extract_keywords`'s stop set accordingly. Add a unit test:

```python
def test_fallback_requirements_are_not_bare_stopwords():
    from packages.agent.analysts.jd_analyst import fallback_jd_analysis
    jd = "Act as the technical bridge between engineering and enterprise customers."
    a = fallback_jd_analysis(jd)
    reqs = {r.requirement for r in a.must_have}
    assert "between" not in reqs and "act" not in reqs
```

- [ ] **Step 6: Full E2E confirmation across providers**

Re-run the tailor flow for OpenAI and Grok; assert the Skills section reads as real skills and
no fit bullet cites a bare stopword. Verify with screenshots.

- [ ] **Step 7: Commit**

```bash
git add packages/agent/analysts/ packages/agent/state.py tests/unit/agent/test_input_analysis_no_silent_fallback.py
git commit -m "fix(agent): stop silent analysis fallback; fix garbled skills/requirements"
```

### Task B7: MinIO bucket bootstrap

**Files:**
- Create: `apps/web/services/s3_bootstrap.py`
- Modify: `apps/web/main.py` (startup)
- Test: `tests/unit/apps/test_s3_bootstrap.py`

**Interfaces:**
- Produces: `ensure_bucket_exists()` creates `settings.s3_bucket` if missing (idempotent,
  local/dev only - guarded by `settings.s3_endpoint` being set, i.e. MinIO/local, not AWS).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/apps/test_s3_bootstrap.py
from unittest.mock import MagicMock, patch
from apps.web.services.s3_bootstrap import ensure_bucket_exists


def test_creates_bucket_when_missing():
    client = MagicMock()
    client.head_bucket.side_effect = Exception("404")
    with patch("apps.web.services.s3_bootstrap._client", return_value=client), \
         patch("apps.web.services.s3_bootstrap.settings") as s:
        s.s3_endpoint = "http://minio:9000"
        s.s3_bucket = "resume-builder"
        ensure_bucket_exists()
    client.create_bucket.assert_called_once()


def test_skips_when_no_endpoint():
    client = MagicMock()
    with patch("apps.web.services.s3_bootstrap._client", return_value=client), \
         patch("apps.web.services.s3_bootstrap.settings") as s:
        s.s3_endpoint = None
        ensure_bucket_exists()
    client.create_bucket.assert_not_called()
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/unit/apps/test_s3_bootstrap.py -v`
Expected: FAIL (module does not exist).

- [ ] **Step 3: Implement bootstrap (reuse existing S3 client construction)**

Create `apps/web/services/s3_bootstrap.py` mirroring how `packages/integrations/s3_storage.py`
builds its boto3 client:

```python
from __future__ import annotations
import logging
from apps.web.config import settings
from packages.integrations import s3_storage

logger = logging.getLogger(__name__)


def _client():
    return s3_storage._s3_client()  # reuse existing constructor


def ensure_bucket_exists() -> None:
    if not settings.s3_endpoint:  # AWS/prod manages buckets out of band
        return
    client = _client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except Exception:
        logger.info("Creating missing S3 bucket %s", settings.s3_bucket)
        client.create_bucket(Bucket=settings.s3_bucket)
```

If `s3_storage` has no `_s3_client()` helper, extract the client construction there into one and
call it from both places (DRY). Wire into `apps/web/main.py` startup:

```python
@app.on_event("startup")
async def _bootstrap_bucket():
    from apps.web.services.s3_bootstrap import ensure_bucket_exists
    ensure_bucket_exists()
```

- [ ] **Step 4: Run test + fresh-volume E2E**

Run: `pytest tests/unit/apps/test_s3_bootstrap.py -v` -> PASS.
Then `docker compose down -v && docker compose up -d`, wait for health, upload the FDE resume
via `chromium-cli` and confirm no `NoSuchBucket` in `docker logs resumebild-web-1`.

- [ ] **Step 5: Commit**

```bash
git add apps/web/services/s3_bootstrap.py apps/web/main.py packages/integrations/s3_storage.py tests/unit/apps/test_s3_bootstrap.py
git commit -m "fix(storage): auto-create S3 bucket on startup for local/dev"
```

---

## Workstream C - Minimalist restyle (in place)

### Task C1: Restyle form controls, remove joke filler, tighten hierarchy

**Files:**
- Modify: `apps/web/ui/app.py` (the `_install_page_shell` `<style>` block, the upload/select
  markup, and placeholder text constants)
- Test: manual pixel review via `chromium-cli` screenshots

**Interfaces:**
- Consumes: none new.
- Produces: unified minimal styling; no functional/API/IA change.

- [ ] **Step 1: Remove joke-quote filler**

Delete `_RESUME_QUOTES` usage as section filler. Replace every
`random.choice(_RESUME_QUOTES)` with `""` (empty) or a single quiet loading/empty string
constant `_EMPTY_SECTION = ""`. Remove the now-unused `random` import if nothing else uses it.

- [ ] **Step 2: Restyle the AI-model select and fix label overlap**

In `_install_page_shell`'s `<style>`, add rules so the select label doesn't overlap its value on
first paint and controls match the hero:

```css
          .q-field--float .q-field__label { transform: translateY(-40%) scale(0.75); }
          .q-field__control { background: var(--rb-panel); }
          .rb-panel .q-field__control:before { border-color: var(--rb-line); }
```

- [ ] **Step 3: Restyle / de-emphasize the upload widget**

Add CSS to make the NiceGUI upload block quiet (no bright blue bar): neutral background,
`var(--rb-line)` border, `var(--rb-accent)` only for the confirmed-check state:

```css
          .q-uploader { box-shadow: none; border: 1px dashed var(--rb-line); border-radius: 8px; }
          .q-uploader__header { background: var(--rb-panel); color: var(--rb-ink); }
          .q-uploader__title { font-size: 13px; }
```

- [ ] **Step 4: Tighten spacing / hierarchy**

Reduce the proof-step card padding and unify gaps; ensure one accent color and consistent
radius (8-10px) already defined in `:root`. Adjust `.rb-proof` gap to `12px`, `.rb-soft` padding
to `12px 14px` (verify against current values; only change if inconsistent).

- [ ] **Step 5: Pixel review**

Drive the app and screenshot the key states (empty, uploaded, completed) via `chromium-cli`;
Read each screenshot and confirm: no joke text anywhere, no label overlap, upload widget reads
as minimal, consistent spacing. Iterate on CSS until it looks deliberately minimal.

```bash
chromium-cli --session restyle <<'EOF'
set-cookie rb_device_fingerprint restyle-1 localhost:8000
nav http://localhost:8000/app
nav http://localhost:8000/app
wait-for "text=Free trial" 8000
screenshot restyle_empty
console --errors
EOF
```

- [ ] **Step 6: Commit**

```bash
git add apps/web/ui/app.py
git commit -m "style(ui): minimalist in-place restyle; remove joke-quote filler"
```

---

## Final verification (after all tasks)

- [ ] Full test suite + gate: `docker compose -f docker-compose.test.yml run --rm test`
      (ruff, mypy, `pytest --cov-fail-under=85`). All green.
- [ ] E2E all five providers via `chromium-cli` with the real FDE resume: no first-visit 401,
      no cross-vendor calls (grep `docker logs` per provider), Gemini survives a 429, clean
      error state on forced failure, real Skills content, and (payments off) no paywall + working
      export + one soft-upsell link.
- [ ] Revert any local-only `docker-compose.yml` port edits before opening the PR.
- [ ] Open PR into `develop`; run the repo's `no-mistakes` gate.

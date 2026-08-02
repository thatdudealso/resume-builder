from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import UUID

from nicegui import ui
from nicegui.storage import request_contextvar

from apps.web.services.run_launcher import (
    RunLaunchError,
    create_run_record,
    execute_run_background,
)
from apps.web.ui.auth_guard import api_client, login_redirect_url
from apps.web.ui.console_log import log_console
from apps.web.ui.request_auth import request_user_session
from apps.web.ui.run_progress import watch_run_progress
from apps.web.ui.workflow_session import (
    WORKFLOW_SESSION_SCRIPT,
    apply_run_context,
    clear_browser_workflow,
    ensure_device_fingerprint,
    load_browser_workflow,
    merge_query_workflow_state,
    save_browser_workflow,
)
from packages.agent.schemas.providers import DEFAULT_PROVIDER
from packages.agent.schemas.variants import DEFAULT_VARIANT, SECTION_KEYS

STEPS = {
    "prepare_inputs": "Reading resume",
    "understand_resume": "Understanding resume structure",
    "analyze_inputs": "Analyzing job fit",
    "rewrite_sections": "Tailoring content",
    "validate_output": "Checking facts",
    "format_output": "Formatting result",
    "assess_fit": "Assessing fit",
}

_SECTION_LABELS: dict[str, str] = {
    "summary": "Summary",
    "experience": "Experience",
    "skills": "Skills",
    "education": "Education",
}

_PLACEHOLDER_GENERATE = "_Generate this variant after the main run completes._"
_PLACEHOLDER_LOADING = "Starting the tailoring workflow..."
_EMPTY_SECTION = ""

_VERDICT_COLOR = {
    "Strong fit": "#2f6f5f",
    "Moderate fit": "#b07d27",
    "Not a fit": "#a33b30",
}

_VERDICT_BG = {
    "Strong fit": "#eef5f1",
    "Moderate fit": "#fdf7ee",
    "Not a fit": "#fdf0ef",
}


def _format_price(amount: float) -> str:
    return f"${amount:.2f}"


def _request() -> Any:
    return request_contextvar.get()


def _format_detail(response_text: str, fallback: str) -> str:
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError:
        return fallback
    return str(data.get("detail") or data.get("message") or fallback)


def _score_label(score: float | None) -> str:
    if score is None:
        return "-"
    return f"{score:.0f}/100"


def _billing_shows_payments(billing: dict[str, Any]) -> bool:
    """Pure gating decision: should the UI show payment controls for this billing status?"""
    return bool(billing.get("payments_enabled", True))


def _should_show_support_link(payments_enabled: bool, support_url: str) -> bool:
    """Pure gating decision: should the soft-upsell support link be shown?

    Shows only when payments are disabled AND a non-empty support URL is provided.
    """
    return (not payments_enabled) and bool(support_url.strip())


_RUN_ERROR_GENERIC = "We couldn't complete that request. Please try again."


def _sanitize_run_error(message: str) -> str:
    """Pure helper: turn a raw run-error message into a clean, human string."""
    return _RUN_ERROR_GENERIC


def _install_page_shell() -> None:
    ui.add_head_html(
        """
        <style>
          :root {
            --rb-ink: #17201b;
            --rb-muted: #66736d;
            --rb-line: #dce3df;
            --rb-panel: #fbfcfb;
            --rb-accent: #2f6f5f;
            --rb-soft: #eef5f1;
          }
          body {
            background: #f7f8f6;
            color: var(--rb-ink);
            font-family: Inter, ui-sans-serif, system-ui, -apple-system,
              BlinkMacSystemFont, "Segoe UI", sans-serif;
          }
          .rb-page { min-height: 100vh; padding: 28px; }
          .rb-shell { width: min(1180px, 100%); margin: 0 auto; }
          .rb-header { padding: 10px 0 22px; }
          .rb-title {
            font-size: clamp(36px, 6vw, 68px);
            line-height: 0.98;
            font-weight: 680;
            letter-spacing: -0.04em;
            max-width: 760px;
          }
          .rb-section-title { font-size: 20px; line-height: 1.2; font-weight: 650; }
          .rb-wordmark { font-size: 14px; font-weight: 680; }
          .rb-subtle { color: var(--rb-muted); font-size: 14px; line-height: 1.5; }
          .rb-copy { color: var(--rb-muted); font-size: 17px; line-height: 1.55; max-width: 620px; }
          .rb-grid {
            display: grid;
            grid-template-columns: minmax(300px, 390px) minmax(0, 1fr);
            gap: 18px;
            align-items: start;
          }
          .rb-panel {
            background: var(--rb-panel);
            border: 1px solid var(--rb-line);
            border-radius: 10px;
            padding: 18px;
          }
          .rb-soft {
            background: var(--rb-soft);
            border: 1px solid #d6e6dd;
            border-radius: 10px;
            padding: 12px 14px;
          }
          .rb-section-box {
            border: 1px solid var(--rb-line);
            border-radius: 8px;
            padding: 14px 16px;
            background: var(--rb-panel);
          }
          .rb-section-box-header {
            font-size: 12px;
            font-weight: 650;
            color: var(--rb-muted);
            text-transform: uppercase;
            letter-spacing: 0.06em;
          }
          .rb-locked { filter: blur(3px); user-select: none; pointer-events: none; }
          .rb-danger { color: #a33b30; }
          .rb-success { color: #2f6f5f; }
          .rb-proof {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 12px;
          }
          .rb-score-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
          }
          .rb-score-card {
            border-radius: 8px;
            padding: 12px 16px;
            border: 1px solid var(--rb-line);
            background: var(--rb-panel);
          }
          .rb-score-num {
            font-size: 32px;
            font-weight: 700;
            line-height: 1;
            color: var(--rb-accent);
          }
          .rb-score-label { font-size: 12px; color: var(--rb-muted); margin-top: 4px; }
          .rb-fit-panel {
            border-radius: 8px;
            padding: 14px 16px;
            margin-top: 12px;
          }
          .rb-coaching-bullet {
            font-size: 13px;
            color: var(--rb-ink);
            padding: 3px 0;
            border-left: 3px solid var(--rb-accent);
            padding-left: 8px;
            margin: 4px 0;
          }
          .rb-gen-placeholder {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 300px;
            color: var(--rb-muted);
            gap: 12px;
          }
          .q-field__control, .q-textarea .q-field__control { border-radius: 8px; }
          .q-btn.bg-primary { background: var(--rb-accent) !important; }
          .text-primary { color: var(--rb-accent) !important; }
          .q-field__control { background: var(--rb-panel); }
          .rb-panel .q-field__control:before { border-color: var(--rb-line); }
          .q-uploader {
            box-shadow: none;
            border: 1px dashed var(--rb-line);
            border-radius: 8px;
            background: var(--rb-panel);
          }
          .q-uploader__header {
            background: var(--rb-panel);
            color: var(--rb-ink);
            box-shadow: none;
            border-bottom: 1px solid var(--rb-line);
          }
          .q-uploader__title { font-size: 13px; }
          .q-uploader__subtitle { color: var(--rb-muted); }
          .q-uploader__list { background: var(--rb-panel); }
          .q-uploader .q-btn.bg-primary {
            background: transparent !important;
            color: var(--rb-muted) !important;
          }
          .q-uploader .q-uploader__header .q-btn { color: var(--rb-muted) !important; }
          .q-uploader .q-uploader__file--uploaded .q-icon { color: var(--rb-accent); }
          .q-linear-progress { color: var(--rb-accent); }
          @media (max-width: 900px) {
            .rb-page { padding: 18px; }
            .rb-grid, .rb-proof, .rb-score-row { grid-template-columns: 1fr; }
          }
        </style>
        <script>
          window.rbFingerprint = {
            get() {
              const existing = document.cookie
                .split('; ')
                .find((row) => row.startsWith('rb_device_fingerprint='));
              if (existing) return decodeURIComponent(existing.split('=')[1]);
              const raw = [
                navigator.userAgent, navigator.language,
                screen.width, screen.height, screen.colorDepth,
                Intl.DateTimeFormat().resolvedOptions().timeZone || 'unknown'
              ].join('|');
              let hash = 0;
              for (let i = 0; i < raw.length; i += 1) {
                hash = ((hash << 5) - hash) + raw.charCodeAt(i);
                hash |= 0;
              }
              const value = `web-${Math.abs(hash).toString(16)}`;
              document.cookie = `rb_device_fingerprint=${encodeURIComponent(value)}; `
                + 'path=/; max-age=31536000; samesite=lax';
              return value;
            }
          };
          window.rbFingerprint.get();
        </script>
        """
        + WORKFLOW_SESSION_SCRIPT
    )


@ui.page("/")
def index_page() -> None:
    _install_page_shell()
    request = _request()
    query = dict(request.query_params) if request is not None else {}
    paid_return = query.get("paid") == "1" and bool(query.get("run_id"))

    state: dict[str, Any] = {
        "run_id": query.get("run_id"),
        "resume_id": query.get("resume_id"),
        "jd_text": None,
        "payment_id": None,
        "poll_payment": paid_return,
        "before_score_task": None,
        "cached_before_jd": None,
        "cached_before_score": None,
        "payments_enabled": True,
        "support_url": "",
        "last_error": None,
    }

    with ui.column().classes("rb-page"):
        with ui.column().classes("rb-shell gap-5"):
            with ui.row().classes("rb-header items-center justify-between w-full"):
                ui.label("ResumeBild").classes("rb-wordmark")
                ui.label("One private device workspace.").classes("rb-subtle")

            with ui.column().classes("gap-3"):
                ui.label("Tailor your resume without inventing facts.").classes("rb-title")
                ui.label(
                    "Upload a master resume, paste a job description, get three tailored "
                    "variations with a real job-fit score."
                ).classes("rb-copy")

            with ui.row().classes("rb-proof"):
                with ui.column().classes("rb-soft gap-1"):
                    ui.label("1. Upload your resume").classes("font-medium")
                    ui.label("Add a PDF, DOCX, or TXT master resume.").classes("rb-subtle")
                with ui.column().classes("rb-soft gap-1"):
                    ui.label("2. Paste the job description").classes("font-medium")
                    ui.label("Use the role details to guide each tailored variation.").classes(
                        "rb-subtle"
                    )
                with ui.column().classes("rb-soft gap-1"):
                    ui.label("3. Review and export").classes("font-medium")
                    ui.label("Unlock DOCX/PDF exports when the tailored resume is ready.").classes(
                        "rb-subtle"
                    )

            with ui.element("section").classes("rb-grid w-full"):
                # ── Left: Inputs ──────────────────────────────────────────
                with ui.column().classes("rb-panel gap-4"):
                    ui.label("Inputs").classes("rb-section-title")
                    status_label = ui.label("Preparing device workspace...").classes("rb-subtle")
                    provider_select = (
                        ui.select(label="AI model", options={}, value=None)
                        .props("outlined")
                        .classes("w-full")
                    )
                    resume_label = ui.label("No resume uploaded yet.").classes("rb-subtle")
                    upload_status = ui.label("").classes("text-sm")
                    upload = (
                        ui.upload(auto_upload=True)
                        .props("accept=.pdf,.txt,.docx")
                        .classes("w-full")
                    )
                    jd_input = (
                        ui.textarea("Job description").props("outlined autogrow").classes("w-full")
                    )

                    # Before-score card (hidden until data available)
                    with ui.element("div").classes("rb-score-card hidden") as before_card:
                        ui.label("Pre-run fit estimate").classes("rb-score-label")
                        before_score_num = ui.label("-").classes("rb-score-num")
                        before_score_sub = ui.label("").classes("rb-subtle text-xs")

                    run_button = ui.button("Tailor resume", icon="auto_awesome").props("unelevated")
                    progress_label = ui.label("Ready").classes("rb-subtle")
                    progress = ui.linear_progress(value=0).props("rounded").classes("w-full")
                    new_resume_btn = (
                        ui.button("New resume", icon="add_circle_outline")
                        .props("flat")
                        .classes("w-full")
                    )

                # ── Right: Output ─────────────────────────────────────────
                with ui.column().classes("gap-3").style("min-width: 0;"):
                    # Score comparison row (hidden until run complete)
                    with ui.element("div").classes("rb-score-row hidden") as score_row:
                        with ui.element("div").classes("rb-score-card"):
                            ui.label("Before tailoring").classes("rb-score-label")
                            score_before_num = ui.label("-").classes("rb-score-num")
                        with ui.element("div").classes("rb-score-card"):
                            ui.label("After tailoring").classes("rb-score-label")
                            score_after_num = ui.label("-").classes("rb-score-num")

                    # Variant tabs
                    with (
                        ui.card()
                        .classes("w-full p-0")
                        .style(
                            "border:1px solid var(--rb-line);border-radius:10px;overflow:hidden;"
                        )
                    ):
                        with ui.tabs().classes("w-full") as variant_tabs:
                            ui.tab("conservative", label="Light touch", icon="tune")
                            ui.tab("balanced", label="Standard fit", icon="balance")
                            ui.tab("bold", label="Bold match", icon="bolt")

                        # section refs: {vname: {section_key: ui.markdown}}
                        _variant_sections: dict[str, dict[str, Any]] = {}
                        # wrapper refs for paywall blur: {vname: ui.column}
                        _variant_wrappers: dict[str, Any] = {}
                        # copy button refs: {vname: {section_key: ui.button}}
                        _variant_copy_btns: dict[str, dict[str, Any]] = {}

                        with ui.tab_panels(variant_tabs, value=DEFAULT_VARIANT.value).classes(
                            "w-full p-0"
                        ):
                            _tab_cfg = [
                                (
                                    "conservative",
                                    "Generate Light Touch",
                                    "tune",
                                    _PLACEHOLDER_GENERATE,
                                ),
                                (
                                    "balanced",
                                    "Generate Standard Fit",
                                    "balance",
                                    "Upload a resume, paste a JD, then start a tailored run.",
                                ),
                                ("bold", "Generate Bold Match", "bolt", _PLACEHOLDER_GENERATE),
                            ]
                            _gen_rows: dict[str, Any] = {}
                            _gen_btns: dict[str, Any] = {}
                            _gen_statuses: dict[str, Any] = {}

                            for _vname, _gen_label, _gen_icon, _placeholder in _tab_cfg:
                                with ui.tab_panel(_vname).classes("p-4"):
                                    with ui.column().classes("gap-3 w-full") as _wrapper:
                                        _variant_wrappers[_vname] = _wrapper
                                        _variant_sections[_vname] = {}
                                        _variant_copy_btns[_vname] = {}
                                        for _sk in SECTION_KEYS:
                                            with ui.element("div").classes("rb-section-box w-full"):
                                                with ui.row().classes(
                                                    "items-center justify-between w-full"
                                                ):
                                                    ui.label(_SECTION_LABELS[_sk]).classes(
                                                        "rb-section-box-header"
                                                    )
                                                    _copy_btn = ui.button(
                                                        icon="content_copy"
                                                    ).props("flat dense round")
                                                    _variant_copy_btns[_vname][_sk] = _copy_btn
                                                _variant_sections[_vname][_sk] = ui.markdown(
                                                    _placeholder if _sk == "summary" else ""
                                                ).classes("w-full")
                                    _gen_row = ui.row().classes("gap-2 items-center hidden")
                                    with _gen_row:
                                        _gen_btn = ui.button(_gen_label, icon=_gen_icon).props(
                                            "unelevated"
                                        )
                                        _gen_status = ui.label("").classes("rb-subtle")
                                    _gen_rows[_vname] = _gen_row
                                    _gen_btns[_vname] = _gen_btn
                                    _gen_statuses[_vname] = _gen_status

                        conservative_gen_row = _gen_rows["conservative"]
                        conservative_gen_btn = _gen_btns["conservative"]
                        conservative_gen_status = _gen_statuses["conservative"]
                        balanced_gen_row = _gen_rows["balanced"]
                        balanced_gen_btn = _gen_btns["balanced"]
                        balanced_gen_status = _gen_statuses["balanced"]
                        bold_gen_row = _gen_rows["bold"]
                        bold_gen_btn = _gen_btns["bold"]
                        bold_gen_status = _gen_statuses["bold"]

                    # Export buttons row
                    export_row = ui.row().classes("gap-2 hidden")

                    # Fit assessment panel (hidden until run complete)
                    fit_panel = ui.element("div").classes("rb-fit-panel hidden")
                    with fit_panel:
                        fit_verdict_label = ui.label("").classes("font-medium text-base")
                        fit_bullets_col = ui.column().classes("gap-1 mt-2")

                    payment_status = ui.label("").classes("rb-subtle")
                    support_link = ui.link("", "").classes("rb-subtle").style("margin-top:8px;")
                    support_link.set_visibility(False)

    # ── Paywall dialog ─────────────────────────────────────────────────────
    paywall_dialog = ui.dialog()
    with paywall_dialog, ui.card().classes("gap-3").style("width: min(420px, 92vw);"):
        ui.label("Unlock full output").classes("text-lg font-medium")
        paywall_price = ui.label("Unlock for $3.99").classes("text-base font-medium")
        ui.label(
            "The run is complete, but the tailored resume stays hidden until payment confirms."
        ).classes("rb-subtle")
        with ui.row().classes("gap-2"):
            stripe_button = ui.button("Stripe", icon="credit_card").props("unelevated")
            crypto_button = ui.button("Crypto", icon="currency_bitcoin").props("outline")
        crypto_status = ui.label("").classes("rb-subtle")

    # ── Helpers ────────────────────────────────────────────────────────────
    state["section_texts"] = {}

    _variant_gen_rows = {
        "conservative": (conservative_gen_row, conservative_gen_btn, conservative_gen_status),
        "balanced": (balanced_gen_row, balanced_gen_btn, balanced_gen_status),
        "bold": (bold_gen_row, bold_gen_btn, bold_gen_status),
    }

    def _make_copy_handler(vname: str, sk: str, btn: Any) -> Any:
        async def _copy() -> None:
            text = (state["section_texts"].get(vname) or {}).get(sk) or ""
            try:
                await ui.run_javascript(f"navigator.clipboard.writeText({json.dumps(text)})")
                btn.props("icon=check")
                await asyncio.sleep(1.5)
            except Exception:
                pass
            finally:
                btn.props("icon=content_copy")

        return _copy

    for _v, _sks in _variant_copy_btns.items():
        for _s, _btn in _sks.items():
            _btn.on_click(_make_copy_handler(_v, _s, _btn))

    async def load_providers() -> None:
        async with api_client() as client:
            resp = await client.get("/api/v1/runs/providers")
        if resp.status_code != 200:
            provider_select.options = {}
            provider_select.value = None
            return
        providers = resp.json().get("providers", [])
        options = {p["id"]: p["label"] for p in providers if p.get("configured")}
        if not options:
            provider_select.options = {}
            provider_select.value = None
            return
        provider_select.options = options
        default = next((p["id"] for p in providers if p.get("is_default")), None)
        provider_select.value = default if default in options else next(iter(options))

    async def load_account() -> None:
        async with api_client() as client:
            user_resp = await client.get("/api/v1/auth/me")
            billing_resp = await client.get("/api/v1/billing/status")
            resumes_resp = await client.get("/api/v1/resumes")

        if user_resp.status_code == 401:
            # Cognito hard-gate: send the browser through 5432wire login handoff.
            # Must be origin-absolute so NiceGUI does not prefix the /app mount.
            ui.navigate.to(login_redirect_url())
            return
        if user_resp.status_code != 200:
            status_label.set_text("Device workspace unavailable. Refresh this page.")
            return

        user = user_resp.json()
        billing = billing_resp.json() if billing_resp.status_code == 200 else {}
        resumes = resumes_resp.json().get("resumes", []) if resumes_resp.status_code == 200 else []
        free_label = "used" if user.get("free_trial_used") else "available"
        upload_label = "yes" if user.get("can_upload") else "payment required"
        price = float(billing.get("price_usd", 3.99))
        state["payments_enabled"] = _billing_shows_payments(billing)
        state["support_url"] = billing.get("support_url", "")

        if state["payments_enabled"]:
            paywall_price.set_visibility(True)
            paywall_price.set_text(f"Unlock for {_format_price(price)}")
            stripe_button.set_visibility(True)
            crypto_button.set_visibility(True)
            state["stripe_configured"] = billing.get("stripe_configured", False)
            if not state["stripe_configured"]:
                stripe_button.props("disable")
                crypto_status.set_text(
                    "Stripe is not configured on this server (set STRIPE_SECRET_KEY)."
                )
            else:
                stripe_button.props(remove="disable")
                if not state.get("poll_payment"):
                    crypto_status.set_text("")
            status_label.set_text(
                f"Free trial: {free_label} · Upload: {upload_label} · "
                f"Unlock: {_format_price(price)}"
            )
            support_link.set_visibility(False)
        else:
            paywall_price.set_visibility(False)
            stripe_button.set_visibility(False)
            crypto_button.set_visibility(False)
            status_label.set_text(f"Free workspace - {free_label} runs")
            if _should_show_support_link(state["payments_enabled"], state["support_url"]):
                support_link.text = "Built by one developer - support this project"
                support_link._props["target"] = "_blank"
                support_link._props["href"] = state["support_url"]
                support_link.update()
                support_link.set_visibility(True)
            else:
                support_link.set_visibility(False)
        if resumes:
            match = None
            if state.get("resume_id"):
                match = next(
                    (r for r in resumes if r["resume_id"] == str(state["resume_id"])),
                    None,
                )
            target = match or resumes[0]
            resume_label.set_text(f"Resume: {target['filename']}")
            state["resume_id"] = target["resume_id"]
        elif state.get("resume_id"):
            resume_label.set_text(f"Resume: saved ({str(state['resume_id'])[:8]}…)")

    def apply_form_from_state(body: dict[str, Any] | None = None) -> None:
        if body:
            apply_run_context(state, body)
        resume_id = state.get("resume_id")
        filename = (body or {}).get("resume_filename")
        if filename:
            resume_label.set_text(f"Resume: {filename}")
        elif resume_id:
            resume_label.set_text(f"Resume: saved ({str(resume_id)[:8]}…)")
        jd_text = state.get("jd_text")
        if jd_text and not (jd_input.value or "").strip():
            jd_input.value = jd_text

    async def _compute_before_score() -> None:
        resume_id = state.get("resume_id")
        jd_text = (jd_input.value or "").strip()
        if not resume_id or len(jd_text) < 20:
            return
        if state.get("cached_before_jd") == jd_text:
            return
        provider = provider_select.value or DEFAULT_PROVIDER.value
        async with api_client() as client:
            resp = await client.post(
                "/api/v1/score/preview",
                json={"resume_id": str(resume_id), "jd_text": jd_text, "provider": provider},
            )
        if resp.status_code == 200:
            data = resp.json()
            overall = data.get("overall")
            if overall is not None:
                before_score_num.set_text(f"{overall:.0f}")
                before_score_sub.set_text("out of 100 - before tailoring")
                before_card.classes(remove="hidden")
                state["cached_before_score"] = overall
                state["cached_before_jd"] = jd_text

    async def schedule_before_score() -> None:
        task = state.get("before_score_task")
        if task and not task.done():
            task.cancel()

        async def _delayed():
            await asyncio.sleep(1.5)
            await _compute_before_score()

        state["before_score_task"] = asyncio.create_task(_delayed())

    jd_input.on("update:model-value", lambda _: asyncio.create_task(schedule_before_score()))

    async def handle_upload(event: Any) -> None:
        upload_file = event.file
        upload_status.set_text("Uploading resume...")
        upload_status.classes(remove="rb-danger")
        upload_status.classes(add="rb-subtle")
        try:
            file_bytes = await upload_file.read()
        except Exception as exc:
            upload_status.set_text(f"Could not read upload: {exc}")
            upload_status.classes(remove="rb-subtle")
            upload_status.classes(add="rb-danger")
            return
        async with api_client() as client:
            response = await client.post(
                "/api/v1/resumes",
                files={
                    "file": (
                        upload_file.name,
                        file_bytes,
                        upload_file.content_type or "application/octet-stream",
                    )
                },
            )
        if response.status_code == 200:
            data = response.json()
            state["resume_id"] = data["resume_id"]
            state["cached_before_jd"] = None
            state["cached_before_score"] = None
            resume_label.set_text(f"Resume: {data['filename']}")
            upload_status.set_text("Resume uploaded.")
            upload_status.classes(remove="rb-danger")
            upload_status.classes(add="rb-success")
            await load_account()
            await schedule_before_score()
            return
        upload_status.set_text(_format_detail(response.text, "Upload failed"))
        upload_status.classes(remove="rb-subtle")
        upload_status.classes(add="rb-danger")

    upload.on_upload(handle_upload)

    def _display_variants(final_output: dict) -> None:
        variants = final_output.get("variants") or {}
        state["section_texts"] = {}
        for vname, section_mds in _variant_sections.items():
            gen_row, _gen_btn, _gen_status = _variant_gen_rows[vname]
            if vname in variants:
                sections = variants[vname].get("sections") or {}
                state["section_texts"][vname] = {}
                for sk, md in section_mds.items():
                    text = sections.get(sk) or ""
                    md.set_content(text)
                    state["section_texts"][vname][sk] = text
                gen_row.classes(add="hidden")
            else:
                for md in section_mds.values():
                    md.set_content(_EMPTY_SECTION)
                gen_row.classes(remove="hidden")

    def _display_fit_assessment(final_output: dict) -> None:
        fit = final_output.get("fit_assessment")
        if not fit:
            fit_panel.classes(add="hidden")
            return
        verdict = fit.get("verdict", "Moderate fit")
        bullets = fit.get("coaching_bullets") or []
        color = _VERDICT_COLOR.get(verdict, "#66736d")
        bg = _VERDICT_BG.get(verdict, "#f7f8f6")
        fit_panel.style(f"background:{bg};border:1px solid {color}33;")
        fit_verdict_label.set_text(f"Fit verdict: {verdict}")
        fit_verdict_label.style(f"color:{color};")
        fit_bullets_col.clear()
        with fit_bullets_col:
            for bullet in bullets:
                ui.label(bullet).classes("rb-coaching-bullet")
        fit_panel.classes(remove="hidden")

    async def refresh_run(show_paywall: bool = False) -> dict[str, Any] | None:
        run_id = state.get("run_id")
        if not run_id:
            return None
        async with api_client() as client:
            response = await client.get(f"/api/v1/runs/{run_id}")
        if response.status_code != 200:
            payment_status.set_text(_format_detail(response.text, "Could not load run"))
            return None

        body = response.json()
        state["current_run"] = body
        apply_form_from_state(body)

        payments_enabled = state.get("payments_enabled", True)
        is_locked = (
            payments_enabled and bool(body.get("output_locked")) and not body.get("final_output")
        )
        if is_locked:
            export_row.classes(add="hidden")
            fit_panel.classes(add="hidden")
            for _vn in _variant_wrappers:
                _variant_wrappers[_vn].classes(add="rb-locked")
            preview = body.get("preview_text") or "Payment required."
            _variant_sections["balanced"]["summary"].set_content(f"**Preview**\n\n{preview}")
            for sk in list(SECTION_KEYS)[1:]:
                _variant_sections["balanced"][sk].set_content(_EMPTY_SECTION)
            payment_status.set_text("Payment required to reveal the full tailored resume.")
            # Show scores as a teaser even when locked - API returns these unconditionally
            _sb = body.get("ats_score_before")
            _sa = body.get("ats_score_after")
            if _sb is not None or _sa is not None:
                score_before_num.set_text(_score_label(_sb))
                score_after_num.set_text(_score_label(_sa))
                score_row.classes(remove="hidden")
            else:
                score_row.classes(add="hidden")
            if payments_enabled and (show_paywall or body.get("status") == "completed"):
                paywall_dialog.open()
            return body

        final_output = body.get("final_output") or {}
        for _vn in _variant_wrappers:
            _variant_wrappers[_vn].classes(remove="rb-locked")

        # Scores
        match_score = final_output.get("match_score") or {}
        score_before_val = match_score.get("previous_overall")
        score_after_val = match_score.get("current_overall")
        if score_before_val is not None or score_after_val is not None:
            score_before_num.set_text(_score_label(score_before_val))
            score_after_num.set_text(_score_label(score_after_val))
            score_row.classes(remove="hidden")
            # update before card in inputs panel too
            if score_before_val is not None:
                before_score_num.set_text(f"{score_before_val:.0f}")
                before_score_sub.set_text("out of 100 - before tailoring")
                before_card.classes(remove="hidden")

        # Variant outputs
        _display_variants(final_output)
        _display_fit_assessment(final_output)

        payment_status.set_text("")
        export_row.classes(remove="hidden")
        export_row.clear()
        with export_row:
            ui.button("TXT", icon="description", on_click=lambda: do_export("txt")).props("flat")
            docx_btn = ui.button("DOCX", icon="article", on_click=lambda: do_export("docx")).props(
                "flat"
            )
            pdf_btn = ui.button(
                "PDF",
                icon="picture_as_pdf",
                on_click=lambda: do_export("pdf"),
            ).props(
                "flat",
            )
            if body.get("is_free_trial_run"):
                docx_btn.props("disable")
                pdf_btn.props("disable")
        return body

    def _show_run_error(message: str) -> None:
        """Show one clean, human error state after a failed run.

        Resets the progress bar, replaces the status label with a sanitized
        message, clears any lingering joke-placeholder text from the variant
        panels, and hides the export row.
        """
        clean = _sanitize_run_error(message)
        progress.value = 0
        progress_label.set_text("Run failed")
        payment_status.classes(remove="rb-subtle")
        payment_status.classes(add="rb-danger")
        payment_status.set_text(clean)
        export_row.classes(add="hidden")
        for _vn in _variant_wrappers:
            for _sk in SECTION_KEYS:
                _variant_sections[_vn][_sk].set_content("")

    def _wire_variant_gen_button(variant_name: str) -> None:
        gen_row, gen_btn, gen_status = _variant_gen_rows[variant_name]

        async def _generate() -> None:
            run_id = state.get("run_id")
            if not run_id:
                return
            gen_btn.props("loading")
            gen_status.set_text("Generating variant...")
            try:
                async with api_client() as client:
                    resp = await client.post(
                        f"/api/v1/runs/{run_id}/variants/{variant_name}/generate"
                    )
            except Exception as exc:
                gen_btn.props(remove="loading")
                gen_status.set_text(f"Generation failed: {exc}")
                return
            gen_btn.props(remove="loading")
            if resp.status_code == 200:
                data = resp.json()
                variants = (data.get("final_output") or {}).get("variants") or {}
                if variant_name in variants:
                    gen_row.classes(add="hidden")
                    gen_status.set_text("")
                    await refresh_run()
                else:
                    gen_status.set_text("Variant generated - reload to view.")
            else:
                gen_status.set_text(_format_detail(resp.text, "Generation failed"))

        gen_btn.on_click(_generate)

    _wire_variant_gen_button("conservative")
    _wire_variant_gen_button("balanced")
    _wire_variant_gen_button("bold")

    async def do_export(fmt: str) -> None:
        run_id = state.get("run_id")
        if not run_id:
            return
        payment_status.set_text(f"Preparing {fmt.upper()} export...")
        async with api_client() as client:
            response = await client.post("/api/v1/exports", json={"run_id": run_id, "format": fmt})
        if response.status_code == 200:
            ui.navigate.to(response.json()["download_url"], new_tab=True)
            payment_status.set_text(f"{fmt.upper()} export ready.")
            return
        payment_status.set_text(_format_detail(response.text, "Export failed"))

    async def pay_stripe() -> None:
        run_id = state.get("run_id")
        if not run_id:
            return
        stripe_button.props("loading")
        await save_browser_workflow(
            run_id=str(run_id),
            resume_id=str(state["resume_id"]) if state.get("resume_id") else None,
            jd_text=(jd_input.value or "").strip(),
        )
        async with api_client() as client:
            response = await client.post("/api/v1/billing/stripe/checkout", json={"run_id": run_id})
        stripe_button.props(remove="loading")
        if response.status_code == 200:
            ui.navigate.to(response.json()["checkout_url"])
            payment_status.set_text("Redirecting to Stripe…")
            state["poll_payment"] = True
            return
        payment_status.set_text(_format_detail(response.text, "Stripe checkout failed"))
        crypto_status.set_text(_format_detail(response.text, "Stripe checkout failed"))

    async def pay_crypto() -> None:
        run_id = state.get("run_id")
        if not run_id:
            return
        crypto_button.props("loading")
        async with api_client() as client:
            response = await client.post(
                "/api/v1/billing/crypto/invoice",
                json={"run_id": run_id, "pay_currency": "btc"},
            )
        crypto_button.props(remove="loading")
        if response.status_code == 200:
            data = response.json()
            state["payment_id"] = data["payment_id"]
            state["poll_payment"] = True
            amount = data.get("pay_amount")
            currency = data.get("pay_currency")
            address = data.get("pay_address")
            crypto_status.set_text(f"Send {amount} {currency} to {address}")
            return
        crypto_status.set_text(_format_detail(response.text, "Crypto invoice failed"))

    stripe_button.on_click(pay_stripe)
    crypto_button.on_click(pay_crypto)

    async def stream_progress(run_id: str) -> str:
        def _update(label: str, value: float) -> None:
            state["last_error"] = label
            progress_label.set_text(label)
            progress.value = value

        return await watch_run_progress(run_id, steps=STEPS, on_update=_update)

    async def tailor() -> None:
        jd_text = (jd_input.value or "").strip()
        if len(jd_text) < 20:
            _variant_sections["balanced"]["summary"].set_content(
                "Job description must be at least 20 characters."
            )
            return
        if not state.get("resume_id"):
            await load_account()
        resume_id = state.get("resume_id")
        if not resume_id:
            _variant_sections["balanced"]["summary"].set_content(
                "Upload a resume before tailoring."
            )
            return

        log_console(
            "tailor: submit clicked",
            resume_id=resume_id,
            jd_chars=len(jd_text),
            provider=provider_select.value or DEFAULT_PROVIDER.value,
        )
        run_button.props("loading")
        progress.value = 0.05
        progress_label.set_text("Creating run")
        payment_status.set_text("")
        payment_status.classes(remove="rb-danger")
        payment_status.classes(add="rb-subtle")
        for _vn in _variant_wrappers:
            _variant_wrappers[_vn].classes(remove="rb-locked")
        for _sk in SECTION_KEYS:
            _variant_sections["balanced"][_sk].set_content(
                _PLACEHOLDER_LOADING if _sk == "summary" else _EMPTY_SECTION
            )
            _variant_sections["conservative"][_sk].set_content(
                _PLACEHOLDER_GENERATE if _sk == "summary" else _EMPTY_SECTION
            )
            _variant_sections["bold"][_sk].set_content(
                _PLACEHOLDER_GENERATE if _sk == "summary" else _EMPTY_SECTION
            )
        conservative_gen_row.classes(add="hidden")
        bold_gen_row.classes(add="hidden")
        score_row.classes(add="hidden")
        fit_panel.classes(add="hidden")
        paywall_dialog.close()
        export_row.classes(add="hidden")

        try:
            async with request_user_session() as (session, user):
                data = await create_run_record(
                    session,
                    user,
                    resume_id=UUID(str(resume_id)),
                    jd_text=jd_text,
                    llm_provider=provider_select.value or DEFAULT_PROVIDER.value,
                    variant=DEFAULT_VARIANT.value,
                )
        except RunLaunchError as exc:
            log_console("tailor: run creation failed", level="error", detail=exc.detail)
            run_button.props(remove="loading")
            _show_run_error(exc.detail)
            return
        except Exception as exc:
            log_console("tailor: unexpected error", level="error", detail=str(exc))
            run_button.props(remove="loading")
            _show_run_error(f"Could not start run: {exc}")
            return

        log_console("tailor: run created", run_id=data["run_id"], status=data.get("status"))
        state["run_id"] = data["run_id"]
        state["jd_text"] = jd_text
        await save_browser_workflow(
            run_id=data["run_id"],
            resume_id=str(resume_id),
            jd_text=jd_text,
        )
        try:
            result, _ = await asyncio.gather(
                stream_progress(data["run_id"]),
                execute_run_background(UUID(data["run_id"]), data["variant"]),
            )
            log_console("tailor: progress finished", run_id=data["run_id"], result=result)
            if result == "error":
                _show_run_error(state.get("last_error") or "")
                return
        finally:
            run_button.props(remove="loading")

        body = await refresh_run(show_paywall=True)
        await load_account()

        # Show generate buttons for the other two variants
        if body and body.get("final_output"):
            variants_built = set((body["final_output"].get("variants") or {}).keys())
            for vname in ["conservative", "balanced", "bold"]:
                if vname not in variants_built:
                    gen_row, _, _ = _variant_gen_rows[vname]
                    gen_row.classes(remove="hidden")

    run_button.on_click(tailor)

    async def new_resume() -> None:
        # Cancel any pending before-score computation
        task = state.get("before_score_task")
        if task and not task.done():
            task.cancel()
        # Clear run state; keep resume_id so the same master resume stays selected
        state.update(
            {
                "run_id": None,
                "jd_text": None,
                "payment_id": None,
                "poll_payment": False,
                "section_texts": {},
                "current_run": None,
                "cached_before_jd": None,
                "cached_before_score": None,
                "before_score_task": None,
            }
        )
        await clear_browser_workflow()
        # Reset input fields
        jd_input.value = ""
        upload_status.set_text("")
        upload_status.classes(remove="rb-danger rb-success")
        before_card.classes(add="hidden")
        before_score_num.set_text("-")
        before_score_sub.set_text("")
        progress_label.set_text("Ready")
        progress.value = 0
        # Reset output panel
        score_row.classes(add="hidden")
        score_before_num.set_text("-")
        score_after_num.set_text("-")
        fit_panel.classes(add="hidden")
        fit_bullets_col.clear()
        export_row.classes(add="hidden")
        export_row.clear()
        payment_status.set_text("")
        payment_status.classes(remove="rb-danger")
        payment_status.classes(add="rb-subtle")
        paywall_dialog.close()
        for _vn in _variant_wrappers:
            _variant_wrappers[_vn].classes(remove="rb-locked")
        for _sk in SECTION_KEYS:
            _variant_sections["balanced"][_sk].set_content(
                "Upload a resume, paste a JD, then start a tailored run."
                if _sk == "summary"
                else ""
            )
            _variant_sections["conservative"][_sk].set_content(
                _PLACEHOLDER_GENERATE if _sk == "summary" else ""
            )
            _variant_sections["bold"][_sk].set_content(
                _PLACEHOLDER_GENERATE if _sk == "summary" else ""
            )
        for gen_row, _, gen_status in _variant_gen_rows.values():
            gen_row.classes(add="hidden")
            gen_status.set_text("")

    new_resume_btn.on_click(new_resume)

    async def sync_payment_status() -> bool:
        run_id = state.get("run_id")
        if not run_id:
            return False
        async with api_client() as client:
            response = await client.post("/api/v1/billing/stripe/verify", json={"run_id": run_id})
        if response.status_code != 200:
            return False
        data = response.json()
        return bool(data.get("unlocked")) and not bool(data.get("output_locked"))

    async def poll_after_payment() -> None:
        if not state.get("poll_payment"):
            return
        await sync_payment_status()
        body = await refresh_run(show_paywall=False)
        if body and (body.get("final_output") or not body.get("output_locked")):
            state["poll_payment"] = False
            paywall_dialog.close()
            payment_status.set_text("Payment confirmed. Output unlocked.")
            await load_account()
            await clear_browser_workflow()
        else:
            payment_status.set_text("Waiting for payment confirmation...")

    async def bootstrap_workflow() -> None:
        await ensure_device_fingerprint()
        stored = await load_browser_workflow()
        merge_query_workflow_state(state, query, stored)
        apply_form_from_state()
        await load_providers()
        await load_account()
        apply_form_from_state()
        if state.get("run_id"):
            if state.get("poll_payment"):
                # Returning from payment redirect - restore run and unlock output
                await sync_payment_status()
                await refresh_run(show_paywall=True)
                body = state.get("current_run") or {}
                if body.get("final_output") or not body.get("output_locked"):
                    state["poll_payment"] = False
                    paywall_dialog.close()
                    await clear_browser_workflow()
            else:
                # Regular page load - start fresh, do not show stale run output or scores
                state["run_id"] = None
                await clear_browser_workflow()
                await schedule_before_score()

    ui.timer(0.1, bootstrap_workflow, once=True)
    ui.timer(2.5, poll_after_payment)


def mount_ui() -> None:
    pass

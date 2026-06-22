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
from apps.web.ui.auth_guard import api_client
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
from packages.agent.schemas.variants import DEFAULT_VARIANT, variant_option_labels

STEPS = {
    "prepare_inputs": "Reading resume",
    "understand_resume": "Understanding resume structure",
    "analyze_inputs": "Analyzing job fit",
    "rewrite_sections": "Tailoring content",
    "validate_output": "Checking facts",
    "format_output": "Formatting result",
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
          .rb-page {
            min-height: 100vh;
            padding: 28px;
          }
          .rb-shell {
            width: min(1180px, 100%);
            margin: 0 auto;
          }
          .rb-header {
            padding: 10px 0 22px;
          }
          .rb-title {
            font-size: clamp(36px, 6vw, 68px);
            line-height: 0.98;
            font-weight: 680;
            letter-spacing: -0.04em;
            max-width: 760px;
          }
          .rb-section-title {
            font-size: 20px;
            line-height: 1.2;
            font-weight: 650;
          }
          .rb-wordmark {
            font-size: 14px;
            font-weight: 680;
          }
          .rb-subtle {
            color: var(--rb-muted);
            font-size: 14px;
            line-height: 1.5;
          }
          .rb-copy {
            color: var(--rb-muted);
            font-size: 17px;
            line-height: 1.55;
            max-width: 620px;
          }
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
          .rb-output {
            min-height: 410px;
            max-height: 62vh;
            overflow: auto;
            white-space: normal;
          }
          .rb-locked {
            filter: blur(3px);
            user-select: none;
          }
          .rb-danger {
            color: #a33b30;
          }
          .rb-success {
            color: #2f6f5f;
          }
          .rb-proof {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 12px;
          }
          .q-field__control,
          .q-textarea .q-field__control {
            border-radius: 8px;
          }
          .q-btn.bg-primary {
            background: var(--rb-accent) !important;
          }
          .text-primary {
            color: var(--rb-accent) !important;
          }
          @media (max-width: 900px) {
            .rb-page {
              padding: 18px;
            }
            .rb-grid,
            .rb-proof {
              grid-template-columns: 1fr;
            }
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
                navigator.userAgent,
                navigator.language,
                screen.width,
                screen.height,
                screen.colorDepth,
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
    }

    with ui.column().classes("rb-page"):
        with ui.column().classes("rb-shell gap-5"):
            with ui.row().classes("rb-header items-center justify-between w-full"):
                ui.label("Resume Builder").classes("rb-wordmark")
                with ui.row().classes("items-center gap-3"):
                    ui.link("Advanced dashboard", "/app/dashboard").classes("rb-subtle")
                    ui.label("One private device workspace.").classes("rb-subtle")

            with ui.column().classes("gap-3"):
                ui.label("Tailor your resume without inventing facts.").classes("rb-title")
                ui.label(
                    "Upload a master resume, paste one job description, stream progress, unlock "
                    "paid output when required, and export from one private workspace."
                ).classes("rb-copy")

            with ui.row().classes("rb-proof"):
                with ui.column().classes("rb-soft gap-1"):
                    ui.label("1. Upload").classes("font-medium")
                    ui.label("PDF, DOCX, or TXT master resume.").classes("rb-subtle")
                with ui.column().classes("rb-soft gap-1"):
                    ui.label("2. Tailor").classes("font-medium")
                with ui.column().classes("rb-soft gap-1"):
                    ui.label("3. Unlock").classes("font-medium")

            with ui.element("section").classes("rb-grid w-full"):
                with ui.column().classes("rb-panel gap-4"):
                    ui.label("Inputs").classes("rb-section-title")
                    status_label = ui.label("Preparing device workspace...").classes("rb-subtle")
                    provider_select = ui.select(
                        label="AI model",
                        options={},
                        value=None,
                    ).classes("w-full")
                    variant_select = ui.select(
                        label="Tailoring style",
                        options=variant_option_labels(),
                        value=DEFAULT_VARIANT.value,
                    ).classes("w-full")
                    resume_label = ui.label("No resume uploaded yet.").classes("rb-subtle")
                    upload_status = ui.label("").classes("text-sm")
                    upload = ui.upload(auto_upload=True).props("accept=.pdf,.txt,.docx").classes(
                        "w-full"
                    )
                    jd_input = ui.textarea("Job description").props("outlined").classes("w-full")
                    jd_input.props("autogrow")
                    run_button = ui.button("Tailor resume", icon="auto_awesome").props(
                        "unelevated"
                    )
                    progress_label = ui.label("Ready").classes("rb-subtle")
                    progress = ui.linear_progress(value=0).props("rounded").classes("w-full")

                with ui.column().classes("gap-4").style("min-width: 0;"):
                    with ui.row().classes("items-center justify-between w-full"):
                        ui.label("Output").classes("rb-section-title")
                        export_row = ui.row().classes("gap-2 hidden")
                    output = ui.markdown(
                        "Upload a resume, paste a job description, then start a tailored run."
                    ).classes("rb-panel rb-output w-full")
                    payment_status = ui.label("").classes("rb-subtle")

    paywall_dialog = ui.dialog()
    with paywall_dialog, ui.card().classes("gap-3").style("width: min(420px, 92vw);"):
        ui.label("Unlock full output").classes("text-lg font-medium")
        paywall_price = ui.label(f"Unlock for {_format_price(3.99)}").classes(
            "text-base font-medium"
        )
        ui.label(
            "The run is complete, but the tailored resume stays hidden until payment confirms."
        ).classes("rb-subtle")
        with ui.row().classes("gap-2"):
            stripe_button = ui.button("Stripe", icon="credit_card").props("unelevated")
            crypto_button = ui.button("Crypto", icon="currency_bitcoin").props("outline")
        crypto_status = ui.label("").classes("rb-subtle")

    async def load_providers() -> None:
        async with api_client() as client:
            resp = await client.get("/api/v1/runs/providers")
        if resp.status_code != 200:
            provider_select.options = {"huggingface": "Hugging Face"}
            provider_select.value = "huggingface"
            return
        providers = resp.json().get("providers", [])
        options = {p["id"]: p["label"] for p in providers if p.get("configured")}
        if not options:
            options = {"huggingface": "Hugging Face"}
        provider_select.options = options
        default = next((p["id"] for p in providers if p.get("is_default")), "huggingface")
        provider_select.value = default if default in options else next(iter(options))

    async def load_account() -> None:
        async with api_client() as client:
            user_resp = await client.get("/api/v1/auth/me")
            billing_resp = await client.get("/api/v1/billing/status")
            resumes_resp = await client.get("/api/v1/resumes")

        if user_resp.status_code != 200:
            status_label.set_text("Device workspace unavailable. Refresh this page.")
            output.set_content("Could not prepare the local device workspace.")
            return

        user = user_resp.json()
        billing = billing_resp.json() if billing_resp.status_code == 200 else {}
        resumes = resumes_resp.json().get("resumes", []) if resumes_resp.status_code == 200 else []
        free_label = "used" if user.get("free_trial_used") else "available"
        upload_label = "yes" if user.get("can_upload") else "payment required"
        price = float(billing.get("price_usd", 3.99))
        paywall_price.set_text(f"Unlock for {_format_price(price)}")
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
            resume_label.set_text(f"Resume: {data['filename']}")
            upload_status.set_text("Resume uploaded.")
            upload_status.classes(remove="rb-danger")
            upload_status.classes(add="rb-success")
            await load_account()
            return
        upload_status.set_text(_format_detail(response.text, "Upload failed"))
        upload_status.classes(remove="rb-subtle")
        upload_status.classes(add="rb-danger")

    upload.on_upload(handle_upload)

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
        is_locked = bool(body.get("output_locked")) and not body.get("final_output")
        if is_locked:
            export_row.classes(add="hidden")
            output.classes(add="rb-locked")
            output.set_content(f"**Preview**\n\n{body.get('preview_text') or 'Payment required.'}")
            payment_status.set_text("Payment required to reveal the full tailored resume.")
            if show_paywall:
                paywall_dialog.open()
            return body

        final_output = body.get("final_output") or {}
        output.classes(remove="rb-locked")
        output.set_content(final_output.get("plain_text") or body.get("preview_text") or "")
        payment_status.set_text("Output is available.")
        export_row.classes(remove="hidden")
        export_row.clear()
        with export_row:
            ui.button("TXT", icon="description", on_click=lambda: do_export("txt")).props("flat")
            docx = ui.button("DOCX", icon="article", on_click=lambda: do_export("docx")).props(
                "flat"
            )
            pdf = ui.button("PDF", icon="picture_as_pdf", on_click=lambda: do_export("pdf")).props(
                "flat"
            )
            if body.get("is_free_trial_run"):
                docx.props("disable")
                pdf.props("disable")
        return body

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
            progress_label.set_text(label)
            progress.value = value

        return await watch_run_progress(run_id, steps=STEPS, on_update=_update)

    async def tailor() -> None:
        jd_text = (jd_input.value or "").strip()
        if len(jd_text) < 20:
            output.set_content("Job description must be at least 20 characters.")
            return
        if not state.get("resume_id"):
            await load_account()
        resume_id = state.get("resume_id")
        if not resume_id:
            output.set_content("Upload a resume before tailoring.")
            return

        log_console(
            "tailor: submit clicked",
            resume_id=resume_id,
            jd_chars=len(jd_text),
            provider=provider_select.value or "huggingface",
            variant=variant_select.value or DEFAULT_VARIANT.value,
        )
        run_button.props("loading")
        progress.value = 0.05
        progress_label.set_text("Creating run")
        payment_status.set_text("")
        output.classes(remove="rb-locked")
        output.set_content("Starting the tailoring workflow...")
        paywall_dialog.close()
        export_row.classes(add="hidden")

        try:
            async with request_user_session() as (session, user):
                log_console("tailor: creating run in-process (avoiding HTTP self-call)")
                data = await create_run_record(
                    session,
                    user,
                    resume_id=UUID(str(resume_id)),
                    jd_text=jd_text,
                    llm_provider=provider_select.value or "huggingface",
                    variant=variant_select.value or DEFAULT_VARIANT.value,
                )
        except RunLaunchError as exc:
            log_console("tailor: run creation failed", level="error", detail=exc.detail)
            run_button.props(remove="loading")
            output.set_content(exc.detail)
            return
        except Exception as exc:
            log_console("tailor: unexpected error", level="error", detail=str(exc))
            run_button.props(remove="loading")
            output.set_content(f"Could not start run: {exc}")
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
            log_console("tailor: starting execution and progress watch")
            result, _ = await asyncio.gather(
                stream_progress(data["run_id"]),
                execute_run_background(UUID(data["run_id"]), data["variant"]),
            )
            log_console("tailor: progress finished", run_id=data["run_id"], result=result)
            if result == "error":
                await refresh_run(show_paywall=False)
                return
        finally:
            run_button.props(remove="loading")
        await refresh_run(show_paywall=True)
        await load_account()

    run_button.on_click(tailor)

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
        if body and body.get("final_output"):
            state["poll_payment"] = False
            paywall_dialog.close()
            payment_status.set_text("Payment confirmed. Output unlocked.")
            await load_account()
            await clear_browser_workflow()
        elif body and not body.get("output_locked"):
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
                await sync_payment_status()
            await refresh_run(show_paywall=state.get("poll_payment", False))
            body = state.get("current_run") or {}
            if body.get("final_output") or not body.get("output_locked"):
                state["poll_payment"] = False
                paywall_dialog.close()
                await clear_browser_workflow()

    ui.timer(0.1, bootstrap_workflow, once=True)
    ui.timer(2.5, poll_after_payment)


def mount_ui() -> None:
    from apps.web.ui import dashboard  # noqa: F401

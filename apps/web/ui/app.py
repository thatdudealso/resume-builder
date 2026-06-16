from __future__ import annotations

import json
from typing import Any

from nicegui import ui
from nicegui.storage import request_contextvar

from apps.web.ui.auth_guard import api_client

STEPS = {
    "prepare_inputs": "Reading resume",
    "rewrite_sections": "Tailoring content",
    "validate_output": "Checking facts",
    "format_output": "Formatting result",
}


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
            },
            async auth(path, body) {
              const response = await fetch(path, {
                method: 'POST',
                credentials: 'include',
                headers: {
                  'Content-Type': 'application/json',
                  'X-Device-Fingerprint': this.get()
                },
                body: JSON.stringify(body)
              });
              let payload = {};
              try { payload = await response.json(); } catch (error) {}
              return { ok: response.ok, status: response.status, payload };
            },
            async logout() {
              await fetch('/api/v1/auth/logout', {
                method: 'POST',
                credentials: 'include',
                headers: { 'X-Device-Fingerprint': this.get() }
              });
              window.location.href = '/app/';
            }
          };
        </script>
        """
    )


async def _auth_request(path: str, email: str | None, password: str | None) -> dict[str, Any]:
    payload = {"email": (email or "").strip(), "password": password or ""}
    return await ui.run_javascript(
        f"return await window.rbFingerprint.auth({json.dumps(path)}, {json.dumps(payload)});",
        timeout=20.0,
    )


@ui.page("/")
def index_page() -> None:
    _install_page_shell()
    request = _request()
    query = request.query_params if request is not None else {}
    is_signed_in = bool(request and request.cookies.get("access_token"))
    paid_return = query.get("paid") == "1" and bool(query.get("run_id"))

    state: dict[str, Any] = {
        "run_id": query.get("run_id"),
        "payment_id": None,
        "poll_payment": paid_return,
    }

    with ui.column().classes("rb-page"):
        with ui.column().classes("rb-shell gap-5"):
            with ui.row().classes("rb-header items-center justify-between w-full"):
                ui.label("Resume Builder").classes("rb-wordmark")

                async def do_logout() -> None:
                    await ui.run_javascript("await window.rbFingerprint.logout();", timeout=10.0)

                if is_signed_in:
                    ui.button("Sign out", icon="logout", on_click=do_logout).props("flat")
                else:
                    ui.label("No separate login or dashboard pages").classes("rb-subtle")

            with ui.column().classes("gap-3"):
                ui.label("Tailor your resume without inventing facts.").classes("rb-title")
                ui.label(
                    "Upload a master resume, paste one job description, stream progress, "
                    "unlock paid output when required, and export from this single workspace."
                ).classes("rb-copy")

            with ui.row().classes("rb-proof"):
                with ui.column().classes("rb-soft gap-1"):
                    ui.label("1. Upload").classes("font-medium")
                    ui.label("PDF, DOCX, or TXT master resume.").classes("rb-subtle")
                with ui.column().classes("rb-soft gap-1"):
                    ui.label("2. Tailor").classes("font-medium")
                    ui.label("Live SSE progress from the agent graph.").classes("rb-subtle")
                with ui.column().classes("rb-soft gap-1"):
                    ui.label("3. Unlock").classes("font-medium")
                    ui.label("Pay only when output is locked after the free run.").classes(
                        "rb-subtle"
                    )

            with ui.element("section").classes("rb-grid w-full"):
                with ui.column().classes("rb-panel gap-4"):
                    if is_signed_in:
                        ui.label("Inputs").classes("rb-section-title")
                        status_label = ui.label("Loading account...").classes("rb-subtle")
                        resume_label = ui.label("No resume uploaded yet.").classes("rb-subtle")
                        upload_status = ui.label("").classes("text-sm")
                        upload = ui.upload(auto_upload=True).props(
                            "accept=.pdf,.txt,.docx"
                        ).classes("w-full")
                        jd_input = ui.textarea("Job description").props("outlined").classes(
                            "w-full"
                        )
                        jd_input.props("autogrow")
                        run_button = ui.button("Tailor resume", icon="auto_awesome").props(
                            "unelevated"
                        )
                        progress_label = ui.label("Ready").classes("rb-subtle")
                        progress = ui.linear_progress(value=0).props("rounded").classes("w-full")
                    else:
                        ui.label("Start here").classes("rb-section-title")
                        ui.label(
                            "Create an account or sign in, then this same page becomes the "
                            "resume workspace."
                        ).classes("rb-subtle")
                        mode = ui.toggle(["Create", "Sign in"], value="Create").props(
                            "unelevated"
                        )
                        email = ui.input("Email").props("outlined dense").classes("w-full")
                        password = ui.input(
                            "Password", password=True
                        ).props("outlined dense").classes("w-full")
                        auth_error = ui.label("").classes("rb-danger text-sm")

                        async def submit_auth() -> None:
                            endpoint = (
                                "/api/v1/auth/register"
                                if mode.value == "Create"
                                else "/api/v1/auth/login"
                            )
                            result = await _auth_request(endpoint, email.value, password.value)
                            if result.get("ok"):
                                await ui.run_javascript(
                                    "window.location.href = '/app/';", timeout=5.0
                                )
                                return
                            fallback = (
                                "Could not create account"
                                if mode.value == "Create"
                                else "Login failed"
                            )
                            detail = result.get("payload", {}).get("detail", fallback)
                            auth_error.set_text(str(detail))

                        ui.button(
                            "Continue",
                            icon="arrow_forward",
                            on_click=submit_auth,
                        ).props("unelevated").classes("w-full")
                        ui.separator()
                        ui.label("Workspace preview").classes("font-medium")
                        ui.label("Upload, tailoring, paywall, and exports all live here.").classes(
                            "rb-subtle"
                        )

                with ui.column().classes("gap-4").style("min-width: 0;"):
                    with ui.row().classes("items-center justify-between w-full"):
                        ui.label("Output").classes("rb-section-title")
                        export_row = ui.row().classes("gap-2 hidden")
                    output = ui.markdown(
                        "Sign in on this page to upload a resume and start a tailored run."
                        if not is_signed_in
                        else "Upload a resume, paste a job description, then start a tailored run."
                    ).classes("rb-panel rb-output w-full")
                    payment_status = ui.label("").classes("rb-subtle")

    paywall_dialog = ui.dialog()
    with paywall_dialog, ui.card().classes("gap-3").style("width: min(420px, 92vw);"):
        ui.label("Unlock full output").classes("text-lg font-medium")
        ui.label(
            "The run is complete, but the tailored resume stays hidden until payment confirms."
        ).classes("rb-subtle")
        with ui.row().classes("gap-2"):
            stripe_button = ui.button("Stripe", icon="credit_card").props("unelevated")
            crypto_button = ui.button("Crypto", icon="currency_bitcoin").props("outline")
        crypto_status = ui.label("").classes("rb-subtle")

    if not is_signed_in:
        ui.timer(0.1, lambda: ui.run_javascript("window.rbFingerprint.get();"), once=True)
        return

    async def load_account() -> None:
        async with api_client() as client:
            user_resp = await client.get("/api/v1/auth/me")
            billing_resp = await client.get("/api/v1/billing/status")
            resumes_resp = await client.get("/api/v1/resumes")

        if user_resp.status_code != 200:
            status_label.set_text("Session expired. Sign in again on this page.")
            output.set_content("Refresh this page to sign in again.")
            return

        user = user_resp.json()
        billing = billing_resp.json() if billing_resp.status_code == 200 else {}
        resumes = resumes_resp.json().get("resumes", []) if resumes_resp.status_code == 200 else []
        free_label = "used" if user.get("free_trial_used") else "available"
        upload_label = "yes" if user.get("can_upload") else "payment required"
        price = billing.get("price_usd", "9.99")
        status_label.set_text(
            f"Free trial: {free_label} · Upload: {upload_label} · Unlock: ${price}"
        )
        if resumes:
            resume_label.set_text(f"Resume: {resumes[0]['filename']}")
            state["resume_id"] = resumes[0]["resume_id"]

    async def handle_upload(event: Any) -> None:
        upload_status.set_text("Uploading resume...")
        upload_status.classes(remove="rb-danger")
        upload_status.classes(add="rb-subtle")
        async with api_client() as client:
            response = await client.post(
                "/api/v1/resumes",
                files={
                    "file": (
                        event.name,
                        event.content.read(),
                        event.type or "application/octet-stream",
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
        is_locked = body.get("output_locked") and not body.get("final_output")
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
        async with api_client() as client:
            response = await client.post("/api/v1/billing/stripe/checkout", json={"run_id": run_id})
        stripe_button.props(remove="loading")
        if response.status_code == 200:
            ui.navigate.to(response.json()["checkout_url"], new_tab=True)
            payment_status.set_text("Waiting for Stripe confirmation...")
            state["poll_payment"] = True
            return
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

    async def stream_progress(run_id: str) -> None:
        current_event = ""
        async with api_client() as client:
            async with client.stream("GET", f"/api/v1/runs/{run_id}/stream") as stream:
                async for line in stream.aiter_lines():
                    if line.startswith("event: "):
                        current_event = line.removeprefix("event: ")
                    elif line.startswith("data: "):
                        payload = json.loads(line.removeprefix("data: ") or "{}")
                        if current_event == "progress":
                            node = payload.get("node")
                            verb = "Started" if payload.get("event") == "node_start" else "Done"
                            progress_label.set_text(f"{verb}: {STEPS.get(node, node or 'step')}")
                            progress.value = min(float(progress.value or 0) + 0.18, 0.9)
                        elif current_event == "done":
                            progress.value = 1
                            progress_label.set_text("Run complete")
                            return
                        elif current_event == "error":
                            progress_label.set_text(str(payload.get("message", "Run failed")))
                            return

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

        run_button.props("loading")
        progress.value = 0.05
        progress_label.set_text("Creating run")
        payment_status.set_text("")
        output.classes(remove="rb-locked")
        output.set_content("Starting the tailoring workflow...")
        paywall_dialog.close()
        export_row.classes(add="hidden")

        async with api_client() as client:
            response = await client.post(
                "/api/v1/runs",
                json={"resume_id": resume_id, "jd_text": jd_text},
            )
        if response.status_code != 200:
            run_button.props(remove="loading")
            output.set_content(_format_detail(response.text, "Could not start run"))
            return

        data = response.json()
        state["run_id"] = data["run_id"]
        try:
            await stream_progress(data["run_id"])
        finally:
            run_button.props(remove="loading")
        await refresh_run(show_paywall=True)
        await load_account()

    run_button.on_click(tailor)

    async def poll_after_payment() -> None:
        if not state.get("poll_payment"):
            return
        body = await refresh_run(show_paywall=False)
        if body and not body.get("output_locked"):
            state["poll_payment"] = False
            paywall_dialog.close()
            payment_status.set_text("Payment confirmed. Output unlocked.")
            await load_account()
        else:
            payment_status.set_text("Waiting for payment confirmation...")

    ui.timer(0.1, load_account, once=True)
    ui.timer(0.1, lambda: ui.run_javascript("window.rbFingerprint.get();"), once=True)
    ui.timer(2.5, poll_after_payment)
    if state.get("run_id"):
        ui.timer(0.2, lambda: refresh_run(show_paywall=state["poll_payment"]), once=True)


def register_ui() -> None:
    pass

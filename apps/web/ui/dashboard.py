from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import UUID

from nicegui import ui
from sqlalchemy import select

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
    ensure_device_fingerprint,
    save_browser_workflow,
)
from packages.agent.schemas.variants import DEFAULT_VARIANT, variant_option_labels
from packages.db.models.resume import MasterResume

STEPS = {
    "prepare_inputs": "Reading resume",
    "understand_resume": "Understanding resume structure",
    "analyze_inputs": "Analyzing job fit",
    "rewrite_sections": "Tailoring sections",
    "validate_output": "Checking facts",
    "format_output": "Formatting result",
}


def _format_price(amount: float) -> str:
    return f"${amount:.2f}"


def _format_detail(response_text: str, fallback: str) -> str:
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError:
        return fallback
    detail = data.get("detail")
    if isinstance(detail, list) and detail:
        return str(detail[0].get("msg", fallback))
    return str(detail or data.get("message") or fallback)


def _score_label(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.0f}"
    except (TypeError, ValueError):
        return "—"


_FINGERPRINT_SCRIPT = """
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


@ui.page("/dashboard")
def dashboard_page() -> None:
    ui.add_head_html(
        """
        <style>
          .rb-score-card {
            border: 1px solid #dce3df;
            border-radius: 10px;
            padding: 12px 14px;
            background: #fbfcfb;
            min-width: 120px;
          }
          .rb-score-value { font-size: 28px; font-weight: 650; color: #2f6f5f; }
          .rb-score-label { font-size: 12px; color: #66736d; text-transform: uppercase; }
          .rb-variant-active { background: #2f6f5f !important; color: white !important; }
          .rb-output-panel {
            border: 1px solid #dce3df;
            border-radius: 10px;
            padding: 16px;
            min-height: 280px;
            max-height: 50vh;
            overflow: auto;
          }
          .rb-locked { filter: blur(3px); user-select: none; }
        </style>
        """
        + _FINGERPRINT_SCRIPT
        + WORKFLOW_SESSION_SCRIPT
    )

    state: dict[str, Any] = {
        "run_id": None,
        "selected_variant": "balanced",
        "providers": [],
        "can_view_output": False,
    }

    ui.label("Resume Builder").classes("text-2xl font-bold")
    ui.link("← Simple workflow", "/app/").classes("text-sm text-gray-600")
    status_label = ui.label("").classes("text-sm text-gray-600")
    upload_status = ui.label("")

    provider_select = ui.select(label="AI model", options={}, value=None).classes("w-full")
    variant_select = ui.select(
        label="Tailoring style",
        options=variant_option_labels(),
        value=DEFAULT_VARIANT.value,
    ).classes("w-full")
    upload = ui.upload(auto_upload=True).classes("w-full").props("accept=.pdf,.txt,.docx")
    jd_input = ui.textarea("Job description").classes("w-full").props("outlined autogrow")

    score_row = ui.row().classes("w-full gap-3 items-center hidden")
    with score_row:
        with ui.column().classes("rb-score-card"):
            ui.label("Previous resume score").classes("rb-score-label")
            score_before_val = ui.label("—").classes("rb-score-value")
        with ui.column().classes("rb-score-card"):
            ui.label("Current resume score").classes("rb-score-label")
            score_after_val = ui.label("—").classes("rb-score-value")

    variant_row = ui.row().classes("gap-2 hidden")
    variant_buttons: dict[str, Any] = {}
    with variant_row:
        ui.label("Style:").classes("self-center text-sm font-medium")
        for name, label in variant_option_labels().items():
            variant_buttons[name] = ui.button(label).props("outline dense")

    missing_row = ui.column().classes("gap-2 hidden")
    changelog_panel = ui.expansion("What changed", icon="history").classes("w-full hidden")
    with changelog_panel:
        changelog_content = ui.column().classes("w-full gap-1")
    section_editor = ui.expansion("Edit sections", icon="edit").classes("w-full hidden")
    with section_editor:
        section_editor_content = ui.column().classes("w-full gap-2")

    output = ui.markdown(
        "Upload a resume, choose an AI provider, paste a JD, then tailor."
    ).classes("rb-output-panel w-full")
    progress_label = ui.label("").classes("text-sm text-gray-600")
    progress = ui.linear_progress(value=0).props("rounded").classes("w-full")

    paywall = ui.column().classes("hidden gap-2")
    with paywall:
        ui.label("Unlock your tailored resume").classes("text-lg font-bold")
        paywall_price = ui.label(f"Unlock for {_format_price(3.99)}").classes(
            "text-base font-medium"
        )
        stripe_btn = ui.button("Pay with Stripe")
        crypto_btn = ui.button("Pay with Crypto")

    export_row = ui.row().classes("gap-2 hidden")
    with export_row:
        export_txt = ui.button("Export TXT")
        export_docx = ui.button("Export DOCX")
        export_pdf = ui.button("Export PDF")

    tailor_btn = ui.button("Tailor resume", icon="auto_awesome").props("unelevated color=primary")

    add_section_dialog = ui.dialog()
    pending_section: dict[str, str | None] = {"name": None}
    with add_section_dialog, ui.card().classes("gap-3").style("min-width: 360px"):
        add_section_title = ui.label("Add section").classes("text-lg font-medium")
        add_section_input = ui.textarea("Section content").classes("w-full").props(
            "outlined autogrow"
        )
        add_section_confirm = ui.button("Add and tailor").props("unelevated")

    def _highlight_variant(name: str) -> None:
        for key, btn in variant_buttons.items():
            if key == name:
                btn.classes(add="rb-variant-active")
            else:
                btn.classes(remove="rb-variant-active")

    def _update_score_display(body: dict[str, Any], final: dict[str, Any]) -> None:
        match = final.get("match_score") or body.get("match_score") or {}
        prev = (
            match.get("previous_overall")
            or match.get("previous")
            or body.get("ats_score_before")
        )
        curr = match.get("current_overall") or match.get("current") or body.get("ats_score_after")
        if prev is not None or curr is not None:
            score_row.classes(remove="hidden")
            score_before_val.set_text(_score_label(prev))
            score_after_val.set_text(_score_label(curr))
        else:
            score_row.classes(add="hidden")

    def _render_missing_sections(final: dict[str, Any]) -> None:
        missing_row.clear()
        suggestions = final.get("sections_suggested") or []
        if not suggestions or not state.get("can_view_output"):
            missing_row.classes(add="hidden")
            return
        missing_row.classes(remove="hidden")
        with missing_row:
            ui.label("Optional sections you could add (not required for this output):").classes(
                "text-sm font-medium"
            )
            with ui.column().classes("gap-1"):
                for item in suggestions:
                    section = item.get("section", "section")
                    reason = item.get("reason", "")
                    ui.label(f"• {section}: {reason}").classes("text-sm rb-subtle")
            with ui.row().classes("gap-2 flex-wrap mt-2"):
                for item in suggestions:
                    section = item.get("section")
                    if not section:
                        continue
                    ui.button(
                        f"Add {section}",
                        on_click=lambda s=section: open_add_section(s),
                    ).props("outline dense")

    def _render_changelog(final: dict[str, Any]) -> None:
        changelog_content.clear()
        changelog = final.get("changelog") or []
        selected = state.get("selected_variant", "balanced")
        filtered = [c for c in changelog if c.get("variant") == selected]
        if not filtered or not state.get("can_view_output"):
            changelog_panel.classes(add="hidden")
            return
        changelog_panel.classes(remove="hidden")
        with changelog_content:
            for entry in filtered[:12]:
                ui.label(f"• {entry.get('detail', entry.get('type', 'change'))}").classes("text-sm")

    def _render_section_editor(final: dict[str, Any]) -> None:
        section_editor_content.clear()
        editable = final.get("sections_editable") or {}
        if not editable or not state.get("can_view_output"):
            section_editor.classes(add="hidden")
            return
        section_editor.classes(remove="hidden")
        with section_editor_content:
            for section, data in editable.items():
                with ui.expansion(section.capitalize(), icon="article").classes("w-full"):
                    ui.label("Original").classes("text-xs text-gray-500")
                    ui.markdown(str(data.get("original") or "_Empty_")).classes("text-sm mb-2")
                    override = ui.textarea(
                        "Your edit",
                        value=str(data.get("user_override") or ""),
                    ).classes("w-full").props("outlined autogrow")
                    ui.button(
                        "Save section",
                        on_click=lambda s=section, field=override: save_section(s, field),
                    ).props("flat dense")

    def open_add_section(section: str) -> None:
        pending_section["name"] = section
        add_section_title.set_text(f"Add {section.capitalize()} section")
        add_section_input.value = ""
        add_section_dialog.open()

    async def load_providers() -> None:
        async with api_client() as client:
            resp = await client.get("/api/v1/runs/providers")
        if resp.status_code != 200:
            return
        providers = resp.json().get("providers", [])
        state["providers"] = providers
        options = {p["id"]: p["label"] for p in providers if p.get("configured")}
        if not options:
            options = {"huggingface": "Hugging Face"}
        provider_select.options = options
        default = next((p["id"] for p in providers if p.get("is_default")), "huggingface")
        provider_select.value = default if default in options else next(iter(options))

    async def load_status() -> None:
        async with api_client() as client:
            resp = await client.get("/api/v1/auth/me")
            billing = await client.get("/api/v1/billing/status")
        if resp.status_code != 200:
            status_label.set_text("Device workspace unavailable. Refresh this page.")
            return
        data = resp.json()
        bill = billing.json() if billing.status_code == 200 else {}
        price = float(bill.get("price_usd", 3.99))
        paywall_price.set_text(f"Unlock for {_format_price(price)}")
        status_label.set_text(
            f"Free trial: {'used' if data.get('free_trial_used') else 'available'} | "
            f"Upload: {'yes' if data.get('can_upload') else 'pay required'} | "
            f"Unlock: {_format_price(price)}"
        )

    async def handle_upload(event: Any) -> None:
        upload_file = event.file
        upload_status.set_text("Uploading resume...")
        try:
            file_bytes = await upload_file.read()
        except Exception as exc:
            upload_status.set_text(f"Could not read upload: {exc}")
            return
        async with api_client() as client:
            resp = await client.post(
                "/api/v1/resumes",
                files={
                    "file": (
                        upload_file.name,
                        file_bytes,
                        upload_file.content_type or "application/octet-stream",
                    )
                },
            )
        if resp.status_code == 200:
            data = resp.json()
            state["resume_id"] = data["resume_id"]
            upload_status.set_text(f"Uploaded: {data.get('filename')}")
        else:
            upload_status.set_text(_format_detail(resp.text, "Upload failed"))

    async def refresh_run() -> dict[str, Any] | None:
        run_id = state.get("run_id")
        if not run_id:
            return None
        async with api_client() as client:
            resp = await client.get(f"/api/v1/runs/{run_id}")
        if resp.status_code != 200:
            upload_status.set_text(_format_detail(resp.text, "Could not load run"))
            return None

        body = resp.json()
        final = body.get("final_output") or {}
        apply_run_context(state, body)
        if body.get("resume_filename"):
            upload_status.set_text(f"Resume: {body['resume_filename']}")
        elif state.get("resume_id"):
            upload_status.set_text(f"Resume: saved ({str(state['resume_id'])[:8]}…)")
        if body.get("jd_text") and not (jd_input.value or "").strip():
            jd_input.value = body["jd_text"]
        is_locked = body.get("output_locked") and not final
        state["can_view_output"] = not is_locked

        selected = final.get("selected_variant") or state.get("selected_variant", "balanced")
        state["selected_variant"] = selected
        _highlight_variant(selected)
        _update_score_display(body, final)

        if is_locked:
            paywall.classes(remove="hidden")
            export_row.classes(add="hidden")
            variant_row.classes(add="hidden")
            output.classes(add="rb-locked")
            output.set_content(f"**Preview (locked)**\n\n{body.get('preview_text', '')[:500]}")
            return body

        paywall.classes(add="hidden")
        output.classes(remove="rb-locked")
        variant_row.classes(remove="hidden")
        output.set_content(final.get("plain_text") or body.get("preview_text") or "")
        export_row.classes(remove="hidden")
        _render_missing_sections(final)
        _render_changelog(final)
        _render_section_editor(final)
        return body

    async def select_variant(name: str) -> None:
        if not state.get("can_view_output"):
            upload_status.set_text("Unlock output before switching variants.")
            return
        run_id = state.get("run_id")
        if not run_id:
            return
        async with api_client() as client:
            resp = await client.patch(f"/api/v1/runs/{run_id}/variant", json={"variant": name})
        if resp.status_code != 200:
            upload_status.set_text(_format_detail(resp.text, "Could not switch variant"))
            return
        state["selected_variant"] = name
        await refresh_run()

    async def stream_progress(run_id: str) -> str:
        def _update(label: str, value: float) -> None:
            progress_label.set_text(label)
            progress.value = value

        return await watch_run_progress(
            run_id,
            steps=STEPS,
            on_update=_update,
            step_increment=0.15,
        )

    async def tailor() -> None:
        jd = (jd_input.value or "").strip()
        if len(jd) < 20:
            output.set_content("Job description must be at least 20 characters.")
            return
        log_console(
            "dashboard tailor: submit clicked",
            jd_chars=len(jd),
            provider=provider_select.value or "huggingface",
            variant=variant_select.value or DEFAULT_VARIANT.value,
        )
        progress.value = 0.05
        progress_label.set_text("Starting run...")
        paywall.classes(add="hidden")
        export_row.classes(add="hidden")
        variant_row.classes(add="hidden")
        changelog_panel.classes(add="hidden")
        section_editor.classes(add="hidden")
        missing_row.classes(add="hidden")
        output.classes(remove="rb-locked")
        output.set_content("_Processing..._")

        try:
            async with request_user_session() as (session, user):
                resume_id = state.get("resume_id")
                if not resume_id:
                    result = await session.execute(
                        select(MasterResume.id)
                        .where(MasterResume.user_id == user.id)
                        .order_by(MasterResume.created_at.desc())
                        .limit(1)
                    )
                    resume_id = result.scalar_one_or_none()
                if not resume_id:
                    output.set_content("Upload a resume first.")
                    return
                log_console(
                    "dashboard tailor: creating run in-process",
                    resume_id=str(resume_id),
                )
                run_data = await create_run_record(
                    session,
                    user,
                    resume_id=UUID(str(resume_id)),
                    jd_text=jd,
                    llm_provider=provider_select.value or "huggingface",
                    variant=variant_select.value or DEFAULT_VARIANT.value,
                )
        except RunLaunchError as exc:
            log_console("dashboard tailor: run creation failed", level="error", detail=exc.detail)
            output.set_content(exc.detail)
            return
        except Exception as exc:
            log_console("dashboard tailor: unexpected error", level="error", detail=str(exc))
            output.set_content(f"Could not start run: {exc}")
            return

        state["run_id"] = run_data["run_id"]
        state["jd_text"] = jd
        await save_browser_workflow(
            run_id=run_data["run_id"],
            resume_id=str(resume_id),
            jd_text=jd,
        )
        log_console("dashboard tailor: run created", run_id=run_data["run_id"])
        await asyncio.gather(
            stream_progress(state["run_id"]),
            execute_run_background(UUID(run_data["run_id"]), run_data["variant"]),
        )
        await refresh_run()
        await load_status()

    async def pay_stripe() -> None:
        run_id = state.get("run_id")
        if not run_id:
            return
        await save_browser_workflow(
            run_id=str(run_id),
            resume_id=str(state["resume_id"]) if state.get("resume_id") else None,
            jd_text=(jd_input.value or "").strip(),
        )
        async with api_client() as client:
            resp = await client.post("/api/v1/billing/stripe/checkout", json={"run_id": run_id})
        if resp.status_code == 200:
            ui.navigate.to(resp.json()["checkout_url"])

    async def pay_crypto() -> None:
        run_id = state.get("run_id")
        if not run_id:
            return
        async with api_client() as client:
            resp = await client.post(
                "/api/v1/billing/crypto/invoice",
                json={"run_id": run_id, "pay_currency": "btc"},
            )
        if resp.status_code == 200:
            data = resp.json()
            upload_status.set_text(
                f"Send {data.get('pay_amount')} {data.get('pay_currency')} "
                f"to {data.get('pay_address')}"
            )

    async def do_export(fmt: str) -> None:
        run_id = state.get("run_id")
        if not run_id:
            return
        async with api_client() as client:
            resp = await client.post("/api/v1/exports", json={"run_id": run_id, "format": fmt})
        if resp.status_code == 200:
            ui.navigate.to(resp.json()["download_url"], new_tab=True)

    async def confirm_add_section() -> None:
        section = pending_section["name"]
        run_id = state.get("run_id")
        content = (add_section_input.value or "").strip()
        if not section or not run_id or not content:
            upload_status.set_text("Enter section content first.")
            return
        async with api_client() as client:
            resp = await client.post(
                f"/api/v1/runs/{run_id}/sections/{section}/add",
                json={"content": content, "retailor": True},
            )
        if resp.status_code != 200:
            upload_status.set_text(_format_detail(resp.text, "Could not add section"))
            return
        add_section_dialog.close()
        await refresh_run()
        upload_status.set_text(f"Added and tailored {section} section.")

    async def save_section(section: str, field: Any) -> None:
        run_id = state.get("run_id")
        content = (field.value or "").strip()
        if not run_id or not content:
            return
        async with api_client() as client:
            resp = await client.patch(
                f"/api/v1/runs/{run_id}/sections/{section}",
                json={"content": content},
            )
        if resp.status_code == 200:
            await refresh_run()
            upload_status.set_text(f"Updated {section} section.")
        else:
            upload_status.set_text(_format_detail(resp.text, "Section save failed"))

    upload.on_upload(handle_upload)
    stripe_btn.on_click(pay_stripe)
    crypto_btn.on_click(pay_crypto)
    export_txt.on_click(lambda: do_export("txt"))
    export_docx.on_click(lambda: do_export("docx"))
    export_pdf.on_click(lambda: do_export("pdf"))
    tailor_btn.on_click(tailor)
    add_section_confirm.on_click(confirm_add_section)
    for name, btn in variant_buttons.items():
        btn.on_click(lambda n=name: select_variant(n))

    ui.timer(0.1, load_providers, once=True)
    ui.timer(0.15, load_status, once=True)
    ui.timer(0.1, lambda: ui.run_javascript("window.rbFingerprint.get();"), once=True)

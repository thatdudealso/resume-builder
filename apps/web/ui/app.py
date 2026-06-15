from __future__ import annotations

from nicegui import ui

from apps.web.ui.auth_guard import api_client, require_auth


@ui.page("/login")
def login_page() -> None:
    ui.label("Resume Builder").classes("text-2xl font-bold")
    email = ui.input("Email").classes("w-full")
    password = ui.input("Password", password=True).classes("w-full")
    error = ui.label("").classes("text-red")

    async def do_login() -> None:
        async with api_client() as client:
            resp = await client.post(
                "/api/v1/auth/login",
                json={"email": email.value, "password": password.value},
                headers={"X-Device-Fingerprint": "nicegui-client"},
            )
        if resp.status_code == 200:
            ui.navigate.to("/app/dashboard")
        else:
            detail = resp.json().get("detail", "Login failed") if resp.content else "Login failed"
            error.set_text(str(detail))

    ui.button("Login", on_click=do_login)
    ui.link("Register", "/app/register")


@ui.page("/register")
def register_page() -> None:
    ui.label("Create account").classes("text-2xl font-bold")
    email = ui.input("Email").classes("w-full")
    password = ui.input("Password", password=True).classes("w-full")
    error = ui.label("").classes("text-red")

    async def do_register() -> None:
        async with api_client() as client:
            resp = await client.post(
                "/api/v1/auth/register",
                json={"email": email.value, "password": password.value},
                headers={"X-Device-Fingerprint": "nicegui-client"},
            )
        if resp.status_code == 200:
            ui.navigate.to("/app/dashboard")
        else:
            detail = resp.json().get("detail", "Registration failed") if resp.content else "Registration failed"
            error.set_text(str(detail))

    ui.button("Register", on_click=do_register)


@ui.page("/dashboard")
@require_auth
def dashboard_page() -> None:
    ui.label("Dashboard").classes("text-2xl font-bold")
    status_label = ui.label("")
    upload_status = ui.label("")
    jd_input = ui.textarea("Job Description").classes("w-full")
    output = ui.markdown("").classes("w-full")
    paywall = ui.column().classes("hidden")
    export_row = ui.row().classes("gap-2 hidden")
    current_run_id: dict[str, str | None] = {"value": None}

    with paywall:
        ui.label("Unlock your tailored resume — $9.99").classes("text-lg font-bold")

        async def pay_stripe() -> None:
            run_id = current_run_id["value"]
            if not run_id:
                return
            async with api_client() as client:
                resp = await client.post(
                    "/api/v1/billing/stripe/checkout",
                    json={"run_id": run_id},
                )
            if resp.status_code == 200:
                ui.navigate.to(resp.json()["checkout_url"], new_tab=True)
            else:
                upload_status.set_text(f"Stripe error: {resp.text}")

        async def pay_crypto() -> None:
            run_id = current_run_id["value"]
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
                    f"Send {data.get('pay_amount')} {data.get('pay_currency')} to {data.get('pay_address')}"
                )
            else:
                upload_status.set_text(f"Crypto error: {resp.text}")

        ui.button("Pay with Stripe", on_click=pay_stripe)
        ui.button("Pay with Crypto", on_click=pay_crypto)

    async def do_export(fmt: str) -> None:
        run_id = current_run_id["value"]
        if not run_id:
            return
        async with api_client() as client:
            resp = await client.post("/api/v1/exports", json={"run_id": run_id, "format": fmt})
        if resp.status_code == 200:
            path = resp.json()["download_url"]
            ui.navigate.to(path, new_tab=True)
        else:
            upload_status.set_text(f"Export failed: {resp.text}")

    with export_row:
        ui.button("Export TXT", on_click=lambda: do_export("txt"))
        ui.button("Export DOCX", on_click=lambda: do_export("docx"))
        ui.button("Export PDF", on_click=lambda: do_export("pdf"))

    async def load_status() -> None:
        async with api_client() as client:
            resp = await client.get("/api/v1/auth/me")
            billing = await client.get("/api/v1/billing/status")
        if resp.status_code == 200:
            data = resp.json()
            bill = billing.json() if billing.status_code == 200 else {}
            status_label.set_text(
                f"Free trial used: {data.get('free_trial_used')} | "
                f"Can upload: {data.get('can_upload')} | "
                f"Price: ${bill.get('price_usd', '9.99')}"
            )

    async def handle_upload(e) -> None:
        async with api_client() as client:
            resp = await client.post(
                "/api/v1/resumes",
                files={"file": (e.name, e.content.read(), e.type or "application/octet-stream")},
            )
        if resp.status_code == 200:
            upload_status.set_text(f"Uploaded: {resp.json().get('filename')}")
        else:
            upload_status.set_text(f"Upload failed: {resp.text}")

    ui.upload(on_upload=handle_upload, auto_upload=True).classes("w-full")
    ui.timer(0.1, load_status, once=True)

    async def tailor() -> None:
        jd = (jd_input.value or "").strip()
        if len(jd) < 20:
            output.set_content("Job description must be at least 20 characters.")
            return
        output.set_content("_Processing..._")
        paywall.classes(add="hidden")
        export_row.classes(add="hidden")

        async with api_client() as client:
            resumes_resp = await client.get("/api/v1/resumes")
            resumes = resumes_resp.json().get("resumes", [])
            if not resumes:
                output.set_content("Upload a resume first.")
                return
            run_resp = await client.post(
                "/api/v1/runs",
                json={"resume_id": resumes[0]["resume_id"], "jd_text": jd},
            )
            if run_resp.status_code != 200:
                output.set_content(f"Error: {run_resp.text}")
                return
            run_data = run_resp.json()
            run_id = run_data["run_id"]
            current_run_id["value"] = run_id

            stream_text = []
            async with client.stream("GET", f"/api/v1/runs/{run_id}/stream") as stream:
                async for line in stream.aiter_lines():
                    if line.startswith("data: "):
                        stream_text.append(line[6:])
                    if line.startswith("event: done") or line.startswith("event: error"):
                        break

            detail = await client.get(f"/api/v1/runs/{run_id}")
            if detail.status_code != 200:
                output.set_content(f"Error loading run: {detail.text}")
                return
            body = detail.json()
            if body.get("output_locked") and not body.get("final_output"):
                paywall.classes(remove="hidden")
                output.set_content(
                    f"**Preview (locked):**\n\n{body.get('preview_text', '')[:400]}"
                )
                output.classes(add="blur-sm")
            else:
                fo = body.get("final_output") or {}
                output.set_content(fo.get("plain_text", body.get("preview_text", "")))
                output.classes(remove="blur-sm")
                export_row.classes(remove="hidden")

    ui.button("Tailor Resume", on_click=tailor)


def register_ui() -> None:
    pass

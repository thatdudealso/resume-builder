# feature/nicegui-paywall-polish

## Goal

Production-quality NiceGUI UX for one-page device workspace, streaming, paywall, and post-payment unlock.

## Tasks

- [x] Create/reuse device workspace without user-facing login or registration
- [x] Live SSE progress on the home page (replace fixed sleep)
- [x] Poll billing/run status after Stripe return (`?paid=1`)
- [x] Client-side device fingerprint header on all API calls
- [x] Blur + paywall modal until webhook confirms payment
- [x] Show export buttons only when `can_view_output` is true
- [x] Build functional single-page `/app/` workflow with no login or account UI

## Acceptance

User can upload, tailor, pay, see full output, and export without login, account creation, or manual API calls.

## Implementation Notes

- Rebuilt `apps/web/ui/app.py` as a minimal task-first NiceGUI workflow.
- Kept the complete product flow on the `/app/` home page. There are no
  NiceGUI login, registration, dashboard, account, password, or logout flows.
- The home page creates or reuses a private device workspace from
  `rb_device_fingerprint`; there is no user-facing auth step.
- A stable `rb_device_fingerprint` cookie is generated in-browser and sent as
  `X-Device-Fingerprint` by the server-side UI API client.
- The home page streams `/api/v1/runs/{run_id}/stream`, updates progress by graph
  node, and loads the final run payload from `/api/v1/runs/{run_id}`.
- Locked runs show only `preview_text`, apply a blur class, and open the paywall
  dialog. Export controls remain hidden until output is viewable.
- Stripe return URLs at `/app/?paid=1&run_id=...` trigger polling until the run is
  unlocked by backend webhook processing.
- Browser E2E still needs verification with a running Docker/local stack.

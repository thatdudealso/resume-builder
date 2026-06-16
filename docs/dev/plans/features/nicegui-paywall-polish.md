# feature/nicegui-paywall-polish

## Goal

Production-quality NiceGUI UX for auth, streaming, paywall, and post-payment unlock.

## Tasks

- [x] Set auth cookies in browser (form POST or `run_javascript` fetch with `credentials: 'include'`)
- [x] Live SSE progress on the home page (replace fixed sleep)
- [x] Poll billing/run status after Stripe return (`?paid=1`)
- [x] Client-side device fingerprint header on all API calls
- [x] Blur + paywall modal until webhook confirms payment
- [x] Show export buttons only when `can_view_output` is true
- [x] Build functional single-page `/app/` workflow with register/sign-in entrypoint

## Acceptance

User can register, upload, tailor, pay, see full output, and export without manual API calls.

## Implementation Notes

- Rebuilt `apps/web/ui/app.py` as a minimal task-first NiceGUI workflow.
- Kept the complete product flow on the `/app/` home page. There are no
  NiceGUI `/login`, `/register`, or `/dashboard` pages.
- Added an embedded create/sign-in form on the home page; successful auth reloads
  `/app/` into the authenticated workspace.
- Browser-side auth uses `fetch(..., credentials: 'include')` so backend httpOnly
  cookies are set on the real browser session.
- A stable `rb_device_fingerprint` cookie is generated in-browser and sent as
  `X-Device-Fingerprint` by browser auth and the server-side UI API client.
- The home page streams `/api/v1/runs/{run_id}/stream`, updates progress by graph
  node, and loads the final run payload from `/api/v1/runs/{run_id}`.
- Locked runs show only `preview_text`, apply a blur class, and open the paywall
  dialog. Export controls remain hidden until output is viewable.
- Stripe return URLs at `/app/?paid=1&run_id=...` trigger polling until the run is
  unlocked by backend webhook processing.
- Browser E2E still needs verification with a running Docker/local stack.

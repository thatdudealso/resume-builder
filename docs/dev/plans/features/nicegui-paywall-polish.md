# feature/nicegui-paywall-polish

## Goal

Production-quality NiceGUI UX for auth, streaming, paywall, and post-payment unlock.

## Tasks

- [ ] Set auth cookies in browser (form POST or `run_javascript` fetch with `credentials: 'include'`)
- [ ] Live SSE progress in dashboard (replace fixed sleep)
- [ ] Poll billing/run status after Stripe return (`?paid=1`)
- [ ] Client-side device fingerprint header on all API calls
- [ ] Blur + paywall modal until webhook confirms payment
- [ ] Show export buttons only when `can_view_output` is true

## Acceptance

User can register, upload, tailor, pay, see full output, and export without manual API calls.

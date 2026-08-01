from __future__ import annotations

AUTH_CALLBACK_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>ResumeBild — Signing in</title>
  <style>
    body { font-family: "Source Serif 4", Georgia, serif; background:
           linear-gradient(160deg, #ebe4d6 0%, #f7f3ea 45%, #e7efe8 100%);
           color: #1c1917; display: grid; place-items: center; min-height: 100vh; margin: 0; }
    main { text-align: center; max-width: 28rem; padding: 2rem; }
    h1 { font-size: 2rem; letter-spacing: -0.03em; margin: 0 0 0.75rem; }
    p { line-height: 1.5; color: #44403c; }
    .err { color: #9f1239; }
  </style>
</head>
<body>
  <main>
    <h1>ResumeBild</h1>
    <p id="status">Finishing sign-in…</p>
  </main>
  <script>
    (async () => {
      const status = document.getElementById('status');
      const hash = window.location.hash.startsWith('#')
        ? window.location.hash.slice(1)
        : '';
      const params = new URLSearchParams(hash || window.location.search);
      const idToken = params.get('id_token');
      if (!idToken) {
        status.className = 'err';
        status.textContent = 'Missing sign-in token. Return to login and try again.';
        return;
      }
      try {
        const resp = await fetch('/api/v1/auth/cognito/exchange', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({ id_token: idToken }),
        });
        if (!resp.ok) {
          throw new Error('exchange failed');
        }
        history.replaceState(null, '', '/auth/callback');
        window.location.replace('/app/');
      } catch (err) {
        status.className = 'err';
        status.textContent = 'Sign-in failed. Please try again from 5432wire login.';
      }
    })();
  </script>
</body>
</html>
"""

#!/usr/bin/env bash
# Forward Stripe webhooks to the local Resume Builder app.
# Requires: Stripe CLI (brew install stripe/stripe-cli/stripe)
# Usage: ./scripts/stripe_webhook_listen.sh
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v stripe >/dev/null 2>&1; then
  echo "Stripe CLI not found. Install with: brew install stripe/stripe-cli/stripe"
  exit 1
fi

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [[ -z "${STRIPE_SECRET_KEY:-}" ]]; then
  echo "Set STRIPE_SECRET_KEY in .env before running this script."
  exit 1
fi

FORWARD_URL="${STRIPE_WEBHOOK_FORWARD_URL:-http://localhost:8000/api/v1/webhooks/stripe}"
SECRET=$(stripe listen --api-key "$STRIPE_SECRET_KEY" --print-secret)

if grep -q '^STRIPE_WEBHOOK_SECRET=' .env 2>/dev/null; then
  if [[ "$(uname)" == "Darwin" ]]; then
    sed -i '' "s|^STRIPE_WEBHOOK_SECRET=.*|STRIPE_WEBHOOK_SECRET=${SECRET}|" .env
  else
    sed -i "s|^STRIPE_WEBHOOK_SECRET=.*|STRIPE_WEBHOOK_SECRET=${SECRET}|" .env
  fi
else
  echo "STRIPE_WEBHOOK_SECRET=${SECRET}" >> .env
fi

echo "Updated STRIPE_WEBHOOK_SECRET in .env"
echo "Restart the web container: docker compose restart web"
echo ""
echo "Forwarding checkout.session.completed -> ${FORWARD_URL}"
exec stripe listen \
  --api-key "$STRIPE_SECRET_KEY" \
  --events checkout.session.completed \
  --forward-to "$FORWARD_URL"

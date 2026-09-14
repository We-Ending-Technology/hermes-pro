#!/usr/bin/env bash
set -u
base="${1:-https://hermes-pro-api-commercial.onrender.com}"
for attempt in $(seq 1 30); do
  health=$(curl -sS -o /tmp/hermes-health -w '%{http_code}' "$base/health" || true)
  dashboard=$(curl -sS -o /tmp/hermes-dashboard -w '%{http_code}' "$base/api/v1/dashboard" || true)
  products=$(curl -sS -o /tmp/hermes-products -w '%{http_code}' "$base/api/v1/products" || true)
  jobs=$(curl -sS -o /tmp/hermes-jobs -w '%{http_code}' "$base/api/v1/jobs" || true)
  chat=$(curl -sS -o /tmp/hermes-chat -w '%{http_code}' -X POST -H 'Content-Type: application/json' --data '{"message":"Responda apenas: Hermes online"}' "$base/api/v1/chat" || true)
  echo "attempt=$attempt health=$health dashboard=$dashboard products=$products jobs=$jobs chat=$chat"
  if [ "$health" = 200 ] && [ "$dashboard" = 200 ] && [ "$products" = 200 ] && [ "$jobs" = 200 ] && [ "$chat" = 200 ]; then
    printf '%s\n' '--- chat ---'; cat /tmp/hermes-chat
    printf '%s\n' '--- dashboard ---'; cat /tmp/hermes-dashboard
    exit 0
  fi
  sleep 10
done
exit 1

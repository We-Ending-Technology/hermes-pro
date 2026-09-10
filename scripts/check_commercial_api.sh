#!/usr/bin/env bash
set -u
base="https://hermes-pro-api-commercial.onrender.com"
for attempt in $(seq 1 30); do
  code=$(curl -sS -o /tmp/hermes-commercial-health -w '%{http_code}' "$base/health" || true)
  echo "attempt=$attempt health=$code"
  if [ "$code" = "200" ]; then
    ok=1
    for path in / /health /api/v1/dashboard /api/v1/products /api/v1/jobs; do
      status=$(curl -sS -o "/tmp/hermes-commercial-${attempt}" -w '%{http_code}' "$base$path" || true)
      echo "$path HTTP $status"
      [ "$status" = "200" ] || ok=0
    done
    if [ "$ok" = "1" ]; then exit 0; fi
  fi
  sleep 10
done
exit 1

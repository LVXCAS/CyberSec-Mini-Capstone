#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Tearing down all containers and volumes ==="
docker compose down -v --remove-orphans 2>/dev/null || true

echo "=== Rebuilding from scratch ==="
docker compose up --build -d

echo "=== Waiting for orchestrator to be healthy ==="
timeout 120 bash -c '
  until curl -sf http://localhost:8000/health > /dev/null 2>&1; do
    sleep 2
    echo -n "."
  done
' || { echo " TIMEOUT: orchestrator did not become healthy"; exit 1; }
echo " healthy"

echo "=== Reset complete ==="

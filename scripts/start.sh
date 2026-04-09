#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Starting services ==="
docker compose up -d

echo "=== Waiting for orchestrator ==="
timeout 120 bash -c '
  until curl -sf http://localhost:8000/health > /dev/null 2>&1; do
    sleep 2
  done
' || { echo "Orchestrator did not become healthy"; exit 1; }

echo "=== Services ready ==="

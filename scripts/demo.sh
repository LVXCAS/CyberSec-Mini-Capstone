#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "========================================="
echo "  CyberSec AI Capstone — Demo Launcher"
echo "========================================="

# Step 1: Clean reset
./scripts/reset.sh

# Step 2: Launch dashboard (foreground)
echo "=== Launching live dashboard ==="
echo "(Press Ctrl+C to exit dashboard)"
python -m display.dashboard

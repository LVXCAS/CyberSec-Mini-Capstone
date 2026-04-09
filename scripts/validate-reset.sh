#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

RUNS=5
echo "=== Validating $RUNS consecutive reset+start cycles ==="

for i in $(seq 1 $RUNS); do
  echo ""
  echo "--- Run $i/$RUNS ---"
  ./scripts/reset.sh

  # Verify health
  if ! curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "FAIL: Run $i — orchestrator not healthy after reset"
    exit 1
  fi

  # Verify no stale game data
  SCORE_COUNT=$(curl -sf http://localhost:8000/game/status 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('scores',{}).get('red',0) + d.get('scores',{}).get('blue',0))" 2>/dev/null || echo "0")
  if [ "$SCORE_COUNT" != "0" ]; then
    echo "FAIL: Run $i — stale score data detected ($SCORE_COUNT points)"
    exit 1
  fi

  echo "Run $i: PASS"
done

echo ""
echo "=== All $RUNS runs passed — no stale data ==="

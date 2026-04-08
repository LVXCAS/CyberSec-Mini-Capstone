---
phase: "01"
plan: "07"
subsystem: agent-core
tags: [act_node, response-parsing, orchestrator, bug-fix, regression-test]
requires: []
provides: [corrected-act-node-parsing, act-node-regression-tests]
affects: [phase-02-agent-skills]
tech-stack:
  added: []
  patterns: [nested-dict-parsing, mock-isolation-tests]
key-files:
  created: [tests/test_act_node_parsing.py]
  modified: [agents/base_agent.py]
decisions:
  - id: mock-log-decision
    summary: "_log_decision mocked in tests to avoid Docker-only /app/data path dependency"
    rationale: "Tests run on host machine; log path hardcoded for container. Mocking isolates parsing logic."
metrics:
  duration: "~5 minutes"
  completed: "2026-04-08"
---

# Phase 01 Plan 07: Act Node Response Parsing Fix Summary

**One-liner:** Fixed act_node to read exit_code/stdout from nested `result.result` dict and derive `was_blocked` from `allowed` field, matching orchestrator ExecuteResponse schema.

## What Was Done

### Task 1: Fix act_node response parsing

Replaced three incorrect flat-dict lookups in `agents/base_agent.py` (lines 277-280):

```python
# Before (broken — keys don't exist at top level)
exit_code = result.get("exit_code", -1)
stdout = result.get("stdout", "")
was_blocked = result.get("blocked", False)

# After (correct — matches ExecuteResponse schema)
was_blocked = not result.get("allowed", True)
cmd_result = result.get("result") or {}
exit_code = cmd_result.get("exit_code", -1)
stdout = cmd_result.get("stdout", "")
```

**Impact:** Before this fix, every command returned exit_code=-1, empty stdout, and was_blocked=False, making findings and observations useless.

### Task 2: Regression tests for act_node parsing

Created `tests/test_act_node_parsing.py` with three test scenarios:

1. **Allowed command with output** - asserts exit_code==0, stdout populated, finding appended
2. **Blocked command** - asserts was_blocked==True, exit_code==-1, no finding
3. **Allowed command with nonzero exit** - asserts exit_code==1, was_blocked==False, no finding

All three pass. `_log_decision` is mocked to isolate parsing from Docker-specific file paths.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Mocked _log_decision in tests**

- **Found during:** Task 2
- **Issue:** `_log_decision` tries to `mkdir /app/data` (Docker container path), causing OSError on host machine
- **Fix:** Added `@patch("agents.base_agent._log_decision")` to all three tests
- **Files modified:** tests/test_act_node_parsing.py
- **Commit:** 08141b3

No other deviations.

## Verification

```
grep -n "cmd_result" agents/base_agent.py
278:        cmd_result = result.get("result") or {}
279:        exit_code = cmd_result.get("exit_code", -1)
280:        stdout = cmd_result.get("stdout", "")

grep -n "was_blocked = not result" agents/base_agent.py
277:        was_blocked = not result.get("allowed", True)

pytest tests/test_act_node_parsing.py -v
3 passed in 0.16s
```

## Next Phase Readiness

This fix unblocks Phase 2 agent skills work. Agents will now correctly:
- Accumulate findings when commands succeed
- Detect blocked commands and log them
- Build meaningful observations with real stdout

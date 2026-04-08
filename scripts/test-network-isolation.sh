#!/usr/bin/env bash
set -euo pipefail

# Network isolation verification script for CyberSec AI Capstone
# Validates that red-agent and blue-agent cannot reach each other,
# but both can reach orchestrator.

GREEN='\033[0;32m'
RED='\033[0;31m'
RESET='\033[0m'

PASS=0
FAIL=0

pass() {
    printf "${GREEN}[PASS]${RESET} %s\n" "$1"
    PASS=$((PASS + 1))
}

fail() {
    printf "${RED}[FAIL]${RESET} %s\n" "$1"
    FAIL=$((FAIL + 1))
}

# Check that required containers are running
echo "Checking containers are running..."
if ! docker compose ps --format '{{.Name}}' 2>/dev/null | grep -q "red-agent"; then
    printf "${RED}ERROR:${RESET} Containers are not running. Start them with: docker compose up -d\n"
    exit 1
fi

echo ""
echo "=== Network Isolation Tests ==="
echo ""

# Test 1: red-agent CANNOT reach blue-agent (expected failure)
printf "Test 1: red-agent -> blue-agent (expected: BLOCKED)\n"
if docker compose exec red-agent ping -c 1 -W 2 blue-agent > /dev/null 2>&1; then
    fail "red-agent CAN reach blue-agent — isolation is BROKEN"
else
    pass "red-agent cannot reach blue-agent"
fi

# Test 2: blue-agent CANNOT reach red-agent (expected failure)
printf "Test 2: blue-agent -> red-agent (expected: BLOCKED)\n"
if docker compose exec blue-agent ping -c 1 -W 2 red-agent > /dev/null 2>&1; then
    fail "blue-agent CAN reach red-agent — isolation is BROKEN"
else
    pass "blue-agent cannot reach red-agent"
fi

# Test 3: red-agent CAN reach orchestrator (expected success)
printf "Test 3: red-agent -> orchestrator (expected: REACHABLE)\n"
if docker compose exec red-agent ping -c 1 -W 2 orchestrator > /dev/null 2>&1; then
    pass "red-agent can reach orchestrator"
else
    fail "red-agent cannot reach orchestrator — connectivity is BROKEN"
fi

# Test 4: blue-agent CAN reach orchestrator (expected success)
printf "Test 4: blue-agent -> orchestrator (expected: REACHABLE)\n"
if docker compose exec blue-agent ping -c 1 -W 2 orchestrator > /dev/null 2>&1; then
    pass "blue-agent can reach orchestrator"
else
    fail "blue-agent cannot reach orchestrator — connectivity is BROKEN"
fi

# Summary
echo ""
echo "=== Summary ==="
printf "Passed: ${GREEN}%d${RESET}  Failed: ${RED}%d${RESET}\n" "$PASS" "$FAIL"
echo ""

if [ "$FAIL" -gt 0 ]; then
    printf "${RED}NETWORK ISOLATION TEST FAILED${RESET}\n"
    exit 1
else
    printf "${GREEN}ALL TESTS PASSED — network isolation is correctly configured${RESET}\n"
    exit 0
fi

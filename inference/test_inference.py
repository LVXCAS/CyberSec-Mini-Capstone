#!/usr/bin/env python3
"""Inference validation tests for KoboldCpp + Gemma 4 on K80 GPU.

Run on the server after starting KoboldCpp:
    python3 test_inference.py [--host HOST] [--port PORT]

Tests:
    1. Basic completion via /v1/chat/completions
    2. JSON tool-call structured output
    3. Latency measurement (flag if >30s)
    4. VRAM usage check via nvidia-smi
"""

import argparse
import json
import subprocess
import sys
import time

import requests

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"


def test_basic_completion(base_url: str, timeout: float = 30.0) -> bool:
    """Test 1: Basic chat completion returns a valid response."""
    print("\n--- Test 1: Basic Completion ---")
    url = f"{base_url}/v1/chat/completions"
    payload = {
        "model": "gemma-4",
        "messages": [
            {"role": "user", "content": "What is a firewall? Answer in one sentence."}
        ],
        "max_tokens": 128,
        "temperature": 0.7,
    }

    start = time.time()
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        elapsed = time.time() - start
        resp.raise_for_status()
        data = resp.json()

        content = data["choices"][0]["message"]["content"]
        if not content or len(content.strip()) < 5:
            print(f"  {FAIL}: Empty or too-short response: {content!r}")
            return False

        print(f"  Response: {content[:120]}...")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  {PASS}")
        return True
    except requests.exceptions.Timeout:
        print(f"  {FAIL}: Request timed out after {timeout}s")
        return False
    except Exception as e:
        print(f"  {FAIL}: {e}")
        return False


def test_json_tool_call(base_url: str, timeout: float = 30.0) -> bool:
    """Test 2: Model produces a valid JSON tool-call response."""
    print("\n--- Test 2: JSON Tool-Call ---")
    url = f"{base_url}/v1/chat/completions"
    payload = {
        "model": "gemma-4",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a cybersecurity agent. Respond ONLY with a JSON object: "
                    '{"tool": "command_name", "args": {"cmd": "the command"}}'
                ),
            },
            {
                "role": "user",
                "content": "What command would you run to scan open ports on 10.0.0.5?",
            },
        ],
        "max_tokens": 256,
        "temperature": 0.3,
    }

    start = time.time()
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        elapsed = time.time() - start
        resp.raise_for_status()
        data = resp.json()

        content = data["choices"][0]["message"]["content"].strip()
        print(f"  Raw response: {content[:200]}")
        print(f"  Time: {elapsed:.2f}s")

        # Try to extract JSON from response (model may wrap in markdown)
        json_str = content
        if "```" in json_str:
            # Extract from code block
            parts = json_str.split("```")
            for part in parts:
                cleaned = part.strip().removeprefix("json").strip()
                if cleaned.startswith("{"):
                    json_str = cleaned
                    break

        parsed = json.loads(json_str)
        if "tool" in parsed and "args" in parsed:
            print(f"  Parsed tool: {parsed['tool']}")
            print(f"  Parsed args: {parsed['args']}")
            print(f"  {PASS}")
            return True
        else:
            print(f"  {FAIL}: JSON missing 'tool' or 'args' keys: {parsed}")
            return _try_grammar_fallback(base_url, timeout)

    except json.JSONDecodeError:
        print(f"  [!] JSON parse failed, trying grammar-constrained fallback...")
        return _try_grammar_fallback(base_url, timeout)
    except Exception as e:
        print(f"  {FAIL}: {e}")
        return False


def _try_grammar_fallback(base_url: str, timeout: float = 30.0) -> bool:
    """Fallback: Use KoboldCpp grammar sampling for structured JSON."""
    print("  [*] Attempting grammar-constrained generation...")
    url = f"{base_url}/api/extra/generate"

    grammar = r'''
root ::= "{" ws "\"tool\"" ws ":" ws string "," ws "\"args\"" ws ":" ws "{" ws "\"cmd\"" ws ":" ws string ws "}" ws "}"
string ::= "\"" [a-zA-Z0-9_./\- ]+ "\""
ws ::= [ \t\n]*
'''

    payload = {
        "prompt": (
            "You are a cybersecurity agent. Respond with a JSON tool call.\n"
            "User: What command would you run to scan open ports on 10.0.0.5?\n"
            "Response: "
        ),
        "max_length": 256,
        "temperature": 0.3,
        "grammar": grammar,
    }

    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        content = data.get("results", [{}])[0].get("text", "").strip()
        print(f"  Grammar response: {content[:200]}")

        parsed = json.loads(content)
        if "tool" in parsed and "args" in parsed:
            print(f"  {PASS} (via grammar fallback)")
            return True
        else:
            print(f"  {FAIL}: Grammar output missing required keys")
            return False
    except Exception as e:
        print(f"  {FAIL}: Grammar fallback failed: {e}")
        return False


def test_latency(base_url: str, timeout: float = 60.0) -> bool:
    """Test 3: Measure completion latency, flag if >30s total."""
    print("\n--- Test 3: Latency ---")
    url = f"{base_url}/v1/chat/completions"
    payload = {
        "model": "gemma-4",
        "messages": [
            {"role": "user", "content": "List 3 common network protocols."}
        ],
        "max_tokens": 128,
        "temperature": 0.5,
        "stream": True,
    }

    start = time.time()
    first_token_time = None
    full_response = ""

    try:
        resp = requests.post(url, json=payload, timeout=timeout, stream=True)
        resp.raise_for_status()

        for line in resp.iter_lines():
            if not line:
                continue
            decoded = line.decode("utf-8", errors="replace")
            if not decoded.startswith("data: "):
                continue
            chunk_data = decoded[6:]
            if chunk_data.strip() == "[DONE]":
                break

            if first_token_time is None:
                first_token_time = time.time()

            try:
                chunk = json.loads(chunk_data)
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                full_response += content
            except json.JSONDecodeError:
                pass

        total_time = time.time() - start
        ttft = (first_token_time - start) if first_token_time else total_time

        print(f"  Time to first token: {ttft:.2f}s")
        print(f"  Total completion time: {total_time:.2f}s")
        print(f"  Response length: {len(full_response)} chars")

        if total_time > 30.0:
            print(f"  [!] WARNING: Total time exceeds 30s threshold")
            print(f"  {FAIL}: Latency too high ({total_time:.1f}s > 30s)")
            return False

        print(f"  {PASS}")
        return True

    except requests.exceptions.Timeout:
        print(f"  {FAIL}: Stream timed out after {timeout}s")
        return False
    except Exception as e:
        print(f"  {FAIL}: {e}")
        return False


def test_vram(base_url: str) -> bool:
    """Test 4: Check VRAM usage via nvidia-smi after inference."""
    print("\n--- Test 4: VRAM Check ---")
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            print(f"  {FAIL}: nvidia-smi failed: {result.stderr.strip()}")
            return False

        output = result.stdout.strip()
        print(f"  GPU info: {output}")

        # Parse: name, total_mb, used_mb, free_mb
        parts = [p.strip() for p in output.split(",")]
        if len(parts) >= 4:
            gpu_name = parts[0]
            total_mb = int(parts[1])
            used_mb = int(parts[2])
            free_mb = int(parts[3])
            usage_pct = (used_mb / total_mb) * 100

            print(f"  GPU: {gpu_name}")
            print(f"  VRAM: {used_mb}MB / {total_mb}MB ({usage_pct:.1f}% used)")
            print(f"  Free: {free_mb}MB")

            if usage_pct > 90:
                print(f"  [!] WARNING: VRAM usage above 90%")
                print(f"  [!] Consider switching to E2B variant for more headroom")
                print(f"  {FAIL}: Insufficient VRAM headroom")
                return False

            print(f"  {PASS}")
            return True
        else:
            print(f"  {FAIL}: Could not parse nvidia-smi output")
            return False

    except FileNotFoundError:
        print(f"  {FAIL}: nvidia-smi not found (no GPU driver?)")
        return False
    except Exception as e:
        print(f"  {FAIL}: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="KoboldCpp inference validation")
    parser.add_argument("--host", default="localhost", help="Server host")
    parser.add_argument("--port", type=int, default=5001, help="Server port")
    args = parser.parse_args()

    base_url = f"http://{args.host}:{args.port}"
    print(f"Testing KoboldCpp at {base_url}")

    # Verify server is reachable
    try:
        resp = requests.get(f"{base_url}/api/v1/info", timeout=5)
        resp.raise_for_status()
        info = resp.json()
        print(f"Server info: {json.dumps(info, indent=2)[:200]}")
    except Exception as e:
        print(f"\n[!] Cannot reach KoboldCpp at {base_url}: {e}")
        print("[!] Make sure start_koboldcpp.sh is running")
        sys.exit(1)

    results = {
        "Basic Completion": test_basic_completion(base_url),
        "JSON Tool-Call": test_json_tool_call(base_url),
        "Latency": test_latency(base_url),
        "VRAM": test_vram(base_url),
    }

    print("\n" + "=" * 44)
    print("  RESULTS SUMMARY")
    print("=" * 44)
    all_pass = True
    for name, passed in results.items():
        status = PASS if passed else FAIL
        print(f"  {name}: {status}")
        if not passed:
            all_pass = False

    print("")
    if all_pass:
        print("All tests PASSED")
    else:
        failed = [n for n, p in results.items() if not p]
        print(f"FAILED tests: {', '.join(failed)}")
        if not results["VRAM"]:
            print("\n[!] RECOMMENDATION: If VRAM is tight, switch to E2B variant:")
            print("    ./download_model.sh  # will try E2B as fallback")

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()

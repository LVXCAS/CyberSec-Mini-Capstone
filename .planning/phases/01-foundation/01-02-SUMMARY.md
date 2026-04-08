---
phase: 01-foundation
plan: 02
subsystem: inference
tags: [koboldcpp, gemma-4, cuda, k80, gguf, inference]
dependency-graph:
  requires: []
  provides: [koboldcpp-launch, model-download, inference-validation]
  affects: [01-03, 01-04, 02-01]
tech-stack:
  added: [koboldcpp-cu11, gemma-4-E4B-it-GGUF]
  patterns: [grammar-constrained-sampling, openai-compatible-api]
key-files:
  created:
    - inference/download_model.sh
    - inference/start_koboldcpp.sh
    - inference/test_inference.py
  modified: []
decisions:
  - id: E4B-approved
    description: "Proceed with Gemma 4 E4B Q4_K_M variant"
    rationale: "User approved after checkpoint; E4B fits K80 24GB VRAM"
metrics:
  duration: ~5min
  completed: 2026-04-08
---

# Phase 01 Plan 02: KoboldCpp + Gemma 4 Inference Summary

**One-liner:** KoboldCpp CUDA 11 launch scripts for Gemma 4 E4B on K80 with 4-test validation suite (completion, JSON tool-call, latency, VRAM)

## What Was Done

### Task 1: Model download + KoboldCpp launch script
- Created `inference/download_model.sh` with HuggingFace download for E4B Q4_K_M, automatic E2B fallback, file size verification
- Created `inference/start_koboldcpp.sh` using koboldcpp_cu11 binary (CUDA 11 for K80 compute 3.7) with --jinja flag, port 5001, 120s startup timeout, VRAM monitoring via nvidia-smi
- Both scripts validated with `bash -n` and made executable

### Task 2: Inference validation test
- Created `inference/test_inference.py` with 4 tests:
  1. Basic completion via /v1/chat/completions
  2. JSON tool-call with grammar-constrained fallback
  3. Streaming latency measurement (30s threshold)
  4. VRAM usage check with E2B recommendation if tight
- Syntax validated with `ast.parse()`

### Task 3: Checkpoint — User approved E4B variant
- User verified and approved proceeding with E4B

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| E4B variant approved | User checkpoint approval; fits 24GB K80 VRAM |
| Grammar fallback for JSON | KoboldCpp grammar sampling as backup if model doesn't produce clean JSON |
| koboldcpp_cu11 binary | K80 is compute 3.7, requires CUDA 11 (not 12) |

## Deviations from Plan

None -- plan executed exactly as written.

## Commits

| Hash | Message |
|------|---------|
| 2487cb8 | feat(01-02): add model download and KoboldCpp launch scripts |
| 7af1ecf | feat(01-02): add inference validation test script |

## Next Phase Readiness

Scripts are ready to run on the K80 server. Critical unknowns to validate on actual hardware:
- K80 VRAM headroom with E4B loaded
- Actual inference latency
- JSON tool-call reliability (grammar fallback may or may not be needed)

No blockers for proceeding to plan 01-03.

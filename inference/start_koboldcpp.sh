#!/usr/bin/env bash
# start_koboldcpp.sh — Launch KoboldCpp with Gemma 4 on K80 GPU (CUDA 11)
# Requires: koboldcpp_cu11 binary (CUDA 11 for compute capability 3.7)
# Minimum version: KoboldCpp v1.111.2+
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_DIR="${SCRIPT_DIR}/models"
PORT=5001
HOST="0.0.0.0"
CONTEXT_SIZE=4096
STARTUP_TIMEOUT=120

# Auto-detect model file (prefer E4B, fall back to E2B)
if [[ -f "${MODEL_DIR}/gemma-4-E4B-it-Q4_K_M.gguf" ]]; then
    MODEL_PATH="${MODEL_DIR}/gemma-4-E4B-it-Q4_K_M.gguf"
    echo "[+] Using E4B model"
elif [[ -f "${MODEL_DIR}/gemma-4-E2B-it-Q4_K_M.gguf" ]]; then
    MODEL_PATH="${MODEL_DIR}/gemma-4-E2B-it-Q4_K_M.gguf"
    echo "[+] Using E2B model (fallback)"
else
    echo "[!] No model file found in ${MODEL_DIR}"
    echo "[!] Run download_model.sh first"
    exit 1
fi

# Locate koboldcpp_cu11 binary
KOBOLD_BIN=""
for candidate in \
    "koboldcpp_cu11" \
    "/usr/local/bin/koboldcpp_cu11" \
    "${HOME}/koboldcpp/koboldcpp_cu11" \
    "${SCRIPT_DIR}/koboldcpp_cu11"; do
    if command -v "${candidate}" &>/dev/null || [[ -x "${candidate}" ]]; then
        KOBOLD_BIN="${candidate}"
        break
    fi
done

if [[ -z "${KOBOLD_BIN}" ]]; then
    echo "[!] koboldcpp_cu11 binary not found"
    echo "[!] The K80 GPU requires CUDA 11 build (compute capability 3.7)"
    echo "[!] Download from: https://github.com/LostRuins/koboldcpp/releases"
    echo "[!] Use the _cu11 variant, NOT the default CUDA 12 build"
    exit 1
fi

echo "============================================"
echo "  KoboldCpp + Gemma 4 (K80 GPU)"
echo "============================================"
echo ""
echo "Binary:  ${KOBOLD_BIN}"
echo "Model:   ${MODEL_PATH}"
echo "Port:    ${PORT}"
echo "Context: ${CONTEXT_SIZE}"
echo ""

# Print VRAM baseline before launch
echo "[*] GPU status before launch:"
if command -v nvidia-smi &>/dev/null; then
    nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free \
        --format=csv,noheader,nounits 2>/dev/null || nvidia-smi
else
    echo "[!] nvidia-smi not available — cannot verify GPU"
fi
echo ""

# Launch KoboldCpp in background
echo "[*] Starting KoboldCpp..."
"${KOBOLD_BIN}" \
    --model "${MODEL_PATH}" \
    --port "${PORT}" \
    --host "${HOST}" \
    --contextsize "${CONTEXT_SIZE}" \
    --jinja \
    --gpulayers 999 \
    --usecublas \
    --threads "$(nproc)" &

KOBOLD_PID=$!
echo "[*] KoboldCpp PID: ${KOBOLD_PID}"

# Wait for server to become ready
echo "[*] Waiting for server (timeout: ${STARTUP_TIMEOUT}s)..."
ELAPSED=0
while (( ELAPSED < STARTUP_TIMEOUT )); do
    if ! kill -0 "${KOBOLD_PID}" 2>/dev/null; then
        echo "[!] KoboldCpp process died unexpectedly"
        echo "[!] Check logs above for CUDA or memory errors"
        exit 1
    fi

    if curl -s -o /dev/null -w '' "http://localhost:${PORT}/api/v1/info" 2>/dev/null; then
        echo ""
        echo "[+] KoboldCpp is ready on port ${PORT}"
        echo "[+] OpenAI-compatible API: http://localhost:${PORT}/v1/chat/completions"
        echo "[+] PID: ${KOBOLD_PID}"
        echo ""
        echo "[*] GPU status after model load:"
        nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free \
            --format=csv,noheader,nounits 2>/dev/null || true
        echo ""
        echo "[+] Server running. Press Ctrl+C to stop."
        wait "${KOBOLD_PID}"
        exit 0
    fi

    sleep 2
    ELAPSED=$((ELAPSED + 2))
    printf "\r[*] Waiting... %ds / %ds" "${ELAPSED}" "${STARTUP_TIMEOUT}"
done

echo ""
echo "[!] TIMEOUT: KoboldCpp did not respond within ${STARTUP_TIMEOUT}s"
echo "[!] Killing process ${KOBOLD_PID}"
kill "${KOBOLD_PID}" 2>/dev/null || true
exit 1

#!/usr/bin/env bash
# download_model.sh — Download Gemma 4 GGUF model for KoboldCpp inference
# Target: unsloth/gemma-4-E4B-it-GGUF Q4_K_M (~5GB)
# Fallback: unsloth/gemma-4-E2B-it-GGUF Q4_K_M (~2.5GB) if E4B fails
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_DIR="${SCRIPT_DIR}/models"
mkdir -p "${MODEL_DIR}"

# Primary model (E4B)
E4B_REPO="unsloth/gemma-4-E4B-it-GGUF"
E4B_FILE="gemma-4-E4B-it-Q4_K_M.gguf"
E4B_MIN_SIZE_BYTES=4000000000  # ~4GB minimum expected

# Fallback model (E2B)
E2B_REPO="unsloth/gemma-4-E2B-it-GGUF"
E2B_FILE="gemma-4-E2B-it-Q4_K_M.gguf"
E2B_MIN_SIZE_BYTES=2000000000  # ~2GB minimum expected

download_with_hf_cli() {
    local repo="$1"
    local file="$2"
    local dest="$3"

    echo "[*] Downloading ${file} from ${repo} via huggingface-cli..."
    if command -v huggingface-cli &>/dev/null; then
        huggingface-cli download "${repo}" "${file}" \
            --local-dir "${MODEL_DIR}" \
            --local-dir-use-symlinks False
    else
        echo "[!] huggingface-cli not found, falling back to wget..."
        local url="https://huggingface.co/${repo}/resolve/main/${file}"
        wget -c -O "${dest}" "${url}"
    fi
}

verify_download() {
    local filepath="$1"
    local min_size="$2"

    if [[ ! -f "${filepath}" ]]; then
        echo "[!] File not found: ${filepath}"
        return 1
    fi

    local actual_size
    actual_size=$(stat -c%s "${filepath}" 2>/dev/null || stat -f%z "${filepath}" 2>/dev/null)

    if (( actual_size < min_size )); then
        echo "[!] File too small: ${actual_size} bytes (expected >= ${min_size})"
        echo "[!] Download may be incomplete or corrupted"
        return 1
    fi

    echo "[+] Verified: ${filepath} ($(( actual_size / 1024 / 1024 )) MB)"
    return 0
}

echo "============================================"
echo "  Gemma 4 GGUF Model Downloader"
echo "============================================"
echo ""

# Try E4B first
E4B_PATH="${MODEL_DIR}/${E4B_FILE}"
if [[ -f "${E4B_PATH}" ]] && verify_download "${E4B_PATH}" "${E4B_MIN_SIZE_BYTES}"; then
    echo "[+] E4B model already downloaded and verified"
    echo "MODEL_PATH=${E4B_PATH}"
    exit 0
fi

echo "[*] Attempting E4B download..."
if download_with_hf_cli "${E4B_REPO}" "${E4B_FILE}" "${E4B_PATH}" && \
   verify_download "${E4B_PATH}" "${E4B_MIN_SIZE_BYTES}"; then
    echo ""
    echo "[+] E4B model downloaded successfully"
    echo "MODEL_PATH=${E4B_PATH}"
    exit 0
fi

# Fallback to E2B
echo ""
echo "[!] E4B download failed or file invalid. Falling back to E2B..."
E2B_PATH="${MODEL_DIR}/${E2B_FILE}"

if [[ -f "${E2B_PATH}" ]] && verify_download "${E2B_PATH}" "${E2B_MIN_SIZE_BYTES}"; then
    echo "[+] E2B model already downloaded and verified"
    echo "MODEL_PATH=${E2B_PATH}"
    exit 0
fi

echo "[*] Attempting E2B download..."
if download_with_hf_cli "${E2B_REPO}" "${E2B_FILE}" "${E2B_PATH}" && \
   verify_download "${E2B_PATH}" "${E2B_MIN_SIZE_BYTES}"; then
    echo ""
    echo "[+] E2B model downloaded successfully (fallback)"
    echo "MODEL_PATH=${E2B_PATH}"
    exit 0
fi

echo ""
echo "[!] FATAL: Both E4B and E2B downloads failed"
echo "[!] Check network connectivity and HuggingFace availability"
exit 1

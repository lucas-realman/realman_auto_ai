#!/usr/bin/env bash
# ============================================================
# benchmark_vllm.sh — Quick latency/throughput benchmark for vLLM
#
# Usage:
#   bash scripts/benchmark_vllm.sh
#
# Environment variables:
#   VLLM_BASE_URL  — Server URL   (default: http://localhost:8000)
#   VLLM_MODEL     — Model name   (default: Qwen/Qwen3-30B-A3B)
#   NUM_REQUESTS   — Iterations   (default: 5)
#
# Acceptance criteria (Sprint 1-2):
#   TTFT < 2 s, throughput > 20 tok/s
# ============================================================
set -euo pipefail

BASE_URL="${VLLM_BASE_URL:-http://localhost:8000}"
MODEL="${VLLM_MODEL:-Qwen/Qwen3-30B-A3B}"
NUM_REQUESTS="${NUM_REQUESTS:-5}"
MAX_TOKENS=50

echo "=========================================="
echo "  vLLM Benchmark"
echo "=========================================="
echo "  Server:       ${BASE_URL}"
echo "  Model:        ${MODEL}"
echo "  Requests:     ${NUM_REQUESTS}"
echo "  Max tokens:   ${MAX_TOKENS}"
echo "=========================================="
echo ""

# Pre-flight: server must be up
if ! curl -sf "${BASE_URL}/v1/models" >/dev/null 2>&1; then
    echo "[ERROR] vLLM server not reachable at ${BASE_URL}"
    echo "        Start with: bash scripts/start_vllm.sh --daemon"
    exit 1
fi

PROMPTS=(
    "Explain what a CRM system is in one paragraph."
    "List three benefits of AI in sales."
    "What is lead scoring?"
    "Describe the sales funnel stages."
    "How does customer segmentation work?"
)

TOTAL_TIME_MS=0
TOTAL_TOKENS=0
declare -a LATENCIES=()

for i in $(seq 1 "${NUM_REQUESTS}"); do
    IDX=$(( (i - 1) % ${#PROMPTS[@]} ))
    PROMPT="${PROMPTS[${IDX}]}"

    printf "  Request %d/%d … " "${i}" "${NUM_REQUESTS}"

    START_NS=$(date +%s%N)
    RESP=$(curl -sf -X POST "${BASE_URL}/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d "{
            \"model\": \"${MODEL}\",
            \"messages\": [{\"role\": \"user\", \"content\": \"${PROMPT}\"}],
            \"max_tokens\": ${MAX_TOKENS},
            \"temperature\": 0.0
        }" 2>&1) || { echo "FAILED"; continue; }
    END_NS=$(date +%s%N)

    ELAPSED_MS=$(( (END_NS - START_NS) / 1000000 ))
    LATENCIES+=("${ELAPSED_MS}")

    COMP_TOKENS=$(echo "${RESP}" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('usage', {}).get('completion_tokens', 0))
except Exception:
    print(0)
" 2>/dev/null || echo 0)

    TOTAL_TOKENS=$((TOTAL_TOKENS + COMP_TOKENS))
    TOTAL_TIME_MS=$((TOTAL_TIME_MS + ELAPSED_MS))

    if [ "${COMP_TOKENS}" -gt 0 ] && [ "${ELAPSED_MS}" -gt 0 ]; then
        TPS=$(python3 -c "print(f'{${COMP_TOKENS}/(${ELAPSED_MS}/1000):.1f}')")
    else
        TPS="N/A"
    fi
    echo "${ELAPSED_MS} ms | ${COMP_TOKENS} tokens | ${TPS} tok/s"
done

# --- Summary ---
echo ""
echo "=========================================="
echo "  Results"
echo "=========================================="

if [ "${#LATENCIES[@]}" -eq 0 ]; then
    echo "  No successful requests."
    exit 1
fi

SORTED=($(printf '%s\n' "${LATENCIES[@]}" | sort -n))
COUNT=${#SORTED[@]}
MIN_MS=${SORTED[0]}
MAX_MS=${SORTED[$((COUNT - 1))]}
AVG_MS=$((TOTAL_TIME_MS / COUNT))
P95_IDX=$(( (COUNT * 95 + 99) / 100 - 1 ))
[ "${P95_IDX}" -ge "${COUNT}" ] && P95_IDX=$((COUNT - 1))
P95_MS=${SORTED[${P95_IDX}]}

echo "  Successful:   ${COUNT} / ${NUM_REQUESTS}"
echo "  Avg latency:  ${AVG_MS} ms"
echo "  Min latency:  ${MIN_MS} ms"
echo "  Max latency:  ${MAX_MS} ms"
echo "  P95 latency:  ${P95_MS} ms"
echo "  Total tokens: ${TOTAL_TOKENS}"

if [ "${TOTAL_TIME_MS}" -gt 0 ]; then
    OVERALL_TPS=$(python3 -c "print(f'{${TOTAL_TOKENS}/(${TOTAL_TIME_MS}/1000):.1f}')")
    echo "  Throughput:   ${OVERALL_TPS} tok/s"
fi

echo ""
if [ "${P95_MS}" -le 2000 ]; then
    echo "  [PASS] P95 latency ≤ 2 s  (${P95_MS} ms)"
else
    echo "  [WARN] P95 latency > 2 s  (${P95_MS} ms) — consider tuning vLLM params"
fi
echo "=========================================="

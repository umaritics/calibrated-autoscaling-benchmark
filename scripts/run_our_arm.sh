#!/usr/bin/env bash
# Usage: ./scripts/run_our_arm.sh <repeat> <pattern> <arm>
# arm is one of: strawman_hpa holtwinters calibrated_hpa
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LAB_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
REPEAT=${1:?repeat number required}
PATTERN=${2:?pattern required}
ARM=${3:?arm required}

case "$PATTERN" in
  seasonal|burst) ;;
  *) echo "This deliverable only runs seasonal or burst." >&2; exit 1 ;;
esac

export NAMESPACE=phpa-lab
export RUN_DURATION=120
export SAMPLING_INTERVAL=5
export WARMUP_DURATION=30
export PYTHON="${PYTHON:-python3}"

unset HPA_MANIFEST || true
unset HPA_TAG || true

case "$ARM" in
  strawman_hpa)
    export MODELS=hpa
    export HPA_MANIFEST="${LAB_ROOT}/manifests/hpa-baseline.yaml"
    export HPA_TAG=strawman_hpa
    SRC_NAME="strawman_hpa.csv"
    ;;
  holtwinters)
    export MODELS=holtwinters
    SRC_NAME="phpa_holtwinters.csv"
    ;;
  calibrated_hpa)
    export MODELS=hpa
    export HPA_MANIFEST="${LAB_ROOT}/manifests/hpa-calibrated.yaml"
    export HPA_TAG=calibrated_hpa
    SRC_NAME="calibrated_hpa.csv"
    ;;
  *)
    echo "Unknown arm: $ARM" >&2
    exit 1
    ;;
esac

echo "[our] repeat=${REPEAT} pattern=${PATTERN} arm=${ARM} duration=${RUN_DURATION} warmup=${WARMUP_DURATION}"
bash "${LAB_ROOT}/scripts/run_pattern_tests.sh" "$PATTERN"

SRC="${LAB_ROOT}/output/online/patterns/${PATTERN}/${SRC_NAME}"
DEST_DIR="${LAB_ROOT}/output/our_study/runs/repeat${REPEAT}/${PATTERN}"
mkdir -p "$DEST_DIR"
if [ ! -s "$SRC" ]; then
  echo "[our] ERROR: missing or empty $SRC" >&2
  exit 1
fi
cp "$SRC" "${DEST_DIR}/${ARM}.csv"
ROWS=$(awk 'END{print NR-1}' "${DEST_DIR}/${ARM}.csv")
echo "[our] saved ${DEST_DIR}/${ARM}.csv rows=${ROWS}"
if [ "${ROWS}" -lt 10 ]; then
  echo "[our] ERROR: fewer than 10 data rows" >&2
  exit 1
fi

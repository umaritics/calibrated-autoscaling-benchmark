#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
UPSTREAM_URL=${UPSTREAM_URL:-https://github.com/syswe/workloads-predictional-scaling-operators.git}
LAB="${ROOT}/upstream/workloads-predictional-scaling-operators"

if [ ! -d "${LAB}/.git" ]; then
  git clone --depth 1 "$UPSTREAM_URL" "$LAB"
fi

# Overlay our policies and scripts
cp "${ROOT}/policies/hpa-baseline.yaml" "${LAB}/manifests/"
cp "${ROOT}/policies/hpa-calibrated.yaml" "${LAB}/manifests/"
cp "${ROOT}/policies/phpa-holtwinters.yaml" "${LAB}/manifests/"
cp "${ROOT}/manifests/"*.yaml "${LAB}/manifests/"
cp "${ROOT}/scripts/run_our_arm.sh" "${LAB}/scripts/"
cp "${ROOT}/scripts/analyze_our_results.py" "${LAB}/scripts/"
cp "${ROOT}/scripts/patch_run_pattern_tests.py" "${LAB}/scripts/"
chmod +x "${LAB}/scripts/"*.sh

python3 "${LAB}/scripts/patch_run_pattern_tests.py"
echo "Upstream ready at ${LAB}"
echo "Next: cd ${LAB} && python3 -m venv .venv && source .venv/bin/activate"
echo "      pip install -r requirements.txt  # or numpy pandas matplotlib only"
echo "      Install PHPA operator: helm install ... jthomperoo v0.13.2 (see docs/reproduction_report.md)"
echo "      Then: ./scripts/run_our_arm.sh 1 seasonal strawman_hpa"

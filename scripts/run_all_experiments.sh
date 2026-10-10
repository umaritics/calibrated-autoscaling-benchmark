#!/usr/bin/env bash
set -euo pipefail
export HOME=/root
cd /root/calibrated-autoscaling-work/workloads-predictional-scaling-operators
# shellcheck disable=SC1091
source .venv/bin/activate
export PYTHON=python

mkdir -p docs output/our_study/logs
LOG=output/our_study/logs/run_all_$(date +%Y%m%d_%H%M%S).log
exec > >(tee -a "$LOG") 2>&1

arms=(strawman_hpa holtwinters calibrated_hpa)
patterns=(seasonal burst)

for repeat in 1 2 3; do
  for pattern in "${patterns[@]}"; do
    for arm in "${arms[@]}"; do
      dest="output/our_study/runs/repeat${repeat}/${pattern}/${arm}.csv"
      if [ -s "$dest" ]; then
        rows=$(awk 'END{print NR-1}' "$dest")
        if [ "${rows:-0}" -ge 10 ]; then
          echo "[skip] already have $dest rows=$rows"
          continue
        fi
      fi
      echo "============================================================"
      echo "[run] repeat=${repeat} pattern=${pattern} arm=${arm} $(date -Is)"
      echo "============================================================"
      if ./scripts/run_our_arm.sh "$repeat" "$pattern" "$arm"; then
        echo "[ok] repeat=${repeat} pattern=${pattern} arm=${arm}"
      else
        echo "[FAIL] repeat=${repeat} pattern=${pattern} arm=${arm}" | tee -a docs/run_failures.md
        # one retry
        sleep 10
        if ./scripts/run_our_arm.sh "$repeat" "$pattern" "$arm"; then
          echo "[ok-retry] repeat=${repeat} pattern=${pattern} arm=${arm}"
        else
          echo "[FAIL2] giving up this arm" | tee -a docs/run_failures.md
        fi
      fi
    done
  done
done

python scripts/analyze_our_results.py
find output/our_study/runs -name '*.csv' | sort
echo ALL_EXPERIMENTS_FINISHED

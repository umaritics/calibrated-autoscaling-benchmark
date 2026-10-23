#!/usr/bin/env python3
"""Write hashes and status for the safety-stopped chaotic milestone."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/live_trace_phase/chaotic_first_comparison"


def digest(path):
    return {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}


def main():
    soft = OUT / "chaotic_d1_s1/repeat1/strawman_hpa"
    summary = json.loads((soft / "summary.json").read_text())
    interrupted = sorted((OUT / "interrupted_runs").iterdir())
    checkpoint = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "BLOCKED_HOST_SAFETY",
        "comparison_complete": False,
        "run_dispositions": {
            "strawman_hpa": summary["decision"],
            "holtwinters": "INCOMPLETE_EXCLUDED_TWO_HOST_FREEZES",
            "calibrated_hpa": "NOT_RUN",
        },
        "safety_observations": {
            "soft_hpa_max_host_load1": 106.3515625,
            "post_recovery_filesystem_percent_used": 94,
            "post_recovery_free_bytes_approx": 5905580032,
            "kernel_oom_or_hung_task_evidence_found": False,
            "active_benchmark_autoscaler_after_cleanup": False,
        },
        "accepted_soft_summary": {key: summary.get(key) for key in (
            "scheduled_measurement_requests", "successful_requests", "recorded_failures",
            "error_rate", "timeouts", "connection_failures", "generator_drops",
            "p50_latency_s", "p95_latency_s", "p99_latency_s", "p99_dispatch_delay_s",
            "max_client_inflight", "pod_seconds", "mean_ready", "max_ready", "cpu_coverage",
            "mean_cpu_m", "max_cpu_m", "readiness_deficit_samples", "max_workload_restarts")},
        "interrupted_directories": [str(path.relative_to(ROOT)) for path in interrupted],
    }
    (OUT / "safety_checkpoint.json").write_text(json.dumps(checkpoint, indent=2) + "\n")

    files = {}
    for path in sorted(item for item in OUT.rglob("*") if item.is_file()
                       and item.name != "evidence_manifest.json"):
        files[str(path.relative_to(ROOT))] = digest(path)
    code = {}
    for relative in (
        "scripts/live/prepare_chaotic_comparison.py", "scripts/live/preflight_chaotic.py",
        "scripts/live/run_chaotic_comparison.py", "scripts/live/finalize_chaotic_safety_checkpoint.py",
        "scripts/live/run_trace.py", "scripts/live/analyze_runs.py", "policies/hpa-baseline.yaml",
        "policies/hpa-calibrated.yaml", "policies/phpa-holtwinters.yaml", "manifests/sample-app.yaml"):
        code[relative] = digest(ROOT / relative)
    manifest = {"generated_utc": datetime.now(timezone.utc).isoformat(), "algorithm": "sha256",
                "status": "BLOCKED_HOST_SAFETY", "files": files, "code_and_configuration": code}
    (OUT / "evidence_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"status": checkpoint["status"], "files_hashed": len(files),
                      "soft_decision": summary["decision"]}, indent=2))


if __name__ == "__main__":
    main()

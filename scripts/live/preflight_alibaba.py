#!/usr/bin/env python3
"""Capture and enforce the preflight gate for the Alibaba-derived comparison."""

import json
import os
import platform
import shutil
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/live_trace_phase/alibaba_first_comparison"
KUBECTL = [str(ROOT / ".tools/kubectl"), "--kubeconfig", str(ROOT / "live-kubeconfig"),
           "--request-timeout=15s"]


def kubectl(args):
    process = subprocess.run(KUBECTL + args, cwd=ROOT, capture_output=True, text=True, timeout=30)
    if process.returncode:
        raise RuntimeError(process.stderr.strip())
    return process.stdout


def main():
    nodes = json.loads(kubectl(["get", "nodes", "-o", "json"]))
    pods = json.loads(kubectl(["get", "pods", "-A", "-o", "json"]))
    api = json.loads(kubectl(["get", "apiservice", "v1beta1.metrics.k8s.io", "-o", "json"]))
    node_metrics = json.loads(kubectl(["get", "--raw", "/apis/metrics.k8s.io/v1beta1/nodes"]))
    controllers = json.loads(kubectl(["-n", "trace-benchmark", "get", "hpa,phpa", "-o", "json"]))
    with urllib.request.urlopen("http://127.0.0.1:18080/index.php", timeout=5) as response:
        endpoint = {"status": response.status, "body": response.read().decode(errors="replace")[:100]}
    memory = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        if key in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}:
            memory[key] = value.strip()
    ready_nodes = sum(any(condition.get("type") == "Ready" and condition.get("status") == "True"
                          for condition in node.get("status", {}).get("conditions", []))
                      for node in nodes["items"])
    unready_pods = [{"namespace": pod["metadata"]["namespace"], "name": pod["metadata"]["name"],
                     "phase": pod.get("status", {}).get("phase")}
                    for pod in pods["items"] if pod.get("status", {}).get("phase") != "Running"]
    metrics_available = any(condition.get("type") == "Available" and condition.get("status") == "True"
                            for condition in api.get("status", {}).get("conditions", []))
    phpa_ready = any(pod["metadata"]["namespace"] == "phpa-system" and
                     pod["metadata"]["name"].startswith("predictive-horizontal-pod-autoscaler") and
                     all(status.get("ready") for status in pod.get("status", {}).get("containerStatuses", []))
                     for pod in pods["items"])
    checks = {
        "node_ready": ready_nodes == len(nodes["items"]) == 1,
        "all_existing_pods_running": not unready_pods,
        "metrics_api_available": metrics_available and len(node_metrics.get("items", [])) == 1,
        "phpa_operator_ready": phpa_ready,
        "no_active_benchmark_controller": len(controllers.get("items", [])) == 0,
        "workload_endpoint_idle_healthy": endpoint == {"status": 200, "body": "OK!"},
        "free_disk_above_1_gib": shutil.disk_usage(ROOT).free >= 1024**3,
    }
    record = {
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "cluster": "calibrated-live", "checks": checks, "ready_nodes": ready_nodes,
        "node_count": len(nodes["items"]), "unready_pods": unready_pods,
        "metrics_api_condition": api.get("status", {}).get("conditions", []),
        "node_metrics_items": len(node_metrics.get("items", [])), "endpoint": endpoint,
        "filesystem": {"total_bytes": shutil.disk_usage(ROOT).total,
                       "used_bytes": shutil.disk_usage(ROOT).used,
                       "free_bytes": shutil.disk_usage(ROOT).free},
        "memory": memory, "host_loadavg": os.getloadavg(), "platform": platform.platform(),
        "instrumentation_difference_from_nasa": "The collector now records explicit per-command availability diagnostics. NASA accepted runs used the earlier payload-only collector; Alibaba interpretation uses the same acceptance threshold but richer diagnostics and is not assumed field-for-field comparable for availability classifications.",
    }
    (OUT / "environment_metadata.json").write_text(json.dumps(record, indent=2) + "\n")
    failed = [name for name, value in checks.items() if not value]
    lines = ["# Alibaba comparison preflight", "", f"Captured: `{record['captured_utc']}`", "",
             f"Decision: **{'PASS' if not failed else 'BLOCKED'}**.", "", "## Checks", ""]
    lines.extend(f"- {'PASS' if value else 'FAIL'}: `{name}`" for name, value in checks.items())
    lines += ["", "No image was downloaded and no cluster was created. The existing application, resources, replica limits, timeout, probes, controllers, and collector were retained.", "",
              "Collector difference: Alibaba runs retain explicit command status, response classification, duration, and stderr diagnostics. This is richer than the accepted NASA runs, so collector-derived availability classifications are not assumed directly comparable without qualification."]
    (OUT / "PREFLIGHT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"decision": "PASS" if not failed else "BLOCKED", "checks": checks}, indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

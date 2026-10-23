#!/usr/bin/env python3
"""Capture the infrastructure and generator-resource preflight for chaotic runs."""

import json
from pathlib import Path

import preflight_stepped as base


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/live_trace_phase/chaotic_first_comparison"


def main():
    base.OUT = OUT
    base.main()
    report = OUT / "PREFLIGHT.md"
    text = report.read_text().replace("Stepped comparison", "Chaotic comparison")
    text += ("\n## Targeted generator review\n\n"
             "The previous stepped soft-HPA rejection was retained and not rerun. Its schedule was exact, "
             "had zero generator drops, and failed only the frozen dispatch-p99 threshold (0.315 s). "
             "This preflight therefore records host load, available memory, free disk, endpoint health, "
             "and metrics health immediately before the new fixed run order. No workload intensity or "
             "acceptance threshold was changed.\n")
    report.write_text(text)


if __name__ == "__main__":
    main()

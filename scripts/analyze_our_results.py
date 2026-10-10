#!/usr/bin/env python3
"""Summarise our_study CSVs. Never invent a missing run."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "output" / "our_study" / "runs"
OUT_DIR = ROOT / "output" / "our_study"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PATTERNS = ("seasonal", "burst")
ARMS = ("strawman_hpa", "holtwinters", "calibrated_hpa")
HOT_MILLICORES = 160.0


def fnum(row, key):
    try:
        return float(row[key])
    except (KeyError, TypeError, ValueError):
        return 0.0


def load_rows(path: Path):
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def summarize(rows):
    if len(rows) < 2:
        return None
    ready = [fnum(r, "ready_replicas") for r in rows]
    desired = [fnum(r, "desired_replicas") for r in rows]
    cpu = [fnum(r, "cpu_millicores_avg") for r in rows]
    elapsed = [fnum(r, "elapsed_seconds") for r in rows]
    diffs = [elapsed[i] - elapsed[i - 1] for i in range(1, len(elapsed)) if elapsed[i] > elapsed[i - 1]]
    diffs.sort()
    interval = diffs[len(diffs) // 2] if diffs else 5.0
    changes = sum(1 for i in range(1, len(desired)) if desired[i] != desired[i - 1])
    first = next((elapsed[i] for i, value in enumerate(ready) if value >= 2), None)
    hot = sum(1 for value in cpu if value > HOT_MILLICORES) / len(cpu)
    return {
        "n": len(rows),
        "mean_ready": sum(ready) / len(ready),
        "max_ready": max(ready),
        "pod_seconds": sum(ready) * interval,
        "mean_cpu_avg": sum(cpu) / len(cpu),
        "desired_changes": changes,
        "first_ready_ge2_s": first,
        "hot_fraction": hot,
        "interval_s": interval,
    }


def mean(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def cell(value, digits=2):
    if value is None:
        return "NOT MEASURED"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def main():
    per_run = []
    for repeat_dir in sorted(RUNS.glob("repeat*")):
        repeat = repeat_dir.name
        for pattern in PATTERNS:
            for arm in ARMS:
                path = repeat_dir / pattern / f"{arm}.csv"
                if not path.is_file():
                    per_run.append((repeat, pattern, arm, None, path))
                    continue
                summary = summarize(load_rows(path))
                per_run.append((repeat, pattern, arm, summary, path))

    lines = []
    lines.append("# Measured results")
    lines.append("")
    lines.append(
        "Every figure below was computed from a CSV under `output/our_study/runs`. "
        "Missing runs are `NOT MEASURED`. No latency or SLA column exists because the collector does not record requests."
    )
    lines.append("")
    lines.append("## Per run")
    lines.append("")
    lines.append(
        "| Repeat | Pattern | Arm | Rows | Mean ready replicas | Max ready | Pod-seconds | "
        "Mean CPU millicores | Desired-replica changes | First time ready>=2 (s) | Hot fraction |"
    )
    lines.append("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for repeat, pattern, arm, summary, path in per_run:
        if summary is None:
            lines.append(
                f"| {repeat} | {pattern} | {arm} | NOT MEASURED | NOT MEASURED | NOT MEASURED | "
                "NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |"
            )
            continue
        first = cell(summary["first_ready_ge2_s"], 1)
        lines.append(
            "| {repeat} | {pattern} | {arm} | {n} | {mean_ready} | {max_ready} | {pod_seconds} | "
            "{cpu} | {changes} | {first} | {hot} |".format(
                repeat=repeat,
                pattern=pattern,
                arm=arm,
                n=summary["n"],
                mean_ready=cell(summary["mean_ready"]),
                max_ready=cell(summary["max_ready"], 0),
                pod_seconds=cell(summary["pod_seconds"]),
                cpu=cell(summary["mean_cpu_avg"]),
                changes=summary["desired_changes"],
                first=first,
                hot=cell(summary["hot_fraction"], 3),
            )
        )

    lines.append("")
    lines.append("## Mean across repeats")
    lines.append("")
    lines.append(
        "| Pattern | Arm | Repeats found | Mean pod-seconds | Mean hot fraction | Mean desired-replica changes |"
    )
    lines.append("|---|---|---:|---:|---:|---:|")

    grouped = {}
    for repeat, pattern, arm, summary, path in per_run:
        grouped.setdefault((pattern, arm), []).append(summary)

    def metric_list(pattern, arm, key):
        out = []
        for summary in grouped.get((pattern, arm), []):
            if summary is None:
                continue
            out.append(summary[key])
        return out

    for pattern in PATTERNS:
        for arm in ARMS:
            pods = metric_list(pattern, arm, "pod_seconds")
            hot = metric_list(pattern, arm, "hot_fraction")
            changes = metric_list(pattern, arm, "desired_changes")
            lines.append(
                f"| {pattern} | {arm} | {len(pods)} | {cell(mean(pods))} | "
                f"{cell(mean(hot), 3)} | {cell(mean(changes))} |"
            )

    lines.append("")
    lines.append("## Derived arms (no extra cluster run)")
    lines.append("")
    lines.append(
        "Component B uses Holt–Winters on seasonal and strawman HPA on burst. "
        "Components A+B use Holt–Winters on seasonal and calibrated HPA on burst. "
        "The numbers are the same CSV means as the selected arm."
    )
    lines.append("")
    lines.append(
        "| Pattern | Derived arm | Selected measured arm | Mean pod-seconds | Mean hot fraction |"
    )
    lines.append("|---|---|---|---:|---:|")
    derived = {
        ("seasonal", "B_switch_strawman"): "holtwinters",
        ("burst", "B_switch_strawman"): "strawman_hpa",
        ("seasonal", "AB_switch_calibrated"): "holtwinters",
        ("burst", "AB_switch_calibrated"): "calibrated_hpa",
    }
    for (pattern, label), selected in derived.items():
        lines.append(
            f"| {pattern} | {label} | {selected} | "
            f"{cell(mean(metric_list(pattern, selected, 'pod_seconds')))} | "
            f"{cell(mean(metric_list(pattern, selected, 'hot_fraction')), 3)} |"
        )

    lines.append("")
    lines.append("## Calibration gap")
    lines.append("")
    lines.append(
        "`advantage_vs_reactive = pod_seconds(reactive) - pod_seconds(holtwinters)`. "
        "Positive means Holt–Winters used fewer pod-seconds."
    )
    lines.append(
        "`calibration_gap = advantage_vs_strawman - advantage_vs_calibrated`. "
        "Positive means some of the Holt–Winters win existed only against the 50% HPA."
    )
    lines.append("")
    lines.append(
        "| Pattern | Mean pod-seconds strawman | Mean pod-seconds Holt–Winters | "
        "Mean pod-seconds calibrated | Advantage vs strawman | Advantage vs calibrated | Calibration gap |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for pattern in PATTERNS:
        straw = mean(metric_list(pattern, "strawman_hpa", "pod_seconds"))
        hw = mean(metric_list(pattern, "holtwinters", "pod_seconds"))
        cal = mean(metric_list(pattern, "calibrated_hpa", "pod_seconds"))
        if None in (straw, hw, cal):
            lines.append(
                f"| {pattern} | {cell(straw)} | {cell(hw)} | {cell(cal)} | "
                "NOT MEASURED | NOT MEASURED | NOT MEASURED |"
            )
            continue
        adv_s = straw - hw
        adv_c = cal - hw
        gap = adv_s - adv_c
        lines.append(
            f"| {pattern} | {cell(straw)} | {cell(hw)} | {cell(cal)} | "
            f"{cell(adv_s)} | {cell(adv_c)} | {cell(gap)} |"
        )

    lines.append("")
    lines.append("## Files read")
    lines.append("")
    for repeat, pattern, arm, summary, path in per_run:
        state = "ok" if summary else "missing"
        lines.append(f"- {state}: `{path}`")

    text = "\n".join(lines) + "\n"
    (OUT_DIR / "results.md").write_text(text, encoding="utf-8")
    print(f"Wrote {OUT_DIR / 'results.md'}")


if __name__ == "__main__":
    main()

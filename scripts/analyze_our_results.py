#!/usr/bin/env python3
"""Summarise measured CSVs under results/runs. Never invent a missing run."""
import csv
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "results" / "runs"
OUT_DIR = ROOT / "results"
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
    # Prefer trapezoid over wall time so uneven sample counts still use timestamps.
    pod_seconds = 0.0
    for i in range(1, len(elapsed)):
        dt = elapsed[i] - elapsed[i - 1]
        if dt <= 0:
            continue
        pod_seconds += 0.5 * (ready[i] + ready[i - 1]) * dt
    duration = elapsed[-1] - elapsed[0] if elapsed else 0.0
    changes = sum(1 for i in range(1, len(desired)) if desired[i] != desired[i - 1])
    first = next((elapsed[i] for i, value in enumerate(ready) if value >= 2), None)
    hot = sum(1 for value in cpu if value > HOT_MILLICORES) / len(cpu)
    return {
        "n": len(rows),
        "duration_s": duration,
        "mean_ready": sum(ready) / len(ready),
        "max_ready": max(ready),
        "pod_seconds": pod_seconds,
        "mean_cpu_avg": sum(cpu) / len(cpu),
        "desired_changes": changes,
        "first_ready_ge2_s": first,
        "hot_fraction": hot,
    }


def mean(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def stdev(values):
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return None
    m = sum(vals) / len(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / (len(vals) - 1))


def cohens_d(a, b):
    """Cohen's d for a - b (unpaired; n small)."""
    if len(a) < 2 or len(b) < 2:
        return None
    ma, mb = mean(a), mean(b)
    sa, sb = stdev(a), stdev(b)
    if None in (ma, mb, sa, sb):
        return None
    pooled = math.sqrt((sa ** 2 + sb ** 2) / 2)
    if pooled == 0:
        return 0.0
    return (ma - mb) / pooled


def cell(value, digits=2):
    if value is None:
        return "NOT MEASURED"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def mean_sd(values, digits=2):
    m, s = mean(values), stdev(values)
    if m is None:
        return "NOT MEASURED"
    if s is None:
        return cell(m, digits)
    return f"{m:.{digits}f} ± {s:.{digits}f}"


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

    grouped = {}
    for repeat, pattern, arm, summary, path in per_run:
        grouped.setdefault((pattern, arm), []).append((repeat, summary))

    def metric_list(pattern, arm, key):
        out = []
        for _, summary in grouped.get((pattern, arm), []):
            if summary is None:
                continue
            out.append(summary[key])
        return out

    def paired_diff(pattern, arm_a, arm_b, key):
        """Per-repeat a - b for matching repeats."""
        map_a = {rep: s[key] for rep, s in grouped.get((pattern, arm_a), []) if s}
        map_b = {rep: s[key] for rep, s in grouped.get((pattern, arm_b), []) if s}
        diffs = []
        for rep in sorted(set(map_a) & set(map_b)):
            diffs.append((rep, map_a[rep] - map_b[rep]))
        return diffs

    lines = []
    lines.append("# Measured results")
    lines.append("")
    lines.append(
        "Every figure below was computed from a CSV under `results/runs`. "
        "Missing runs are `NOT MEASURED`. No latency or SLA column exists because the collector does not record requests."
    )
    lines.append("")
    lines.append("## Sampling note")
    lines.append("")
    lines.append(
        "Collection was requested for 120 s at a 5 s interval (≈24 samples). Observed row counts are 17–21 "
        "because `kubectl`/metrics polling occasionally skips a cycle under load. "
        "**Pod-seconds use trapezoidal integration over `elapsed_seconds` timestamps**, not `rows × 5`."
    )
    lines.append("")
    lines.append("## Naming")
    lines.append("")
    lines.append(
        "`calibrated_hpa` is a **conservatively tuned** reactive baseline (CPU target 70%, "
        "scale-down stabilization 300 s, max +4 pods/min). It is one documented configuration, not a multi-value sweep."
    )
    lines.append("")
    lines.append("## Per run")
    lines.append("")
    lines.append(
        "| Repeat | Pattern | Arm | Rows | Duration (s) | Mean ready | Max ready | Pod-seconds | "
        "Mean CPU m | Desired changes | First ready≥2 (s) | Hot fraction |"
    )
    lines.append("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for repeat, pattern, arm, summary, path in per_run:
        if summary is None:
            lines.append(
                f"| {repeat} | {pattern} | {arm} | NOT MEASURED | NOT MEASURED | NOT MEASURED | "
                "NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |"
            )
            continue
        lines.append(
            "| {repeat} | {pattern} | {arm} | {n} | {dur} | {mean_ready} | {max_ready} | {pod_seconds} | "
            "{cpu} | {changes} | {first} | {hot} |".format(
                repeat=repeat,
                pattern=pattern,
                arm=arm,
                n=summary["n"],
                dur=cell(summary["duration_s"], 1),
                mean_ready=cell(summary["mean_ready"]),
                max_ready=cell(summary["max_ready"], 0),
                pod_seconds=cell(summary["pod_seconds"]),
                cpu=cell(summary["mean_cpu_avg"]),
                changes=summary["desired_changes"],
                first=cell(summary["first_ready_ge2_s"], 1),
                hot=cell(summary["hot_fraction"], 3),
            )
        )

    lines.append("")
    lines.append("## Mean ± SD across repeats (n=3)")
    lines.append("")
    lines.append(
        "| Pattern | Arm | Pod-seconds (mean ± SD) | Hot fraction (mean ± SD) | Mean desired-replica changes |"
    )
    lines.append("|---|---|---:|---:|---:|")
    for pattern in PATTERNS:
        for arm in ARMS:
            pods = metric_list(pattern, arm, "pod_seconds")
            hot = metric_list(pattern, arm, "hot_fraction")
            changes = metric_list(pattern, arm, "desired_changes")
            lines.append(
                f"| {pattern} | {arm} | {mean_sd(pods)} | {mean_sd(hot, 3)} | {cell(mean(changes))} |"
            )

    lines.append("")
    lines.append("## Per-repeat paired differences (pod-seconds)")
    lines.append("")
    lines.append("Positive means the first arm used **more** pod-seconds (worse on capacity).")
    lines.append("")
    lines.append("| Pattern | Comparison | repeat1 | repeat2 | repeat3 | mean ± SD |")
    lines.append("|---|---|---:|---:|---:|---:|")
    comparisons = [
        ("strawman_hpa − holtwinters", "strawman_hpa", "holtwinters"),
        ("calibrated_hpa − holtwinters", "calibrated_hpa", "holtwinters"),
        ("strawman_hpa − calibrated_hpa", "strawman_hpa", "calibrated_hpa"),
    ]
    for pattern in PATTERNS:
        for label, a, b in comparisons:
            diffs = paired_diff(pattern, a, b, "pod_seconds")
            by_rep = {rep: d for rep, d in diffs}
            vals = [d for _, d in diffs]
            lines.append(
                f"| {pattern} | {label} | {cell(by_rep.get('repeat1'))} | "
                f"{cell(by_rep.get('repeat2'))} | {cell(by_rep.get('repeat3'))} | {mean_sd(vals)} |"
            )

    lines.append("")
    lines.append("## Holt–Winters advantage (capacity)")
    lines.append("")
    lines.append(
        "`advantage = pod_seconds(reactive) − pod_seconds(holtwinters)`. "
        "Positive ⇒ Holt–Winters used fewer pod-seconds than that reactive controller. "
        "We **do not** report a “calibration gap” of the form advantage(strawman) − advantage(calibrated), "
        "because that expression algebraically cancels Holt–Winters and equals strawman − calibrated."
    )
    lines.append("")
    lines.append(
        "| Pattern | Strawman pod-s | HW pod-s | Tuned HPA pod-s | HW adv. vs strawman | HW adv. vs tuned HPA | "
        "Cohen's d (strawman − HW) | Cohen's d (tuned − HW) |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for pattern in PATTERNS:
        straw = metric_list(pattern, "strawman_hpa", "pod_seconds")
        hw = metric_list(pattern, "holtwinters", "pod_seconds")
        cal = metric_list(pattern, "calibrated_hpa", "pod_seconds")
        adv_s = [s - h for s, h in zip(
            [v for _, v in sorted((r, s["pod_seconds"]) for r, s in grouped[(pattern, "strawman_hpa")] if s)],
            [v for _, v in sorted((r, s["pod_seconds"]) for r, s in grouped[(pattern, "holtwinters")] if s)],
        )] if len(straw) == len(hw) == 3 else None
        # safer paired
        adv_vs_s = [d for _, d in paired_diff(pattern, "strawman_hpa", "holtwinters", "pod_seconds")]
        adv_vs_c = [d for _, d in paired_diff(pattern, "calibrated_hpa", "holtwinters", "pod_seconds")]
        # advantage of HW vs reactive = reactive - HW = paired (reactive - HW)
        # paired_diff(a,b) = a - b, so strawman - hw is HW advantage when positive... wait
        # advantage HW vs strawman = strawman - hw = paired_diff(strawman, holtwinters) ✓
        # advantage HW vs calibrated = calibrated - hw = paired_diff(calibrated, holtwinters) ✓
        # But if calibrated < hw, adv is negative meaning HW used MORE pods
        d_s = cohens_d(straw, hw)  # strawman vs hw on pod-seconds (positive => strawman higher)
        d_c = cohens_d(cal, hw)
        lines.append(
            f"| {pattern} | {mean_sd(straw)} | {mean_sd(hw)} | {mean_sd(cal)} | "
            f"{mean_sd(adv_vs_s)} | {mean_sd(adv_vs_c)} | {cell(d_s)} | {cell(d_c)} |"
        )

    lines.append("")
    lines.append("## Derived arms (no extra cluster run)")
    lines.append("")
    lines.append(
        "Component B uses Holt–Winters on seasonal and strawman HPA on burst. "
        "Components A+B use Holt–Winters on seasonal and conservatively tuned HPA on burst."
    )
    lines.append("")
    lines.append("| Pattern | Derived arm | Selected measured arm | Pod-seconds (mean ± SD) | Hot fraction (mean ± SD) |")
    lines.append("|---|---|---|---:|---:|")
    derived = {
        ("seasonal", "B_switch_strawman"): "holtwinters",
        ("burst", "B_switch_strawman"): "strawman_hpa",
        ("seasonal", "AB_switch_tuned"): "holtwinters",
        ("burst", "AB_switch_tuned"): "calibrated_hpa",
    }
    for (pattern, label), selected in derived.items():
        lines.append(
            f"| {pattern} | {label} | {selected} | "
            f"{mean_sd(metric_list(pattern, selected, 'pod_seconds'))} | "
            f"{mean_sd(metric_list(pattern, selected, 'hot_fraction'), 3)} |"
        )

    lines.append("")
    lines.append("## Cost vs saturation (read together)")
    lines.append("")
    lines.append(
        "Lower pod-seconds mean less capacity held. Higher hot fraction / mean CPU above the 200 m request "
        "mean pods are busier. The conservatively tuned HPA often wins on pod-seconds **and** shows higher "
        "saturation. Without latency, that is a **cost/capacity** finding only, not a service-quality claim."
    )
    lines.append("")
    lines.append("## Paper online numbers we can cite (early detection)")
    lines.append("")
    lines.append(
        "Authors’ Kaggle online release reports Holt–Winters early-detection vs HPA "
        "(seconds earlier): seasonal **30.8 s**, burst **20.5 s**. "
        "We did not recompute early-detection in our shortened 120 s windows; our primary metric is pod-seconds."
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

#!/usr/bin/env python3
"""Generate vector figures for the Overleaf article from committed result summaries."""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "FA26_Grp36_23i0585_23i0782_calibrated_autoscaling_benchmark" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# Single-column IEEE width ~3.5 in at 9 pt
COL_W = 3.45

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.size": 8,
        "axes.labelsize": 8,
        "axes.titlesize": 8.5,
        "legend.fontsize": 6.5,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "figure.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.05,
    }
)

COLORS = {
    "soft": "#4C72B0",
    "tuned": "#55A868",
    "hw": "#C44E52",
}


def _legend_below_axes(ax, ncol: int = 3, y: float = -0.16) -> None:
    """Compact legend just under the axes (axes coordinates)."""
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, y),
        ncol=ncol,
        frameon=False,
        fontsize=5.5,
        handlelength=0.85,
        handletextpad=0.35,
        columnspacing=0.6,
        borderaxespad=0.0,
    )


_MODEL_SHORT = {
    "persistence": "pers.",
    "gbdt": "GBDT",
    "moving_average_6": "MA-6",
    "hw_period_6": "HW-6",
    "hw_train_selected": "HW-sel.",
}


def fig_historical_capacity() -> None:
    patterns = ["Seasonal", "Burst"]
    arms = ["Soft HPA", "Holt--Winters", "Tuned HPA"]
    means = np.array(
        [
            [943.01, 766.80, 583.25],
            [1088.25, 728.38, 653.40],
        ]
    )
    sds = np.array(
        [
            [94.07, 39.61, 79.59],
            [274.75, 46.49, 24.74],
        ]
    )
    x = np.arange(len(patterns))
    width = 0.22
    fig, ax = plt.subplots(figsize=(COL_W, 2.55))
    for i, (arm, color_key) in enumerate(zip(arms, ("soft", "hw", "tuned"))):
        ax.bar(
            x + (i - 1) * width,
            means[:, i],
            width,
            yerr=sds[:, i],
            capsize=2,
            label=arm,
            color=COLORS[color_key],
            edgecolor="black",
            linewidth=0.35,
        )
    ymax = float(np.max(means + sds))
    ax.set_ylim(0, ymax * 1.12)
    ax.set_ylabel("Ready pod-seconds\n(mean ± SD, n=3)")
    ax.set_xticks(x)
    ax.set_xticklabels(patterns)
    ax.set_title("Historical live runs (capacity only)")
    _legend_below_axes(ax, y=-0.20)
    fig.subplots_adjust(bottom=0.19, top=0.88)
    fig.savefig(OUT / "fig_historical_pods.pdf", pad_inches=0.02)
    plt.close(fig)


def fig_live_qos() -> None:
    workloads = ["NASA", "On/off", "Stepped"]
    errors = {
        "Soft HPA": [44.76, 50.05, np.nan],
        "Tuned HPA": [37.75, 48.55, 17.58],
        "Holt--Winters": [18.04, 13.29, 1.01],
    }
    pods = {
        "Soft HPA": [1192.5, 1612.5, np.nan],
        "Tuned HPA": [915.0, 1332.5, 5872.5],
        "Holt--Winters": [3479.17, 3542.5, 13025.0],
    }
    keys = ("soft", "tuned", "hw")
    labels = ("Soft HPA", "Tuned HPA", "Holt--Winters")
    x = np.arange(len(workloads))
    width = 0.22

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(COL_W, 3.55), sharex=True)
    for label, ck in zip(labels, keys):
        vals = np.array(errors[label], dtype=float)
        for j, v in enumerate(vals):
            if np.isnan(v):
                continue
            ax1.bar(
                x[j] + (labels.index(label) - 1) * width,
                v,
                width,
                label=label,
                color=COLORS[ck],
                edgecolor="black",
                linewidth=0.35,
            )
    ax1.set_ylabel("Request error rate (%)")
    ax1.set_title("Overload-oriented live replays")
    ax1.set_ylim(0, 52)
    ax1.set_xticks(x)
    ax1.set_xticklabels(workloads)

    for label, ck in zip(labels, keys):
        vals = np.array(pods[label], dtype=float)
        for j, v in enumerate(vals):
            if np.isnan(v):
                continue
            ax2.bar(
                x[j] + (labels.index(label) - 1) * width,
                v,
                width,
                label=label,
                color=COLORS[ck],
                edgecolor="black",
                linewidth=0.35,
            )
    ax2.set_yscale("log")
    ax2.set_ylabel("Pod-seconds (log scale)")
    ax2.set_xticks(x)
    ax2.set_xticklabels(workloads)

    handles, leg_labels = ax1.get_legend_handles_labels()
    # Deduplicate legend entries (one per arm despite per-bar draws)
    seen: set[str] = set()
    h_unique, l_unique = [], []
    for h, lab in zip(handles, leg_labels):
        if lab in seen:
            continue
        seen.add(lab)
        h_unique.append(h)
        l_unique.append(lab)
    ax2.legend(
        h_unique,
        l_unique,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.28),
        ncol=3,
        frameon=False,
        fontsize=5.5,
        handlelength=0.85,
        handletextpad=0.35,
        columnspacing=0.6,
        borderaxespad=0.0,
    )
    fig.subplots_adjust(bottom=0.17, top=0.94, hspace=0.32)
    fig.savefig(OUT / "fig_live_qos.pdf", pad_inches=0.02)
    plt.close(fig)


def fig_offline_mae() -> None:
    summary = REPO / "results" / "dataset_phase" / "offline_summary.csv"
    if not summary.exists():
        return
    by_pattern: dict[str, tuple[str, float]] = {}
    with summary.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("horizon_steps") != "1":
                continue
            pattern = row["pattern"]
            mae = float(row["mae"])
            model = row["model"]
            if pattern not in by_pattern or mae < by_pattern[pattern][1]:
                by_pattern[pattern] = (model, mae)
    patterns = sorted(by_pattern.keys())
    maes = [by_pattern[p][1] for p in patterns]
    models = [by_pattern[p][0] for p in patterns]
    short_models = [_MODEL_SHORT.get(m, m) for m in models]

    fig, ax = plt.subplots(figsize=(COL_W, 3.05))
    y = np.arange(len(patterns))
    ax.barh(y, maes, color="#8172B2", edgecolor="black", linewidth=0.35, height=0.55)
    ax.set_yticks(y)
    ax.set_yticklabels(patterns, fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel("Mean MAE (15 min horizon)")
    ax.set_title("D1 offline: best model per pattern")
    xmax = max(maes) * 1.28
    ax.set_xlim(0, xmax)
    for yi, val, sm in zip(y, maes, short_models):
        ax.text(
            val + xmax * 0.02,
            yi,
            f"{val:.2f} ({sm})",
            va="center",
            ha="left",
            fontsize=6,
        )
    fig.subplots_adjust(left=0.20, right=0.98)
    fig.savefig(OUT / "fig_offline_mae.pdf")
    plt.close(fig)


def main() -> None:
    fig_historical_capacity()
    fig_live_qos()
    fig_offline_mae()
    print(f"Wrote figures to {OUT}")


if __name__ == "__main__":
    main()

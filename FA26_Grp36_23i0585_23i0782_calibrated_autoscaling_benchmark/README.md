# Overleaf project: FA26 Grp36 (calibrated autoscaling benchmark)

Overleaf project name: **`FA26_Grp36_23i0585_23i0782_calibrated_autoscaling_benchmark`** (or your Overleaf copy of it).

Compile **`main.tex`** (IEEEtran journal class). This project is maintained manually on Overleaf; it is **not** auto-synced from GitHub.

## Figures

Regenerate bar charts from repo root:

```bash
pip install -r requirements-paper.txt
python scripts/plot_paper_figures.py
```

Output goes to `figures/` in this folder. Upload those three PDFs into Overleaf’s `figures/` folder if you regenerate locally.

| File | Used in paper |
|------|----------------|
| `figures/fig_historical_pods.pdf` | Historical pod-seconds |
| `figures/fig_offline_mae.pdf` | D1 offline MAE |
| `figures/fig_live_qos.pdf` | Live QoS replays |

Fig. 1 (evaluation stack) is **TikZ** inside `main.tex` — no separate image file.

## Overleaf manual sync

When you pull updates from this git repo:

1. Copy changed text from `main.tex` into Overleaf, **or** upload `main.tex` to replace the Overleaf copy.
2. If `scripts/plot_paper_figures.py` changed, rerun it and re-upload `figures/*.pdf`.
3. Recompile on Overleaf.
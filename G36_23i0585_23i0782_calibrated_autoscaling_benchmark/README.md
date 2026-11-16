# Overleaf / LaTeX article (versioned in repo)

Compile **`main_article.tex`** (IEEEtran journal class). Figures are generated from measured results:

```bash
python scripts/plot_paper_figures.py
```

Output PDFs are written to `figures/` (bar charts only). The evaluation-stack figure is drawn with TikZ inside `main_article.tex`. Requires `matplotlib` (see `requirements-paper.txt` in repo root).

### Overleaf / placeholders

`main_article.tex` includes three bar-chart PDFs:

- `figures/fig_historical_pods.pdf`
- `figures/fig_offline_mae.pdf`
- `figures/fig_live_qos.pdf`

If Overleaf shows empty boxes, the `figures/` folder is missing in the project. Either:

1. **GitHub sync:** pull latest `main` (these PDFs are committed in the repo), or  
2. **Manual upload:** in Overleaf, create folder `figures/` next to `main_article.tex` and upload the three PDFs from this directory, or  
3. **Regenerate locally:** run `python scripts/plot_paper_figures.py` from repo root, then upload/copy the new PDFs.

Recompile after the files are present (LaTeX → Recompile).

The file `main_article_v1a_change_this.tex` is retired; use `main_article.tex` only.

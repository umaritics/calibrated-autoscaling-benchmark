# NASA repetition checkpoint

Status: **PARTIAL**.

- Accepted: three soft-HPA runs, two tuned-HPA runs, three Holt-Winters runs.
- Retained but excluded: two repeat-3 tuned-HPA attempts, both INCONCLUSIVE due
  to 75/84 CPU samples versus the fixed minimum of 76/84.
- No accepted run was overwritten, no failed evidence was deleted, and no run
  was selected by performance outcome.
- `nine_run_summary.json`, `per_repeat.csv`, `mean_sd.csv`, paired tables, the
  independent verification report, and SHA-256 evidence manifest are present.
- The NASA experiment remains a trace-derived replay against the benchmark
  service. It does not complete the broader research project.

Known limitation: the required third accepted tuned-HPA repeat is unavailable.
Further unchanged retries after two identical coverage failures risk selection
bias because missing metrics coincide with measured workload unavailability.

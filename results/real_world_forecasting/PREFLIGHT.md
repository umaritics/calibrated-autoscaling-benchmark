# Resource preflight

Captured before Task 11 computation on 2026-10-24:

- Filesystem: 95 GiB total, 85 GiB used, 5.4 GiB available (95% used).
- Memory: 19 GiB total, 11 GiB available; 15 GiB swap, unused.
- Logical CPUs: 8.
- Git: `main` was three commits ahead of `origin/main` at `c135525`.
- Input footprint: NASA 36 MiB; Alibaba 17 MiB.

The evaluator uses one numerical thread, streams compressed sources, retains
only small preprocessed series, and checkpoints prediction output after each
dataset. The measured peak RSS for the first complete run was 169,364 KiB and
wall time was 25.57 seconds before adding the August inventory scan. No Docker,
kind, Kubernetes, or stress workload was started.

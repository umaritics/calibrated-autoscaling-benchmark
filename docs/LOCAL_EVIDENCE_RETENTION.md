# Local evidence retention and reconstruction

Raw source archives are intentionally excluded from Git. They remain on the
research machine under `data/`; live kubeconfig and tool environments are also
local-only. Do not substitute a newly downloaded file without recording its
hash and provenance.

## Production-trace inputs retained locally

| Path | SHA-256 | Bytes | Role |
|---|---|---:|---|
| `data/nasa/NASA_access_log_Jul95.gz` | `199109ed0f273e095da6ccd5fc9dc4cd8bb58daa06d62135e62090fea9d27488` | 20,676,672 | NASA replay source |
| `data/nasa/NASA_access_log_Aug95.gz` | `14995aed0ba4558ab832613ebea9a3ef2d87cb4297fc67f5694e0032bbb6b788` | 16,633,316 | retained NASA companion archive |
| `data/alibaba/container_usage.prefix.tar.gz` | `726e6240926dc2d7ba53cdfb88a91be8564d124d88d4dec1391e9f745e0a2988` | 16,777,216 | bounded Alibaba HTTP-range prefix; not a complete archive |

Verify the retained files:

```bash
sha256sum data/nasa/NASA_access_log_Jul95.gz \
  data/nasa/NASA_access_log_Aug95.gz \
  data/alibaba/container_usage.prefix.tar.gz
```

Rebuild the derived replay inputs and provenance without changing selection or
normalization parameters:

```bash
.venv/bin/python scripts/live/prepare_traces.py
.venv/bin/python -m unittest discover -s tests -v
```

The committed live run directories contain request records, Kubernetes object
snapshots, metrics, events, controller logs, summaries, and input copies. The
NASA evidence manifest records SHA-256 and byte size for every retained run
file. Verify it with the commands in
`results/live_trace_phase/nasa_three_repeat/REPRODUCE.md`; do not rerun the
inconclusive arm merely to obtain a preferable outcome.

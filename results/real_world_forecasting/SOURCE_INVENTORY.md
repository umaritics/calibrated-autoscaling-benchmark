# Source inventory and provenance

| Source | Retained file | SHA-256 | Role |
|---|---|---|---|
| NASA HTTP July 1995 | `data/nasa/NASA_access_log_Jul95.gz` | `199109ed0f273e095da6ccd5fc9dc4cd8bb58daa06d62135e62090fea9d27488` | Forecast evaluation source |
| NASA HTTP August 1995 | `data/nasa/NASA_access_log_Aug95.gz` | `14995aed0ba4558ab832613ebea9a3ef2d87cb4297fc67f5694e0032bbb6b788` | Paper-protocol inventory clue only; not scored |
| Alibaba v2018 container usage | `data/alibaba/container_usage.prefix.tar.gz` | `726e6240926dc2d7ba53cdfb88a91be8564d124d88d4dec1391e9f745e0a2988` | Forecast evaluation source; bounded 16 MiB byte-range prefix |

NASA originates from the Internet Traffic Archive; the retained archives were
downloaded through the documented mirror because the original host failed DNS.
Alibaba originates from the official v2018 `container_usage.tar.gz`; only bytes
0–16,777,215 are retained, so its hash cannot equal the complete archive hash.
The official full container archive SHA-256 is
`b4bd3b1b82f5407c1b0dd47fe736ff5152c4b016a9c30cb26f988e2d1c5e5031`.

Across the two NASA archives, direct parsing finds 3,461,612 requests and
16,364 nonempty five-minute bins, exactly matching the sample count described
by the authors' public repository. This strongly suggests their aggregation
dropped empty bins, but does not establish their split, forecast horizon,
features, or MAPE zero rule. The independent evaluation therefore uses July
complete calendar bins and reports its protocol separately.

Official documentation:

- https://ita.ee.lbl.gov/html/contrib/NASA-HTTP.html
- https://github.com/alibaba/clusterdata/tree/master/cluster-trace-v2018
- https://github.com/syswe/llm-phpa

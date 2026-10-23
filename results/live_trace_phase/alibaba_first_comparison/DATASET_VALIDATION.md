# Alibaba subset validation

Decision: **PASS WITH SEVERE LIMITATIONS** for an observation-indexed demand
shape replay only. The required label is **"Alibaba-trace-derived demand replay
on a benchmark Kubernetes service."** This is not a replay of Alibaba request
traffic, original service behavior, latency, or cluster infrastructure.

## Source and bounded evidence

The source is Alibaba Cluster Trace v2018 `container_usage.tar.gz`, member
`container_usage.csv`. Official documentation and schema:
https://github.com/alibaba/clusterdata/tree/master/cluster-trace-v2018. The
download URL used was
`https://aliopentrace.oss-cn-beijing.aliyuncs.com/v2018Traces/container_usage.tar.gz`.
The official full-archive SHA-256 is
`b4bd3b1b82f5407c1b0dd47fe736ff5152c4b016a9c30cb26f988e2d1c5e5031`.

Only bytes 0–16,777,215 were downloaded from the 29,208,338,602-byte object.
The prefix SHA-256 is
`726e6240926dc2d7ba53cdfb88a91be8564d124d88d4dec1391e9f745e0a2988`.
It decodes 2,308,039 complete rows before the expected truncated-stream error,
covering 2,430 named identifiers plus 3,503 rows with an empty identifier. The
complete observed identifier list is in `available_container_ids.txt`. This is
a lexicographic prefix, not a random or representative sample; its final
identifier may be truncated.

## `c_1` audit

Within the prefix, `c_1` is one stored block of 1,018 rows followed by `c_10`.
All timestamps are unique and strictly increasing, from 86,610 to 777,370
relative seconds (690,760 seconds, about 7.995 days). This establishes a
complete stored block within the prefix, but not independent equality with the
unavailable full archive. CPU values are valid schema-range percentages.

The observations are sparse and irregular: gaps are 10–21,520 seconds, median
450 seconds; the longest 10-second-cadence chain is two observations. The
official schema specifies timestamp units but not a fixed sampling cadence, so
unobserved timestamps cannot automatically be called missing measurements. On
a hypothetical 10-second grid, `c_1` occupies 1,018 of 69,077 slots. It has no
42-observation contiguous interval at that cadence.

## Predeclared selection and sufficiency

The selected input is the first 42 `c_1` observations in timestamp order,
source times 86,610–119,730. It spans 33,120 source seconds; gaps are 20–3,650
seconds (median 460), and no adjacent pair is 10 seconds apart. On a hypothetical
10-second grid it occupies 42 of 3,313 slots; the other 3,271 slots are
unobserved, not imputed zeros. CPU ranges 3–58%
(mean 16.595%, sample SD 14.570%, 26 unique values), so it has ample amplitude
variation for a scaling stress test.

The selection and derived CSV were committed in `55fdc3e` before any Alibaba
controller outcome. Exactly 42 real observations support a 42-bin replay
without fabrication, repetition, interpolation, or imputation. They do not
support a temporally faithful contiguous-source replay. The experiment is
therefore admissible only as the explicitly time-warped observation-sequence
transformation in `WORKLOAD_TRANSFORMATION.md`.

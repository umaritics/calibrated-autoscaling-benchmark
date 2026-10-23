# Frozen Alibaba trace-to-load transformation

Frozen before live comparison. No parameter in this specification may be
changed after observing a controller outcome.

Experiment label: **"Alibaba-trace-derived demand replay on a benchmark
Kubernetes service."**

1. Read `container_usage.csv` with the official 11-column v2018 schema.
   `time_stamp` is relative seconds and `cpu_util_percent` is container CPU
   utilization in percent. CPU utilization is telemetry, not HTTP demand.
2. Select identifier `c_1` because it is the first nonempty identifier in the
   stored prefix, then select its first 42 timestamp-ordered observations. This
   selection is outcome-independent.
3. Reject invalid timestamps, duplicate/non-increasing timestamps, negative
   CPU, CPU above 100, or fewer than 42 rows. The selected data pass. Do not
   impute, interpolate, repeat, smooth, or aggregate observations.
4. Map observation index `i` to replay second `10*i`. This maps 33,120 source
   seconds to 420 replay seconds. Because the source gaps vary from 20 to 3,650
   seconds, this is nonlinear time warping rather than one constant compression
   ratio. It changes burst frequency and inter-burst spacing.
5. Map each CPU value `x_i` to `target_rps_i = 120 * x_i / 58`, where 58 is the
   maximum fixed before execution. This preserves relative amplitude ratios but
   changes units and absolute amplitude. The resulting range is 6.206897–120
   requests/s.
6. For each 10-second bin schedule `round(target_rps_i * 10)` requests evenly
   within the bin. The frozen measurement schedule contains 14,420 requests
   over 420 seconds (34.333 scheduled requests/s). Before it, run the established
   120-second warmup at exactly 4 requests/s (480 requests).
7. Use the identical `trace.csv`, schedule construction, five-second request
   timeout, 2,048 in-flight cap, application, resources, probes, and replica
   bounds for all three arms.

The generator knows the schedule. Neither HPA receives future values. The PHPA
observes Kubernetes CPU history only and is restarted before its arm; its CR has
a fresh UID. No controller is given container IDs, source timestamps, future
CPU observations, or target RPS values.

Frozen input SHA-256:
`5bc5d7705562b791602824bc8498866cef92db0a726b48c7c9aeeecccb850e47`.
Frozen raw-selection SHA-256:
`6efde9ad776c4836944d45ff0782ea650db77e955d83538708017f587f38edfa`.

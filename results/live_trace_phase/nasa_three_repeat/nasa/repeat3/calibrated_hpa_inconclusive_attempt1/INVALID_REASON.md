# Inconclusive attempt retained

This first repeat-3 tuned-HPA attempt completed collection but was classified
`INCONCLUSIVE` by the frozen analyzer. CPU telemetry was present for 75 of 84
measurement samples (89.3%), just below the predeclared 90% minimum. The nine
missing samples were empty metrics-server responses at elapsed seconds
175--185, 220--230, and 265--275. Request accounting, deterministic schedule,
dispatch delay, generator drops, controller exclusivity, timestamps, metric
sample spacing, window bracketing, and scaling-response checks all passed.

The evidence is retained without use in the accepted nine-run comparison. A
single unchanged retry of only this invalid arm was permitted as the minimum
correction for an instrumentation defect.

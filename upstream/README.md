# Upstream experiment harness

Do not commit a full clone here.

```bash
./scripts/setup_from_upstream.sh
```

That clones [syswe/workloads-predictional-scaling-operators](https://github.com/syswe/workloads-predictional-scaling-operators)
into `upstream/workloads-predictional-scaling-operators/` (gitignored) and overlays
our policies and scripts.

The authors' Docker Hub image `syswe/predictive-horizontal-pod-autoscaler` was not
publicly pullable (2026-10-10). Install the upstream operator they document:

```bash
helm install predictive-horizontal-pod-autoscaler-operator \
  https://github.com/jthomperoo/predictive-horizontal-pod-autoscaler/releases/download/v0.13.2/predictive-horizontal-pod-autoscaler-v0.13.2.tgz \
  --namespace phpa-system --create-namespace
```

Our `policies/phpa-holtwinters.yaml` already uses API group `jamiethompson.me/v1alpha1`
with the paper's Holt–Winters coefficients.

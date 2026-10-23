#!/usr/bin/env bash
# Creates only the named benchmark cluster; never modifies existing research clusters.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
mkdir -p .tools data
kind create cluster --name calibrated-live --image "${KIND_IMAGE:-kindest/node:v1.32.2}" \
  --config manifests/live/kind.yaml --kubeconfig live-kubeconfig --wait 120s
docker cp calibrated-live-control-plane:/usr/bin/kubectl .tools/kubectl
chmod +x .tools/kubectl
curl -fL https://github.com/jthomperoo/predictive-horizontal-pod-autoscaler/releases/download/v0.13.2/predictive-horizontal-pod-autoscaler-v0.13.2.tgz \
  -o data/phpa-operator-v0.13.2.tgz
helm install phpa data/phpa-operator-v0.13.2.tgz --kubeconfig live-kubeconfig --namespace phpa-system --create-namespace
.tools/kubectl --kubeconfig live-kubeconfig apply -f manifests/metrics-server.yaml
.tools/kubectl --kubeconfig live-kubeconfig create namespace trace-benchmark
.tools/kubectl --kubeconfig live-kubeconfig -n trace-benchmark apply -f manifests/sample-app.yaml
.tools/kubectl --kubeconfig live-kubeconfig -n trace-benchmark patch svc php-apache \
  -p '{"spec":{"type":"NodePort","ports":[{"port":80,"targetPort":80,"nodePort":30080}]}}'
.tools/kubectl --kubeconfig live-kubeconfig -n phpa-system rollout status deploy/predictive-horizontal-pod-autoscaler --timeout=300s
.tools/kubectl --kubeconfig live-kubeconfig -n kube-system rollout status deploy/metrics-server --timeout=300s
.tools/kubectl --kubeconfig live-kubeconfig -n trace-benchmark rollout status deploy/php-apache --timeout=300s

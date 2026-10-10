#!/bin/bash
set -e

echo "1. Creating kind cluster..."
kind create cluster --name research-cluster || echo "Cluster already exists."

echo "2. Installing Metrics Server (required for HPA)..."
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
# Patch metrics server to allow insecure TLS (required for local kind cluster)
kubectl patch -n kube-system deployment metrics-server --type=json \
  -p '[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]'

echo "3. Installing KEDA..."
kubectl apply --server-side -f https://github.com/kedacore/keda/releases/download/v2.12.1/keda-2.12.1.yaml

echo "Waiting for metrics-server to be ready..."
kubectl rollout status deployment metrics-server -n kube-system

echo "Cluster setup complete!"

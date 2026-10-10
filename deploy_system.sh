#!/bin/bash
set -e

echo "Deploying Target Application..."
kubectl apply -f app.yaml

echo "Deploying Hybrid Scaler metrics API..."
kubectl apply -f scaler-api.yaml

echo "Waiting for pods to be ready..."
kubectl wait --for=condition=available deployment/workload-app --timeout=60s
kubectl wait --for=condition=available deployment/scaler-api --timeout=60s

echo "Applying KEDA Predictive/Hybrid Scaler..."
kubectl apply -f keda-hybrid.yaml

echo "Applying Calibrated Reactive HPA..."
# Need to delete the KEDA one if applying this to the same target, or keep them separate.
# In a real evaluation, you'd apply them one at a time and run Locust for each.
echo "(HPA manifest is ready at hpa-reactive.yaml for baseline testing)"

echo "System Deployed Successfully!"
echo "Run locust with: source venv/bin/activate && pip install locust && locust -f load_test.py --host=http://<node-ip>:<node-port>"

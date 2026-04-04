# Client App Helm Chart

A Helm chart for deploying static frontend applications served by nginx.

## Installation

```bash
helm repo add mucsi96 https://mucsi96.github.io/k8s-helm-charts
helm repo update
helm install my-client-app mucsi96/client-app
```

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `appPort` | Port the application listens on | `8000` |
| `metricsPort` | Port for Prometheus metrics | `8085` |
| `resources.requests.memory` | Memory request | `20Mi` |
| `resources.requests.cpu` | CPU request | `20m` |
| `resources.limits.memory` | Memory limit | `100Mi` |
| `resources.limits.cpu` | CPU limit | `500m` |

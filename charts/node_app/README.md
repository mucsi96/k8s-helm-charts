# Node App Helm Chart

A Helm chart for deploying Node.js backend applications.

## Installation

```bash
helm repo add mucsi96 https://mucsi96.github.io/k8s-helm-charts
helm repo update
helm install my-node-app mucsi96/node-app
```

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `appPort` | Port the application listens on | `8080` |
| `resources.requests.memory` | Memory request | `300Mi` |
| `resources.requests.cpu` | CPU request | `20m` |
| `resources.limits.memory` | Memory limit | `500Mi` |
| `resources.limits.cpu` | CPU limit | `500m` |

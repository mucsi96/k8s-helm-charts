# Grafana Alloy Helm Chart

A Helm chart for deploying [Grafana Alloy](https://grafana.com/oss/alloy/) as a telemetry collector for metrics, logs, and traces.

## Installation

```bash
helm repo add mucsi96 https://mucsi96.github.io/k8s-helm-charts
helm repo update
helm install my-alloy mucsi96/grafana-alloy --set-file config=config.alloy
```

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `config` | Alloy configuration file contents in Alloy syntax (required) | - |
| `port` | HTTP server port | `12345` |
| `env` | Environment variables stored as a secret and exposed via `envFrom` | `{}` |
| `resources.requests.memory` | Memory request | `128Mi` |
| `resources.requests.cpu` | CPU request | `50m` |
| `resources.limits.memory` | Memory limit | `512Mi` |
| `resources.limits.cpu` | CPU limit | `500m` |

## RBAC

The chart creates a `ServiceAccount`, `ClusterRole`, and `ClusterRoleBinding`
that grant Alloy read access to nodes, services, endpoints, pods, namespaces,
endpoint slices, and ingresses for Kubernetes service discovery.

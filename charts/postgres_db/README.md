# Postgres DB Helm Chart

A Helm chart for deploying a PostgreSQL database with Prometheus exporter.

## Installation

```bash
helm repo add mucsi96 https://mucsi96.github.io/k8s-helm-charts
helm repo update
helm install my-postgres-db mucsi96/postgres-db
```

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `port` | PostgreSQL port | `5432` |
| `metricsPort` | Port for Prometheus metrics | `8085` |
| `initSql` | SQL to run on initialization | `""` |
| `resources.requests.memory` | Memory request | `200Mi` |
| `resources.requests.cpu` | CPU request | `20m` |
| `resources.limits.memory` | Memory limit | `300Mi` |
| `resources.limits.cpu` | CPU limit | `500m` |
| `persistentVolumeClaim.accessMode` | PVC access mode | `ReadWriteOnce` |
| `persistentVolumeClaim.storageClassName` | PVC storage class | `""` |
| `persistentVolumeClaim.volumeName` | PVC volume name | `""` |
| `persistentVolumeClaim.storage` | PVC storage size | `1Gi` |

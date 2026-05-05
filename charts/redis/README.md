# Redis Helm Chart

A simple Helm chart for deploying Redis as a session store for oauth2-proxy.

## Installation

```bash
helm repo add mucsi96 https://mucsi96.github.io/k8s-helm-charts
helm repo update
helm install my-redis mucsi96/redis --set password=changeme
```

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `password` | Redis password (required) | - |
| `port` | Redis service port | `6379` |
| `resources.requests.memory` | Memory request | `64Mi` |
| `resources.requests.cpu` | CPU request | `10m` |
| `resources.limits.memory` | Memory limit | `256Mi` |
| `resources.limits.cpu` | CPU limit | `200m` |
| `persistentVolumeClaim.accessMode` | PVC access mode | `ReadWriteOnce` |
| `persistentVolumeClaim.storageClassName` | PVC storage class | `""` |
| `persistentVolumeClaim.volumeName` | PVC volume name | `""` |
| `persistentVolumeClaim.storage` | PVC storage size | `1Gi` |

## Using with oauth2-proxy

Configure oauth2-proxy with:

```
--session-store-type=redis
--redis-connection-url=redis://:<password>@<release-name>.<namespace>.svc.cluster.local:6379
```

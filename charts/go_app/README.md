# Go App Helm Chart

A Helm chart for Go HTTP services, based on `spring_app`. It retains the Spring
chart's resource naming, Azure Workload Identity, environment/config secrets,
checksum-triggered rollouts, HTTPRoute and persistent volume configuration.

## Installation

```bash
helm repo add mucsi96 https://mucsi96.github.io/k8s-helm-charts
helm repo update
helm upgrade my-go-app mucsi96/go-app --install \
  --set image=myregistry.io/my-go-app:1.0.0 \
  --set host=api.example.com \
  --set basePath=/api \
  --set serviceAccountName=my-go-app-sa \
  --set clientId=12345678-1234-1234-1234-123456789abc
```

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `image` | Application container image | Required |
| `host` | Hostname for the HTTPRoute | Required |
| `serviceAccountName` | Workload identity service account name | Required |
| `clientId` | Azure client ID for workload identity | Required |
| `appPort` | Application container and Service port; sets `SERVER_PORT` | `8080` |
| `managementPort` | Health listener container and Service port; sets `MANAGEMENT_PORT` | `8082` |
| `basePath` | Route prefix, also supplied as `BASE_PATH` | `/` |
| `health.livenessPath` | Liveness endpoint on the management listener | `/health/liveness` |
| `health.readinessPath` | Readiness and startup endpoint on the management listener | `/health/readiness` |
| `env` | Environment variables stored in a Secret | `{}` |
| `configFile` | Config secrets with `name`, `mountPath` and base64-encoded `data` | `[]` |
| `persistentVolumeClaims` | PVCs with `name`, `mountPath`, `accessMode`, `storageClassName`, `volumeName`, `storage` | `[]` |
| `resources.requests.memory` | Memory request | `300Mi` |
| `resources.requests.cpu` | CPU request | `20m` |
| `resources.limits.memory` | Memory limit | `500Mi` |
| `resources.limits.cpu` | CPU limit; set to null to omit | `500m` |

Applications must listen on `SERVER_PORT` and `MANAGEMENT_PORT`, expose the
configured health endpoints, and handle SIGTERM. The route preserves its path;
the application must serve the configured prefix. `BASE_PATH` is available to
applications that configure their routing from the environment. The management
listener is exposed on the internal Service but is not routed through the public
HTTPRoute. As in the Spring chart, the image must include `sh` and `sleep` for
the ten-second pre-stop drain hook.

The chart sets the port/base-path environment variables directly; configure
them with chart values rather than duplicate entries under `env`.

## Migrating from spring-app

Use the same Helm release name and existing `image`, `host`, `basePath`,
`clientId`, `serviceAccountName`, `env`, `configFile`, `persistentVolumeClaims`
and `resources` values, changing the chart name to `mucsi96/go-app`.

Replace `springActuatorPort` with `managementPort` if overridden. The default
remains 8082; its named port changes from `actuator` to `management`.
Spring Admin and servlet-context environment variables are not emitted.
The Go service implements `/health/liveness` and `/health/readiness` directly;
these endpoints do not depend on Spring Actuator. Override `health` paths if
the service uses different endpoints.
Readiness is checked in addition to the existing startup and liveness probes.
The route continues to attach to the shared Traefik `websecure` Gateway listener.

PVC definitions and mounted paths are unchanged. Environment and config secrets
and the workload identity service account retain their existing resource names.

## Local validation

```bash
helm lint charts/go_app --set image=example/go-app:1 \
  --set host=api.example.com --set serviceAccountName=go-app --set clientId=example
bash scripts/render_go_app.sh
```

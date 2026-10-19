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
| `healthPath` | Static origin path used by startup/readiness/liveness probes | `/` |
| `route.enabled` | Create this chart's root HTTPRoute | `true` |
| `resources.requests.memory` | Memory request | `20Mi` |
| `resources.requests.cpu` | CPU request | `20m` |
| `resources.limits.memory` | Memory limit | `100Mi` |
| `resources.limits.cpu` | CPU limit | `500m` |

When the platform ForwardAuth release owns SPA routing, set `route.enabled=false`
and `healthPath=/index.html`. The Deployment and Service remain managed by this
chart; Gateway authentication, deep-link rewriting and inline configuration are
configured in `oauth2-proxy-forwardauth`. The origin should serve real files and
return 404 for missing paths.

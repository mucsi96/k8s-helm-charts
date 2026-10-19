# Rust App Helm Chart

Deploys native Rust HTTP services, including distroless Axum-style applications.
Uses the same release/Service/Secret/PVC naming conventions and standard Gateway
API `routeFilters` as `go-app`. Azure Workload Identity is optional; Kubernetes
service-account reuse is supported without creating RBAC permissions.

```bash
helm repo add mucsi96 https://mucsi96.github.io/k8s-helm-charts
helm repo update
helm upgrade my-rust-app mucsi96/rust-app --install \
  --set image=ghcr.io/example/rust-app:1 \
  --set host=rust.example.com
```

## Runtime contract

The chart supplies `LISTEN_ADDR=0.0.0.0:<appPort>`, `BASE_PATH` and `K8S_POD_IP`.
Applications must bind to the configured port, serve their configured route
prefix without a URL rewrite, and handle SIGTERM gracefully. Health probes use
the same HTTP listener, defaulting to `/healthz`, matching Observatory's current
Rust contract. Apps with dependency-aware readiness (for example `/readyz`)
should override `health.readinessPath`; startup uses that readiness path too.

There is no shell-based pre-stop hook or separate management listener. The image
need not contain `sh`, `sleep`, curl or wget: Kubernetes executes HTTP probes.
The default security context is non-root, read-only root filesystem, no privilege
escalation and all capabilities dropped. Configure writable volumes/fsGroup where
the application's storage contract requires them. Optional `lifecycle` settings
can use Kubernetes-native hooks if the cluster supports them.

## Values

| Parameter | Meaning | Default |
| --- | --- | --- |
| `image` | Complete versioned container image reference | Required |
| `host` | HTTPRoute hostname | Required |
| `appPort` | Container/Service HTTP port and `LISTEN_ADDR` port | `8080` |
| `basePath` | HTTPRoute prefix and `BASE_PATH` | `/` |
| `routeFilters` | Ordered Gateway API HTTPRoute filters | `[]` |
| `replicaCount` | Deployment replicas | `1` |
| `imagePullSecrets` | Existing registry credential references | `[]` |
| `serviceAccountName` | Service account name | Release name |
| `serviceAccount.create` | Create the named service account | `true` |
| `serviceAccount.automountServiceAccountToken` | Mount the Kubernetes API token | `false` |
| `serviceAccount.annotations` | Additional service-account annotations | `{}` |
| `clientId` | Optional Azure client ID; enables workload-identity annotation/label | Empty |
| `env` | Values in the chart-owned `<release>-env` Secret | `{}` |
| `envFrom` | Existing Secret/ConfigMap environment references | `[]` |
| `configFile` | `{name, mountPath, data}` entries; `data` is base64 content | `[]` |
| `persistentVolumeClaims` | Same `{name, mountPath, accessMode, storageClassName, volumeName, storage}` shape as Go | `[]` |
| `extraVolumes`, `extraVolumeMounts` | Existing config/secret or scratch mounts | `[]` |
| `podAnnotations` | Extra rollout/configuration annotations | `{}` |
| `podSecurityContext`, `securityContext` | Pod/container security settings | See values.yaml |
| `terminationGracePeriodSeconds` | Time for graceful shutdown | `30` |
| `lifecycle` | Optional native container lifecycle hooks | `{}` |
| `health.livenessPath`, `health.readinessPath` | HTTP health paths | `/healthz` |
| `resources.requests` | CPU/memory requests | `10m` / `64Mi` |
| `resources.limits` | Memory limit; CPU is not limited by default | `256Mi` |

Configure chart-owned environment variables with `appPort`/`basePath`, not `env`.
The env/file Secrets are only created when configured; their checksums roll pods
when chart-managed values change. Existing `envFrom`/volume data needs an explicit
rollout (for example a `podAnnotations` checksum managed by the deploy job).
Prefer existing Secret references for externally provisioned credentials.

## Standard routing filters and ForwardAuth

```yaml
routeFilters:
  - type: ResponseHeaderModifier
    responseHeaderModifier:
      set:
        - name: Cache-Control
          value: no-store
```

For ForwardAuth, provide a same-namespace proxy reference:

```bash
helm upgrade my-rust-app mucsi96/rust-app \
  --set auth.proxyService=my-app-oauth2-proxy \
  --set auth.cookieName=__Host-my-app-oauth2-proxy # plus app values
```

The Rust chart owns the API authentication Middleware and header/cache filters.
`auth: null` leaves direct Service routing. Use a client chart for static UI
document authentication; this chart calls `/oauth2/auth` and returns 401/403.
Do not combine `auth` and manual `routeFilters`. See
[application authentication](../../docs/application-auth.md) for modes and upgrade
order. Backend authorization and CSRF protection remain application contracts.

## Existing Kubernetes service accounts and configuration

An Observatory-style collector can retain platform-provisioned resources:

```yaml
image: ghcr.io/example/observatory:1
host: apps.example.com
serviceAccountName: observatory-reader
serviceAccount:
  create: false
  automountServiceAccountToken: true
envFrom:
  - secretRef:
      name: observatory-runtime
extraVolumes:
  - name: inventory
    configMap:
      name: observatory-config
extraVolumeMounts:
  - name: inventory
    mountPath: /app/config.json
    subPath: config.json
    readOnly: true
```

The platform must own that account's RBAC. Supplying `clientId` enables Azure
workload identity without granting vault/storage permissions. For a reused
account, its Azure annotation must already be managed by its owner.
Keep existing PVC names and volume bindings when adopting persisted data. Check
Helm resource ownership before migrating a Terraform-owned workload; the chart
does not change application registrations, permissions or data schemas.

## Local validation

```bash
helm lint charts/rust_app --set image=example/rust-app:1 --set host=rust.example.com
python3 scripts/check_rust_app.py
python3 scripts/check_forwardauth.py
bash scripts/render_rust_app.sh
```

The release workflow publishes `mucsi96/rust-app` with the `rust-app` version/tag
prefix, following the other application charts.

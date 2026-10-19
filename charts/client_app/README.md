# Client App Helm Chart

A Helm chart for deploying static frontend applications served by nginx.
The client release always owns its SPA document and static-asset HTTPRoute,
independently of whether authentication or runtime injection is configured.

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
| `routeFilters` | Standard auth/header filters applied to document requests | `[]` |
| `runtimeConfig` | Public string-valued JSON injected into index HTML | `{}` |
| `gateway` | Parent Gateway name, namespace and listener section | `traefik`, `traefik`, `websecure` |
| `resources.requests.memory` | Memory request | `20Mi` |
| `resources.requests.cpu` | CPU request | `20m` |
| `resources.limits.memory` | Memory limit | `100Mi` |
| `resources.limits.cpu` | CPU limit | `500m` |

## SPA routing and optional authentication

GET/HEAD `/`, `/index.html` and document requests (`Sec-Fetch-Dest: document` or
HTML in `Accept`) use the document rule. The Gateway selects `/index.html` for
these requests; nginx/storage only serves actual files and returns 404 for
missing assets. `basePath`, when supplied, scopes both rules and the index path
under that prefix. For a static-only origin, use `healthPath=/index.html`.

The static catchall does not perform document authentication or index rewriting.
More-specific API, OAuth and telemetry routes keep their own policy. Both static
origin paths strip app cookies, bearer and identity headers before the backend.

Authentication is optional. For ForwardAuth, enable `documentAuth` on the auth
chart and pass its published `document` policy as `routeFilters`. The client
chart accepts RequestHeaderModifier, ResponseHeaderModifier and ExtensionRef
filters. It combines response header settings into a single outer filter,
enforces credential/validator stripping and no-store document caching, and runs
auth before URL rewriting. Backend request filters strip origin credentials
only after authentication, avoiding duplicate filter types in a rule.

The auth release supplies only auth middleware and policies. It does not own
this HTTPRoute, SPA fallback or frontend configuration. With no `routeFilters`,
the same SPA routes work without an auth release.

## Inline runtime configuration

```yaml
runtimeConfig:
  clientLogUrl: https://hello.example.test/_telemetry/collect
  clientAppName: hello-client
```

A nonempty map creates `<client-release>-index-config`, replacing the quoted
marker in the built HTML:

```html
<script>window.__APP_CONFIG__ = "__APP_CONFIG_JSON__";</script>
```

Values are public strings; never include credentials. Helm JSON serialization
escapes HTML delimiters and the replacement escapes literal dollars. Applications
should reject missing/unreplaced config. An empty map creates no plugin resource.

Enable the pinned plugin in Traefik static configuration before using injection:

```yaml
experimental:
  plugins:
    rewritebody:
      moduleName: github.com/traefik/plugin-rewritebody
      version: v0.3.1
```

Traefik 3.7.13 preserves the configured filter order. Document responses use
`private, no-cache, no-store`; validators, conditional and range headers are
removed. The origin is requested with `Accept-Encoding: identity` so the plugin
can replace uncompressed HTML. Immutable assets keep ordinary compression and
caching. These contracts apply equally to a future storage origin.

For same-origin Faro, logging Terraform owns the exact collector route and
strips app cookies/bearer/CSRF headers before rewriting to `/collect`. Configure
the runtime URL on the app origin to avoid cross-origin browser preflight while
retaining the collector's origin allowlist and rate limits.

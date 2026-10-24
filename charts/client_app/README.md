# Client App Helm Chart

A Helm chart for routing static frontend applications from nginx or an HTTPS storage origin.
The client release always owns its SPA document and static-asset HTTPRoute,
independently of whether authentication or runtime injection is configured.

## Installation

```bash
helm repo add mucsi96 https://mucsi96.github.io/k8s-helm-charts
helm repo update
helm install my-client-app mucsi96/client-app
```

For source checkout development, run `python3 scripts/build_app_dependencies.py`
at the repository root first. Published charts already bundle the shared library.

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `appPort` | Port the application listens on | `8000` |
| `staticOrigin` | External HTTPS origin hostname; omits client Deployment and Secret | `null` |
| `auth` | Same-namespace proxy reference; creates client-owned document authentication | `null` |
| `runtimeConfig` | Public string-valued JSON injected into index HTML | `{}` |
| `gateway` | Parent Gateway name, namespace and listener section | `traefik`, `traefik`, `websecure` |
| `resources.requests.memory` | Memory request | `20Mi` |
| `resources.requests.cpu` | CPU request | `20m` |
| `resources.limits.memory` | Memory limit | `100Mi` |
| `resources.limits.cpu` | CPU limit | `500m` |

## SPA routing and optional authentication

### Azure Storage origin

Set `staticOrigin` to the account's `primary_web_host` (hostname only). Keep the
same release name on upgrade with `--reset-values`: Helm removes the old client
Deployment/Secret and replaces the Service with an ExternalName Service.
No image or application port is needed in this mode.

The HTTPRoute references a same-namespace TraefikService using HTTPS on port 443,
normal certificate verification, and `passHostHeader: false` for the storage Host
header. Enable `providers.kubernetesCRD.allowExternalNameServices` in Traefik and
grant the app deployment identity namespace-scoped TraefikService permissions.
Direct Gateway API ExternalName backends are unsupported by Traefik 3.7.

Document credential/conditional-header stripping runs through a route-level
Middleware after ForwardAuth because Traefik ignores backend filters on
TraefikService references. The existing container mode retains its backend filters.
Both modes are covered by `scripts/check_spa_frontend.py`; run with
`STATIC_ORIGIN=1` to exercise an external TLS origin, including Host headers.

Upload only public files, set correct MIME types, and publish index last. Azure's
website endpoint is publicly readable; authentication is enforced at the app's
gateway hostname and by the API, not by Storage. Leave the website's 404 document
unset so missing assets never become SPA HTML. No credentials belong in HTML.

### Document rules

GET/HEAD `/`, `/index.html` and document requests (`Sec-Fetch-Dest: document` or
HTML in `Accept`) use the document rule. The Gateway selects `/index.html` for
these requests; nginx/storage only serves actual files and returns 404 for
missing assets. Every client app is hosted at `/` on its own hostname; there is
no configurable UI base path. Startup, readiness and liveness probes always use
`/` directly on the origin, bypassing the Gateway. The origin must serve
`index.html` at `/`; nested SPA paths remain Gateway-owned.

The static catchall does not perform document authentication or index rewriting.
More-specific API, OAuth and telemetry routes keep their own policy. Both static
origin paths strip app cookies, bearer and identity headers before the backend.

Authentication is optional. Supply the proxy reference directly:

```yaml
auth:
  proxyService: hello-oauth2-proxy
  proxyPort: 80
  mode: api-token
```

The client chart creates `<client-release>-auth` and its own header/auth filters.
It calls the proxy's internal `/` endpoint to start login before URL rewriting.
It forwards no identity credentials to the static server. Backend request filters
strip cookies only after authentication, avoiding duplicate rule filters.
All proxies and app middleware use the fixed host-only `__Host-session` cookie
and its `__Host-session_csrf` login companion. No cookie-name setting is needed.
`proxyPort` defaults to 80; `mode` defaults to api-token and may also be
email-header or login-gate. Static document checks forward no identity in any mode.

The platform release supplies the proxy, credentials and login routes, not app
middleware or policy lists. With `auth: null`, the same SPA routes work publicly.
The chart owns header/cache policies; callers do not supply manual filter lists.
See [application authentication](../../docs/application-auth.md).

### React path-based routing, including nested routes

History routing is framework-agnostic: React Router's `BrowserRouter` or
`createBrowserRouter`, Angular and Vue Router's HTML5 history mode use the same
document rule. No route list is needed in Helm. Direct navigation or refresh at
`/teams/acme/projects/42/settings/members?tab=permissions` serves index HTML while
the browser keeps the original path/query for the client router to resolve.
Trailing slashes and route parameters containing dots are supported too.

For example, React Router can define nested routes normally:

```jsx
<BrowserRouter>
  <Routes>
    <Route path="teams/:teamId">
      <Route path="projects/:projectId/settings/members" element={<Members />} />
    </Route>
  </Routes>
</BrowserRouter>
```

Bundle URLs must be root-relative or base-aware so refreshing a deep route does
not request assets relative to that route. A root deployment can use Vite's
default `base: '/'`, producing `/assets/...` URLs.

Keep the router and bundler base at `/`, with origin files at `/index.html` and
`/assets/...`. A URL such as `/portal/teams/acme/projects/42` is simply another
nested application route; it still receives `/index.html`.

The shared Gateway regression covers protected and public apps on separate
hostnames, including direct entry, refresh, trailing slashes, query preservation,
dotted parameters, asset loading, cookie isolation and missing-asset 404s.

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

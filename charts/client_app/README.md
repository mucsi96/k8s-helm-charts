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
| `basePath` | Browser URL prefix and origin file prefix | `/` |
| `healthPath` | Static origin path used by startup/readiness/liveness probes | `/` |
| `auth` | Same-namespace proxy reference; creates client-owned document authentication | `null` |
| `routeFilters` | Manual document filters when `auth` is null | `[]` |
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

Authentication is optional. Supply the proxy reference directly:

```yaml
auth:
  proxyService: hello-oauth2-proxy
  proxyPort: 80
  cookieName: __Host-hello-oauth2-proxy
  mode: api-token
```

The client chart creates `<client-release>-auth` and its own header/auth filters.
It calls the proxy's internal `/` endpoint to start login before URL rewriting.
It forwards no identity credentials to the static server. Backend request filters
strip cookies only after authentication, avoiding duplicate rule filters.
The cookie name must match the proxy so refresh/clear cookies propagate correctly.
`proxyPort` defaults to 80; `mode` defaults to api-token and may also be
email-header or login-gate. Static document checks forward no identity in any mode.

The platform release supplies the proxy, credentials and login routes, not app
middleware or policy lists. With `auth: null`, the same SPA routes work publicly.
For manual configurations, `routeFilters` remains available; do not combine it
with `auth`. See [application authentication](../../docs/application-auth.md).

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

For an app hosted at `/portal`, set chart `basePath: /portal`, React Router
`basename="/portal"` (or the equivalent `createBrowserRouter` option), and the
bundler asset base to `/portal/`. Host the build files under that same origin
prefix: `/portal/index.html` and `/portal/assets/...`. Nested navigation at
`/portal/teams/acme/projects/42/settings/members` then uses that app's index and
assets. Paths outside the prefix are not captured by this client route.

The shared Gateway regression covers protected root history routes and public
prefixed history routes, including direct entry, refresh, trailing slashes,
query preservation, dotted parameters, asset loading and missing-asset 404s.

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

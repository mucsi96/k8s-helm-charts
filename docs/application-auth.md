# Application-owned authentication

The platform owns oauth2-proxy and login configuration. Each client/API chart
owns the Middleware and HTTPRoute policies that use it. Deployment supplies a
small non-secret proxy reference, not generated Gateway filters:

```yaml
auth:
  proxyService: hello-oauth2-proxy
  proxyPort: 80
  cookieName: __Host-hello-oauth2-proxy
  mode: api-token
```

Supported by `client-app`, `spring-app`, `go-app`, `node-app` and `rust-app`.
The Service must be in the app release namespace. `proxyPort` defaults to 80;
`mode` defaults to api-token and must match the platform proxy configuration.
`proxyService` and `cookieName` are required. `auth: null` creates no auth
Middleware and leaves the route public. An incomplete auth object fails rendering.

| Chart | Internal proxy check | No session | Forwarded identity |
| --- | --- | --- | --- |
| Client | `/` | Browser login | None; static origin receives no app credentials |
| API | `/oauth2/auth` | 401/403, no redirect | Access token (`api-token`), verified email (`email-header`), or none (`login-gate`) |

Each release creates `<release>-auth`. The route removes caller-supplied identity
before checking the session. The API preserves ordinary application cookies and
forwards the verified identity to its backend. The client strips cookies and
identity only after document authentication. Both propagate the configured
session cookie and its `_csrf` companion, and strip credential response headers.
An outer response policy also prevents caching authentication failures.

Backend JWT issuer/audience/scope/role checks and mutation CSRF protection remain
mandatory for API-token applications. Do not expose the private auth endpoints.
The proxy release owns only its exact public OAuth/control/asset routes and any
configured exact session-gate exclusions.

`routeFilters` remains an escape hatch for manual/legacy routes when `auth` is
null. Setting both is rejected, preventing ambiguous order or repeated filters.
Platform-managed service UIs outside these charts must own equivalent document
middleware themselves; backend charts intentionally perform API checks.

## Upgrade order from policy-exporting proxy charts

This proxy-chart update removes its old application Middleware and policy
ConfigMap. Before upgrading an existing proxy release, deploy every consuming
client/API chart with `auth` and clear its old `routeFilters`. The new app charts
can use an existing chart-5 proxy: its Service, endpoints and cookie contract
are unchanged. Then remove the old proxy-owned policy resources by upgrading
the proxy release. Never leave live app routes referencing deleted middleware.

The Terraform/deploy handoff must publish the reference shown above, rather than
read a policy ConfigMap. Verify namespace-scoped `traefik.io/middlewares` write
permissions for application deployment. Keep unconverted apps on their current
proxy/module releases until their deployment scripts and routes are ready.

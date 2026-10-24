# Application-owned authentication

Implementation is shared through the `app-common` Helm library: auth validation,
Middleware, header policies and the backend HTTPRoute have one source. The
library is bundled in each app package and does not change resource ownership.

The platform owns oauth2-proxy and login configuration. Each client/API chart
owns the Middleware and HTTPRoute policies that use it. Deployment supplies a
small non-secret proxy reference, not generated Gateway filters:

```yaml
auth:
  proxyService: hello-oauth2-proxy
  proxyPort: 80
  mode: api-token
```

Supported by `client-app`, `static-client-app`, `spring-app`, `go-app`, `node-app` and `rust-app`.
The Service must be in the app release namespace. `proxyPort` defaults to 80;
`mode` defaults to api-token and must match the platform proxy configuration.
Only `proxyService` is required. `auth: null` creates no auth
Middleware and leaves the route public. An incomplete auth object fails rendering.

| Chart | Internal proxy check | No session | Forwarded identity |
| --- | --- | --- | --- |
| Client | `/` | Browser login | None; static origin receives no app credentials |
| API | `/oauth2/auth` | 401/403, no redirect | Access token (`api-token`), verified email (`email-header`), or none (`login-gate`) |

Each release creates `<release>-auth`. The route removes caller-supplied identity
before checking the session. The API preserves ordinary application cookies and
forwards the verified identity to its backend. The client strips cookies and
identity only after document authentication. Both propagate `__Host-session`
and `__Host-session_csrf`, and strip credential response headers.
An outer response policy also prevents caching authentication failures.

The cookie name is fixed across apps. Secure, HttpOnly, Path=/ and no Domain
attribute keep each cookie scoped to its own hostname. This is a separate session
per app, not shared sign-in state. Keep registrations and cookie secrets per-app.
Client apps always use `/`; nested routes rewrite to `/index.html`. Backend
charts retain their API `basePath`, such as `/api`.

Backend JWT issuer/audience/scope/role checks and mutation CSRF protection remain
mandatory for API-token applications. Do not expose the private auth endpoints.
The proxy release owns only its exact public OAuth/control/asset routes and any
configured exact session-gate exclusions.

There is one authentication input: `auth`. The charts own their header/cache
policies; there is no manual filter-list option. A nonempty legacy `routeFilters`
value fails rendering even with `auth: null`, so an old authentication policy
cannot be silently ignored and expose a route.
Platform-managed service UIs outside these charts must own equivalent document
middleware themselves; backend charts intentionally perform API checks.

## Upgrade order from policy-exporting proxy charts

This proxy-chart update removes its old application Middleware and policy
ConfigMap. Before upgrading an existing proxy release, deploy every consuming
client/API chart with `auth` and discard old Helm values containing `routeFilters`
(for example, `--reset-values` while supplying the complete intended app values).
First configure the
existing chart-5 proxy with `global.forwardAuth.cookieName: __Host-session`.
Its Service/endpoints remain the same; changing the name starts a new login
session. The pending Terraform module supplies this value for the staged cutover.
The new proxy chart fixes the name and only accepts that same value if supplied
by an older module; there is no configurable cookie-name deployment handoff.
Then remove the old proxy-owned policy resources by upgrading
the proxy release. Never leave live app routes referencing deleted middleware.

The Terraform/deploy handoff must publish the reference shown above, rather than
read a policy ConfigMap. Verify namespace-scoped `traefik.io/middlewares` write
permissions for application deployment. Keep unconverted apps on their current
proxy/module releases until their deployment scripts and routes are ready.

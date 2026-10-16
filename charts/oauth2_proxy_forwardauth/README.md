# oauth2-proxy-forwardauth

One stock oauth2-proxy per application or protected service, with Redis sessions,
standard Gateway API HTTPRoutes/header filters and same-namespace ForwardAuth
extensions. The upstream chart is a pinned dependency, not a fork.
Requires Gateway API and Traefik's Kubernetes CRD provider.

```yaml
global:
  forwardAuth:
    host: hello.example.test
    issuerURL: https://login.microsoftonline.com/TENANT_ID/v2.0
    credentialsSecret: hello-oidc
    mode: api-token
    apiScope: api://HELLO_API_CLIENT_ID/api-access
    trustedProxyCIDRs: [10.42.0.0/16]
oauth2-proxy:
  sessionStorage:
    redis:
      existingSecret: hello-redis
      standalone:
        connectionUrl: redis://redis.redis.svc.cluster.local:6379
```

The credentials Secret has `client-id`, `client-secret`, and `cookie-secret`.
The Redis Secret has `redis-password` (override upstream `passwordKey` if needed).
Use a distinct, persisted cookie secret for every application. Secrets and the
confidential Entra Web registration are provisioned outside this chart. Web app
assignment must be required; the proxy deliberately permits any authenticated
email and relies on Entra assignment and downstream API roles for authorization.
API/login-gate modes use Entra's `preferred_username` for the proxy's required
email slot, with `sub` as user ID; this avoids a Graph user-info lookup using an
API access token when the optional email claim is absent. Email-header mode
uses the actual `email` claim for Grafana. Neither email nor UPN decides API roles.
The cookie defaults to `__Host-<release>`, Secure, HttpOnly and SameSite=Lax.
Default refresh/expiry are `5m`/`168h`; refresh must be below access-token lifetime.

Install the auth release through platform Terraform. It publishes non-secret JSON
HTTPRoute filter lists in `<auth-release>-route-filters`. `api-token` mode emits
only `api`; static frontend routes remain public. `email-header` and `login-gate`
also emit `document`, allowing Terraform-owned services such as Grafana to
protect both their UI and API routes.

The ForwardAuth Terraform module reads those policies. App modules pass its
consumed output to `setup_app_base`, which publishes `forward-auth-config` in
the app's Azure Key Vault with scoped deployment read permission. Deploy jobs
read AKV and pass the API list to the backend chart's generic `routeFilters` value:

```bash
AUTH_CONFIG=$(az keyvault secret show --vault-name p07-hello --name forward-auth-config --query value -o tsv)
API_FILTERS=$(jq -ce '.route_filters.api' <<<"$AUTH_CONFIG")
helm upgrade hello-server mucsi96/spring-app --set-json routeFilters="$API_FILTERS" # plus app values
```

Each policy contains, in order, `RequestHeaderModifier` (remove untrusted identity),
one `ExtensionRef` (authenticate), and `ResponseHeaderModifier` (cache/header
policy). OAuth and machine routes use standard response-header filters directly.
The chart creates no custom Headers or Chain resources.

For protected service UIs, the document authenticator starts login through a
static-202 upstream. The API authenticator uses internal `/oauth2/auth` and
returns 401/403 without an error-page redirect. API tokens are forwarded only
on API routes; frontend static servers do not receive them. Preserve ordinary
application cookies.

Supported `mode` values:

| Mode | API scope | Verified header |
| --- | --- | --- |
| `api-token` | Required, one `api://.../api-access` scope | `Authorization: Bearer <access_token>` on API routes |
| `email-header` | Empty | `X-Auth-Request-Email` on both authenticators (Grafana) |
| `login-gate` | Empty | No identity credentials |

### Upgrade from 2.0.0

Existing API-app consumers must remove document filters from their frontend
HTTPRoutes and deploy server-driven bootstrap before upgrading this auth release.
The upgrade removes their document Middleware/policy and public sign-out/userinfo
routes. Keep the existing chart pin during the consumer cutover, then advance it
to the newly published release. Protected service modes retain both policies.

API-app mode exposes exact `/oauth2/start`, `/oauth2/callback` and
`/oauth2/sign_in` control endpoints. Service modes also support the stock
`/oauth2/sign_out` and `/oauth2/userinfo` handlers. Never expose
`/oauth2/auth` or the static-202 root directly: they can carry bearer credentials
in response headers. `/userinfo` is token-free; `/sign_out` is local app logout,
not Entra-wide logout. A protected document can immediately restart Entra SSO.
These handlers are provided by stock oauth2-proxy. The app server's bootstrap
response selects `/oauth2/start` when a session is needed; the generic frontend
loader follows the redirect instruction. Entra redirects to `/oauth2/callback`,
registered by Terraform. The chart's `oauth-route.yaml` forwards those requests through
Traefik to the proxy. The SPAs contain no auth UI, OAuth/session logic, userinfo
requests or logout feature. Protected service UIs use document ForwardAuth to
start login without application-specific client code.

**Application mutations require Origin or CSRF-token protection.** OAuth callback
CSRF validation does not protect application POST/PUT/DELETE requests. SameSite
and CORS do not isolate sibling apps. Preserve separately authenticated machine
endpoints using explicit platform routes and keep backend JWT/role validation.

Optional `machineRoutes` entries contain `path`, `method`, `service` and `port`.
They create exact host/path/method routes directly to that same-namespace API,
preserving its caller bearer token. Use only for independently authenticated
machine endpoints; their backend must reject a browser cookie alone.

```bash
helm repo add oauth2-proxy https://oauth2-proxy.github.io/manifests
helm dependency build charts/oauth2_proxy_forwardauth
python3 scripts/check_forwardauth.py
```

`global.forwardAuth` is shared with the dependency so generated legacy/alpha
configuration has one source of truth. Configure ordinary runtime resources,
scheduling and Redis Secret references under `oauth2-proxy`. Do not replace its
generated configuration or enable a second upstream public route.

## Standard API support

Gateway API v1.6.3 defines `ExternalAuth` in its experimental channel. Traefik
v3.7.13/v3.7.14 does not implement that HTTPRoute filter, and p07's v1.6.1
standard-channel CRDs do not expose it. The ForwardAuth Middleware CRDs are
therefore the remaining implementation-specific part; routing, header policies,
Services and ConfigMaps use standard APIs.

- [GEP-1494 status](https://gateway-api.sigs.k8s.io/geps/gep-1494/)
- [Traefik v3.7.14 filter switch](https://github.com/traefik/traefik/blob/v3.7.14/pkg/provider/kubernetes/gateway/httproute.go#L406-L479)

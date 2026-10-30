# Client App

Container-hosted SPA with chart-owned document routing and optional authentication.
For external HTTPS storage use [static-client-app](../static_client_app/README.md).
Both charts share routing and authentication through `app-common`.

| Value | Default |
| --- | --- |
| `image`, `host` | Required container image and application hostname |
| `appPort` | `8000` |
| `auth` | `null` (public); otherwise same-namespace proxy reference |
| `gateway` | `traefik` / `traefik` / `websecure` |
| `resources.requests` | `20Mi` memory, `20m` CPU |
| `resources.limits` | `100Mi` memory, `500m` CPU |

```yaml
auth:
  proxyService: hello-oauth2-proxy
  proxyPort: 80
  mode: api-token
```

The gateway authenticates document requests before rewriting their URL to
`/index.html`. Deep links retain their path/query in the browser. Serve actual
files at the origin, with `/` returning index for probes; missing assets return
404. Keep the router/bundler base at `/` and asset URLs root-relative.

Document bodies pass through unchanged. Build public configuration into the
client. Documents use no-store, no-referrer and nosniff; assets remain public.
Cookies and identity headers are stripped before reaching the static server.
API, OAuth and same-origin telemetry routes retain their separate policies.

See [application authentication](../../docs/application-auth.md). For local chart
development run `python3 scripts/build_app_dependencies.py` first.

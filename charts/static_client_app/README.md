# Static Client App

Authenticated SPA documents from an external HTTPS origin, without a client
Deployment. Configuration belongs in the build; document bodies are not rewritten.

```bash
helm install hello-client mucsi96/static-client-app \
  --namespace hello \
  --set host=hello.example.com \
  --set staticOrigin=example.z1.web.core.windows.net \
  --set auth.proxyService=hello-oauth2-proxy
```

| Value | Default |
| --- | --- |
| `host` | Required application hostname |
| `staticOrigin` | Required HTTPS origin hostname, without scheme/path |
| `auth` | `null` (public); otherwise same-namespace proxy reference |
| `contentSecurityPolicy` | `null` |
| `gateway` | `traefik` / `traefik` / `websecure` |

The gateway authenticates before rewriting deep links to `/index.html`, strips
credentials, verifies origin TLS and sets no-store, no-referrer and nosniff.
The API retains its own authorization. Use `--reset-values` when upgrading.

Assets load directly from public Blob URLs with `crossorigin="anonymous"` and
app-origin CORS. Keep navigation, APIs and telemetry on the app origin. Upload
assets before index and retain old bundles. Storage contains public build files.

Requires Traefik's CRD provider with `allowExternalNameServices` and deployer
permissions for Middleware/TraefikService. ExternalName-backed TraefikService
provides HTTPS origin access; the chart has no asset catchall.

Checks: `scripts/build_app_dependencies.py`, `scripts/check_forwardauth.py` and
`scripts/check_static_spa_frontend.py` (real Traefik/auth/TLS integration).

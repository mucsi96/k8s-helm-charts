# Static Client App Helm Chart

Hosts a SPA from an external HTTPS static website, including Azure Storage, with
no client Deployment, environment Secret, image, resource requests or probes.
The chart owns only the app's routing resources and middleware. SPA routing,
document authentication and inline runtime config reuse the `app-common` library
used by `client-app`; they are not separate implementations.

## Installation and migration

```bash
helm upgrade --install hello-client mucsi96/static-client-app \
  --namespace hello --reset-values \
  --set host=hello.example.com \
  --set staticOrigin=example.z1.web.core.windows.net \
  --set auth.proxyService=hello-oauth2-proxy \
  --set runtimeConfig.clientAppName=hello-client \
  --set runtimeConfig.clientLogUrl=https://hello.example.com/_telemetry/collect
```

When replacing `client-app`, retain the release name and use `--reset-values`.
Helm removes its Deployment/environment Secret, changes the Service to
ExternalName, and retains the route and middleware names. No uninstall is needed.
Storage provisioning and artifact uploads remain outside this chart. Publish
index last and retain old bundles for open browser tabs.

| Parameter | Description | Default |
|-----------|-------------|---------|
| `host` | Application hostname | required |
| `staticOrigin` | Storage `primary_web_host`, without scheme or path | required |
| `auth` | Same-namespace proxy reference, as in client-app | `null` |
| `runtimeConfig` | Public string values injected into index HTML | `{}` |
| `gateway` | Gateway name, namespace and section | `traefik`, `traefik`, `websecure` |

The document/asset matching, deep-link rewriting, session and HTML marker contracts
are shared with [client-app](../client_app/README.md). Missing files must return
404: leave Azure's error document unset. Only public build files belong in storage;
Azure's website endpoint is anonymously readable even though the app hostname
authenticates document requests. The API retains its own authorization.

## Gateway API and Traefik

Validated with **Traefik 3.7.16**, which supports **Gateway API 1.6.3**. The chart uses
`gateway.networking.k8s.io/v1` HTTPRoute with native match rules, URLRewrite (path
and storage hostname), and request/response header filters. Document rewrites run
after ForwardAuth so login returns to the original application URL.

Traefik 3.7.16 still rejects direct ExternalName Service references in HTTPRoute.
The route therefore references a same-namespace TraefikService, backed by an
ExternalName Service, for DNS resolution and HTTPS on port 443 with normal TLS
certificate verification. Native URLRewrite sets the storage Host header.
BackendTLSPolicy cannot remove this limitation for an external DNS origin.

Enable `providers.kubernetesCRD.allowExternalNameServices` and grant the deploy
identity namespace-scoped TraefikService permissions. Traefik also ignores backend
filters on TraefikService references: document cookie/conditional/range stripping
uses a route-level Middleware after ForwardAuth. ForwardAuth and response-body
config injection use the shared Traefik middleware integration as before.

An upgrade from 3.7.13 to 3.7.16 brings Gateway routing/security fixes, but does not
remove the need for these extensions. Coordinate controller upgrades with the
platform's k3s-owned Traefik release; installing this chart does not upgrade it.

## Development

Run `python3 scripts/build_app_dependencies.py`, then
`python3 scripts/check_static_frontend.py`. The shared suite tests
real Traefik, proxy login, TLS/Host handling, deep links, missing assets, config
injection, credential stripping, API isolation and telemetry. Run
`python3 scripts/check_spa_frontend.py` to check the container-hosted chart with
the same assertions.

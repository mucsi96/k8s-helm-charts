# app-common

Helm **library chart** used by container/static client, Spring, Go, Node and Rust charts. It renders
no resources independently and requires no cluster release. Each application
release still owns the resources produced by these helpers.

- `app-common.auth.middleware`: auth reference validation, fixed session cookie handling,
  document/API endpoints and mode-specific identity forwarding.
- `app-common.auth.requestFilters`: caller identity stripping and middleware reference.
- `app-common.auth.apiFilters`: API cache/header policy plus the request filters.
- `app-common.api.route`: common backend HTTPRoute, with optional proxy-based auth.
- `app-common.client.route`: shared SPA document HTTPRoute and header policy; container clients also include an asset catchall.
- `app-common.client.backend`: container Service or external TraefikService reference.
- `app-common.client.runtimeConfig`: public inline HTML bootstrap configuration injection.

Charts own their authentication and header policies. Both client charts use the same SPA/config
and authentication helpers. Origin-specific resources remain in their charts.

SPA document responses always set `Referrer-Policy: no-referrer` and
`X-Content-Type-Options: nosniff`. Both client charts accept an application-specific
`contentSecurityPolicy`; all other document headers are fixed.

## Dependencies and releases

Consumer Chart.yaml files pin this library using `file://../../libraries/app_common`.
Run `python3 scripts/build_app_dependencies.py` after checkout or library edits.
The dependency is bundled inside each published app chart, so installing an app
does not require this repository or another chart repository/release.

When changing templates, bump this library's semantic version and update all six
consumer dependency versions. Regenerate their locks with
`helm dependency update --skip-refresh charts/<chart>` for each consumer.
Their Chart.yaml changes trigger the
existing numbered app releases. CI checks matching versions and rejects library
template changes without a version bump relative to the PR/push base.

Run `python3 scripts/check_app_common.py` to validate dependencies and packaged
chart rendering. `--compare-ref <commit>` additionally compares representative
rendered manifests with a previous revision, useful for behavior-preserving
refactors.

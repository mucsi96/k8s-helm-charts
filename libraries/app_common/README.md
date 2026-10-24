# app-common

Helm **library chart** used by container/static client, Spring, Go, Node and Rust charts. It renders
no resources independently and requires no cluster release. Each application
release still owns the resources produced by these helpers.

- `p07.auth.middleware`: auth reference validation, fixed session cookie handling,
  document/API endpoints and mode-specific identity forwarding.
- `p07.auth.requestFilters`: caller identity stripping and middleware reference.
- `p07.auth.apiFilters`: API cache/header policy plus the request filters.
- `p07.api.route`: common backend HTTPRoute, with optional proxy-based auth.
- `p07.client.route`: shared document/static HTTPRoute, SPA rewriting and header policy.
- `p07.client.backend`: container Service or external TraefikService reference.
- `p07.client.runtimeConfig`: public inline HTML bootstrap configuration injection.

Nonempty legacy filter lists are rejected; charts own the policies instead of
accepting caller-authored Gateway filters. Both client charts use the same SPA/config
and authentication helpers. Origin-specific resources remain in their charts.

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

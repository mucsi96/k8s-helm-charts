"""Render the routing trust boundary, token modes and legacy app chart contract."""
import base64
import copy
import json
from pathlib import Path
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[1]
invalid_configurations_rejected = 0
VALUES = {
    "global": {"forwardAuth": {
        "host": "hello.example.test", "issuerURL": "https://login.example.test/tenant/v2.0",
        "credentialsSecret": "hello-oidc", "apiScope": "api://hello-api/api-access",
        "trustedProxyCIDRs": ["10.42.0.0/16"],
    }},
    "oauth2-proxy": {"sessionStorage": {"redis": {
        "existingSecret": "hello-redis", "standalone": {"connectionUrl": "redis://redis.redis.svc.cluster.local:6379"},
    }}},
}


def render(chart, values, success=True):
    global invalid_configurations_rejected
    result = subprocess.run(
        ["helm", "template", "hello-oauth2-proxy", str(ROOT / "charts" / chart), "--namespace", "hello", "-f", "-"],
        input=yaml.safe_dump(values), text=True, capture_output=True,
    )
    if not success:
        assert result.returncode != 0, "invalid authentication configuration rendered successfully"
        invalid_configurations_rejected += 1
        return []
    assert result.returncode == 0, result.stderr
    return [resource for resource in yaml.safe_load_all(result.stdout) if resource]


def resource(resources, kind, suffix):
    return next(item for item in resources if item["kind"] == kind and item["metadata"]["name"].endswith(suffix))


for mode in ["api-token", "email-header", "login-gate"]:
    values = copy.deepcopy(VALUES)
    values["global"]["forwardAuth"].update(mode=mode, apiScope="api://hello-api/api-access" if mode == "api-token" else "")
    resources = render("oauth2_proxy_forwardauth", values)
    assert not any(item["kind"] == "HTTPRoute" and item["metadata"]["name"].endswith("-excluded-routes") for item in resources)
    alpha = yaml.safe_load(base64.b64decode(resource(resources, "Secret", "-alpha")["data"]["oauth2_proxy.yml"]))
    provider = alpha["providers"][0]
    assert provider["code_challenge_method"] == "S256"
    assert provider["oidcConfig"]["insecureSkipNonce"] is False
    assert provider["oidcConfig"]["emailClaim"] == ("email" if mode == "email-header" else "preferred_username")
    assert provider["oidcConfig"]["userIDClaim"] == "sub"
    assert provider["skipClaimsFromProfileURL"] == (mode != "email-header")
    assert "User.Read" not in provider["scope"]
    assert ("api://hello-api/api-access" in provider["scope"]) == (mode == "api-token")
    injected = alpha.get("injectResponseHeaders", [])
    assert len(injected) == (0 if mode == "login-gate" else 1)
    if injected:
        assert injected[0]["values"][0]["claimSource"]["claim"] == ("access_token" if mode == "api-token" else "email")
    assert alpha["upstreamConfig"]["upstreams"] == [{"id": "forwardauth", "path": "/", "static": True, "staticCode": 202}]
    config = resource(resources, "ConfigMap", "oauth2-proxy")["data"]["oauth2_proxy.cfg"]
    assert 'cookie_name = "__Host-session"' in config
    assert 'cookie_path = "/"' in config and 'cookie_secure = true' in config and 'cookie_httponly = true' in config
    assert "cookie_domains" not in config
    assert 'trusted_proxy_ips = ["10.42.0.0/16"]' in config
    route = resource(resources, "HTTPRoute", "-oauth")
    paths = route["spec"]["rules"][0]["matches"]
    control_paths = [match for match in paths if match["path"]["type"] == "Exact"]
    asset_paths = [match for match in paths if match["path"]["type"] == "PathPrefix"]
    public_paths = ["start", "callback", "sign_in", "sign_out", "userinfo"]
    assert {match["path"]["value"] for match in control_paths} == {f"/oauth2/{path}" for path in public_paths}
    assert asset_paths == [{"path": {"type": "PathPrefix", "value": "/oauth2/static"}, "method": method} for method in ["GET", "HEAD"]]
    assert len(paths) == len(control_paths) + len(asset_paths) == 7
    assert [item["type"] for item in route["spec"]["rules"][0]["filters"]] == ["ResponseHeaderModifier"]
    assert not any(item["apiVersion"].startswith("traefik.io/") for item in resources)
    assert not any(item["metadata"]["name"].endswith("-route-filters") for item in resources)
    deployment = resource(resources, "Deployment", "oauth2-proxy")
    env = deployment["spec"]["template"]["spec"]["containers"][0]["env"]
    secret_env = {item["name"]: item.get("valueFrom", {}) for item in env}
    assert secret_env["OAUTH2_PROXY_CLIENT_SECRET"]["secretKeyRef"]["name"] == "hello-oidc"
    assert secret_env["OAUTH2_PROXY_REDIS_PASSWORD"]["secretKeyRef"]["name"] == "hello-redis"
    assert not any(item["kind"] == "NetworkPolicy" for item in resources)

for path, value in [
    (("global", "forwardAuth", "apiScope"), ""),
    (("global", "forwardAuth", "credentialsSecret"), ""),
    (("global", "forwardAuth", "trustedProxyCIDRs"), []),
    (("oauth2-proxy", "sessionStorage", "redis", "existingSecret"), ""),
    (("oauth2-proxy", "gatewayApi", "enabled"), True),
]:
    values = copy.deepcopy(VALUES)
    target = values
    for key in path[:-1]:
        target = target.setdefault(key, {})
    target[path[-1]] = value
    render("oauth2_proxy_forwardauth", values, success=False)

for mode in ["api-token", "email-header", "login-gate"]:
    values = copy.deepcopy(VALUES)
    values["global"]["forwardAuth"].update(host="bootstrap.example.test", mode=mode, apiScope="api://hello-api/api-access" if mode == "api-token" else "")
    values["gateway"] = {"name": "shared-gateway", "namespace": "ingress", "sectionName": "https"}
    values["excludedRoutes"] = [
        {"path": "/api/environment", "method": "GET", "service": "cooking-server", "port": 8080},
        {"path": "/api/integrations/recipes/import", "method": "POST", "service": "cooking-server", "port": 8080},
        {"path": "/healthz", "method": "GET", "service": "other-service", "port": 9090},
    ]
    resources = render("oauth2_proxy_forwardauth", values)
    excluded = resource(resources, "HTTPRoute", "-excluded-routes")
    assert excluded["metadata"] == {"name": "hello-oauth2-proxy-excluded-routes", "namespace": "hello"}
    assert excluded["spec"]["hostnames"] == ["bootstrap.example.test"]
    assert excluded["spec"]["parentRefs"] == [{"name": "shared-gateway", "namespace": "ingress", "sectionName": "https"}]
    assert len(excluded["spec"]["rules"]) == 3
    assert len([item for item in resources if item["kind"] == "HTTPRoute" and not item["metadata"]["name"].endswith("-oauth")]) == 1
    for rule, supplied in zip(excluded["spec"]["rules"], values["excludedRoutes"]):
        assert rule["matches"] == [{"path": {"type": "Exact", "value": supplied["path"]}, "method": supplied["method"]}]
        assert rule["backendRefs"] == [{"name": supplied["service"], "port": supplied["port"]}]
        assert rule["filters"] == [{"type": "ResponseHeaderModifier", "responseHeaderModifier": {
            "set": [{"name": "Cache-Control", "value": "no-store"}],
            "remove": ["Authorization", "X-Auth-Request-Access-Token"],
        }}]

for field, invalid in [("path", "/oauth2/auth"), ("path", "api/environment"), ("path", "/api/environment?token=bad"), ("service", ""), ("port", 0), ("method", "*")]:
    values = copy.deepcopy(VALUES)
    values["excludedRoutes"] = [{"path": "/api/environment", "method": "GET", "service": "hello-server", "port": 8080, field: invalid}]
    render("oauth2_proxy_forwardauth", values, success=False)
for missing in ["service", "method"]:
    values = copy.deepcopy(VALUES)
    route = {"path": "/api/environment", "method": "GET", "service": "hello-server", "port": 8080}
    del route[missing]
    values["excludedRoutes"] = [route]
    render("oauth2_proxy_forwardauth", values, success=False)

for chart in ["spring_app", "go_app", "node_app", "rust_app"]:
    values = {"image": "example/app:1", "host": "hello.example.test", "serviceAccountName": "hello-api", "clientId": "example-client"}
    before = resource(render(chart, values), "HTTPRoute", "-route")
    assert "filters" not in before["spec"]["rules"][0]

AUTH = {"proxyService": "platform-proxy", "proxyPort": 80}
for chart in ["client_app", "spring_app", "go_app", "node_app", "rust_app"]:
    for mode in ["api-token", "email-header", "login-gate"]:
        values = {"image": "example/app:1", "host": "hello.example.test", "serviceAccountName": "hello-api", "clientId": "example-client", "auth": {**AUTH, "mode": mode}}
        resources = render(chart, values)
        middleware = resource(resources, "Middleware", "-auth")["spec"]["forwardAuth"]
        document = chart == "client_app"
        assert middleware["address"] == "http://platform-proxy.hello.svc.cluster.local:80/" + ("" if document else "oauth2/auth")
        assert middleware["forwardBody"] is False and middleware["trustForwardHeader"] is False
        assert "Authorization" not in middleware["authRequestHeaders"]
        expected = [] if document or mode == "login-gate" else ["Authorization"] if mode == "api-token" else ["X-Auth-Request-Email"]
        assert middleware["authResponseHeaders"] == expected
        assert middleware["addAuthCookiesToResponse"] == ["__Host-session", "__Host-session_csrf"]
        filters = resource(resources, "HTTPRoute", "-route")["spec"]["rules"][0]["filters"]
        assert [item["type"] for item in filters[:3]] == ["ResponseHeaderModifier", "RequestHeaderModifier", "ExtensionRef"]
        assert filters[2]["extensionRef"]["name"] == "hello-oauth2-proxy-auth"
        assert "Authorization" in filters[1]["requestHeaderModifier"]["remove"] and "Cookie" not in filters[1]["requestHeaderModifier"]["remove"]
        if not document:
            assert filters[0]["responseHeaderModifier"]["set"] == [{"name": "Cache-Control", "value": "no-store"}]
    for invalid in [{}, {"proxyPort": 80}, {**AUTH, "proxyService": "https://external.test"}, {**AUTH, "cookieName": "insecure"}, {**AUTH, "proxyPort": 0}, {**AUTH, "proxyPort": 65536}, {**AUTH, "proxyPort": 80.5}, {**AUTH, "mode": "unknown"}]:
        render(chart, {**values, "auth": invalid}, success=False)
    render(chart, {**values, "routeFilters": [{"type": "ExtensionRef"}]}, success=False)
    render(chart, {**values, "auth": None, "routeFilters": [{"type": "ExtensionRef"}]}, success=False)

for mode in ["api-token", "email-header", "login-gate"]:
    client_values = {"image": "example/client:1", "host": "hello.example.test", "auth": {**AUTH, "mode": mode}, "runtimeConfig": {
        "clientLogUrl": "https://hello.example.test/_telemetry/collect", "clientAppName": "fixture-$1-</script>",
    }}
    client = render("client_app", client_values)
    document = resource(client, "Middleware", "-auth")["spec"]["forwardAuth"]
    assert document["address"].endswith(":80/") and document["preserveLocationHeader"] is True
    route = resource(client, "HTTPRoute", "-route")["spec"]
    index, assets = route["rules"]
    assert len(index["matches"]) == 8
    assert all(match["method"] in {"GET", "HEAD"} for match in index["matches"])
    assert [item["type"] for item in index["filters"]] == ["ResponseHeaderModifier", "RequestHeaderModifier", "ExtensionRef", "ExtensionRef", "URLRewrite"]
    assert index["filters"][2]["extensionRef"]["name"] == "hello-oauth2-proxy-auth"
    cache = index["filters"][0]["responseHeaderModifier"]
    assert cache["set"] == [{"name": "Cache-Control", "value": "private, no-cache, no-store"}]
    assert "Authorization" in cache["remove"] and "ETag" in cache["remove"]
    origin = index["backendRefs"][0]
    headers = origin["filters"][0]["requestHeaderModifier"]
    assert "Cookie" in headers["remove"] and "If-None-Match" in headers["remove"]
    assert headers["set"] == [{"name": "Accept-Encoding", "value": "identity"}]
    assert index["filters"][-1]["urlRewrite"]["path"] == {"type": "ReplaceFullPath", "replaceFullPath": "/index.html"}
    assert {key: value for key, value in origin.items() if key != "filters"} == assets["backendRefs"][0] == {"name": "hello-oauth2-proxy", "port": 8000}
    assert assets["matches"] == [{"path": {"type": "PathPrefix", "value": "/"}}]
    assert not any(item["type"] in {"ExtensionRef", "URLRewrite"} for item in assets["filters"])
    middleware = resource(client, "Middleware", "-index-config")["spec"]["plugin"]["rewritebody"]
    replacement = middleware["rewrites"][0]["replacement"]
    assert "</script>" not in replacement and "$$1" in replacement
    assert json.loads(replacement.replace("$$", "$")) == client_values["runtimeConfig"]
    client_values["runtimeConfig"] = {}
    no_config = render("client_app", client_values)
    assert not any(item["kind"] == "Middleware" and item["metadata"]["name"].endswith("-index-config") for item in no_config)

for invalid in [{"runtimeConfig": {"bad": {"nested": True}}}, {"routeFilters": [{"type": "URLRewrite"}]}, {"basePath": "/portal"}]:
    render("client_app", {"image": "example/client:1", "host": "hello.example.test", **invalid}, success=False)

values = {"image": "example/client:1", "host": "hello.example.test"}
resources = render("client_app", values)
route = resource(resources, "HTTPRoute", "-route")["spec"]
assert len(route["rules"]) == 2 and not any(item["type"] == "ExtensionRef" for item in route["rules"][0]["filters"])
assert route["rules"][0]["filters"][-1]["urlRewrite"]["path"]["replaceFullPath"] == "/index.html"
assert not any(item["kind"] == "Middleware" for item in resources)
container = resource(resources, "Deployment", "hello-oauth2-proxy")["spec"]["template"]["spec"]["containers"][0]
assert all(container[probe]["httpGet"]["path"] == f"/?{probe.removesuffix('Probe')}" for probe in ["startupProbe", "readinessProbe", "livenessProbe"])
index = route["rules"][0]
assert {match["path"]["value"] for rule in route["rules"] for match in rule["matches"]} == {"/", "/index.html"}
assert index["filters"][-1]["urlRewrite"]["path"]["replaceFullPath"] == "/index.html"

values = copy.deepcopy(VALUES)
values["global"]["forwardAuth"]["cookieName"] = "__Host-custom"
render("oauth2_proxy_forwardauth", values, success=False)

print(json.dumps({"modes": 3, "invalidConfigurationsRejected": invalid_configurations_rejected, "compatibleAppCharts": 5, "exactForwardAuthExclusions": True, "rootOnlySpa": True, "hostOnlySessionCookie": True, "appOwnedAuth": True, "proxyPolicyResources": 0}))

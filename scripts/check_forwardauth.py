"""Render the routing trust boundary, token modes and legacy app chart contract."""
import base64
import copy
import json
from pathlib import Path
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[1]
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
    result = subprocess.run(
        ["helm", "template", "hello-oauth2-proxy", str(ROOT / "charts" / chart), "--namespace", "hello", "-f", "-"],
        input=yaml.safe_dump(values), text=True, capture_output=True,
    )
    if not success:
        assert result.returncode != 0, "invalid authentication configuration rendered successfully"
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
    assert "User.Read" not in provider["scope"]
    assert ("api://hello-api/api-access" in provider["scope"]) == (mode == "api-token")
    injected = alpha.get("injectResponseHeaders", [])
    assert len(injected) == (0 if mode == "login-gate" else 1)
    if injected:
        assert injected[0]["values"][0]["claimSource"]["claim"] == ("access_token" if mode == "api-token" else "email")
    assert alpha["upstreamConfig"]["upstreams"] == [{"id": "forwardauth", "path": "/", "static": True, "staticCode": 202}]
    config = resource(resources, "ConfigMap", "oauth2-proxy")["data"]["oauth2_proxy.cfg"]
    assert 'cookie_name = "__Host-hello-oauth2-proxy"' in config
    assert "cookie_domains" not in config
    assert 'trusted_proxy_ips = ["10.42.0.0/16"]' in config
    route = resource(resources, "HTTPRoute", "-oauth")
    paths = route["spec"]["rules"][0]["matches"]
    assert all(match["path"]["type"] == "Exact" for match in paths)
    public_paths = ["start", "callback", "sign_in", "sign_out", "userinfo"]
    assert {match["path"]["value"] for match in paths} == {f"/oauth2/{path}" for path in public_paths}
    assert [item["type"] for item in route["spec"]["rules"][0]["filters"]] == ["ResponseHeaderModifier"]
    custom = [item for item in resources if item["apiVersion"].startswith("traefik.io/")]
    targets = ["api"] if mode == "api-token" else ["document", "api"]
    assert len(custom) == len(targets)
    assert all(set(item["spec"]) == {"forwardAuth"} for item in custom)
    route_policies = resource(resources, "ConfigMap", "-route-filters")["data"]
    assert set(route_policies) == set(targets)
    for target in targets:
        middleware = resource(resources, "Middleware", f"-{target}")["spec"]["forwardAuth"]
        assert middleware["forwardBody"] is False
        assert middleware["trustForwardHeader"] is False
        assert "Authorization" not in middleware["authRequestHeaders"]
        expected_headers = ["X-Auth-Request-Email"] if mode == "email-header" else ["Authorization"] if mode == "api-token" and target == "api" else []
        assert middleware["authResponseHeaders"] == expected_headers
        assert middleware["address"].endswith("/oauth2/auth" if target == "api" else ":80/")
        policy = json.loads(route_policies[target])
        assert [item["type"] for item in policy] == ["RequestHeaderModifier", "ExtensionRef", "ResponseHeaderModifier"]
        assert "Authorization" in policy[0]["requestHeaderModifier"]["remove"]
        assert "Cookie" not in policy[0]["requestHeaderModifier"]["remove"]
        assert policy[1]["extensionRef"] == {"group": "traefik.io", "kind": "Middleware", "name": f"hello-oauth2-proxy-{target}"}
        assert policy[2]["responseHeaderModifier"]["set"] == [{"name": "Cache-Control", "value": "no-store" if target == "api" else "private, no-cache"}]
        assert "Authorization" in policy[2]["responseHeaderModifier"]["remove"]
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

for chart in ["client_app", "spring_app", "go_app", "node_app", "rust_app"]:
    values = {"image": "example/app:1", "host": "hello.example.test", "serviceAccountName": "hello-api", "clientId": "example-client"}
    before = resource(render(chart, values), "HTTPRoute", "-route")
    assert "filters" not in before["spec"]["rules"][0]
    values["routeFilters"] = json.loads(route_policies["api"])
    after = resource(render(chart, values), "HTTPRoute", "-route")
    assert after["spec"]["rules"][0]["filters"] == values["routeFilters"]
    del after["spec"]["rules"][0]["filters"]
    assert before == after

print(json.dumps({"modes": 3, "invalidConfigurationsRejected": 13, "compatibleAppCharts": 5, "exactForwardAuthExclusions": True, "apiModeCustomResources": 1, "documentModeCustomResources": 2}))

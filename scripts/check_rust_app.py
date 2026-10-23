"""Verify the Rust runtime, identity, configuration and storage chart contracts."""
import base64
import copy
import json
from pathlib import Path
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[1]
BASE = {"image": "ghcr.io/example/rust-app:1", "host": "rust.example.test"}


def render(values, success=True):
    result = subprocess.run(
        ["helm", "template", "demo-rust", str(ROOT / "charts/rust_app"), "-n", "demo", "-f", "-"],
        input=yaml.safe_dump(values), text=True, capture_output=True,
    )
    if not success:
        assert result.returncode != 0, "invalid Rust configuration rendered successfully"
        return []
    assert result.returncode == 0, result.stderr
    return [item for item in yaml.safe_load_all(result.stdout) if item]


def get(resources, kind, name=None):
    return next(item for item in resources if item["kind"] == kind and (name is None or item["metadata"]["name"] == name))


minimal = render(BASE)
assert {item["kind"] for item in minimal} == {"Deployment", "Service", "ServiceAccount", "HTTPRoute"}
pod = get(minimal, "Deployment")["spec"]["template"]
container = pod["spec"]["containers"][0]
assert pod["spec"]["serviceAccountName"] == "demo-rust"
assert pod["spec"]["automountServiceAccountToken"] is False
assert "azure.workload.identity/use" not in pod["metadata"]["labels"]
assert "lifecycle" not in container and "command" not in container
assert pod["spec"]["securityContext"]["runAsNonRoot"] is True
assert container["securityContext"]["readOnlyRootFilesystem"] is True
assert container["securityContext"]["allowPrivilegeEscalation"] is False
assert container["securityContext"]["capabilities"]["drop"] == ["ALL"]
assert "envFrom" not in container and "volumes" not in pod["spec"]
assert {item["name"]: item.get("value") for item in container["env"]}["LISTEN_ADDR"] == "0.0.0.0:8080"
assert all(container[key]["httpGet"] == {"path": "/healthz", "port": "http"} for key in ["startupProbe", "readinessProbe", "livenessProbe"])
assert get(minimal, "Service")["spec"]["ports"] == [{"name": "http", "port": 8080, "targetPort": "http", "protocol": "TCP"}]
assert "filters" not in get(minimal, "HTTPRoute")["spec"]["rules"][0]

configured = copy.deepcopy(BASE)
configured.update({
    "appPort": 8090, "basePath": "/api", "imagePullSecrets": [{"name": "ghcr-pull"}],
    "health": {"livenessPath": "/live", "readinessPath": "/readyz"},
    "env": {"RUST_LOG": "info", "CONFIG_FILE": "/config/app.json"},
    "configFile": [{"name": "app.json", "mountPath": "/config/app.json", "data": base64.b64encode(b'{"mode":"fixture"}').decode()}],
    "envFrom": [{"secretRef": {"name": "external-runtime"}}],
    "extraVolumes": [{"name": "inventory", "configMap": {"name": "external-config"}}],
    "extraVolumeMounts": [{"name": "inventory", "mountPath": "/inventory", "readOnly": True}],
    "persistentVolumeClaims": [{"name": "retained-data", "mountPath": "/data", "accessMode": "ReadWriteOnce", "storageClassName": "", "volumeName": "existing-rust-pv", "storage": "5Gi"}],
    "auth": {"proxyService": "demo-oauth2-proxy"},
})
resources = render(configured)
pod = get(resources, "Deployment")["spec"]["template"]
container = pod["spec"]["containers"][0]
assert pod["spec"]["imagePullSecrets"] == [{"name": "ghcr-pull"}]
assert {item["name"]: item.get("value") for item in container["env"]}["LISTEN_ADDR"] == "0.0.0.0:8090"
assert container["readinessProbe"]["httpGet"] == {"path": "/readyz", "port": "http"}
assert container["startupProbe"]["httpGet"] == container["readinessProbe"]["httpGet"]
assert container["envFrom"] == [{"secretRef": {"name": "demo-rust-env"}}, {"secretRef": {"name": "external-runtime"}}]
assert get(resources, "Secret", "demo-rust-env")["stringData"]["RUST_LOG"] == "info"
assert get(resources, "Secret", "demo-rust-config-files")["stringData"]["app.json"] == '{"mode":"fixture"}'
assert {"name": "secret-config-files", "mountPath": "/config/app.json", "subPath": "app.json", "readOnly": True} in container["volumeMounts"]
assert {"name": "inventory", "configMap": {"name": "external-config"}} in pod["spec"]["volumes"]
assert get(resources, "PersistentVolumeClaim")["metadata"]["name"] == "retained-data"
assert get(resources, "PersistentVolumeClaim")["spec"]["volumeName"] == "existing-rust-pv"
assert {"name": "pvc-retained-data", "persistentVolumeClaim": {"claimName": "retained-data"}} in pod["spec"]["volumes"]
route = get(resources, "HTTPRoute")["spec"]["rules"][0]
assert route["matches"][0]["path"]["value"] == "/api"
assert route["filters"][0]["responseHeaderModifier"]["set"] == [{"name": "Cache-Control", "value": "no-store"}]
assert route["filters"][2]["extensionRef"]["name"] == "demo-rust-auth"
assert route["backendRefs"] == [{"name": "demo-rust", "port": 8090}]
updated = copy.deepcopy(configured)
updated["env"]["RUST_LOG"] = "debug"
updated["configFile"][0]["data"] = base64.b64encode(b'{"mode":"updated"}').decode()
after = get(render(updated), "Deployment")["spec"]["template"]["metadata"]["annotations"]
for key in ["checksum/secret_env", "checksum/secret_config_files"]:
    assert pod["metadata"]["annotations"][key] != after[key]

identity = copy.deepcopy(BASE)
identity.update({"clientId": "12345678-1234-1234-1234-123456789abc", "serviceAccountName": "rust-workload"})
resources = render(identity)
assert get(resources, "Deployment")["spec"]["template"]["metadata"]["labels"]["azure.workload.identity/use"] == "true"
assert get(resources, "ServiceAccount")["metadata"]["annotations"]["azure.workload.identity/client-id"] == identity["clientId"]
identity.update({"clientId": "", "serviceAccount": {"create": False, "automountServiceAccountToken": True}})
resources = render(identity)
assert not any(item["kind"] == "ServiceAccount" for item in resources)
assert get(resources, "Deployment")["spec"]["template"]["spec"]["serviceAccountName"] == "rust-workload"
assert get(resources, "Deployment")["spec"]["template"]["spec"]["automountServiceAccountToken"] is True

for values in [
    {"host": "rust.example.test"}, {"image": BASE["image"]}, {**BASE, "appPort": 0},
    {**BASE, "serviceAccount": {"create": False}},
    {**BASE, "env": {"LISTEN_ADDR": "127.0.0.1:9999"}},
    {**BASE, "configFile": [{"name": "app.json", "mountPath": "/config/app.json", "data": "not base64"}]},
]:
    render(values, success=False)

print(json.dumps({"distrolessDefaults": True, "standardFilters": True, "configurationRollouts": True,
                  "retainedStorage": True, "optionalAzureIdentity": True, "existingServiceAccount": True,
                  "invalidConfigurationsRejected": 6}))

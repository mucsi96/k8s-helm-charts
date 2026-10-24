"""Exercise rendered index routing/config with real Traefik and stock ForwardAuth."""
import base64
import copy
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import tomllib
from urllib.error import HTTPError
from urllib.parse import urljoin
from urllib.request import build_opener, HTTPCookieProcessor, HTTPRedirectHandler, Request

import yaml
from check_forwardauth_login import free_port, wait_for

ROOT = Path(__file__).resolve().parents[1]


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_):
        return None


def fetch(url, cookies=None, headers=None, data=None, follow=True, method=None):
    handlers = [HTTPCookieProcessor(cookies if cookies is not None else CookieJar())]
    if not follow:
        handlers.append(NoRedirect())
    try:
        response = build_opener(*handlers).open(Request(url, headers=headers or {}, data=data, method=method), timeout=10)
    except HTTPError as error:
        response = error
    return response.status, response.headers, response.read(), response.geturl()


def main(*, external=False):
    ports = set()
    while len(ports) < 6:
        ports.add(free_port())
    issuer_port, proxy_port, origin_port, gateway_port, kubernetes_port, tls_port = sorted(ports)
    public = f'http://localhost:{gateway_port}'
    other_app = f'http://127.0.0.1:{gateway_port}'
    issuer = f'http://localhost:{issuer_port}/default'
    runtime = {'clientLogUrl': f'{public}/_telemetry/collect', 'clientAppName': 'fixture-$1-</script>'}
    values = {
        'global': {'forwardAuth': {'host': 'localhost', 'issuerURL': 'https://issuer.example.test/default',
                                  'credentialsSecret': 'fixture-oidc', 'mode': 'api-token',
                                  'apiScope': 'api://fixture-api/api-access', 'trustedProxyCIDRs': ['127.0.0.1/32']}},
        'gateway': {'name': 'fixture', 'namespace': 'default', 'sectionName': 'web'},
        'oauth2-proxy': {'sessionStorage': {'redis': {'existingSecret': 'fixture-redis', 'standalone': {'connectionUrl': 'redis://127.0.0.1:6379'}}}},
    }
    rendered = subprocess.run(['helm', 'template', 'fixture', str(ROOT / 'charts/oauth2_proxy_forwardauth'), '-f', '-'],
                              input=yaml.safe_dump(values), capture_output=True, text=True, check=True)
    resources = [item for item in yaml.safe_load_all(rendered.stdout) if item]
    get = lambda kind, suffix: next(item for item in resources if item['kind'] == kind and item['metadata']['name'].endswith(suffix))
    client_values = {
        'image': 'example/static-origin:1', 'host': 'localhost', 'appPort': origin_port,
        'gateway': values['gateway'], 'runtimeConfig': runtime,
        'documentResponseHeaders': {'Content-Security-Policy': "default-src 'self'"},
        'auth': {'proxyService': get('Service', 'oauth2-proxy')['metadata']['name'], 'proxyPort': 80},
    }
    public_runtime = {**runtime, 'clientAppName': 'public-fixture'}
    if external:
        client_values.pop('image')
        client_values['staticOrigin'] = 'localhost'
    client_resources = []
    for release, configuration in [
        ('static-origin', client_values),
        ('public-origin', {**client_values, 'host': '127.0.0.1', 'auth': None, 'runtimeConfig': public_runtime}),
    ]:
        chart = 'static_client_app' if external else 'client_app'
        rendered_client = subprocess.run(['helm', 'template', release, str(ROOT / 'charts' / chart), '-f', '-'],
                                         input=yaml.safe_dump(configuration), capture_output=True, text=True, check=True)
        client_resources.extend(item for item in yaml.safe_load_all(rendered_client.stdout) if item)
    if external:
        assert not any(item['kind'] in {'Deployment', 'Secret'} for item in client_resources)
        for item in client_resources:
            if item['kind'] == 'Service':
                assert item['spec']['type'] == 'ExternalName'
                item['spec']['ports'][0]['port'] = tls_port
            if item['kind'] == 'TraefikService':
                service = item['spec']['weighted']['services'][0]
                assert service['scheme'] == 'https' and service['passHostHeader'] is True
                service['port'] = tls_port
    assert not any(item['kind'] == 'HTTPRoute' and item['metadata']['name'].endswith('-frontend') for item in resources)
    rendered_api = subprocess.run(['helm', 'template', 'api-origin', str(ROOT / 'charts/spring_app'), '-f', '-'],
                                 input=yaml.safe_dump({'image': 'example/api:1', 'host': 'localhost', 'appPort': origin_port,
                                                      'basePath': '/api', 'clientId': 'fixture-api', 'auth': client_values['auth']}),
                                 capture_output=True, text=True, check=True)
    api_resources = [item for item in yaml.safe_load_all(rendered_api.stdout) if item and item['kind'] in {'HTTPRoute', 'Middleware'}]
    for item in api_resources:
        if item['kind'] == 'HTTPRoute':
            item['spec']['parentRefs'] = [{'name': 'fixture'}]
    alpha = yaml.safe_load(base64.b64decode(get('Secret', '-alpha')['data']['oauth2_proxy.yml']))
    alpha['server'] = {'bindAddress': f'0.0.0.0:{proxy_port}'}
    provider = alpha['providers'][0]
    provider['clientID'], provider['clientSecret'] = 'edge-web', 'fixture-client-secret'
    provider['oidcConfig']['issuerURL'] = issuer
    legacy = tomllib.loads(get('ConfigMap', 'oauth2-proxy')['data']['oauth2_proxy.cfg'])
    legacy.update(cookie_secure=False, cookie_name='edge-fixture', redirect_url=f'{public}/oauth2/callback',
                  whitelist_domains=['localhost:*'], session_store_type='redis', redis_connection_url='redis://127.0.0.1:6379',
                  cookie_secret=base64.b64encode(b'0123456789abcdef0123456789abcdef').decode())
    kubernetes = copy.deepcopy([item for item in [*resources, *client_resources, *api_resources] if item['kind'] in {'HTTPRoute', 'Middleware'}])
    if external:
        kubernetes.extend(copy.deepcopy([item for item in client_resources if item['kind'] in {'Service', 'TraefikService'}]))
    for item in kubernetes:
        if item['kind'] == 'Middleware' and 'forwardAuth' in item['spec']:
            auth = item['spec']['forwardAuth']
            auth['address'] = f'http://127.0.0.1:{proxy_port}' + ('/oauth2/auth' if auth['address'].endswith('/oauth2/auth') else '/')
            auth['addAuthCookiesToResponse'] = ['edge-fixture', 'edge-fixture_csrf']
    kubernetes.extend([
        {'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': 'default'}},
        {'apiVersion': 'gateway.networking.k8s.io/v1', 'kind': 'GatewayClass', 'metadata': {'name': 'traefik'},
         'spec': {'controllerName': 'traefik.io/gateway-controller'}},
        {'apiVersion': 'gateway.networking.k8s.io/v1', 'kind': 'Gateway', 'metadata': {'name': 'fixture', 'namespace': 'default'},
         'spec': {'gatewayClassName': 'traefik', 'listeners': [{'name': 'web', 'protocol': 'HTTP', 'port': gateway_port}]}},
        {'apiVersion': 'gateway.networking.k8s.io/v1', 'kind': 'HTTPRoute', 'metadata': {'name': 'telemetry', 'namespace': 'default'},
         'spec': {'parentRefs': [{'name': 'fixture'}], 'hostnames': ['localhost'], 'rules': [{
             'matches': [{'path': {'type': 'Exact', 'value': '/_telemetry/collect'}, 'method': 'POST'}],
             'filters': [
                 {'type': 'RequestHeaderModifier', 'requestHeaderModifier': {'remove': ['Cookie', 'Authorization', 'X-XSRF-TOKEN']}},
                 {'type': 'URLRewrite', 'urlRewrite': {'path': {'type': 'ReplaceFullPath', 'replaceFullPath': '/collect'}}},
             ],
              'backendRefs': [{'name': 'api-origin', 'port': origin_port}],
         }]}},
    ])
    for service, port, target in [('static-origin', origin_port, origin_port), ('public-origin', origin_port, origin_port), ('api-origin', origin_port, origin_port),
                                  (get('Service', 'oauth2-proxy')['metadata']['name'], 80, proxy_port)]:
        if external and service in {'static-origin', 'public-origin'}:
            continue
        kubernetes.extend([
            {'apiVersion': 'v1', 'kind': 'Service', 'metadata': {'name': service, 'namespace': 'default'},
             'spec': {'ports': [{'name': 'http', 'port': port, 'targetPort': target, 'protocol': 'TCP'}]}},
            {'apiVersion': 'discovery.k8s.io/v1', 'kind': 'EndpointSlice',
             'metadata': {'name': service, 'namespace': 'default', 'labels': {'kubernetes.io/service-name': service}},
             'addressType': 'IPv4', 'ports': [{'name': 'http', 'port': target, 'protocol': 'TCP'}],
             'endpoints': [{'addresses': ['127.0.0.1'], 'conditions': {'ready': True}}]},
        ])
    for index, item in enumerate(kubernetes):
        item['metadata'].update(uid=f'fixture-{index}', resourceVersion='1', generation=1)
    name = f'spa-edge-{os.getpid()}'
    with tempfile.TemporaryDirectory(prefix='spa-edge-', dir=os.environ.get('RUNNER_TEMP', '/tmp/opencode')) as temporary:
        directory = Path(temporary)
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                        '-keyout', str(directory / 'origin.key'), '-out', str(directory / 'origin.crt'),
                        '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost'], check=True, capture_output=True)
        plugin = directory / 'plugins/src/github.com/traefik/plugin-rewritebody'
        plugin.parent.mkdir(parents=True)
        subprocess.run(['git', 'clone', '--quiet', '--depth', '1', '--branch', 'v0.3.1', 'https://github.com/traefik/plugin-rewritebody.git', str(plugin)], check=True, capture_output=True)
        (directory / 'proxy.cfg').write_text(''.join(f'{key} = {json.dumps(value)}\n' for key, value in legacy.items()))
        (directory / 'proxy.yaml').write_text(yaml.safe_dump(alpha))
        (directory / 'resources.json').write_text(json.dumps(kubernetes))
        (directory / 'traefik.yaml').write_text(yaml.safe_dump({
            'entryPoints': {'web': {'address': f':{gateway_port}'}}, 'ping': {'entryPoint': 'web'},
            'providers': {
                'kubernetesGateway': {'endpoint': f'http://127.0.0.1:{kubernetes_port}', 'statusAddress': {'ip': '127.0.0.1'}},
                'kubernetesCRD': {'endpoint': f'http://127.0.0.1:{kubernetes_port}', 'allowExternalNameServices': external},
            },
            'experimental': {'localPlugins': {'rewritebody': {'moduleName': 'github.com/traefik/plugin-rewritebody'}}},
        }))
        (directory / 'issuer.json').write_text(json.dumps({'issuer_url': issuer, 'access_token_ttl_secs': 600, 'clients': {'edge-web': {
            'secret': 'fixture-client-secret', 'redirect_uri': f'{public}/oauth2/callback', 'api_audience': 'fixture-api',
            'api_scope': 'api://fixture-api/api-access', 'allowed_users': ['owner'], 'roles': {'owner': ['read']},
        }}}))
        env = {'PORT': str(issuer_port), 'ISSUER_ID': 'default', 'SUB': 'owner', 'NAME': 'Owner',
               'PREFERRED_USERNAME': 'owner@example.test', 'ROLES': 'read', 'SCP': 'api-access', 'AUD': 'fixture-api',
               'OID': '00000000-0000-0000-0000-000000000001', 'FIXTURE_CONFIG_FILE': '/config/issuer.json'}
        mount = [{'name': 'config', 'mountPath': '/config', 'readOnly': True}]
        containers = [
            {'name': 'proxy', 'image': 'quay.io/oauth2-proxy/oauth2-proxy:v7.15.2-alpine', 'args': ['--config=/config/proxy.cfg', '--alpha-config=/config/proxy.yaml'], 'volumeMounts': mount},
            {'name': 'redis', 'image': 'docker.io/library/redis:8.2-alpine', 'args': ['redis-server', '--save', '', '--appendonly', 'no']},
            {'name': 'issuer', 'image': 'ghcr.io/mucsi96/mock-oidc-provider:14', 'env': [{'name': key, 'value': value} for key, value in env.items()], 'volumeMounts': mount,
             'ports': [{'containerPort': issuer_port, 'hostPort': issuer_port}]},
            {'name': 'origin', 'image': 'docker.io/library/python:3.14-alpine', 'command': ['python3', '-B', '-u', '/fixture/spa_origin.py'],
              'env': [{'name': 'PORT', 'value': str(origin_port)}, {'name': 'TLS_PORT', 'value': str(tls_port)},
                      {'name': 'ASSET_ORIGIN', 'value': f'http://localhost:{origin_port}' if external else ''}],
              'volumeMounts': [*mount, {'name': 'fixture', 'mountPath': '/fixture', 'readOnly': True}],
             'ports': [{'containerPort': origin_port, 'hostPort': origin_port}]},
            {'name': 'kubernetes', 'image': 'docker.io/library/python:3.14-alpine', 'command': ['python3', '-B', '-u', '/fixture/kubernetes_api.py'],
             'env': [{'name': 'PORT', 'value': str(kubernetes_port)}],
             'volumeMounts': [*mount, {'name': 'fixture', 'mountPath': '/fixture', 'readOnly': True}],
             'ports': [{'containerPort': kubernetes_port, 'hostPort': kubernetes_port}]},
            {'name': 'gateway', 'image': 'docker.io/library/traefik:v3.7.16', 'args': ['--configFile=/config/traefik.yaml'],
              'env': [{'name': 'SSL_CERT_FILE', 'value': '/config/origin.crt'}],
             'volumeMounts': [*mount, {'name': 'plugins', 'mountPath': '/plugins-local', 'readOnly': True}],
             'ports': [{'containerPort': gateway_port, 'hostPort': gateway_port}]},
        ]
        volumes = [{'name': 'config', 'hostPath': {'path': str(directory), 'type': 'Directory'}},
                   {'name': 'plugins', 'hostPath': {'path': str(directory / 'plugins'), 'type': 'Directory'}},
                   {'name': 'fixture', 'hostPath': {'path': str(ROOT / 'scripts/fixtures'), 'type': 'Directory'}}]
        pod = directory / 'pod.json'
        pod.write_text(json.dumps({'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': name}, 'spec': {'containers': containers, 'volumes': volumes}}))
        try:
            subprocess.run(['podman', 'kube', 'play', str(pod)], check=True, capture_output=True)
            wait_for(f'http://localhost:{issuer_port}/health')
            wait_for(f'http://localhost:{origin_port}/health')
            subprocess.run(['podman', 'restart', f'{name}-proxy'], check=True, capture_output=True)
            wait_for(f'{public}/ping')
            wait_for(f'{public}/oauth2/static/css/bulma.min.css')
            # Gateway and CRD providers synchronize independently at startup.
            for _ in range(60):
                if fetch(f'{public}/index.html', follow=False)[0] == 302:
                    break
                time.sleep(1)
            else:
                raise RuntimeError('Client document route did not become ready')
            status, _, _, _ = fetch(f'{public}/index.html', headers={'Accept': 'application/javascript'}, follow=False)
            assert status == 302, 'Raw index bypassed document authentication'
            assert fetch(f'{public}/index.html', follow=False, method='HEAD')[0] == 302
            assert fetch(f'{public}/main.js', headers={'Cookie': 'private=secret', 'Authorization': 'Bearer forged'})[0] == (404 if external else 200)
            assert fetch(f'{public}/missing.js')[0] == 404
            assert fetch(f'{public}/api/data')[0] == 401
            status, headers, _, _ = fetch(f'{public}/api/data', headers={'Authorization': 'Bearer forged', 'X-Auth-Request-Email': 'forged@example.test'}, follow=False)
            assert status == 401 and headers.get('Location') is None
            assert headers.get('Cache-Control') == 'no-store' and headers.get('Authorization') is None
            assert fetch(f'{public}/api/data', headers={'Accept': 'text/html'}, follow=False)[0] == 401
            assert fetch(f'{public}/oauth2/staticevil')[0] == 404
            nested_path = '/teams/acme/projects/42/settings/members'
            assert fetch(f'http://localhost:{origin_port}{nested_path}')[0] == 404
            cookies = CookieJar()
            target = f'{public}{nested_path}?tab=permissions&returnTo=%2Freports%2Fweekly'
            status, headers, body, final = fetch(target, cookies, {'Accept': 'text/html', 'Accept-Encoding': 'gzip'})
            assert status == 200 and final == target, 'SPA login did not restore the original path/query'
            assert '__APP_CONFIG_JSON__' not in body.decode() and 'no-store' in headers.get('Cache-Control', '')
            assert headers.get('ETag') is None and headers.get('Authorization') is None
            injected = re.search(r'__APP_CONFIG__\s*=\s*({.*?});', body.decode()).group(1)
            assert json.loads(injected) == runtime and '</script>' not in injected
            # BrowserRouter/history URLs must survive direct entry and refresh at any depth.
            public_cookies = CookieJar()
            for host, path, expected_config, session in [
                (public, nested_path + '/', runtime, cookies),
                (public, '/teams/acme/projects/release.v2/files/report.csv/edit?mode=preview', runtime, cookies),
                (other_app, '/', public_runtime, public_cookies),
                (other_app, nested_path + '?tab=permissions', public_runtime, public_cookies),
                (other_app, nested_path + '/', public_runtime, public_cookies),
                (public, '/portal' + nested_path, runtime, cookies),
            ]:
                url = host + path
                for _ in range(2):
                    status, headers, body, final = fetch(url, session, {'Accept': 'text/html'}, follow=False)
                    assert status == 200 and final == url, f'Nested navigation/refresh failed: {path}'
                    assert headers.get('Location') is None and 'no-store' in headers.get('Cache-Control', '')
                    config = re.search(r'__APP_CONFIG__\s*=\s*({.*?});', body.decode()).group(1)
                    assert json.loads(config) == expected_config, f'Wrong app handled nested route: {path}'
                    scripts = re.findall(r'<script[^>]+src="([^"]+)"', body.decode())
                    expected_asset = f'http://localhost:{origin_port}/assets/main-HASH.js' if external else '/assets/main-HASH.js'
                    assert scripts == [expected_asset], 'Nested documents must resolve assets independently of their SPA path'
                    assert headers['content-security-policy'] == "default-src 'self'"
                    assert headers['referrer-policy'] == 'no-referrer'
                    assert headers['x-content-type-options'] == 'nosniff'
                    asset_status, asset_headers, _, _ = fetch(urljoin(final, scripts[0]))
                    assert asset_status == 200 and 'javascript' in asset_headers.get('Content-Type', '')
            assert len(public_cookies) == 0, 'Public SPA unexpectedly started login'
            assert fetch(f'{other_app}/assets/missing.js')[0] == 404
            assert fetch(f'{other_app}{nested_path}', headers={'Sec-Fetch-Dest': 'document'}, method='HEAD')[0] == 200
            # A session established on one hostname is not sent to another app host.
            same_host_request = Request(public + '/api/data')
            cookies.add_cookie_header(same_host_request)
            assert 'edge-fixture=' in same_host_request.get_header('Cookie', '')
            other_host_request = Request(other_app + '/api/data')
            cookies.add_cookie_header(other_host_request)
            assert other_host_request.get_header('Cookie') is None
            status, headers, body, _ = fetch(f'{public}/index.html', cookies, {
                'If-None-Match': '"origin-only-etag"', 'If-Modified-Since': 'Mon, 01 Jan 2024 00:00:00 GMT',
                'Range': 'bytes=0-10', 'If-Range': '"origin-only-etag"',
            })
            assert status == 200 and '__APP_CONFIG_JSON__' not in body.decode(), 'Conditional/range request bypassed config injection'
            status, headers, body, _ = fetch(target, cookies, {'Sec-Fetch-Dest': 'document'}, method='HEAD')
            assert status == 200 and not body and 'no-store' in headers.get('Cache-Control', '')
            status, headers, body, _ = fetch(f'{public}/api/data', cookies, {'Authorization': 'Bearer forged'})
            assert status == 200 and json.loads(body)['bearerAudience'] == 'fixture-api'
            assert headers.get('Authorization') is None and headers.get('Cache-Control') == 'no-store'
            assert fetch(f'{public}/oauth2/auth', cookies)[0] == 404
            assert fetch(f'{public}/_telemetry/collect', cookies, {'Content-Type': 'application/json', 'Authorization': 'Bearer forged', 'X-XSRF-TOKEN': 'private'}, b'{}')[0] == 202
            records = json.loads(fetch(f'http://localhost:{origin_port}/requests')[2])
            index_requests = [item for item in records if item['path'].split('?')[0] == '/index.html']
            assert index_requests and all(not item['cookie'] and not item['authorization'] and item['encoding'] == 'identity'
                                          and not item['conditional'] and not item['range'] for item in index_requests)
            assets = [item for item in records if item['path'] in {'/main.js', '/assets/main-HASH.js'}]
            assert assets and all(not item['cookie'] and not item['authorization'] for item in assets)
            if external:
                assert all(item['tls'] and item['host'] == 'localhost' for item in index_requests), 'Documents require verified TLS and native Gateway hostname rewriting'
                assert all(not item['tls'] and item['host'] == f'localhost:{origin_port}' for item in assets), 'Assets must bypass the gateway and use their direct URLs'
            telemetry = next(item for item in records if item['path'] == '/collect')
            assert not telemetry['cookie'] and not telemetry['authorization'] and not telemetry['xsrf']
            objects = json.loads(fetch(f'http://localhost:{kubernetes_port}/objects')[2])
            routes = [item for item in objects if item['kind'] == 'HTTPRoute']
            assert routes and all({'Accepted': 'True', 'ResolvedRefs': 'True'}.items() <= {
                condition['type']: condition['status']
                for parent in item.get('status', {}).get('parents', []) for condition in parent['conditions']
            }.items() for item in routes), 'Gateway controller rejected a rendered route'
            print(json.dumps({'documentAuthBeforeIndex': True, 'spaPathQueryRestored': True, 'runtimeConfigInjected': True,
                              'originHasNoSpaFallback': True, 'sameOriginTelemetry': True, 'staticOriginReceivesNoCredentials': True,
                              'nestedHistoryRoutes': True, 'hostOnlyCookieIsolation': True, 'rootOnlyApps': True, 'deepLinkRefreshAndAssets': True}))
        except Exception:
            for container in ['gateway', 'proxy', 'kubernetes']:
                result = subprocess.run(['podman', 'logs', '--tail', '40', f'{name}-{container}'], capture_output=True, text=True)
                print(result.stdout, result.stderr)
            raise
        finally:
            subprocess.run(['podman', 'pod', 'rm', '--force', name], capture_output=True)


if __name__ == '__main__':
    main()

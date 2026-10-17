"""Shared stock-proxy regression: missing optional claims must not call UserInfo."""
import base64
import copy
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import tomllib
from urllib.error import HTTPError, URLError
from urllib.request import build_opener, HTTPCookieProcessor

import yaml


ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def fetch(url, cookies=None):
    opener = build_opener(HTTPCookieProcessor(cookies if cookies is not None else CookieJar()))
    try:
        response = opener.open(url, timeout=5)
    except HTTPError as error:
        response = error
    return response.status, response.headers, response.read()


def wait_for(url):
    for _ in range(60):
        try:
            if fetch(url)[0] == 200:
                return
        except (OSError, URLError):
            pass
        time.sleep(1)
    raise RuntimeError('Fixture did not become ready')


def main():
    ports = set()
    while len(ports) < 3:
        ports.add(free_port())
    issuer_port, control_port, fixed_port = sorted(ports)
    issuer = f'http://localhost:{issuer_port}/default'
    values = {
        'global': {'forwardAuth': {
            'host': 'hello.example.test', 'issuerURL': 'https://issuer.example.test/default',
            'credentialsSecret': 'fixture-oidc', 'mode': 'api-token',
            'apiScope': 'api://fixture-api/api-access', 'trustedProxyCIDRs': ['127.0.0.1/32'],
        }},
        'oauth2-proxy': {'sessionStorage': {'redis': {
            'existingSecret': 'fixture-redis', 'standalone': {'connectionUrl': 'redis://127.0.0.1:6379'},
        }}},
    }
    rendered = subprocess.run(
        ['helm', 'template', 'fixture', str(ROOT / 'charts/oauth2_proxy_forwardauth'), '-f', '-'],
        input=yaml.safe_dump(values), text=True, capture_output=True, check=True,
    )
    resources = [item for item in yaml.safe_load_all(rendered.stdout) if item]
    config = next(item for item in resources if item['kind'] == 'ConfigMap' and 'oauth2_proxy.cfg' in item.get('data', {}))
    secret = next(item for item in resources if item['kind'] == 'Secret' and 'oauth2_proxy.yml' in item.get('data', {}))
    legacy = tomllib.loads(config['data']['oauth2_proxy.cfg'])
    alpha = yaml.safe_load(base64.b64decode(secret['data']['oauth2_proxy.yml']))
    assert alpha['providers'][0]['skipClaimsFromProfileURL'] is True
    name = f'forwardauth-login-{os.getpid()}'
    with tempfile.TemporaryDirectory(prefix='forwardauth-login-', dir=os.environ.get('RUNNER_TEMP', '/tmp/opencode')) as temporary:
        directory = Path(temporary)
        clients, containers = {}, []
        for variant, port in [('control', control_port), ('fixed', fixed_port)]:
            client = f'{variant}-web'
            callback = f'http://localhost:{port}/oauth2/callback'
            clients[client] = {
                'secret': 'fixture-client-secret', 'redirect_uri': callback,
                'api_audience': 'fixture-api', 'api_scope': 'api://fixture-api/api-access',
                'allowed_users': ['owner'], 'roles': {'owner': ['read']},
            }
            proxy = copy.deepcopy(alpha)
            proxy['server'] = {'bindAddress': f'0.0.0.0:{port}'}
            provider = proxy['providers'][0]
            provider['clientID'], provider['clientSecret'] = client, 'fixture-client-secret'
            provider['oidcConfig'].update(issuerURL=issuer, groupsClaim='absent_optional_groups',
                                          skipDiscovery=True, jwksURL=f'{issuer}/jwks')
            provider['loginURL'], provider['redeemURL'] = f'{issuer}/authorize', f'{issuer}/token'
            # This endpoint deliberately rejects profile lookups, like Graph rejects
            # an app-API token. Only the negative control may request it.
            provider['profileURL'] = f'http://localhost:{issuer_port}/requires-a-different-token-audience'
            if variant == 'control':
                provider['skipClaimsFromProfileURL'] = False
            runtime = dict(legacy, cookie_secure=False,
                           cookie_name=f'fixture-{variant}', redirect_url=callback,
                           whitelist_domains=['localhost:*'], session_store_type='redis',
                           redis_connection_url='redis://127.0.0.1:6379',
                           cookie_secret=base64.b64encode(b'0123456789abcdef0123456789abcdef').decode())
            (directory / f'{variant}.cfg').write_text(''.join(f'{key} = {json.dumps(value)}\n' for key, value in runtime.items()))
            (directory / f'{variant}.yaml').write_text(yaml.safe_dump(proxy))
            containers.append({
                'name': variant, 'image': 'quay.io/oauth2-proxy/oauth2-proxy:v7.15.2-alpine',
                'args': [f'--config=/config/{variant}.cfg', f'--alpha-config=/config/{variant}.yaml'],
                'ports': [{'containerPort': port, 'hostPort': port}],
                'volumeMounts': [{'name': 'config', 'mountPath': '/config', 'readOnly': True}],
            })
        (directory / 'issuer.json').write_text(json.dumps({
            'issuer_url': issuer, 'access_token_ttl_secs': 600, 'clients': clients,
        }))
        env = {
            'PORT': str(issuer_port), 'ISSUER_ID': 'default', 'SUB': 'owner', 'NAME': 'Owner',
            'PREFERRED_USERNAME': 'owner@example.test', 'ROLES': 'read', 'SCP': 'api-access',
            'AUD': 'fixture-api', 'OID': '00000000-0000-0000-0000-000000000001',
            'FIXTURE_CONFIG_FILE': '/config/issuer.json',
        }
        containers.extend([
            {'name': 'redis', 'image': 'docker.io/library/redis:8.2-alpine', 'args': ['redis-server', '--save', '', '--appendonly', 'no']},
            {'name': 'issuer', 'image': 'ghcr.io/mucsi96/mock-oidc-provider:14',
             'env': [{'name': key, 'value': value} for key, value in env.items()],
             'ports': [{'containerPort': issuer_port, 'hostPort': issuer_port}],
             'volumeMounts': [{'name': 'config', 'mountPath': '/config', 'readOnly': True}]},
        ])
        manifest = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': name}, 'spec': {
            'containers': containers,
            'volumes': [{'name': 'config', 'hostPath': {'path': str(directory), 'type': 'Directory'}}],
        }}
        path = directory / 'pod.json'
        path.write_text(json.dumps(manifest))
        try:
            subprocess.run(['podman', 'kube', 'play', str(path)], check=True, capture_output=True)
            wait_for(f'http://localhost:{issuer_port}/health')
            subprocess.run(['podman', 'restart', f'{name}-control', f'{name}-fixed'], check=True, capture_output=True)
            wait_for(f'http://localhost:{control_port}/ping')
            wait_for(f'http://localhost:{fixed_port}/ping')
            assert fetch(f'http://localhost:{control_port}/oauth2/start?rd=/')[0] == 500, 'Negative control did not reproduce callback failure'
            cookies = CookieJar()
            assert fetch(f'http://localhost:{fixed_port}/oauth2/start?rd=/', cookies)[0] == 202, 'Callback failed with missing optional groups'
            status, headers, _ = fetch(f'http://localhost:{fixed_port}/oauth2/auth', cookies)
            assert status == 202 and headers.get('Authorization', '').startswith('Bearer ')
            payload = headers['Authorization'].split('.')[1]
            assert json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))['aud'] == 'fixture-api'
            for stylesheet in ['bulma.min.css', 'all.min.css']:
                status, headers, body = fetch(f'http://localhost:{fixed_port}/oauth2/static/css/{stylesheet}', cookies)
                assert status == 200 and 'text/css' in headers.get('Content-Type', '') and body
                assert 'Authorization' not in headers
            print(json.dumps({'missingClaimsControlStatus': 500, 'fixedCallbackStatus': 202, 'stockErrorStylesStatus': 200}))
        except Exception:
            for variant in ['control', 'fixed']:
                logs = subprocess.run(['podman', 'logs', '--tail', '30', f'{name}-{variant}'], text=True, capture_output=True)
                print(logs.stdout, logs.stderr)
            raise
        finally:
            subprocess.run(['podman', 'pod', 'rm', '--force', name], capture_output=True)


if __name__ == '__main__':
    main()

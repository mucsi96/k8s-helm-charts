"""List/watch/status fixture for Traefik's real Kubernetes providers, not an API validator."""
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import time
from urllib.parse import parse_qs, urlsplit

objects = json.loads(Path('/config/resources.json').read_text())
kinds = [
    'Namespace', 'Service', 'Secret', 'ConfigMap', 'Node', 'EndpointSlice',
    'GatewayClass', 'Gateway', 'HTTPRoute', 'GRPCRoute', 'TLSRoute', 'TCPRoute',
    'ReferenceGrant', 'BackendTLSPolicy', 'Middleware', 'MiddlewareTCP',
    'IngressRoute', 'IngressRouteTCP', 'IngressRouteUDP', 'TraefikService',
    'ServersTransport', 'ServersTransportTCP', 'TLSOption', 'TLSStore',
]
plural = lambda kind: kind.lower() + ('es' if kind.endswith('s') else 's')
collections = {plural(kind): kind for kind in kinds}
collections['backendtlspolicies'] = 'BackendTLSPolicy'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def respond(self, status, value):
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def lookup(self):
        parts = urlsplit(self.path).path.strip('/').split('/')
        version = '/'.join(parts[1:3]) if parts[0] == 'apis' else parts[1]
        path = parts[3:] if parts[0] == 'apis' else parts[2:]
        namespace = path[1] if len(path) > 2 and path[0] == 'namespaces' else None
        path = path[2:] if namespace else path
        kind = collections[path[0]]
        matches = [item for item in objects if item['apiVersion'] == version and item['kind'] == kind
                   and (namespace is None or item['metadata'].get('namespace') == namespace)
                   and (len(path) == 1 or item['metadata']['name'] == path[1])]
        return version, kind, matches

    def do_GET(self):
        if self.path == '/objects':
            self.respond(200, objects)
            return
        version, kind, matches = self.lookup()
        query = parse_qs(urlsplit(self.path).query)
        if query.get('watch') == ['true']:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            if query.get('sendInitialEvents') == ['true']:
                events = [{'type': 'ADDED', 'object': item} for item in matches]
                events.append({'type': 'BOOKMARK', 'object': {
                    'apiVersion': version, 'kind': kind,
                    'metadata': {'resourceVersion': '1', 'annotations': {'k8s.io/initial-events-end': 'true'}},
                }})
                for event in events:
                    self.wfile.write(json.dumps(event).encode() + b'\n')
                self.wfile.flush()
            time.sleep(60)
        elif urlsplit(self.path).path.rstrip('/').split('/')[-1] in collections:
            self.respond(200, {'apiVersion': version, 'kind': kind + 'List', 'metadata': {'resourceVersion': '1'}, 'items': matches})
        else:
            self.respond(200 if matches else 404, matches[0] if matches else {'kind': 'Status', 'code': 404})

    def do_PATCH(self):
        _, _, matches = self.lookup()
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if not matches:
            self.respond(404, {'kind': 'Status', 'code': 404})
            return
        # Only status writes are accepted; fixture specs remain immutable.
        if not urlsplit(self.path).path.endswith('/status'):
            self.respond(405, {'kind': 'Status', 'code': 405})
            return
        matches[0]['status'] = deepcopy(body.get('status', {}))
        self.respond(200, matches[0])

    do_PUT = do_PATCH


ThreadingHTTPServer(('0.0.0.0', int(os.environ['PORT'])), Handler).serve_forever()

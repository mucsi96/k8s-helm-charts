"""Static-only origin and telemetry sink for the shared Gateway regression."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import base64
import json
import os

requests = []
INDEX = b'''<!doctype html><html><head><script>window.__APP_CONFIG__ = "__APP_CONFIG_JSON__";</script></head><body><script src="/assets/main-HASH.js"></script></body></html>'''
ASSETS = {'/main.js', '/assets/main-HASH.js'}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def respond(self, status, body, content_type):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('ETag', '"origin-only-etag"')
        self.send_header('Last-Modified', 'Mon, 01 Jan 2024 00:00:00 GMT')
        self.send_header('Authorization', 'Bearer must-not-reach-browser')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def do_GET(self):
        path = self.path.split('?')[0]
        if path == '/requests':
            self.respond(200, json.dumps(requests).encode(), 'application/json')
            return
        requests.append({'path': self.path, 'cookie': bool(self.headers.get('Cookie')),
                         'authorization': bool(self.headers.get('Authorization')),
                         'conditional': bool(self.headers.get('If-None-Match') or self.headers.get('If-Modified-Since')),
                         'range': bool(self.headers.get('Range') or self.headers.get('If-Range')),
                         'encoding': self.headers.get('Accept-Encoding')})
        if path == '/index.html':
            index = INDEX
            if self.headers.get('If-None-Match') == '"origin-only-etag"' or self.headers.get('If-Modified-Since'):
                self.respond(304, b'', 'text/html')
            elif self.headers.get('Range'):
                self.respond(206, index[:11], 'text/html')
            else:
                self.respond(200, index, 'text/html')
        elif path in ASSETS:
            self.respond(200, b'console.log("fixture asset");', 'application/javascript')
        elif path == '/api/data':
            # Inspect forwarding only; real app tests verify JWT signatures/roles.
            token = self.headers.get('Authorization', '').removeprefix('Bearer ')
            try:
                payload = token.split('.')[1]
                audience = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))['aud']
            except (IndexError, ValueError, KeyError):
                audience = None
            self.respond(200, json.dumps({'bearerAudience': audience}).encode(), 'application/json')
        elif path == '/health':
            self.respond(200, b'up', 'text/plain')
        else:
            self.respond(404, b'Not found', 'text/plain')

    do_HEAD = do_GET

    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length', '0')))
        path = self.path.split('?')[0]
        requests.append({'path': path, 'cookie': bool(self.headers.get('Cookie')),
                         'authorization': bool(self.headers.get('Authorization')),
                         'xsrf': bool(self.headers.get('X-XSRF-TOKEN'))})
        self.respond(202 if path == '/collect' else 404, b'{}', 'application/json')


ThreadingHTTPServer(('0.0.0.0', int(os.environ['PORT'])), Handler).serve_forever()

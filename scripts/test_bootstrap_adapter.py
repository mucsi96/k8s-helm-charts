"""HTTP integration checks for the chart-shipped bootstrap adapter."""
from contextlib import contextmanager
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import threading
import unittest
from urllib.parse import parse_qs, urlencode, urlsplit


SOURCE = Path(__file__).resolve().parents[1] / "charts/oauth2_proxy_forwardauth/files/bootstrap_adapter.py"
spec = importlib.util.spec_from_file_location("bootstrap_adapter", SOURCE)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


@contextmanager
def server(callback):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status, headers, body = callback(self)
            self.send_response(status)
            for name, value in headers:
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    instance = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=instance.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{instance.server_port}"
    finally:
        instance.shutdown()
        instance.server_close()
        worker.join()


class BootstrapAdapterTest(unittest.TestCase):
    def setUp(self):
        self.mode = "authorized"
        self.auth_requests = []
        self.backend_requests = []

        def auth(request):
            self.auth_requests.append((request.path, dict(request.headers)))
            cookies = [("Set-Cookie", "session=refreshed; HttpOnly"), ("Set-Cookie", "csrf=new; HttpOnly")]
            if self.mode == "redirect":
                return 302, [("Location", "https://login.example.test/authorize?state=opaque"), *cookies], b""
            if self.mode == "bad-redirect":
                return 302, [("Location", "javascript:alert(1)")], b""
            if self.mode == "forbidden":
                return 403, cookies, b"Forbidden"
            if self.mode == "unauthorized":
                return 401, cookies, b"{}"
            if self.mode == "unavailable":
                return 500, [], b"error"
            return 202, [("Authorization", "Bearer verified"), ("X-Auth-Request-Email", "owner@example.test"), *cookies], b"Accepted"

        def backend(request):
            self.backend_requests.append((request.path, dict(request.headers)))
            if self.mode == "backend-redirect":
                return 302, [("Location", "https://other.example.test/")], b""
            if self.mode == "backend-forbidden":
                return 403, [("Content-Type", "application/json")], b'{"message":"denied"}'
            if self.mode == "oversize":
                return 200, [], b"x" * (adapter.MAX_BODY + 1)
            return 200, [("Content-Type", "application/json"), ("Authorization", "Bearer must-not-leak"), ("X-Auth-Request-Access-Token", "secret"), ("Set-Cookie", "theme=dark")], b'{"clientAppName":"example"}'

        self.auth_url = self.enterContext(server(auth))
        self.backend_url = self.enterContext(server(backend))
        self.config = adapter.configuration({
            "proxy_root_url": self.auth_url + "/",
            "public_origin": "https://app.example.test",
            "identity_headers": ["Authorization"],
            "routes": [
                {"path": "/api/environment", "upstream": self.backend_url + "/api/environment"},
                {"path": "/runtime/config", "upstream": self.backend_url + "/settings"},
            ],
        })
        self.http = adapter.BootstrapServer(("127.0.0.1", 0), adapter.handler(self.config))
        worker = threading.Thread(target=self.http.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(worker.join)
        self.addCleanup(self.http.server_close)
        self.addCleanup(self.http.shutdown)

    def request(self, path="/api/environment", method="GET", headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.http.server_port, timeout=10)
        try:
            connection.request(method, path, headers=headers or {})
            response = connection.getresponse()
            return response.status, response.getheaders(), response.read()
        finally:
            connection.close()

    def test_authenticated_config_uses_only_verified_identity(self):
        status, headers, body = self.request("/api/environment?returnTo=%2Frecipes&locale=hu", headers={
            "Cookie": "session=original; theme=light", "Authorization": "Bearer forged",
            "X-Auth-Request-Email": "forged@example.test", "Accept": "application/json",
        })
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"clientAppName": "example"})
        request_path, request_headers = self.backend_requests[0]
        self.assertEqual(request_path, "/api/environment?locale=hu")
        self.assertEqual(request_headers["Authorization"], "Bearer verified")
        self.assertNotIn("X-Auth-Request-Email", request_headers)
        self.assertEqual(request_headers["Cookie"], "session=original; theme=light")
        public_headers = {name.lower(): value for name, value in headers}
        self.assertNotIn("authorization", public_headers)
        self.assertNotIn("x-auth-request-access-token", public_headers)
        self.assertEqual(public_headers["cache-control"], "no-store")
        self.assertEqual([value for name, value in headers if name.lower() == "set-cookie"], ["theme=dark", "session=refreshed; HttpOnly", "csrf=new; HttpOnly"])
        self.assertEqual(self.auth_requests[0][1]["Accept"], "text/html")
        self.assertNotIn("Authorization", self.auth_requests[0][1])

    def test_proxy_redirect_and_all_cookies_are_returned_as_json(self):
        self.mode = "redirect"
        status, headers, body = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"redirectTo": "https://login.example.test/authorize?state=opaque"})
        self.assertEqual(len([value for name, value in headers if name.lower() == "set-cookie"]), 2)
        self.assertEqual(self.backend_requests, [])

    def test_service_modes_do_not_pass_caller_identity(self):
        for names, expected_email in [(["X-Auth-Request-Email"], "owner@example.test"), ([], None)]:
            with self.subTest(headers=names):
                self.config["identity_headers"] = names
                self.assertEqual(self.request(headers={"Authorization": "Bearer forged", "X-Auth-Request-Email": "forged@example.test"})[0], 200)
                headers = self.backend_requests[-1][1]
                self.assertNotIn("Authorization", headers)
                self.assertEqual(headers.get("X-Auth-Request-Email"), expected_email)

    def test_return_target_preserves_deep_link_query_and_fragment(self):
        self.mode = "redirect"
        target = "/recipe/42?view=edit#ingredients"
        self.request("/api/environment?" + urlencode({"returnTo": target}))
        self.assertEqual(parse_qs(urlsplit(self.auth_requests[0][0]).query)["rd"], [target])

    def test_external_and_malformed_return_targets_fall_back_to_root(self):
        self.mode = "redirect"
        for target in ["https://evil.example/", "//evil.example/", "/\\evil.example/", "/%2f%2fevil.example/", "bad", "/bad\r\nheader"]:
            with self.subTest(target=target):
                self.request("/api/environment?" + urlencode({"returnTo": target}))
                self.assertEqual(parse_qs(urlsplit(self.auth_requests[-1][0]).query)["rd"], ["/"])

    def test_denials_do_not_become_redirect_loops(self):
        for mode, expected in [("forbidden", 403), ("unauthorized", 401), ("unavailable", 503)]:
            with self.subTest(mode=mode):
                self.mode = mode
                status, _, body = self.request()
                self.assertEqual(status, expected)
                self.assertNotIn("redirectTo", json.loads(body))
                self.assertEqual(self.backend_requests, [])

    def test_dangerous_redirect_scheme_is_rejected(self):
        self.mode = "bad-redirect"
        self.assertEqual(self.request()[0], 503)

    def test_configured_paths_choose_fixed_backends(self):
        self.assertEqual(self.request("/runtime/config?url=https://evil.example/")[0], 200)
        self.assertTrue(self.backend_requests[0][0].startswith("/settings?"))
        self.assertEqual(self.request("/api/unknown")[0], 404)

    def test_methods_and_health(self):
        self.assertEqual(self.request(adapter.HEALTH_PATH)[0], 200)
        self.assertEqual(self.request(method="POST")[0], 405)
        self.assertEqual(self.auth_requests, [])

    def test_backend_denial_is_preserved(self):
        self.mode = "backend-forbidden"
        self.assertEqual(self.request()[0], 403)

    def test_backend_redirect_is_not_followed(self):
        self.mode = "backend-redirect"
        self.assertEqual(self.request()[0], 503)

    def test_oversized_configuration_is_rejected(self):
        self.mode = "oversize"
        self.assertEqual(self.request()[0], 503)

    def test_proxy_outage_fails_closed(self):
        self.config["proxy"] = adapter.endpoint("http://127.0.0.1:1/")
        self.assertEqual(self.request()[0], 503)
        self.assertEqual(self.backend_requests, [])


if __name__ == "__main__":
    unittest.main()

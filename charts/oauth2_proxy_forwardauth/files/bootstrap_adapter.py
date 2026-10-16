"""Shared config-or-redirect transport adapter; OAuth remains in oauth2-proxy."""
import argparse
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import threading
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlsplit, urlunsplit


HEALTH_PATH = "/_bootstrap/health"
MAX_BODY = 1024 * 1024
TIMEOUT = 5
IDENTITY_HEADERS = {"authorization", "x-auth-request-email"}
RESPONSE_BLOCKED = {
    "authorization", "x-auth-request-access-token", "connection", "keep-alive",
    "proxy-authenticate", "proxy-authorization", "te", "trailer",
    "transfer-encoding", "upgrade", "content-length", "cache-control", "server", "date",
}


def endpoint(value):
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None or parsed.password is not None or parsed.fragment:
        raise ValueError("Endpoints must be absolute HTTP(S) URLs")
    return parsed


def return_target(value):
    try:
        target = urlsplit(value)
        path = unquote(target.path)
        if target.scheme or target.netloc or not path.startswith("/") or path.startswith("//") or "\\" in path or re.search(r"[\x00-\x1f\x7f]", value):
            return "/"
        return value
    except ValueError:
        return "/"


def configuration(raw):
    proxy = endpoint(raw["proxy_root_url"])
    origin = endpoint(raw["public_origin"])
    if origin.path not in {"", "/"} or origin.query:
        raise ValueError("public_origin must be an HTTP(S) origin")
    headers = raw["identity_headers"]
    if not isinstance(headers, list) or any(name.lower() not in IDENTITY_HEADERS for name in headers):
        raise ValueError("Unsupported identity header")
    routes = {}
    for route in raw["routes"]:
        path = route["path"]
        if not re.fullmatch(r"/[^?#\s]*", path) or path.startswith(("/oauth2/", "/_bootstrap/")) or path in {"/oauth2", "/_bootstrap"} or path in routes:
            raise ValueError("Bootstrap paths must be unique exact paths outside reserved prefixes")
        routes[path] = endpoint(route["upstream"])
    return {"proxy": proxy, "origin": origin, "identity_headers": headers, "routes": routes}


def exchange(target, headers):
    transport = http.client.HTTPSConnection if target.scheme == "https" else http.client.HTTPConnection
    connection = transport(target.hostname, target.port, timeout=TIMEOUT)
    try:
        path = urlunsplit(("", "", target.path or "/", target.query, ""))
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        body = response.read(MAX_BODY + 1)
        if len(body) > MAX_BODY:
            raise ValueError("Upstream response exceeds bootstrap size limit")
        return response.status, response.getheaders(), body
    finally:
        connection.close()


def handler(config):
    class BootstrapHandler(BaseHTTPRequestHandler):
        server_version = "BootstrapAdapter"
        sys_version = ""

        def log_request(self, code="-", size="-"):
            print(json.dumps({"method": self.command, "path": urlsplit(self.path).path, "status": code}), flush=True)

        def log_error(self, *_):
            print("Bootstrap HTTP request failed", flush=True)

        def reply(self, status, body, headers=()):
            self.send_response(status)
            blocked = RESPONSE_BLOCKED | {part.strip().lower() for name, value in headers if name.lower() == "connection" for part in value.split(",")}
            for name, value in headers:
                if name.lower() not in blocked:
                    self.send_header(name, value)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def json_reply(self, status, value, cookies=()):
            self.reply(status, json.dumps(value).encode(), [("Content-Type", "application/json"), *cookies])

        def unsupported(self):
            self.reply(405, b"Method not allowed", [("Allow", "GET")])

        do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = do_OPTIONS = unsupported

        def do_GET(self):
            parsed = urlsplit(self.path)
            if parsed.path == HEALTH_PATH:
                self.json_reply(200, {"status": "ok"})
                return
            upstream = config["routes"].get(parsed.path)
            if upstream is None:
                self.json_reply(404, {"message": "Unknown bootstrap path"})
                return
            query = parse_qsl(parsed.query, keep_blank_values=True)
            target = return_target(next((value for key, value in query if key == "returnTo"), "/"))
            proxy = config["proxy"]._replace(query=urlencode({"rd": target}))
            cookie = "; ".join(self.headers.get_all("Cookie", []))
            auth_headers = {
                "Accept": "text/html", "Cookie": cookie,
                "X-Forwarded-Host": config["origin"].netloc,
                "X-Forwarded-Proto": config["origin"].scheme,
                "X-Forwarded-Uri": target,
            }
            cookies = []
            try:
                status, headers, _ = exchange(proxy, auth_headers)
                cookies = [(name, value) for name, value in headers if name.lower() == "set-cookie"]
                if status in {301, 302, 303, 307, 308}:
                    location = next((value for name, value in headers if name.lower() == "location"), "")
                    if not location or re.search(r"[\x00-\x1f\x7f]", location):
                        raise ValueError("Missing or invalid authentication redirect")
                    redirect = urljoin(urlunsplit(config["origin"]), location)
                    endpoint(redirect)
                    self.json_reply(200, {"redirectTo": redirect}, cookies)
                    return
                if status in {401, 403}:
                    self.json_reply(status, {"message": "Access denied"}, cookies)
                    return
                if not 200 <= status < 300:
                    self.json_reply(503, {"message": "Authentication service unavailable"}, cookies)
                    return

                # Forward only ordinary caller metadata and verified identity to the
                # configured backend. Caller-supplied identity headers never pass.
                backend_headers = {"Cookie": cookie}
                for name in ["Accept", "Accept-Language", "User-Agent"]:
                    if self.headers.get(name):
                        backend_headers[name] = self.headers[name]
                backend_headers.update({
                    "X-Forwarded-Host": config["origin"].netloc,
                    "X-Forwarded-Proto": config["origin"].scheme,
                })
                verified = {name.lower(): value for name, value in headers}
                for name in config["identity_headers"]:
                    if verified.get(name.lower()):
                        backend_headers[name] = verified[name.lower()]
                backend = upstream._replace(query=urlencode([(key, value) for key, value in query if key != "returnTo"]))
                backend_status, backend_response_headers, body = exchange(backend, backend_headers)
                if 300 <= backend_status < 400:
                    raise ValueError("Configuration backend returned an unexpected redirect")
                self.reply(backend_status, body, [*backend_response_headers, *cookies])
            except (OSError, ValueError, http.client.HTTPException):
                self.json_reply(503, {"message": "Bootstrap service unavailable"}, cookies)

    return BootstrapHandler


class BootstrapServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, *args, **kwargs):
        self.workers = threading.BoundedSemaphore(32)
        super().__init__(*args, **kwargs)

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(TIMEOUT)
        return connection, address

    def process_request(self, request, client_address):
        if not self.workers.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.workers.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.workers.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--listen", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    with open(args.config, encoding="utf-8") as source:
        config = configuration(json.load(source))
    with BootstrapServer((args.listen, args.port), handler(config)) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()

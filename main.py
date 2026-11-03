#!/usr/bin/env python3
"""Tiny request-inspector web server (standard library only).

Endpoints (any HTTP method is accepted):
    /text   -> plain-text report of the request
    /json   -> JSON report of the request

Run:
    python app.py [--host 0.0.0.0] [--port 8000] [--trust-proxy]

Examples:
    curl http://localhost:8000/text
    curl -X POST -d 'hello=world' http://localhost:8000/json
"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_PAYLOAD = 1024 * 1024  # 1 MiB cap on request bodies


class InspectHandler(BaseHTTPRequestHandler):
    server_version = "RequestInspector/1.0"
    trust_proxy = False  # set from CLI

    # ---- information gathering -------------------------------------------
    def client_ip(self):
        if self.trust_proxy:
            forwarded = self.headers.get("X-Forwarded-For")
            if forwarded:
                return forwarded.split(",")[0].strip()
            real_ip = self.headers.get("X-Real-IP")
            if real_ip:
                return real_ip.strip()
        return self.client_address[0]

    def read_payload(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            return b"", False
        data = self.rfile.read(min(length, MAX_PAYLOAD))
        return data, length > MAX_PAYLOAD

    def collect(self):
        body, truncated = self.read_payload()
        text = body.decode("utf-8", errors="replace")
        return {
            "client_ip": self.client_ip(),
            "user_agent": self.headers.get("User-Agent", ""),
            "method": self.command,
            "headers": {k: v for k, v in self.headers.items()},
            "payload": text,
            "payload_truncated": truncated,
        }

    # ---- rendering --------------------------------------------------------
    @staticmethod
    def render_text(info):
        lines = [
            f"Client IP:  {info['client_ip']}",
            f"User-Agent: {info['user_agent']}",
            f"Method:     {info['method']}",
            "Headers:",
        ]
        lines += [f"  {k}: {v}" for k, v in info["headers"].items()]
        lines.append("Payload:")
        lines.append(info["payload"] if info["payload"] else "  (empty)")
        if info["payload_truncated"]:
            lines.append(f"  [truncated at {MAX_PAYLOAD} bytes]")
        return "\n".join(lines) + "\n"

    def respond(self, status, content_type, body):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    # ---- dispatch ---------------------------------------------------------
    def handle_any(self):
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path == "/text":
            self.respond(200, "text/plain; charset=utf-8", self.render_text(self.collect()))
        elif path == "/json":
            body = json.dumps(self.collect(), indent=2) + "\n"
            self.respond(200, "application/json", body)
        elif path == "/":
            self.respond(200, "text/plain; charset=utf-8", self.render_text(self.collect()))
        else:
            self.respond(404, "text/plain; charset=utf-8", "Not found. Try /text or /json.\n")

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = handle_any
    do_HEAD = handle_any


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--trust-proxy", action="store_true",
                        help="use X-Forwarded-For / X-Real-IP for the client IP (only behind a trusted reverse proxy)")
    args = parser.parse_args()

    InspectHandler.trust_proxy = args.trust_proxy
    server = ThreadingHTTPServer((args.host, args.port), InspectHandler)
    print(f"Listening on http://{args.host}:{args.port}  (endpoints: /text, /json)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

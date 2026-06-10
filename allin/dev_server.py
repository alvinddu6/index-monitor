"""Local dev server — static files + CORS proxy (GET/POST, threaded)"""
import http.server
import urllib.request
import urllib.parse
import json
import socketserver
from pathlib import Path

PORT = 8080
ROOT = Path(__file__).resolve().parent

ALLOWED = [
    "hq.sinajs.cn", "money.finance.sina.com.cn",
    "stock.finance.sina.com.cn", "push2his.eastmoney.com",
    "push2.eastmoney.com", "www.sge.com.cn",
]

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):  self._route("GET")
    def do_POST(self): self._route("POST")

    def _route(self, method):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/proxy":
            self._handle_proxy(parsed, method)
        elif self.path == "/":
            self.path = "/index.html"
            super().do_GET()
        else:
            super().do_GET()

    def _handle_proxy(self, parsed, method):
        qs = urllib.parse.parse_qs(parsed.query)
        url = qs.get("url", [None])[0]
        ref = qs.get("ref", ["https://finance.sina.com.cn"])[0]
        if not url:
            return self._json({"error": "missing url"}, 400)
        try:
            host = urllib.parse.urlparse(url).hostname
            if not host or not any(host.endswith(a) for a in ALLOWED):
                return self._json({"error": f"domain not allowed: {host}"}, 403)
        except Exception:
            return self._json({"error": "bad url"}, 400)

        try:
            headers = {
                "Referer": ref,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0",
            }

            body = None
            if method == "POST":
                headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
                origin = qs.get("origin", [None])[0]
                if origin:
                    headers["Origin"] = origin
                xrw = qs.get("xrw", [None])[0]
                if xrw:
                    headers["X-Requested-With"] = xrw
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length) if length else None

            data = body
            if data:
                req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            else:
                req = urllib.request.Request(url, headers=headers)

            with urllib.request.urlopen(req, timeout=15) as resp:
                result = resp.read()

            self.send_response(200)
            if "json" in str(resp.headers.get("Content-Type", "")):
                self.send_header("Content-Type", "application/json; charset=utf-8")
            else:
                self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(result)
        except Exception as e:
            self._json({"error": str(e)}, 502)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def _json(self, data, code=200):
        b = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, fmt, *args):
        pass  # quiet

if __name__ == "__main__":
    server = socketserver.ThreadingTCPServer(("0.0.0.0", PORT), Handler)
    print(f"Dev server: http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        print("\nStopped.")

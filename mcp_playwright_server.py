import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from playwright.sync_api import sync_playwright


def navigate(url: str, screenshot: str = "page.png"):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=60000)
        page.wait_for_load_state("networkidle")

        page.screenshot(path=screenshot, full_page=True)
        text = page.inner_text("body")

        browser.close()

    return {
        "url": url,
        "screenshot": screenshot,
        "text": text[:6000]
    }


TOOLS = {
    "navigate": navigate
}


class InvokeHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/invoke":
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length))
        tool_name = body.get("tool")
        arguments = body.get("arguments", {})

        tool_fn = TOOLS.get(tool_name)
        if not tool_fn:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Unknown tool: {tool_name}"}).encode())
            return

        try:
            result = tool_fn(**arguments)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def log_message(self, format, *args):
        print(f"[playwright-server] {format % args}")


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 7001), InvokeHandler)
    print("[playwright-server] Listening on port 7001")
    server.serve_forever()

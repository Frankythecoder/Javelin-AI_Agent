import json
import os
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)


def create_pull_request(title: str, head: str, base: str = "main", body: str = ""):
    github_token = os.getenv("GITHUB_TOKEN")
    github_repo = os.getenv("GITHUB_REPO")

    if not github_token or not github_repo:
        return {"error": "GITHUB_TOKEN or GITHUB_REPO is not set. Check your .env file."}

    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github+json"
    }

    # Verify head branch exists before attempting the PR
    branches_resp = requests.get(
        f"https://api.github.com/repos/{github_repo}/branches",
        headers=headers
    )
    if branches_resp.status_code == 200:
        existing = [b["name"] for b in branches_resp.json()]
        if head not in existing:
            return {
                "error": f"Branch '{head}' does not exist in {github_repo}. Available branches: {existing}"
            }
        if head == base:
            return {
                "error": f"head '{head}' and base '{base}' are the same branch. A PR requires two different branches."
            }

    url = f"https://api.github.com/repos/{github_repo}/pulls"
    response = requests.post(url, headers=headers, json={
        "title": title,
        "head": head,
        "base": base,
        "body": body
    })

    if response.status_code >= 400:
        return {
            "status_code": response.status_code,
            "error": response.text
        }

    return response.json()



TOOLS = {
    "create_pull_request": create_pull_request
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
        print(f"[github-server] {format % args}")


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 7002), InvokeHandler)
    print("[github-server] Listening on port 7002")
    server.serve_forever()

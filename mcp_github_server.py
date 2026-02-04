import base64
import json
import os
import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)

server = FastMCP("github")


@server.tool()
def create_pull_request(title: str, head: str, base: str = "main", body: str = ""):
    github_token = os.getenv("GITHUB_TOKEN")
    github_repo = os.getenv("GITHUB_REPO")

    if not github_token or not github_repo:
        return json.dumps({"error": "GITHUB_TOKEN or GITHUB_REPO is not set. Check your .env file."})

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
            return json.dumps({
                "error": f"Branch '{head}' does not exist in {github_repo}. Available branches: {existing}"
            })
        if head == base:
            return json.dumps({
                "error": f"head '{head}' and base '{base}' are the same branch. A PR requires two different branches."
            })

    url = f"https://api.github.com/repos/{github_repo}/pulls"
    response = requests.post(url, headers=headers, json={
        "title": title,
        "head": head,
        "base": base,
        "body": body
    })

    if response.status_code >= 400:
        return json.dumps({
            "status_code": response.status_code,
            "error": response.text
        })

    return json.dumps(response.json())


@server.tool()
def create_branch(name: str, source: str = "main"):
    github_token = os.getenv("GITHUB_TOKEN")
    github_repo = os.getenv("GITHUB_REPO")

    if not github_token or not github_repo:
        return json.dumps({"error": "GITHUB_TOKEN or GITHUB_REPO is not set. Check your .env file."})

    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github+json"
    }

    # Resolve the SHA of the source branch
    source_resp = requests.get(
        f"https://api.github.com/repos/{github_repo}/branches/{source}",
        headers=headers
    )
    if source_resp.status_code != 200:
        return json.dumps({"error": f"Source branch '{source}' does not exist in {github_repo}."})

    sha = source_resp.json()["commit"]["sha"]

    # Create the new branch ref
    response = requests.post(
        f"https://api.github.com/repos/{github_repo}/git/refs",
        headers=headers,
        json={"ref": f"refs/heads/{name}", "sha": sha}
    )

    if response.status_code == 422:
        return json.dumps({"error": f"Branch '{name}' already exists in {github_repo}."})

    if response.status_code >= 400:
        return json.dumps({"status_code": response.status_code, "error": response.text})

    return json.dumps({"message": f"Branch '{name}' created from '{source}'.", "sha": sha})


@server.tool()
def commit_file(path: str, content: str, message: str, branch: str):
    github_token = os.getenv("GITHUB_TOKEN")
    github_repo = os.getenv("GITHUB_REPO")

    if not github_token or not github_repo:
        return json.dumps({"error": "GITHUB_TOKEN or GITHUB_REPO is not set. Check your .env file."})

    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github+json"
    }

    encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    # Check if the file already exists on the target branch
    check_resp = requests.get(
        f"https://api.github.com/repos/{github_repo}/contents/{path}",
        headers=headers,
        params={"ref": branch}
    )

    if check_resp.status_code == 200:
        # File exists — PUT to update, requires the existing file's SHA
        file_sha = check_resp.json()["sha"]
        response = requests.put(
            f"https://api.github.com/repos/{github_repo}/contents/{path}",
            headers=headers,
            json={
                "message": message,
                "content": encoded_content,
                "sha": file_sha,
                "branch": branch
            }
        )
    else:
        # File does not exist — PUT to create (no sha needed)
        response = requests.put(
            f"https://api.github.com/repos/{github_repo}/contents/{path}",
            headers=headers,
            json={
                "message": message,
                "content": encoded_content,
                "branch": branch
            }
        )

    if response.status_code >= 400:
        return json.dumps({"status_code": response.status_code, "error": response.text})

    return json.dumps({
        "message": f"File '{path}' committed to '{branch}'.",
        "commit_sha": response.json().get("commit", {}).get("sha", "")
    })


@server.tool()
def commit_local_file(local_path: str, message: str, branch: str, remote_path: str = ""):
    if not os.path.isabs(local_path):
        resolved_path = os.path.join(BASE_DIR, local_path)
    else:
        resolved_path = local_path

    if not os.path.isfile(resolved_path):
        return json.dumps({"error": f"File not found: {resolved_path}"})

    try:
        with open(resolved_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return json.dumps({"error": f"Failed to read '{resolved_path}': {str(e)}"})

    if not remote_path:
        remote_path = os.path.basename(local_path) if os.path.isabs(local_path) else local_path

    return commit_file(path=remote_path, content=content, message=message, branch=branch)


if __name__ == "__main__":
    server.run()

import os
import requests
from typing import Dict, Any
from django.conf import settings
from agents.control import ToolDefinition


def _github_mcp_call(tool_name, args):
    import asyncio
    import sys
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters

    async def _call():
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-B", os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_github_server.py")],
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, args)
                return result.content[0].text if result.content else ""

    try:
        return asyncio.run(_call())
    except Exception as e:
        return f"GitHub MCP error: {e}"


def github_create_pr_tool(args):
    return _github_mcp_call("create_pull_request", args)


def github_create_branch_tool(args):
    return _github_mcp_call("create_branch", args)


def github_commit_file_tool(args):
    return _github_mcp_call("commit_file", args)


def github_commit_local_file_tool(args):
    return _github_mcp_call("commit_local_file", args)


def create_github_issue_tool(args: Dict[str, Any]) -> str:
    """Create a GitHub issue on the configured repository."""
    try:
        title = args.get('title', '')
        body = args.get('body', '')
        labels = args.get('labels', [])
        assignees = args.get('assignees', [])

        if not title:
            return "Error: Issue title is required."

        # Get GitHub credentials from settings
        github_token = getattr(settings, 'GITHUB_TOKEN', None)
        github_repo = getattr(settings, 'GITHUB_REPO', None)

        if not github_token or not github_repo:
            return "Error: GITHUB_TOKEN or GITHUB_REPO not configured in settings."

        # GitHub API endpoint
        url = f"https://api.github.com/repos/{github_repo}/issues"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }

        payload = {
            "title": title,
            "body": body
        }

        if labels:
            payload["labels"] = labels if isinstance(labels, list) else [labels]
        if assignees:
            payload["assignees"] = assignees if isinstance(assignees, list) else [assignees]

        response = requests.post(url, headers=headers, json=payload)

        if response.status_code == 201:
            issue_data = response.json()
            issue_number = issue_data.get('number')
            issue_url = issue_data.get('html_url')
            return f"Successfully created issue #{issue_number}: {issue_url}"
        else:
            return f"Error creating issue: {response.status_code} - {response.text}"

    except Exception as e:
        return f"Error: {str(e)}"


GITHUB_CREATE_BRANCH_DEFINITION = ToolDefinition(
    name="github_create_branch",
    description="Step 1 of 3: Create a new branch on the configured GitHub repository. Call this FIRST before committing files or creating a PR. Do NOT use run_code with git for GitHub operations \u2014 use these MCP tools instead.",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Name of the new branch"},
            "source": {"type": "string", "description": "Branch to create from (default: main)"}
        },
        "required": ["name"]
    },
    function=github_create_branch_tool,
    requires_approval=True
)

GITHUB_COMMIT_FILE_DEFINITION = ToolDefinition(
    name="github_commit_file",
    description="Step 2 of 3: Commit a file with given content to a branch on the configured GitHub repository. Use when file content is provided in the prompt. Call AFTER github_create_branch, BEFORE github_create_pr.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path in the repo"},
            "content": {"type": "string", "description": "Full file content to commit"},
            "message": {"type": "string", "description": "Commit message"},
            "branch": {"type": "string", "description": "Target branch"}
        },
        "required": ["path", "content", "message", "branch"]
    },
    function=github_commit_file_tool,
    requires_approval=True
)

GITHUB_COMMIT_LOCAL_FILE_DEFINITION = ToolDefinition(
    name="github_commit_local_file",
    description="Step 2 of 3: Read a local file and commit it to a branch on the configured GitHub repository. Use when committing an existing local file. Call AFTER github_create_branch, BEFORE github_create_pr.",
    parameters={
        "type": "object",
        "properties": {
            "local_path": {"type": "string", "description": "Local file path to read"},
            "message": {"type": "string", "description": "Commit message"},
            "branch": {"type": "string", "description": "Target branch"},
            "remote_path": {"type": "string", "description": "Path in repo (defaults to filename)"}
        },
        "required": ["local_path", "message", "branch"]
    },
    function=github_commit_local_file_tool,
    requires_approval=True
)

GITHUB_MCP_DEFINITION = ToolDefinition(
    name="github_create_pr",
    description="Step 3 of 3: Create a GitHub pull request on the configured repository. ONLY call this AFTER a branch has been created (github_create_branch) and at least one file committed to it (github_commit_file or github_commit_local_file). Do NOT use run_code with git for any GitHub operations.",
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Title for the pull request"},
            "head": {"type": "string", "description": "The source branch with changes"},
            "base": {"type": "string", "description": "The target branch (default: main)"},
            "body": {"type": "string", "description": "Pull request description"}
        },
        "required": ["title", "head"]
    },
    function=github_create_pr_tool,
    requires_approval=True
)


CREATE_GITHUB_ISSUE_DEFINITION = ToolDefinition(
    name="create_github_issue",
    description="Create a GitHub issue on the configured repository. Use this to track bugs, feature requests, tasks, or automatically create tickets when code execution fails or tests fail. Issues can be labeled and assigned.",
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "The title of the issue (required). Keep it concise and descriptive."
            },
            "body": {
                "type": "string",
                "description": "The body/description of the issue. Supports markdown formatting. Include error details, stack traces, reproduction steps, etc."
            },
            "labels": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional array of label names to apply (e.g., ['bug', 'high-priority', 'test-failure'])."
            },
            "assignees": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional array of GitHub usernames to assign the issue to."
            }
        },
        "required": ["title"]
    },
    function=create_github_issue_tool,
    requires_approval=True
)

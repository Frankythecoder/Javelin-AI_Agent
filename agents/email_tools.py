import os
import json
import time
import re
import subprocess
import platform
import webbrowser
import imaplib
import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formatdate, make_msgid
from email.policy import SMTP
from urllib.parse import quote
from typing import Dict, Any, List
from django.conf import settings
from agents.control import ToolDefinition
from agents.helpers import _normalize_url


def playwright_mcp_tool(args):
    if "url" in args:
        try:
            args["url"] = _normalize_url(args["url"])
        except ValueError as e:
            return f"Playwright MCP error: {e}"

    import asyncio
    from playwright.async_api import async_playwright
    from mcp_servers.playwright_server import _toggle_www

    url = args.get("url", "")
    screenshot = args.get("screenshot", "page.png")

    async def _navigate():
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()

                try:
                    await page.goto(url, timeout=60000)
                except Exception:
                    alt_url = _toggle_www(url)
                    try:
                        await page.goto(alt_url, timeout=60000)
                    except Exception as retry_err:
                        return json.dumps({
                            "error": f"Navigation failed for both {url} and {alt_url}: {retry_err}"
                        })
                    # Use the successful alt URL for the response
                    args["url"] = alt_url

                try:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass

                await page.screenshot(path=screenshot, full_page=True)
                text = await page.inner_text("body")

                return json.dumps({
                    "url": args.get("url", url),
                    "screenshot": screenshot,
                    "text": text[:6000]
                })
            except Exception as e:
                return json.dumps({"error": f"Browser error: {e}"})
            finally:
                await browser.close()

    try:
        return asyncio.run(_navigate())
    except Exception as e:
        return f"Playwright MCP error: {e}"


def create_gmail_draft(recipient: str, subject: str, body: str, attachments: List[str]) -> str:
    """Create a draft in Gmail via IMAP."""
    user = getattr(settings, 'GMAIL_SENDER_ADDRESS', None)
    password = getattr(settings, 'GMAIL_APP_PASSWORD', None)

    if not user or not password:
        return "Error: GMAIL_SENDER_ADDRESS or GMAIL_APP_PASSWORD not configured in settings."

    try:
        # Create message with robust structure
        msg = MIMEMultipart('mixed')
        msg['To'] = recipient
        msg['From'] = user
        msg['Subject'] = subject
        msg['Date'] = formatdate(localtime=True)
        msg['Message-ID'] = make_msgid()

        # Create the body container (multipart/alternative)
        body_part = MIMEMultipart('alternative')

        # Add plain text version
        body_part.attach(MIMEText(body, 'plain'))

        # Add HTML version (simple conversion)
        html_body = body.replace('\n', '<br>')
        body_part.attach(MIMEText(f"<html><body>{html_body}</body></html>", 'html'))

        # Attach body container to the main message
        msg.attach(body_part)

        for path in attachments:
            if os.path.exists(path):
                filename = os.path.basename(path)
                part = MIMEBase('application', "octet-stream")
                try:
                    with open(path, 'rb') as file:
                        part.set_payload(file.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
                    msg.attach(part)
                except Exception as file_err:
                    return f"Error: Reading attachment {path} failed: {str(file_err)}"
            else:
                return f"Error: Attachment file not found at {path}"

        # Connect to Gmail IMAP
        try:
            imap = imaplib.IMAP4_SSL("imap.gmail.com")
            imap.login(user, password)
        except imaplib.IMAP4.error as auth_err:
            return f"Error: Authentication failed. Please ensure: 1. Your GMAIL_PASSWORD in .env is a 16-character App Password. 2. IMAP is enabled. Original error: {str(auth_err)}"
        except Exception as conn_err:
            return f"Error: Failed to connect to Gmail IMAP: {str(conn_err)}"

        # Try to find the Drafts folder
        status, folders = imap.list()
        draft_folder = None
        if status == 'OK':
            for folder in folders:
                folder_str = folder.decode('utf-8')
                # Gmail drafts folder has the \Drafts attribute
                if '\\Drafts' in folder_str:
                    # The folder name is usually the last quoted string
                    matches = re.findall(r'"([^"]+)"', folder_str)
                    if matches:
                        draft_folder = matches[-1]
                    break

        if not draft_folder:
            # Fallback for some configurations
            draft_folder = "[Gmail]/Drafts"

        # Append to drafts
        try:
            # Ensure draft_folder is quoted if it contains spaces or special characters
            quoted_folder = draft_folder
            if not draft_folder.startswith('"') and any(c in draft_folder for c in ' []/'):
                quoted_folder = f'"{draft_folder}"'

            # Use CRLF for line endings as required by IMAP
            msg_bytes = msg.as_bytes(policy=SMTP)
            res, detail = imap.append(quoted_folder, r'(\Draft)', imaplib.Time2Internaldate(time.time()), msg_bytes)
            if res != 'OK':
                return f"Error: IMAP APPEND failed: {res} - {str(detail)}"
        except Exception as append_err:
            return f"Error: Exception during IMAP APPEND to '{draft_folder}': {str(append_err)}"

        imap.logout()
        return "OK"
    except Exception as e:
        return f"Error: {str(e)}"


def find_chrome_profile_for_email(email: str) -> str:
    """Attempt to find the Chrome profile name associated with a specific email."""
    if not email:
        return "Default"

    system = platform.system()
    if system == "Windows":
        base_path = os.path.expandvars(r"%LocalAppData%\Google\Chrome\User Data")
    elif system == "Darwin":
        base_path = os.path.expanduser("~/Library/Application Support/Google/Chrome")
    else:
        base_path = os.path.expanduser("~/.config/google-chrome")

    if not os.path.exists(base_path):
        return "Default"

    try:
        profiles = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d)) and (d == "Default" or d.startswith("Profile"))]

        for profile in profiles:
            pref_path = os.path.join(base_path, profile, "Preferences")
            if os.path.exists(pref_path):
                try:
                    with open(pref_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if email.lower() in content.lower():
                            return profile
                except Exception:
                    continue
    except Exception:
        pass

    return "Default"


def open_url_in_chrome_profile(url: str, email: str = None) -> bool:
    """Attempt to open a URL in a specific Chrome profile."""
    # Priority: 1. Explicitly configured directory, 2. Auto-discovered directory, 3. Default
    profile = getattr(settings, 'CHROME_PROFILE_DIRECTORY', None)
    if not profile or profile == "Default":
        profile = find_chrome_profile_for_email(email)

    system = platform.system()

    try:
        if system == "Windows":
            # Common paths for Chrome on Windows
            chrome_paths = [
                os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")
            ]
            for path in chrome_paths:
                if os.path.exists(path):
                    subprocess.Popen([path, f"--profile-directory={profile}", url])
                    return True
        elif system == "Darwin":  # macOS
            subprocess.Popen(["open", "-a", "Google Chrome", "--args", f"--profile-directory={profile}", url])
            return True
        elif system == "Linux":
            subprocess.Popen(["google-chrome", f"--profile-directory={profile}", url])
            return True
    except Exception:
        pass

    # Fallback to default browser
    return webbrowser.open_new_tab(url)


def open_gmail_and_compose_tool(args: Dict[str, Any]) -> str:
    user = getattr(settings, 'GMAIL_SENDER_ADDRESS', '')
    recipient = args.get('recipient', '').strip()
    subject = args.get('subject', '')
    body = args.get('body', '')
    attachments = args.get('attachments', [])
    if not recipient:
        return "Error: recipient is required"

    if isinstance(attachments, str):
        attachments = [attachments]

    # Use user-specific URL if available
    base_url = f"https://mail.google.com/mail/u/{user}/" if user else "https://mail.google.com/mail/"

    # If there are attachments, we create a draft via IMAP because web URL doesn't support them
    if attachments:
        draft_result = create_gmail_draft(recipient, subject, body, attachments)
        if draft_result == "OK":
            drafts_url = f"{base_url}#drafts"
            try:
                opened = open_url_in_chrome_profile(drafts_url, user)
                if opened:
                    return f"A draft with the attachments has been created in your Gmail Drafts ({user}). I've opened your Drafts folder in the browser (Profile: {find_chrome_profile_for_email(user)}). Please review and send it."
                return f"A draft with the attachments has been created in your Gmail Drafts ({user}). Please open {drafts_url} to review and send it."
            except:
                return f"A draft with the attachments has been created in your Gmail Drafts ({user}). Please open {drafts_url} to review and send it."
        else:
            # If draft fails, we still want to open the compose window as a fallback
            fallback_msg = f"Failed to create draft with attachments: {draft_result}."

            query = [f"to={quote(recipient)}"]
            if subject:
                query.append(f"su={quote(subject)}")
            if body:
                query.append(f"body={quote(body)}")
            compose_url = f"{base_url}?view=cm&fs=1&tf=1&" + "&".join(query)

            try:
                opened = open_url_in_chrome_profile(compose_url, user)
                if opened:
                    return f"{fallback_msg} I've opened the standard compose window for you instead (Profile: {find_chrome_profile_for_email(user)}). Please attach the files manually and send."
                return f"{fallback_msg} Please open this link to compose manually: {compose_url}"
            except:
                return f"{fallback_msg} Please open this link to compose manually: {compose_url}"

    query = [f"to={quote(recipient)}"]
    if subject:
        query.append(f"su={quote(subject)}")
    if body:
        query.append(f"body={quote(body)}")
    compose_url = f"{base_url}?view=cm&fs=1&tf=1&" + "&".join(query)

    try:
        opened = open_url_in_chrome_profile(compose_url, user)
        if opened:
            return f"Gmail compose window for {user} opened in your browser (Profile: {find_chrome_profile_for_email(user)}). Log in if prompted, review the message, and press Send."
        return f"Open this link manually to compose the email: {compose_url}"
    except Exception as e:
        return f"Error launching browser automatically ({str(e)}). Open this link manually: {compose_url}"


OPEN_GMAIL_AND_COMPOSE_DEFINITION = ToolDefinition(
    name="open_gmail_and_compose",
    description="Open Gmail in a browser and compose an email. If attachments are provided, a draft will be created automatically for you to review and send.",
    parameters={
        "type": "object",
        "properties": {
            "recipient": {
                "type": "string",
                "description": "Email address to populate in the compose window."
            },
            "subject": {
                "type": "string",
                "description": "Optional subject line to insert."
            },
            "body": {
                "type": "string",
                "description": "Optional body text to type into the message editor."
            },
            "attachments": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "List of absolute or relative file paths to be attached automatically via a draft. You have access to the entire filesystem."
            }
        },
        "required": ["recipient"]
    },
    function=open_gmail_and_compose_tool
)


PLAYWRIGHT_MCP_DEFINITION = ToolDefinition(
    name="playwright_navigate",
    description="Navigate websites using Playwright MCP server",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "screenshot": {"type": "string"}
        },
        "required": ["url"]
    },
    function=playwright_mcp_tool,
    requires_approval=True
)

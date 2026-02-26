import json
from playwright.async_api import async_playwright
from mcp.server.fastmcp import FastMCP

server = FastMCP("playwright")


def _toggle_www(url: str) -> str:
    """Toggle the www. prefix on a URL for retry purposes."""
    for scheme in ("https://www.", "http://www."):
        if url.startswith(scheme):
            return url.replace(scheme, scheme.replace("www.", ""), 1)
    for scheme in ("https://", "http://"):
        if url.startswith(scheme):
            return url.replace(scheme, scheme + "www.", 1)
    return url


@server.tool()
async def navigate(url: str, screenshot: str = "page.png"):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()

            # First attempt with the original URL
            try:
                await page.goto(url, timeout=60000)
            except Exception:
                # Retry with toggled www. variant
                alt_url = _toggle_www(url)
                try:
                    await page.goto(alt_url, timeout=60000)
                    url = alt_url  # update so the response reflects what actually loaded
                except Exception as retry_err:
                    return json.dumps({
                        "error": f"Navigation failed for both {url} and {alt_url}: {retry_err}"
                    })

            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass  # proceed with whatever has loaded

            await page.screenshot(path=screenshot, full_page=True)
            text = await page.inner_text("body")

            return json.dumps({
                "url": url,
                "screenshot": screenshot,
                "text": text[:6000]
            })
        except Exception as e:
            return json.dumps({
                "error": f"Browser error: {e}"
            })
        finally:
            await browser.close()


if __name__ == "__main__":
    server.run()

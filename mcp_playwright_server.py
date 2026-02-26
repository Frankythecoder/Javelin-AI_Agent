import json
from playwright.async_api import async_playwright
from mcp.server.fastmcp import FastMCP

server = FastMCP("playwright")


@server.tool()
async def navigate(url: str, screenshot: str = "page.png"):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, timeout=60000)
        await page.wait_for_load_state("networkidle")

        await page.screenshot(path=screenshot, full_page=True)
        text = await page.inner_text("body")

        await browser.close()

    return json.dumps({
        "url": url,
        "screenshot": screenshot,
        "text": text[:6000]
    })


if __name__ == "__main__":
    server.run()

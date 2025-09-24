import asyncio
import os

from playwright.async_api import async_playwright


BASE_URL = os.environ.get("ARCHON_UI_URL", "http://archon-ui:3737")
OUT_DIR = "/app/src/screenshots"


async def ensure_out_dir():
    os.makedirs(OUT_DIR, exist_ok=True)


async def shot(page, name: str):
    await page.screenshot(path=os.path.join(OUT_DIR, name), full_page=True)


async def capture():
    await ensure_out_dir()
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()

        # 1) Knowledge Base with Embeddings quick link
        await page.goto(f"{BASE_URL}/", wait_until="networkidle")
        await shot(page, "kb-embeddings-link.png")

        # 2) Embeddings health page
        await page.goto(f"{BASE_URL}/embeddings", wait_until="load")
        try:
            await page.wait_for_timeout(1500)
        except Exception:
            pass
        await shot(page, "embeddings-health.png")

        # 3) Embeddings dry-run backfill (default is dry_run=true)
        try:
            # Click backfill button
            await page.get_by_role("button", name="Dry Run Backfill").click()
            # Wait a moment for toast/banner to update
            await page.wait_for_timeout(1000)
        except Exception:
            pass
        await shot(page, "embeddings-backfill-dryrun.png")

        # 4) MCP session helpers
        await page.goto(f"{BASE_URL}/mcp", wait_until="load")
        await page.wait_for_timeout(1500)

        # Init session
        try:
            await page.get_by_role("button", name="Init Session").click()
            await page.wait_for_timeout(800)
        except Exception:
            pass
        await shot(page, "mcp-session-init.png")

        # Session info
        try:
            await page.get_by_role("button", name="Session Info").click()
            await page.wait_for_timeout(800)
        except Exception:
            pass
        await shot(page, "mcp-session-info.png")

        await browser.close()


def main():
    asyncio.run(capture())


if __name__ == "__main__":
    main()

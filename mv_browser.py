import asyncio
import os
import pathlib
import tempfile
import shutil
from playwright.async_api import async_playwright, TimeoutError as BrowserTimeout

MV_PAGE = "https://mv.tools/pt-br/tools/video-downloader"

async def inspect_mv(url: str):
    """Experimental browser UI check. No private endpoints, session spoofing or CAPTCHA bypass."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, executable_path="/usr/bin/chromium", args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            page = await browser.new_page(locale="pt-BR", accept_downloads=True)
            response = await page.goto(MV_PAGE, wait_until="domcontentloaded", timeout=35000)
            await page.locator("#video-url").fill(url, timeout=12000)
            await page.wait_for_timeout(4000)
            submit = page.locator("form.video-download-form button[type=submit]")
            return {
                "site_status": response.status if response else None,
                "input_matches": await page.locator("#video-url").input_value() == url,
                "submit_enabled": await submit.is_enabled(),
                "submit_text": (await submit.inner_text()).strip()[:140],
                "page_title": (await page.title())[:140],
            }
        finally:
            await browser.close()

async def attempt_mv_download(url: str, max_bytes: int):
    """Only use the site's visible public UI; fail on login, captcha, or access restrictions."""
    folder = tempfile.mkdtemp(prefix="mv-browser-")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, executable_path="/usr/bin/chromium", args=["--no-sandbox", "--disable-dev-shm-usage"])
            try:
                page = await browser.new_page(locale="pt-BR", accept_downloads=True)
                await page.goto(MV_PAGE, wait_until="domcontentloaded", timeout=35000)
                await page.locator("#video-url").fill(url)
                submit = page.locator("form.video-download-form button[type=submit]")
                try:
                    await submit.wait_for(state="visible", timeout=12000)
                    await page.wait_for_function("() => {const b=document.querySelector('form.video-download-form button[type=submit]');return b && !b.disabled}", timeout=15000)
                except BrowserTimeout:
                    raise RuntimeError("O MV Tools exige login ou não habilitou o download no navegador automatizado")
                await submit.click()
                # The service may prepare a file asynchronously. Observe its public download action.
                try:
                    async with page.expect_download(timeout=75000) as pending:
                        await page.get_by_role("button", name="Baixar", exact=False).last.click(timeout=60000)
                    download = await pending.value
                except (BrowserTimeout, Exception) as e:
                    raise RuntimeError("O MV Tools não disponibilizou um download automatizável pela interface pública") from e
                dest = pathlib.Path(folder) / "video.mp4"
                await download.save_as(str(dest))
                if not dest.exists() or dest.stat().st_size < 1024 or dest.stat().st_size > max_bytes:
                    raise RuntimeError("Arquivo inválido ou acima do limite")
                return folder, str(dest)
            finally:
                await browser.close()
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise

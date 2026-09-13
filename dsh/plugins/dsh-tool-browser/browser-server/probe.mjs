import asyncio
from playwright.async_api import async_playwright
async def main():
    try:
        async with async_playwright() as p:
            b=await p.chromium.launch(args=["--no-sandbox","--disable-dev-shm-usage"])
            pg=await b.new_page()
            await pg.goto("about:blank", timeout=15000)
            print("CHROMIUM_OK version=", await b.version())
            await b.close()
    except Exception as e:
        print("CHROMIUM_ERR:", repr(e))
asyncio.run(main())
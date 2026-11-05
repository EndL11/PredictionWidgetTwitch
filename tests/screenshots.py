"""
Генерує скріншоти демо-режиму в docs/ (поверх кольорового фону, щоб було видно прозорість).
Запуск: python tests/screenshots.py [--chrome /path/to/chrome]   (~45 с)
"""
import asyncio, sys, pathlib
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
URL = (ROOT / "widget.html").as_uri() + "?demo=1"
exe = sys.argv[sys.argv.index("--chrome") + 1] if "--chrome" in sys.argv else None

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=exe)
        pg = await b.new_page(viewport={"width": 680, "height": 360})
        await pg.goto(URL)
        await pg.add_style_tag(content="html{background:linear-gradient(135deg,#5a7d4a,#c9a46a 50%,#6d8fb0)!important}")
        await pg.wait_for_timeout(10000)
        await pg.screenshot(path=str(ROOT / "docs/screenshot-active.png"))
        await pg.wait_for_timeout(34000)   # demo: lock at 30s, end at 40s
        await pg.screenshot(path=str(ROOT / "docs/screenshot-results.png"))
        await b.close()

asyncio.run(main())

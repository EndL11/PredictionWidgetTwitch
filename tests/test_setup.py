"""
Автотест сторінки налаштувань StreamerTools (setup/): вкладки, генерація посилання таймера, OAuth state.
Запуск:  python tests/test_setup.py [--chrome /path/to/chrome]
"""
import asyncio, sys, pathlib
from playwright.async_api import async_playwright

URL = (pathlib.Path(__file__).resolve().parent.parent / "setup" / "index.html").as_uri()
exe = sys.argv[sys.argv.index("--chrome") + 1] if "--chrome" in sys.argv else None

async def main():
    fails = []
    def check(name, cond):
        print(("PASS " if cond else "FAIL ") + name)
        if not cond: fails.append(name)

    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=exe)
        pg = await b.new_page()
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        on = lambda tab: pg.evaluate(f"document.getElementById('tab-{tab}').classList.contains('on')")

        # 1. вкладки
        await pg.goto(URL)
        check("за замовчуванням — огляд", await on("overview"))
        await pg.click("nav a[data-tab=timer]"); await pg.wait_for_timeout(100)  # hashchange асинхронний
        check("клік відкриває вкладку таймера", await on("timer") and not await on("overview"))
        await pg.goto(URL + "#predictions"); await pg.reload()
        check("#predictions відкриває прогнози", await on("predictions"))
        check("стиль прогнозів за замовчуванням — GTA 6", await pg.evaluate("document.getElementById('theme').value") == "vice")

        # 2. посилання таймера з керуванням з чату
        await pg.goto(URL + "#timer"); await pg.reload()
        await pg.fill("#t-channel", "@Some_Streamer")
        await pg.click("#t-make")
        out = await pg.evaluate("document.getElementById('t-out').textContent")
        check(f"посилання таймера ({out.split('/')[-1]})", out.endswith("/timer/#channel=some_streamer&theme=vice"))
        await pg.fill("#t-channel", "bad name!")
        await pg.click("#t-make")
        check("невалідний логін — помилка", await pg.evaluate("document.getElementById('t-msg').className") == "err")
        await pg.select_option("#t-mode", "start"); await pg.select_option("#t-theme", "sa")
        await pg.click("#t-make")
        out = await pg.evaluate("document.getElementById('t-out').textContent")
        check("режим від часу старту", "#start=" in out and "theme=sa" in out and "channel" not in out)

        # 3. повернення з Twitch: підроблений state відхиляється, хеш прибирається
        await pg.goto(URL + "#access_token=fake&state=evil"); await pg.reload()
        check("чужий state відхилено", await pg.evaluate("document.getElementById('redir').value") == ""
              and await pg.evaluate("location.hash") == "#predictions" and await on("predictions"))

        check("немає JS-помилок " + str(errs), not errs)
        await b.close()
    sys.exit(1 if fails else 0)

asyncio.run(main())

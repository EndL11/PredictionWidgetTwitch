"""
Автотест віджета таймера марафону.
Запуск:  python tests/test_timer.py [--chrome /path/to/chrome]
"""
import asyncio, sys, pathlib, time
from playwright.async_api import async_playwright

URL = (pathlib.Path(__file__).resolve().parent.parent / "timer" / "index.html").as_uri()
exe = sys.argv[sys.argv.index("--chrome") + 1] if "--chrome" in sys.argv else None

async def main():
    fails = []
    def check(name, cond):
        print(("PASS " if cond else "FAIL ") + name)
        if not cond: fails.append(name)

    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=exe)
        pg = await b.new_page(viewport={"width": 1920, "height": 1080})
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        clock = lambda: pg.evaluate("document.getElementById('clock').textContent")

        # 1. рахує вгору від start, напис за замовчуванням
        start = int(time.time() * 1000) - (26 * 3600 + 3 * 60 + 7) * 1000  # 26 год 3 хв 7 с тому
        await pg.goto(f"{URL}#start={start}")
        await pg.wait_for_timeout(300)
        c = await clock()
        check(f"рахує від старту, з днями ({c})", c in ("1Д 02:03:07", "1Д 02:03:08"))
        check("напис МАРАФОН GTA VI", await pg.evaluate("document.getElementById('label').textContent") == "МАРАФОН GTA VI")

        # 2. «перезапуск OBS»: перезавантаження сторінки не скидає час
        await pg.wait_for_timeout(1200)
        await pg.reload(); await pg.wait_for_timeout(300)
        c2 = await clock()
        check(f"після перезавантаження не скинувся ({c2})", c2 in ("1Д 02:03:08", "1Д 02:03:09", "1Д 02:03:10"))

        await pg.goto(f"{URL}#start={start + 3 * 3600 * 1000}"); await pg.reload(); await pg.wait_for_timeout(300)
        c4 = await clock()
        check(f"менше доби — без днів ({c4})", c4.startswith("23:03:"))
        w = await pg.evaluate("[document.getElementById('clock').getBoundingClientRect().width, innerWidth]")
        await pg.goto(f"{URL}#start={start - 9 * 86400 * 1000}&theme=sa"); await pg.reload(); await pg.wait_for_timeout(300)
        w2 = await pg.evaluate("document.getElementById('clock').getBoundingClientRect().width")
        check(f"«10Д ...» у темі sa вміщається ({w2:.0f} <= {w[1]})", w2 <= w[1])

        # 3. зворотний відлік до end і зупинка на нулі
        end = int(time.time() * 1000) + 90 * 1000
        await pg.goto(f"{URL}#end={end}&theme=hud&title=%3Cb%3Ex%3C%2Fb%3E"); await pg.reload(); await pg.wait_for_timeout(300)
        c3 = await clock()
        check(f"зворотний відлік ({c3})", c3 in ("00:01:30", "00:01:29"))
        check("title виводиться як текст", await pg.evaluate("document.getElementById('label').textContent") == "<b>x</b>")
        await pg.goto(f"{URL}#end={end - 200000}"); await pg.reload(); await pg.wait_for_timeout(300)
        check("після кінця показує нулі", await clock() == "00:00:00")

        await pg.goto(f"{URL}#start={start}&theme=sa"); await pg.reload(); await pg.wait_for_timeout(200)
        check("theme=sa: білий годинник", await pg.evaluate(
            "document.body.classList.contains('sa') && getComputedStyle(document.getElementById('clock')).color === 'rgb(242, 242, 242)'"))

        # 4. без параметрів — генератор посилання
        await pg.goto(URL); await pg.reload()
        await pg.click("#f-make")
        out = await pg.evaluate("document.getElementById('out').textContent")
        check(f"генератор дає посилання з start ({out[-60:]})", "#start=" in out and "theme=vice" in out)

        check("немає JS-помилок " + str(errs), not errs)
        await b.close()
    sys.exit(1 if fails else 0)

asyncio.run(main())

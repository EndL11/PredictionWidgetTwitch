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
        check(f"рахує від старту, з днями ({c})", c in ("1 ДЕНЬ 02:03:07", "1 ДЕНЬ 02:03:08"))
        check("напис МАРАФОН GTA VI", await pg.evaluate("document.getElementById('label').textContent") == "МАРАФОН GTA VI")

        # 2. «перезапуск OBS»: перезавантаження сторінки не скидає час
        await pg.wait_for_timeout(1200)
        await pg.reload(); await pg.wait_for_timeout(300)
        c2 = await clock()
        check(f"після перезавантаження не скинувся ({c2})", c2 in ("1 ДЕНЬ 02:03:08", "1 ДЕНЬ 02:03:09", "1 ДЕНЬ 02:03:10"))

        await pg.goto(f"{URL}#start={start + 3 * 3600 * 1000}"); await pg.reload(); await pg.wait_for_timeout(300)
        c4 = await clock()
        check(f"менше доби — без днів ({c4})", c4.startswith("23:03:"))
        w = await pg.evaluate("[document.getElementById('clock').getBoundingClientRect().width, innerWidth]")
        await pg.goto(f"{URL}#start={start - 9 * 86400 * 1000}&theme=sa"); await pg.reload(); await pg.wait_for_timeout(300)
        w2 = await pg.evaluate("document.getElementById('clock').getBoundingClientRect().width")
        check(f"«10 ДНІВ ...» у темі sa вміщається ({w2:.0f} <= {w[1]})", w2 <= w[1])
        check("відмінки днів", await pg.evaluate("[1,2,4,5,11,12,21,22,25,101,111].map(daysWord).join()") == "ДЕНЬ,ДНІ,ДНІ,ДНІВ,ДНІВ,ДНІВ,ДЕНЬ,ДНІ,ДНІВ,ДЕНЬ,ДНІВ")
        # окремі розміри напису й цифр: напис 200% стає вдвічі більшим відносно цифр
        sizes = "(() => { const l = document.getElementById('label').getBoundingClientRect().height, c = document.getElementById('clock').getBoundingClientRect().height; return l / c; })()"
        await pg.goto(f"{URL}#start={start}"); await pg.reload(); await pg.wait_for_timeout(300)
        r1 = await pg.evaluate(sizes)
        await pg.goto(f"{URL}#start={start}&title_size=200"); await pg.reload(); await pg.wait_for_timeout(300)
        r2 = await pg.evaluate(sizes)
        check(f"title_size=200 удвічі збільшує напис відносно цифр ({r2 / r1:.2f})", abs(r2 / r1 - 2) < .05)
        await pg.goto(f"{URL}#start={start}&clock_size=300&title_size=50"); await pg.reload(); await pg.wait_for_timeout(300)
        bw = await pg.evaluate("(r => [r.left, r.right, r.top, r.bottom])(document.getElementById('w').getBoundingClientRect())")
        check(f"великі цифри все одно в межах джерела ({[round(v) for v in bw]})", bw[0] >= 0 and bw[1] <= 1920 and bw[2] >= 0 and bw[3] <= 1080)

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

        # 4. без параметрів — підказка з посиланням на налаштування
        await pg.goto(URL); await pg.reload()
        check("без параметрів показує підказку", await pg.evaluate("document.getElementById('hint').classList.contains('on')"))

        # 5. керування з чату: start / pause / stop, лише стрімер і модератори
        await pg.goto(f"{URL}#channel=TestChan"); await pg.reload()
        await pg.evaluate("localStorage.clear()")
        T0 = 1_800_000_000_000
        st = lambda: pg.evaluate("load()")
        await pg.evaluate("onChat({badges:'subscriber/12'}, '!timer start')")
        check("глядач не може стартувати", (await st())["status"] == "idle")
        await pg.evaluate("onChat({badges:'broadcaster/1'}, '!timer start')")
        check("стрімер стартує", (await st())["status"] == "running")
        await pg.evaluate("onChat({mod:'1', badges:'moderator/1'}, '!таймер пауза')")
        s = await st()
        check("модератор ставить на паузу (укр. команда)", s["status"] == "paused")
        # детерміновано: старт у T0, пауза через 1 год, продовження через 10 хв, стоп ще через 30 хв -> 1:30:00
        await pg.evaluate("localStorage.clear()")
        await pg.evaluate(f"command('start', {T0}); command('pause', {T0 + 3600_000}); command('start', {T0 + 4200_000}); command('stop', {T0 + 6000_000})")
        s = await st()
        check(f"пауза не рахується, стоп заморожує ({s})", s["status"] == "stopped" and s["base"] == 5400_000)
        await pg.reload(); await pg.wait_for_timeout(300)
        c5 = await clock()
        check(f"після перезапуску OBS показує заморожений час ({c5})", c5 == "01:30:00")
        await pg.wait_for_timeout(1100)
        check("заморожений час не йде", await clock() == "01:30:00")
        await pg.evaluate("onChat({badges:'broadcaster/1'}, '!timer start')")
        check("старт після стопу — новий відлік з нуля", (await st())["base"] == 0 and (await st())["status"] == "running")
        await pg.evaluate("onChat({badges:'broadcaster/1'}, '!timer foo')")
        check("невідома команда ігнорується", (await st())["status"] == "running")
        await pg.evaluate("onChat({badges:'subscriber/3'}, '!timer reset')")
        check("глядач не може скинути", (await st())["status"] == "running")
        await pg.evaluate("onChat({mod:'1'}, '!таймер скинути')")
        await pg.wait_for_timeout(1100)
        s = await st()
        check(f"скидання: 00:00:00 і стоїть ({s['status']}, {await clock()})", s == {"status": "idle", "base": 0, "since": 0} and await clock() == "00:00:00")
        await pg.evaluate("onChat({badges:'broadcaster/1'}, '!timer unpause')")
        check("unpause після скидання нічого не робить", (await st())["status"] == "idle")
        await pg.evaluate("onChat({badges:'broadcaster/1'}, '!timer start')")
        check("після скидання старт працює", (await st())["status"] == "running")

        # unpause: продовжує з того ж часу; resume і укр. аліас теж працюють
        await pg.evaluate("localStorage.clear()")
        await pg.evaluate(f"command('start', {T0}); command('pause', {T0 + 600_000}); command('unpause', {T0 + 900_000}); command('stop', {T0 + 1_200_000})")
        s = await st()
        check(f"unpause продовжує без часу паузи ({s['base']})", s["status"] == "stopped" and s["base"] == 900_000)
        await pg.evaluate("command('unpause')")
        check("unpause після стопу нічого не робить", (await st())["status"] == "stopped")
        await pg.evaluate("localStorage.clear(); command('start'); command('pause')")
        await pg.evaluate("onChat({mod:'1'}, '!таймер продовжити')")
        check("!таймер продовжити знімає з паузи", (await st())["status"] == "running")
        await pg.evaluate("command('pause')")
        await pg.evaluate("onChat({badges:'broadcaster/1'}, '!timer resume')")
        check("!timer resume знімає з паузи", (await st())["status"] == "running")

        check("немає JS-помилок " + str(errs), not errs)
        await b.close()
    sys.exit(1 if fails else 0)

asyncio.run(main())

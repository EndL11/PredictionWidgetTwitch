"""
Автотест життєвого циклу віджета (без Twitch).
Запуск:  python tests/test_lifecycle.py [--chrome /path/to/chrome]
Потрібно: pip install playwright && playwright install chromium
Подаємо події напряму у функції onBegin/onProgress/onLock/onEnd і перевіряємо
видимість картки, плавність анімацій та відсутність JS-помилок.
"""
import asyncio, sys, pathlib
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
URL = (ROOT / "widget" / "index.html").as_uri()

def chrome_path():
    if "--chrome" in sys.argv:
        return sys.argv[sys.argv.index("--chrome") + 1]
    return None

async def main():
    fails = []
    def check(name, cond):
        print(("PASS " if cond else "FAIL ") + name)
        if not cond: fails.append(name)

    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=chrome_path())
        pg = await b.new_page(viewport={"width": 680, "height": 360})
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(URL + "?lock_hide=2&hide=1&speed=400")
        vis = lambda: pg.evaluate("document.getElementById('card').classList.contains('show')")

        # 1. begin -> visible
        await pg.evaluate("""onBegin({id:'t',title:'T',locks_at:new Date(Date.now()+60000).toISOString(),
            outcomes:[{id:'a',title:'A',color:'blue'},{id:'b',title:'B',color:'pink'}]},true)""")
        check("видимий після begin", await vis())

        # 2. smooth tween: значення мають бути проміжними
        await pg.evaluate("onProgress({id:'t',outcomes:[{id:'a',users:1,channel_points:1000},{id:'b',users:1,channel_points:9000}]})")
        await pg.wait_for_timeout(1200)
        await pg.evaluate("onProgress({id:'t',outcomes:[{id:'a',users:5,channel_points:30000},{id:'b',users:2,channel_points:10000}]})")
        await pg.wait_for_timeout(250)
        mid = await pg.evaluate("document.querySelector('[data-tw=\"c0\"]').textContent")
        check(f"плавний перехід відсотків (проміжне значення {mid})", 10 < int(mid) < 75)

        # 3. manual lock -> hides after lock_hide
        await pg.evaluate("onLock({id:'t',outcomes:[{id:'a',users:5,channel_points:30000},{id:'b',users:2,channel_points:10000}]})")
        await pg.wait_for_timeout(1000); check("ще видимий через 1с після lock", await vis())
        await pg.wait_for_timeout(1500); check("схований через 2.5с після lock", not await vis())

        # 4. end -> visible again, results rendered, then hides
        await pg.evaluate("""onEnd({id:'t',status:'resolved',winning_outcome_id:'a',outcomes:[
            {id:'a',top_predictors:[{user_name:'x',channel_points_used:100,channel_points_won:150}]},
            {id:'b',top_predictors:[{user_name:'y',channel_points_used:50,channel_points_won:0}]}]})""")
        await pg.wait_for_timeout(300)
        check("знову видимий після end", await vis())
        check("списки результатів показані", await pg.evaluate("document.getElementById('results').classList.contains('on')"))
        # картка по центру: списки над нею не мають вилазити за верх джерела 680×360 (offsetTop ігнорує transform)
        rtop = await pg.evaluate("card.offsetTop + document.getElementById('results').offsetTop")
        check(f"списки вміщаються над карткою (top={rtop})", rtop >= 0)
        await pg.wait_for_timeout(3000); check("схований після результатів", not await vis())

        # 5. timer reaches 0 without lock event -> hides
        await pg.evaluate("""onBegin({id:'u',title:'U',locks_at:new Date(Date.now()+1000).toISOString(),
            outcomes:[{id:'a',title:'A'},{id:'b',title:'B'}]},true)""")
        await pg.wait_for_timeout(3500); check("схований після 00:00 без події lock", not await vis())

        # 6. cancel
        await pg.evaluate("""onBegin({id:'c',title:'C',locks_at:new Date(Date.now()+60000).toISOString(),
            outcomes:[{id:'a',title:'A'},{id:'b',title:'B'}]},true)""")
        await pg.evaluate("onEnd({id:'c',status:'canceled',winning_outcome_id:null,outcomes:[{id:'a'},{id:'b'}]})")
        await pg.wait_for_timeout(200)
        check("скасування показує банер", await pg.evaluate("document.getElementById('banner').classList.contains('on')"))

        # 7. велике джерело (повний екран) -> картка в центрі й розтягнута на всю ширину
        await pg.set_viewport_size({"width": 1920, "height": 1080})
        await pg.wait_for_timeout(600)
        x, y, w, h = await pg.evaluate("(r => [r.x, r.y, r.width, r.height])(card.getBoundingClientRect())")
        check(f"картка в центрі 1920×1080 ({x + w/2:.0f}, {y + h/2:.0f})", abs(x + w/2 - 960) <= 3 and abs(y + h/2 - 540) <= 3)
        check(f"картка масштабована під джерело (ширина {w:.0f})", abs(w - 640 * 1920 / 660) <= 3)
        # результати 3 варіантів на весь екран теж вміщаються
        await pg.evaluate("""onBegin({id:'m',title:'M',locks_at:new Date(Date.now()+60000).toISOString(),
            outcomes:['a','b','c'].map(id=>({id,title:id}))},true)""")
        await pg.evaluate("""onEnd({id:'m',status:'resolved',winning_outcome_id:'a',outcomes:['a','b','c'].map(id=>({id,
            top_predictors:[{user_name:'n'+id,channel_points_used:100,channel_points_won:id==='a'?300:null}]}))})""")
        await pg.wait_for_timeout(600)
        rt = await pg.evaluate("document.getElementById('results').getBoundingClientRect().top")
        check(f"списки 3 варіантів вміщаються на 1920×1080 (top={rt:.0f})", rt >= 0)

        # 8. параметри з #fragment (токен не йде на сервер); без token віджет нікуди не стукає
        await pg.goto(URL + "#client_id=abc&rows=3")
        check("параметри читаються з #", await pg.evaluate("CFG.clientId === 'abc' && CFG.rows === 3"))

        check("немає JS-помилок " + str(errs), not errs)
        await b.close()
    sys.exit(1 if fails else 0)

asyncio.run(main())

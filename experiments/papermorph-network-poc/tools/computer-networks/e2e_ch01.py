"""Browser acceptance checks for the link-rate lesson.

    URL=http://localhost:8765/computer-networks/ch01/ uv run --with playwright tools/computer-networks/e2e_ch01.py
    BROWSER=firefox URL=http://localhost:8765/computer-networks/ch01/ uv run --with playwright tools/computer-networks/e2e_ch01.py
"""
import asyncio
import os
from pathlib import Path
import sys

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".qoder" / "skills" / "papermorph" / "scripts"))
from browsers import answers, exe, firefox

URL = os.environ.get("URL", "http://localhost:8765/computer-networks/ch01/").rstrip("/") + "/"

SAME_FRAME = r"""
([i, t]) => {
  const snap = () => scene.innerHTML.replace(/(cam)\d+/g, '$1#').replace(/(\d+\.\d{2})\d+/g, '$1');
  seek(i, false); P.t = t; evalTo(t); const a = snap();
  seek(i, false); for (let u = 0; u < t; u += 1 / 60) evalTo(u); evalTo(t);
  return a === snap();
}
"""

CARD = r"""
() => {
  const stage = document.getElementById('stage').getBoundingClientRect();
  const k = stage.width / 1600;
  const c = document.querySelector('.card.quiz');
  const prompt = c.querySelector('.prompt');
  const cr = c.getBoundingClientRect();
  const pr = prompt.getBoundingClientRect();
  const lines = pr.height / (parseFloat(getComputedStyle(prompt).lineHeight) * k);
  const controls = [...c.querySelectorAll('.opt, input.box, .btn:not([hidden])')].map(e => e.getBoundingClientRect());
  const inside = b => b.width > 0 && b.left >= cr.left - 1 && b.right <= cr.right + 1 && b.top >= cr.top - 1 && b.bottom <= cr.bottom + 1;
  const figure = document.querySelector('.network-figure');
  const fig = figure?.getBoundingClientRect();
  return {promptW: pr.width / k, lines, ok: controls.every(inside), bottom: (cr.bottom - stage.top) / k,
    figureTop: fig ? (fig.top - stage.top) / k : null, figureBottom: fig ? (fig.bottom - stage.top) / k : null};
}
"""

LAYOUT = r"""
() => {
  const root = S.net.el;
  const text = value => [...root.querySelectorAll('text')].find(e => e.textContent === value);
  const rect = e => {
    if (!e) return null;
    const r = e.getBoundingClientRect();
    return {left: r.left, right: r.right, top: r.top, bottom: r.bottom};
  };
  return {
    sender: rect(text('发送器')), packet: rect(text('1500 B')),
    totalLabel: rect(text('简化总时延')), rate: rect(text('10 Mbps')),
    note: rect(text('示意：12 块，每块代表 1000 bit')),
  };
}
"""

STATE = r"""
() => {
  const net = S.net;
  const knob = net.knob.getBoundingClientRect();
  const hit = net.knob.querySelector('.rate-hit');
  const hr = hit.getBoundingClientRect();
  return {rate: net.v.rate, tx: net.tx, total: net.total, txText: net.txValue.textContent,
    totalText: net.totalValue.textContent, propText: net.propValue.textContent,
    txW: +net.txBar.getAttribute('width'), propW: +net.propBar.getAttribute('width'),
    propX: +net.propBar.getAttribute('x'), now: net.knob.getAttribute('aria-valuenow'),
    valueText: net.knob.getAttribute('aria-valuetext'), live: net.knob.getAttribute('aria-disabled') === 'false',
    tabIndex: net.knob.getAttribute('tabindex'), touchAction: getComputedStyle(hit).touchAction,
    pointerEvents: getComputedStyle(hit).pointerEvents,
    knob: {x: knob.x + knob.width / 2, y: knob.y + knob.height / 2},
    hit: {left: hr.left, right: hr.right, top: hr.top, bottom: hr.bottom},
    matrix: {a: net.el.getScreenCTM().a, d: net.el.getScreenCTM().d, e: net.el.getScreenCTM().e, f: net.el.getScreenCTM().f}};
}
"""


def ms_text(value):
    if value >= 10:
        return f"{value:.2f}".removesuffix("0")
    return f"{value:.1f}" if value >= 1 else f"{value:.2f}"


def assert_state(s, rate):
    tx = 12000 / (rate * 1000)
    total = tx + 10
    assert s["rate"] == rate, s
    assert abs(s["tx"] - tx) < 1e-9, s
    assert abs(s["total"] - total) < 1e-9, s
    assert abs(s["propW"] - (10 / 22 * 1000)) < 0.01, s
    assert abs(s["propX"] - (300 + s["txW"])) < 0.02, s
    assert s["now"] == str(rate), s
    assert s["txText"] == f"{ms_text(tx)} ms", s
    assert s["totalText"] == f"{ms_text(total)} ms", s
    assert s["propText"] == "10.0 ms", s
    assert f"传输 {ms_text(tx)} 毫秒" in s["valueText"], s
    assert f"总时延 {ms_text(total)} 毫秒" in s["valueText"], s


def overlaps(a, b):
    return min(a["right"], b["right"]) - max(a["left"], b["left"]) > 1 and min(a["bottom"], b["bottom"]) - max(a["top"], b["top"]) > 1


async def open_beat(pg, bid):
    await pg.evaluate("id => seek(BEATS.findIndex(b => b.id === id), false)", bid)
    await pg.wait_for_timeout(250)


async def check_card(pg, bid):
    m = await pg.evaluate(CARD)
    assert m["promptW"] > 400 and m["lines"] <= 4 and m["ok"] and m["bottom"] <= 901, (bid, m)
    if m["figureTop"] is not None:
        assert m["figureTop"] >= -1 and m["figureBottom"] <= m["figureTop"] + 750, (bid, m)


async def mouse_drag(pg, x1, x2, y):
    await pg.mouse.move(x1, y)
    await pg.mouse.down()
    await pg.mouse.move(x2, y, steps=24)
    await pg.mouse.up()


async def touch_drag(pg, x1, x2, y):
    await pg.evaluate("""async ([x1, x2, y]) => {
      const hit = S.net.knob.querySelector('.rate-hit');
      hit.setPointerCapture = () => {};
      hit.hasPointerCapture = () => false;
      const opts = {pointerId: 7, pointerType: 'touch', isPrimary: true, bubbles: true, cancelable: true, clientX: x1, clientY: y};
      hit.dispatchEvent(new PointerEvent('pointerdown', opts));
      for (let i = 1; i <= 24; i++) {
        hit.dispatchEvent(new PointerEvent('pointermove', {...opts, clientX: x1 + (x2 - x1) * i / 24}));
        await new Promise(requestAnimationFrame);
      }
      hit.dispatchEvent(new PointerEvent('pointerup', {...opts, clientX: x2}));
    }""", [x1, x2, y])


async def main():
    answers(URL)
    async with async_playwright() as p:
        ff = os.environ.get("BROWSER") == "firefox"
        browser = await (p.firefox.launch(**firefox()) if ff else p.chromium.launch(**exe()))
        context = await browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce", has_touch=True)
        pg = await context.new_page()
        errs = []
        warnings = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else warnings.append(m.text) if m.type == "warning" else None)
        await pg.goto(URL)
        await pg.wait_for_timeout(400)
        shadow = await pg.evaluate("""() => {
          const value = getComputedStyle(document.getElementById('frame')).boxShadow;
          const lengths = [...value.matchAll(/(-?\\d+(?:\\.\\d+)?)px/g)].map(m => Math.abs(+m[1]));
          return {value, cheap: lengths.length > 0 && lengths.every(n => n <= 1)};
        }""")
        assert shadow["cheap"], shadow
        ev = pg.evaluate
        ids = await ev("BEATS.map(b => b.id)")
        asks = await ev("BEATS.map(b => !!b.ask)")
        packet_lines = await ev("TIMINGS.packet.cues.map(c => c[1]).join('')")
        final_lines = await ev("TIMINGS.final1.cues.map(c => c[1]).join('')")
        assert "在速率不变时，数据包越小" in packet_lines, packet_lines
        assert "检查时会告诉你是否调对" in final_lines and "速率状态" not in final_lines, final_lines

        await pg.keyboard.press("Space")
        await pg.wait_for_timeout(2400)
        assert await ev("P.playing && P.t > 1"), "lesson plays"
        await pg.keyboard.press("Space")
        t1 = await ev("P.t")
        await pg.wait_for_timeout(500)
        assert await ev(f"!P.playing && P.t === {t1}"), "pause freezes"

        for i, bid in enumerate(ids):
            if asks[i]:
                continue
            dur = await ev(f"TIMINGS['{bid}'].dur")
            for t in (round(dur * .55, 2), round(dur - .3, 2)):
                assert await ev(SAME_FRAME, [i, t]), (bid, t, "seek differs from stepped frame")

        for vw, vh in [(1280, 800), (1920, 1080), (390, 844)]:
            await pg.set_viewport_size({"width": vw, "height": vh})
            for i, bid in enumerate(ids):
                if not asks[i] or bid == "finish":
                    continue
                await open_beat(pg, bid)
                await check_card(pg, bid)

        await pg.set_viewport_size({"width": 1440, "height": 900})

        await open_beat(pg, "q1")
        assert await ev("scene.textContent.includes('10 Mbps = 10 000 bit/ms')")
        await pg.locator(".card input.box").fill("2")
        await pg.keyboard.press("Enter")
        assert "还不对" in await pg.locator(".card .fb").inner_text()
        await pg.locator(".card input.box").fill("1.2")
        await pg.keyboard.press("Enter")
        assert "正确" in await pg.locator(".card .fb").inner_text()
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(200)
        assert await ev("BEATS[P.i].id") == "propagate"

        await open_beat(pg, "q2")
        assert_state(await ev(STATE), 10)

        await open_beat(pg, "transmit")
        await ev("() => { const i = BEATS.findIndex(b => b.id === 'transmit'); seek(i, false); evalTo(TIMINGS.transmit.dur - .5); }")
        transmission = await ev("""() => {
          const m = S.net.el.getScreenCTM();
          const xs = S.net.bits.map(e => {
            const r = e.getBoundingClientRect();
            return [(r.left - m.e) / m.a, (r.right - m.e) / m.a];
          });
          return {
            right: Math.max(...xs.map(x => x[1])),
            left: Math.min(...xs.map(x => x[0])),
            minWidth: Math.min(...S.net.bits.map(e => +e.getAttribute('width'))),
            note: [...S.net.el.querySelectorAll('text')].map(e => e.textContent).find(t => t.startsWith('示意：')),
            receiverLeft: 1260,
          };
        }""")
        assert 338 <= transmission["left"] < transmission["right"] <= 600, transmission
        assert transmission["right"] - transmission["left"] >= 200, transmission
        assert transmission["minWidth"] >= 12, transmission
        assert "不按距离比例" in transmission["note"], transmission

        await open_beat(pg, "packet")
        await ev("() => { seek(BEATS.findIndex(b => b.id === 'packet'), false); evalTo(TIMINGS.packet.dur - .5); }")
        assert await ev("scene.textContent.includes('8 块仅演示 1 字节的换算')")
        await open_beat(pg, "rate")
        await ev("() => { seek(BEATS.findIndex(b => b.id === 'rate'), false); evalTo(TIMINGS.rate.dur - .5); }")
        assert await ev("scene.textContent.includes('圆点只表示持续流动，不计数')")
        assert await ev("scene.textContent.includes('分子用比特，不用字节；分母用 bit/s')")
        await open_beat(pg, "total")
        await ev("() => { seek(BEATS.findIndex(b => b.id === 'total'), false); evalTo(TIMINGS.total.dur - .5); }")
        assert await ev("scene.textContent.includes('不计排队、处理与协议开销')")

        await open_beat(pg, "q2")
        s = await ev(STATE)
        assert_state(s, 10)
        layout = await ev(LAYOUT)
        assert not overlaps(layout["sender"], layout["packet"]), layout
        assert not overlaps(layout["totalLabel"], layout["rate"]), layout
        assert layout["note"] is not None, layout
        assert s["live"] and s["tabIndex"] == "0" and s["touchAction"] == "none" and s["pointerEvents"] == "all", s
        assert await ev("document.querySelector('.card .state-note').textContent.includes('蓝色传播段仍为 10 ms')")
        for rate in (1, 5, 10, 20, 100):
            await ev("rate => S.net.set(rate)", rate)
            assert_state(await ev(STATE), rate)
        await pg.locator(".rate-control").focus()
        await pg.keyboard.press("Home")
        await pg.locator(".rate-control").focus()
        await pg.keyboard.press("Home")
        assert_state(await ev(STATE), 1)
        await pg.keyboard.press("ArrowRight")
        assert_state(await ev(STATE), 2)
        await pg.keyboard.press("PageUp")
        assert_state(await ev(STATE), 12)
        await pg.keyboard.press("ArrowDown")
        assert_state(await ev(STATE), 11)
        await pg.keyboard.press("End")
        assert_state(await ev(STATE), 100)
        await pg.keyboard.press("Home")
        for _ in range(19):
            await pg.keyboard.press("ArrowRight")
        assert_state(await ev(STATE), 20)
        assert await ev("document.activeElement === S.net.knob")
        await pg.keyboard.press("Enter")
        feedback = await pg.locator(".card .fb").inner_text()
        assert "正确" in feedback, feedback
        locked = await ev(STATE)
        assert not locked["live"] and locked["tabIndex"] == "-1" and locked["pointerEvents"] == "none" and locked["touchAction"] == "none", locked
        await pg.locator(".rate-control").focus()
        await pg.keyboard.press("End")
        assert_state(await ev(STATE), 20)

        await open_beat(pg, "q2")
        s = await ev(STATE)
        await mouse_drag(pg, s["knob"]["x"], s["hit"]["left"] - 5, s["knob"]["y"])
        assert (await ev(STATE))["rate"] < 20
        await pg.get_by_role("button", name="检查 Enter").click()
        assert "还低了一些" in await pg.locator(".card .fb").inner_text()
        s = await ev(STATE)
        await mouse_drag(pg, s["knob"]["x"], s["matrix"]["e"] + (1180 - s["matrix"]["e"]) / s["matrix"]["a"], s["knob"]["y"])
        assert (await ev(STATE))["rate"] > 20
        await pg.get_by_role("button", name="检查 Enter").click()
        assert "调过头了" in await pg.locator(".card .fb").inner_text()

        await open_beat(pg, "q2")
        s = await ev(STATE)
        await touch_drag(pg, s["knob"]["x"], s["matrix"]["e"] + (1180 - s["matrix"]["e"]) / s["matrix"]["a"], s["knob"]["y"])
        touch = await ev(STATE)
        assert_state(touch, 100)
        assert touch["txText"] == "0.12 ms", touch
        assert touch["totalText"] == "10.12 ms", touch
        await pg.keyboard.press("Home")
        for _ in range(19):
            await pg.keyboard.press("ArrowRight")
        await pg.get_by_role("button", name="检查 Enter").click()
        assert "正确" in await pg.locator(".card .fb").inner_text()
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(200)
        assert await ev("BEATS[P.i].id") == "wrap"

        await open_beat(pg, "lab")
        assert await ev("S.net.v.rate === 10 && S.net.knob.getAttribute('aria-disabled') === 'false'")
        assert await ev("document.querySelector('.card.playground .state-note').textContent === '速率越高，发送段越短；蓝色传播段不动，总时延越接近 10 ms。'")
        await pg.keyboard.press("End")
        assert (await ev(STATE))["rate"] == 100
        assert await ev("document.activeElement === S.net.knob")
        await pg.keyboard.press("Enter")
        assert await ev("BEATS[P.i].id") == "q2"
        assert not await pg.locator(".card.playground").count()

        await open_beat(pg, "final1")
        assert await ev("document.querySelector('.card.screen .state-note').textContent.includes('蓝色传播段仍为 10 ms')")
        await pg.keyboard.press("End")
        await pg.keyboard.press("Home")
        for _ in range(4):
            await pg.keyboard.press("ArrowRight")
        await pg.get_by_role("button", name="检查 Enter").click()
        assert "总时延仍高于" in await pg.locator(".card .fb").inner_text()
        await pg.keyboard.press("ArrowRight")
        await pg.get_by_role("button", name="检查 Enter").click()
        assert "正确" in await pg.locator(".card .fb").inner_text()
        assert_state(await ev(STATE), 6)
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(200)
        assert await ev("BEATS[P.i].id") == "finish" and await pg.is_visible(".card.fin")
        assert "第 1 章完成" in await pg.locator(".card.fin").inner_text()
        assert 1 in (await ev(f"JSON.parse(localStorage.getItem(BOOK_PROGRESS_KEY))"))["done"]

        await ev("restart()")
        await open_beat(pg, "q2")
        await pg.keyboard.press("End")
        await pg.get_by_role("button", name="检查 Enter").click()
        score = await ev("SCORE['c-rate-state']")
        assert score["right"] == 0, score
        await pg.keyboard.press("Home")
        for _ in range(19):
            await pg.keyboard.press("ArrowRight")
        await pg.get_by_role("button", name="检查 Enter").click()
        assert "正确" in await pg.locator(".card .fb").inner_text()
        assert (await ev("SCORE['c-rate-state']"))["right"] == 0
        await open_beat(pg, "q2")
        assert_state(await ev(STATE), 10)
        assert await ev("S.net.knob.getAttribute('aria-disabled') === 'false'")
        await pg.keyboard.press("End")
        await pg.get_by_role("button", name="检查 Enter").click()
        await pg.keyboard.press("S")
        answer = await pg.locator(".card .fb").inner_text()
        assert "显示答案" not in answer and "答案：" in answer
        assert_state(await ev(STATE), 20)
        assert not (await ev(STATE))["live"]

        await ev("restart()")
        assert await ev("Object.keys(SCORE).length") == 0
        assert await ev("P.i === 0")
        for i in range(len(ids)):
            await ev(f"seek({i}, false)")
        assert not errs, errs
        ignored = [w for w in warnings if "Did not find element expected to be parsed from" not in w]
        assert not ignored, ignored
        expect = sum("Did not find element expected to be parsed from" in w for w in warnings)
        print(f"{URL} ({len(ids)} beats, {'firefox' if ff else 'chromium'}): playback, replay, cards, state math, mouse/keyboard/touch, locks, scoring and restart - passed")
        print(f"console: {expect} known rel=expect #bar warnings; 0 other warnings; 0 errors")
        await browser.close()


asyncio.run(main())

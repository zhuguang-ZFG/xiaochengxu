"""Browser acceptance checks for the three-hop store-and-forward lesson.

    URL=http://localhost:8765/computer-networks/ch02/ uv run --with playwright tools/computer-networks/e2e_ch02.py
    BROWSER=firefox URL=http://localhost:8765/computer-networks/ch02/ uv run --with playwright tools/computer-networks/e2e_ch02.py
"""
import asyncio
import json
import os
from pathlib import Path
import sys

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".qoder" / "skills" / "papermorph" / "scripts"))
from browsers import answers, exe, firefox

URL = os.environ.get("URL", "http://localhost:8765/computer-networks/ch02/").rstrip("/") + "/"
BEAT_IDS = ["intro", "packet", "firsthop", "store", "repeat", "q1", "formula", "lab", "q2", "wrap", "final1", "finish"]
ASK_IDS = {"q1", "lab", "q2", "final1", "finish"}
MARKS = {
    "intro": {"route"},
    "packet": {"bits"},
    "firsthop": {"send", "sent", "arrive"},
    "store": {"full", "next"},
    "repeat": {"hop2", "hop3"},
    "formula": {"formula", "floor"},
    "lab": {"try"},
    "wrap": {"one", "two", "three"},
}

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
  const c = document.querySelector('.card.quiz, .card.playground');
  const prompt = c.querySelector('.prompt');
  const cr = c.getBoundingClientRect();
  const pr = prompt.getBoundingClientRect();
  const lines = pr.height / (parseFloat(getComputedStyle(prompt).lineHeight) * k);
  const controls = [...c.querySelectorAll('.opt, input.box, .btn:not([hidden])')].map(e => e.getBoundingClientRect());
  const inside = b => b.width > 0 && b.left >= cr.left - 1 && b.right <= cr.right + 1 && b.top >= cr.top - 1 && b.bottom <= cr.bottom + 1;
  const figure = document.querySelector('.store-forward-figure');
  const fig = figure?.getBoundingClientRect();
  return {promptW: pr.width / k, lines, ok: controls.every(inside), bottom: (cr.bottom - stage.top) / k,
    figureTop: fig ? (fig.top - stage.top) / k : null, figureBottom: fig ? (fig.bottom - stage.top) / k : null};
}
"""

FEEDBACK_OVERLAPS = r"""
() => {
  const fb = document.querySelector('.card .fb');
  if (!fb || !fb.textContent.trim()) return [];
  const f = fb.getBoundingClientRect();
  const intersects = r => r.width > 0 && r.height > 0 && !(r.right <= f.left || r.left >= f.right || r.bottom <= f.top || r.top >= f.bottom);
  const targets = [
    ...document.querySelectorAll('.store-forward-figure text, .card .head, .card .head *, .card .body, .card .body *, .card .acts, .card .acts *'),
  ];
  return targets
    .filter(e => intersects(e.getBoundingClientRect()))
    .map(e => e.className?.baseVal ?? e.className ?? e.tagName.toLowerCase());
}
"""

STATE = r"""
() => {
  const r = S.route;
  const q = s => [...r.el.querySelectorAll(s)];
  const knob = r.knob.getBoundingClientRect();
  const hit = r.hit.getBoundingClientRect();
  const track = r.el.querySelector('.rate-track');
  const tr = track.getBoundingClientRect();
  const axis = r.el.querySelector('.time-axis');
  const ar = axis.getBoundingClientRect();
  const seg = e => { const b = e.getBoundingClientRect(); return {x: +e.getAttribute('x'), width: +e.getAttribute('width'), screenWidth: b.width}; };
  return {
    rate: r.v.rate, tx: r.tx, hop: r.hop, total: r.total,
    linkRates: q('.link-rate').map(e => e.textContent),
    txSegments: q('.timeline-segment.tx').map(seg), propSegments: q('.timeline-segment.prop').map(seg),
    hopValues: q('.hop-value').map(e => e.textContent), totalText: r.totalValue.textContent,
    txText: r.txValue.textContent, rateText: r.rateValue.textContent,
    now: r.knob.getAttribute('aria-valuenow'), valueText: r.knob.getAttribute('aria-valuetext'),
    rootLabel: r.el.getAttribute('aria-label'), live: r.knob.getAttribute('aria-disabled') === 'false',
    tabIndex: r.knob.getAttribute('tabindex'), touchAction: getComputedStyle(r.hit).touchAction,
    pointerEvents: getComputedStyle(r.hit).pointerEvents,
    knob: {x: knob.x + knob.width / 2, y: knob.y + knob.height / 2},
    hit: {left: hit.left, right: hit.right, top: hit.top, bottom: hit.bottom},
    track: {left: tr.left, right: tr.right, y: tr.top + tr.height / 2},
    axis: {x: +axis.getAttribute('x'), width: +axis.getAttribute('width'), max: +axis.dataset.maxMs, screenWidth: ar.width},
    nodes: q('.route-node').map(e => { const b = e.getBoundingClientRect(); return {left: b.left, right: b.right, top: b.top, bottom: b.bottom, width: b.width}; }),
    api: ['v','el','knob','tx','hop','total','set','to','live','nudge','focus','onChange'].every(k => k in r),
  };
}
"""

def oracle(rate):
    tx = 12000 / (rate * 1000)
    hop = tx + 2
    return tx, hop, 3 * hop


def ms_text(value):
    return f"{value:.1f}" if abs(value * 10 - round(value * 10)) < 1e-9 else f"{value:.2f}"


def assert_state(s, rate):
    tx, hop, total = oracle(rate)
    assert s["api"], s
    assert s["rate"] == rate, s
    assert abs(s["tx"] - tx) < 1e-9, s
    assert abs(s["hop"] - hop) < 1e-9, s
    assert abs(s["total"] - total) < 1e-9, s
    assert s["axis"]["max"] == 42, s
    assert s["linkRates"] == [f"{rate} Mbps"] * 3, s
    assert len(s["txSegments"]) == len(s["propSegments"]) == 3, s
    for i in range(3):
        assert abs(s["txSegments"][i]["width"] / s["axis"]["width"] * 42 - tx) < .02, s
        assert abs(s["propSegments"][i]["width"] / s["axis"]["width"] * 42 - 2) < .02, s
        assert abs(s["propSegments"][i]["x"] - (s["axis"]["x"] + i * hop / 42 * s["axis"]["width"] + s["txSegments"][i]["width"])) < .03, s
    assert s["hopValues"] == [f"{ms_text(hop)} ms"] * 3, s
    assert s["totalText"] == f"{ms_text(total)} ms", s
    assert s["txText"] == f"{ms_text(tx)} ms", s
    assert s["rateText"] == f"{rate} Mbps", s
    assert s["now"] == str(rate), s
    assert f"传输 {ms_text(tx)} 毫秒" in s["valueText"], s
    assert f"每跳 {ms_text(hop)} 毫秒" in s["valueText"], s
    assert f"总时延 {ms_text(total)} 毫秒" in s["valueText"], s
    assert f"{rate} Mbps" in s["rootLabel"] and f"{ms_text(total)} 毫秒" in s["rootLabel"], s


async def open_beat(pg, bid):
    await pg.evaluate("id => seek(BEATS.findIndex(b => b.id === id), false)", bid)
    await pg.wait_for_timeout(180)


async def check_card(pg, bid):
    m = await pg.evaluate(CARD)
    assert m["promptW"] > 400 and m["lines"] <= 4 and m["ok"] and m["bottom"] <= 901, (bid, m)
    if m["figureTop"] is not None:
        assert m["figureTop"] >= -1 and m["figureBottom"] <= 901, (bid, m)


async def rate_point(pg, rate):
    return await pg.evaluate("""rate => {
      const track = S.route.el.querySelector('.rate-track');
      const matrix = track.getScreenCTM();
      const x1 = +track.getAttribute('x1'), x2 = +track.getAttribute('x2'), y = +track.getAttribute('y1');
      const a = new DOMPoint(x1, y).matrixTransform(matrix);
      const b = new DOMPoint(x2, y).matrixTransform(matrix);
      const x = a.x + (b.x - a.x) * (rate - 1) / 99;
      return {x, y: a.y + (b.y - a.y) * (rate - 1) / 99};
    }""", rate)


async def mouse_drag(pg, x1, x2, y):
    await pg.mouse.move(x1, y)
    await pg.mouse.down()
    await pg.mouse.move(x2, y, steps=24)
    await pg.mouse.up()


async def touch_drag(pg, x1, x2, y):
    await pg.evaluate("""async ([x1, x2, y]) => {
      const hit = S.route.hit;
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
    narration = json.loads((ROOT / "content/computer-networks/ch02/narration.zh.json").read_text(encoding="utf-8"))
    lab = narration["beats"]["lab"]
    assert "三段发送色块" in lab and "三段传播色块" in lab and "六段发送色块" not in lab, lab
    answers(URL)
    async with async_playwright() as p:
        ff = os.environ.get("BROWSER") == "firefox"
        browser = await (p.firefox.launch(**firefox()) if ff else p.chromium.launch(**exe()))
        context = await browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce", has_touch=True)
        pg = await context.new_page()
        errs, warnings = [], []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else warnings.append(m.text) if m.type == "warning" else None)
        await pg.goto(URL)
        await pg.wait_for_timeout(350)
        axpg = await context.new_page()
        await axpg.goto(URL)
        await open_beat(axpg, "q2")
        ax_slider = axpg.get_by_role("slider", name="三条链路共用速率，单位 Mbps")
        assert await ax_slider.count() == 1, await axpg.locator("#stage").get_attribute("role")
        ax_tree = await axpg.locator("#stage").aria_snapshot()
        assert 'slider "三条链路共用速率，单位 Mbps"' in ax_tree, ax_tree
        assert await axpg.locator("#stage").get_attribute("role") == "group", ax_tree
        assert await ax_slider.get_attribute("aria-valuenow") == "10"
        await axpg.close()
        assert await pg.evaluate("BEATS.map(b => b.id)") == BEAT_IDS
        assert await pg.evaluate("Object.keys(TIMINGS).sort()") == sorted(BEAT_IDS)
        for bid, expected in MARKS.items():
            assert set(await pg.evaluate(f"Object.keys(TIMINGS['{bid}'].marks)")) == expected, bid
        for bid in ("q1", "q2", "final1"):
            assert await pg.evaluate(f"TIMINGS['{bid}'].dur") <= 8, bid
        for bid in BEAT_IDS:
            response = await context.request.get(f"{URL}audio/zh/{bid}.mp3")
            assert response.status == 200, (bid, response.status)

        await pg.keyboard.press("Space")
        await pg.wait_for_timeout(2200)
        assert await pg.evaluate("P.playing && P.t > .5"), "lesson plays"
        await pg.keyboard.press("Space")
        t1 = await pg.evaluate("P.t")
        await pg.wait_for_timeout(350)
        assert await pg.evaluate(f"!P.playing && P.t === {t1}"), "pause freezes"

        for i, bid in enumerate(BEAT_IDS):
            if bid in ASK_IDS and bid != "lab":
                continue
            dur = await pg.evaluate(f"TIMINGS['{bid}'].dur")
            for t in (round(dur * .55, 2), round(dur - .25, 2)):
                assert await pg.evaluate(SAME_FRAME, [i, t]), (bid, t, "seek differs from stepped frame")

        for vw, vh in [(1280, 800), (1920, 1080), (390, 844)]:
            await pg.set_viewport_size({"width": vw, "height": vh})
            for bid in ("q1", "lab", "q2", "final1"):
                await open_beat(pg, bid)
                await check_card(pg, bid)
                state = await pg.evaluate(STATE)
                stage = await pg.locator("#stage").bounding_box()
                assert len(state["nodes"]) == 4, (bid, state["nodes"])
                for node in state["nodes"]:
                    assert node["width"] > 0 and node["left"] >= stage["x"] - 1 and node["right"] <= stage["x"] + stage["width"] + 1, (bid, node)
                    assert node["top"] >= stage["y"] - 1 and node["bottom"] <= stage["y"] + stage["height"] + 1, (bid, node)

        await pg.set_viewport_size({"width": 1440, "height": 900})
        await open_beat(pg, "q1")
        q1_state = await pg.evaluate(STATE)
        assert q1_state["totalText"] == "? ms" and "9.6" not in q1_state["rootLabel"], q1_state
        q1_visible = await pg.locator("#stage text").all_text_contents()
        q1_ax = await pg.locator("#stage").aria_snapshot()
        assert not any("9.6" in value for value in q1_visible), q1_visible
        assert "9.6" not in q1_ax, q1_ax
        await pg.locator(".card input.box").fill("9.5")
        await pg.keyboard.press("Enter")
        assert "还不对" in await pg.locator(".card .fb").inner_text()
        assert (await pg.evaluate("SCORE['c-three-hop-total']"))["right"] == 0
        await pg.locator(".card input.box").fill("9.6")
        await pg.keyboard.press("Enter")
        assert "正确" in await pg.locator(".card .fb").inner_text()
        assert (await pg.evaluate("SCORE['c-three-hop-total']"))["right"] == 0
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(150)
        assert await pg.evaluate("BEATS[P.i].id") == "formula"

        await open_beat(pg, "packet")
        await pg.evaluate("() => evalTo(2.1)")
        packet_labels = await pg.evaluate("() => [...document.querySelectorAll('#stage text')].map(e => e.textContent)")
        assert any("色块只表示 1 字节 = 8 比特" in s for s in packet_labels), packet_labels

        await open_beat(pg, "formula")
        formula_at = await pg.evaluate("TIMINGS.formula.marks.formula")
        await pg.evaluate("t => evalTo(t)", formula_at + .3)
        formula_labels = await pg.evaluate("() => [...document.querySelectorAll('#stage text')].map(e => e.textContent)")
        assert any("R：共用速率（Mbps）" in s and "总时延：ms" in s for s in formula_labels), formula_labels

        await open_beat(pg, "firsthop")
        idle = await pg.evaluate(STATE)
        assert not idle["live"] and idle["tabIndex"] == "-1" and idle["touchAction"] == "auto" and idle["pointerEvents"] == "none", idle
        await open_beat(pg, "q2")
        assert_state(await pg.evaluate(STATE), 10)
        changes = await pg.evaluate("""() => {
          const r = S.route; let n = 0;
          const off = r.onChange(() => n++);
          r.set(5); const first = n;
          r.set(5); const same = n;
          off(); r.set(10);
          return {first, same, after:n};
        }""")
        assert changes == {"first": 1, "same": 1, "after": 1}, changes
        live = await pg.evaluate(STATE)
        assert live["live"] and live["tabIndex"] == "0" and live["touchAction"] == "none" and live["pointerEvents"] == "all", live
        for rate in (1, 5, 10, 20, 100):
            await pg.evaluate("rate => S.route.set(rate)", rate)
            assert_state(await pg.evaluate(STATE), rate)
        await pg.evaluate("S.route.set(10)")
        await pg.locator(".rate-control").focus()
        await pg.keyboard.press("Home")
        await pg.keyboard.press("ArrowRight")
        assert_state(await pg.evaluate(STATE), 2)
        await pg.keyboard.press("PageUp")
        assert_state(await pg.evaluate(STATE), 12)
        await pg.keyboard.press("ArrowDown")
        assert_state(await pg.evaluate(STATE), 11)
        await pg.keyboard.press("End")
        assert_state(await pg.evaluate(STATE), 100)
        await pg.keyboard.press("Home")
        for _ in range(19):
            await pg.keyboard.press("ArrowRight")
        assert_state(await pg.evaluate(STATE), 20)
        assert await pg.evaluate("document.activeElement === S.route.knob")
        await pg.keyboard.press("Enter")
        assert "正确" in await pg.locator(".card .fb").inner_text()
        locked = await pg.evaluate(STATE)
        assert not locked["live"] and locked["tabIndex"] == "-1" and locked["pointerEvents"] == "none" and locked["touchAction"] == "auto", locked
        assert await pg.locator("#stage").get_attribute("role") == "img"
        await pg.locator(".rate-control").focus()
        await pg.keyboard.press("PageUp")
        assert_state(await pg.evaluate(STATE), 20)

        await open_beat(pg, "q2")
        s = await pg.evaluate(STATE)
        await mouse_drag(pg, s["knob"]["x"], s["hit"]["left"] - 5, s["knob"]["y"])
        assert (await pg.evaluate(STATE))["rate"] < 20
        await pg.get_by_role("button", name="检查 Enter").click()
        assert "还低了一些" in await pg.locator(".card .fb").inner_text()
        s = await pg.evaluate(STATE)
        await mouse_drag(pg, s["knob"]["x"], s["track"]["right"], s["track"]["y"])
        assert (await pg.evaluate(STATE))["rate"] > 20
        await pg.get_by_role("button", name="检查 Enter").click()
        assert "调过头了" in await pg.locator(".card .fb").inner_text()

        await open_beat(pg, "q2")
        s = await pg.evaluate(STATE)
        await touch_drag(pg, s["knob"]["x"], s["track"]["right"], s["track"]["y"])
        touch = await pg.evaluate(STATE)
        assert_state(touch, 100)
        assert touch["txText"] == "0.12 ms" and touch["totalText"] == "6.36 ms", touch
        await pg.keyboard.press("Home")
        for _ in range(19):
            await pg.keyboard.press("ArrowRight")
        await pg.get_by_role("button", name="检查 Enter").click()
        assert "正确" in await pg.locator(".card .fb").inner_text()

        await pg.evaluate("restart()")
        await pg.wait_for_timeout(100)
        await open_beat(pg, "q2")
        assert_state(await pg.evaluate(STATE), 10)
        await pg.keyboard.press("End")
        await pg.get_by_role("button", name="检查 Enter").click()
        assert (await pg.evaluate("SCORE['c-rate-state']"))["right"] == 0
        await pg.keyboard.press("Home")
        for _ in range(19):
            await pg.keyboard.press("ArrowRight")
        await pg.get_by_role("button", name="检查 Enter").click()
        assert (await pg.evaluate("SCORE['c-rate-state']"))["right"] == 0
        await open_beat(pg, "q2")
        await pg.keyboard.press("End")
        await pg.get_by_role("button", name="检查 Enter").click()
        await pg.keyboard.press("S")
        answer = await pg.locator(".card .fb").inner_text()
        assert "答案：" in answer and "20 Mbps" in answer, answer
        assert_state(await pg.evaluate(STATE), 20)
        assert not (await pg.evaluate(STATE))["live"]

        await pg.evaluate("restart()")
        await pg.wait_for_timeout(100)
        await open_beat(pg, "q2")
        await pg.keyboard.press("Home")
        for _ in range(19):
            await pg.keyboard.press("ArrowRight")
        await pg.get_by_role("button", name="检查 Enter").click()
        assert (await pg.evaluate("SCORE['c-rate-state']"))["right"] == 1
        await open_beat(pg, "q2")
        await pg.keyboard.press("End")
        await pg.get_by_role("button", name="检查 Enter").click()
        assert (await pg.evaluate("SCORE['c-rate-state']"))["right"] == 1

        await open_beat(pg, "lab")
        assert_state(await pg.evaluate(STATE), 10)
        assert await pg.locator(".card.playground").count() == 1
        before_scores = await pg.evaluate("Object.keys(SCORE).sort()")
        try_at = await pg.evaluate("TIMINGS.lab.marks.try")
        await pg.evaluate("t => evalTo(t)", try_at + .2)
        await pg.keyboard.press("End")
        assert_state(await pg.evaluate(STATE), 100)
        await pg.evaluate("t => evalTo(t)", try_at + .4)
        assert_state(await pg.evaluate(STATE), 100)
        assert await pg.evaluate("Object.keys(SCORE).sort()") == before_scores
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(150)
        assert await pg.evaluate("BEATS[P.i].id") == "q2"
        assert not await pg.locator(".card.playground").count()

        await open_beat(pg, "q2")
        await pg.locator(".rate-control").focus()
        await pg.keyboard.press("Shift+ArrowRight")
        await pg.wait_for_timeout(150)
        assert await pg.evaluate("BEATS[P.i].id") == "wrap", "Shift+Arrow must remain player navigation"

        await open_beat(pg, "final1")
        assert_state(await pg.evaluate(STATE), 1)
        await pg.get_by_role("button", name="检查 Enter").click()
        assert "总时延仍高于" in await pg.locator(".card .fb").inner_text()
        assert not await pg.evaluate(FEEDBACK_OVERLAPS), await pg.evaluate(FEEDBACK_OVERLAPS)
        await pg.keyboard.press("End")
        await pg.get_by_role("button", name="检查 Enter").click()
        assert "总时延已低于" in await pg.locator(".card .fb").inner_text()
        await pg.keyboard.press("Home")
        for _ in range(3):
            await pg.keyboard.press("ArrowRight")
        await pg.get_by_role("button", name="检查 Enter").click()
        correct_feedback = await pg.locator(".card .fb").inner_text()
        assert "正确" in correct_feedback, correct_feedback
        assert "15 − 6 = 9 ms" in correct_feedback, correct_feedback
        assert "9 ÷ 3 = 3 ms" in correct_feedback, correct_feedback
        assert "12 000 bit ÷ 3 ms = 4 Mbps" in correct_feedback, correct_feedback
        assert await pg.locator(".card .fb").evaluate("e => e.scrollHeight <= e.clientHeight + 1")
        assert_state(await pg.evaluate(STATE), 4)

        for mode in ("mouse", "touch"):
            await open_beat(pg, "final1")
            s = await pg.evaluate(STATE)
            target = await rate_point(pg, 4)
            if mode == "mouse":
                await mouse_drag(pg, s["knob"]["x"], target["x"], target["y"])
            else:
                await touch_drag(pg, s["knob"]["x"], target["x"], target["y"])
            assert_state(await pg.evaluate(STATE), 4)
            await pg.get_by_role("button", name="检查 Enter").click()
            assert "正确" in await pg.locator(".card .fb").inner_text()

        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(180)
        assert await pg.evaluate("BEATS[P.i].id") == "finish" and await pg.is_visible(".card.fin")
        assert "第 2 章完成" in await pg.locator(".card.fin").inner_text()
        assert 2 in (await pg.evaluate(f"JSON.parse(localStorage.getItem(BOOK_PROGRESS_KEY))"))["done"]

        marks = await pg.evaluate("TIMINGS.firsthop.marks")
        await pg.evaluate("() => seek(BEATS.findIndex(b => b.id === 'firsthop'), false)")
        await pg.evaluate("t => evalTo(t)", marks["send"] + .1)
        seq = await pg.evaluate("() => ({phase:S.route.el.dataset.phase, fills:S.route.fills.map(e => +e.getAttribute('width')), x:st(S.route.packet).x})")
        assert "send" in seq["phase"] and seq["fills"][0] > 0 and seq["fills"][1] == 0, seq
        await pg.evaluate("t => evalTo(t)", marks["arrive"] - .1)
        seq = await pg.evaluate("() => ({phase:S.route.el.dataset.phase, fills:S.route.fills.map(e => +e.getAttribute('width')), x:st(S.route.packet).x})")
        assert "propagat" in seq["phase"] and seq["fills"][0] > 200 and seq["fills"][1] == 0 and seq["x"] != 600, seq
        await pg.evaluate("t => evalTo(t)", marks["arrive"] + .1)
        seq = await pg.evaluate("() => ({phase:S.route.el.dataset.phase, fills:S.route.fills.map(e => +e.getAttribute('width')), x:st(S.route.packet).x})")
        assert "arrived" in seq["phase"] and seq["x"] == 600 and seq["fills"][1] == 0, seq
        sent = next(t for t, cue in (await pg.evaluate("TIMINGS.firsthop.cues")) if cue.startswith("发送完成后"))
        await pg.evaluate("() => seek(BEATS.findIndex(b => b.id === 'firsthop'), false)")
        await pg.evaluate("t => evalTo(t)", sent + .05)
        seq = await pg.evaluate("() => ({phase:S.route.el.dataset.phase, width:+S.route.fills[0].getAttribute('width'), linkWidth:S.route.linkWidth})")
        assert "propagat" in seq["phase"] and abs(seq["width"] - seq["linkWidth"]) < .1, (sent, seq)

        marks = await pg.evaluate("TIMINGS.store.marks")
        await pg.evaluate("() => seek(BEATS.findIndex(b => b.id === 'store'), false)")
        await pg.evaluate("t => evalTo(t)", marks["full"] + .2)
        seq = await pg.evaluate("() => ({phase:S.route.el.dataset.phase, fills:S.route.fills.map(e => +e.getAttribute('width')), routerFill:+S.route.routerFills[0].getAttribute('width')})")
        assert seq["routerFill"] > 100 and seq["fills"][1] == 0, seq
        await pg.evaluate("t => evalTo(t)", marks["next"] + .2)
        seq = await pg.evaluate("() => ({phase:S.route.el.dataset.phase, fills:S.route.fills.map(e => +e.getAttribute('width'))})")
        assert "send" in seq["phase"] and seq["fills"][1] > 0, seq

        marks = await pg.evaluate("TIMINGS.repeat.marks")
        await pg.evaluate("() => seek(BEATS.findIndex(b => b.id === 'repeat'), false)")
        await pg.evaluate("t => evalTo(t)", marks["hop2"] + .2)
        seq = await pg.evaluate("() => ({fills:S.route.fills.map(e => +e.getAttribute('width')), x:st(S.route.packet).x})")
        assert seq["fills"][1] > 0 and seq["fills"][2] == 0 and seq["x"] == 600, seq
        await pg.evaluate("t => evalTo(t)", marks["hop3"] + .2)
        seq = await pg.evaluate("() => ({phase:S.route.el.dataset.phase, fills:S.route.fills.map(e => +e.getAttribute('width')), x:st(S.route.packet).x})")
        assert seq["fills"][2] > 0 and seq["x"] == 1040, seq

        await pg.evaluate("restart()")
        await pg.wait_for_timeout(100)
        assert await pg.evaluate("Object.keys(SCORE).length") == 0
        assert await pg.evaluate("P.i") == 0
        for i in range(len(BEAT_IDS)):
            await pg.evaluate(f"seek({i}, false)")
        assert not errs, errs
        ignored = [w for w in warnings if "Did not find element expected to be parsed from" not in w]
        assert not ignored, ignored
        known = sum("Did not find element expected to be parsed from" in w for w in warnings)
        durations = await pg.evaluate("BEATS.map(b => TIMINGS[b.id].dur)")
        print(f"{URL} ({len(BEAT_IDS)} beats, {sum(durations):.2f} s narration, {'firefox' if ff else 'chromium'}): replay, cards, oracle, input, locks, scoring, reveal, restart and route sequencing - passed")
        print(f"console: {known} known rel=expect #bar warnings; 0 other warnings; 0 errors")
        await browser.close()


asyncio.run(main())

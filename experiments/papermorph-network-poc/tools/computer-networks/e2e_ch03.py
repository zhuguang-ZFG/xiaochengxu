"""Browser acceptance checks for the stop-and-wait reliable-transport lesson.

    URL=http://localhost:8765/computer-networks/ch03/ uv run --with playwright tools/computer-networks/e2e_ch03.py
    BROWSER=firefox URL=http://localhost:8765/computer-networks/ch03/ uv run --with playwright tools/computer-networks/e2e_ch03.py
"""
import asyncio
import json
import math
import os
from pathlib import Path
import sys

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".qoder" / "skills" / "papermorph" / "scripts"))
from browsers import answers, exe, firefox

URL = os.environ.get("URL", "http://localhost:8765/computer-networks/ch03/").rstrip("/") + "/"
BEAT_IDS = ["intro", "normal", "q1", "timeout", "dataLoss", "ackLoss", "sequence", "lab", "q2", "wrap", "final1", "finish"]
ASK_IDS = {"q1", "lab", "q2", "final1", "finish"}
MARKS = {
    "intro": {"loss"},
    "normal": {"data", "ack", "done"},
    "timeout": {"wait", "timeout"},
    "dataLoss": {"lost", "resend", "delivered"},
    "ackLoss": {"acklost", "duplicate", "discard"},
    "sequence": {"seq", "once"},
    "lab": {"try"},
    "wrap": {"one", "two", "three"},
}
FAULT_NAMES = ["正常", "数据丢失", "确认丢失"]

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
  const c = document.querySelector('.card.quiz, .card.playground, .card.fin');
  if (!c) return null;
  const prompt = c.querySelector('.prompt');
  const cr = c.getBoundingClientRect();
  const pr = prompt?.getBoundingClientRect();
  const lines = pr ? pr.height / (parseFloat(getComputedStyle(prompt).lineHeight) * k) : 0;
  const controls = [...c.querySelectorAll('.opt, input.box, .btn:not([hidden])')].map(e => e.getBoundingClientRect());
  const inside = b => b.width > 0 && b.left >= cr.left - 1 && b.right <= cr.right + 1 && b.top >= cr.top - 1 && b.bottom <= cr.bottom + 1;
  const figure = document.querySelector('.reliable-transport-figure');
  const fig = figure?.getBoundingClientRect();
  const inputs = [...c.querySelectorAll('input.box')].map(e => e.getBoundingClientRect());
  const hits = [...(S.route?.hits || [])].map(e => e.getBoundingClientRect());
  let timeline = null;
  if (figure) {
    const label = [...figure.querySelectorAll('text')].find(e => e.textContent === '协议时间轴 0–100 ms');
    const tick = figure.querySelector('line[stroke="#b54a3a"]');
    const children = [...figure.children];
    const boxes = children.slice(children.indexOf(label), children.indexOf(tick) + 1)
      .map(e => e.getBoundingClientRect()).filter(b => b.width > 0 && b.height > 0);
    if (boxes.length) timeline = {
      left: Math.min(...boxes.map(b => b.left)), right: Math.max(...boxes.map(b => b.right)),
      top: Math.min(...boxes.map(b => b.top)), bottom: Math.max(...boxes.map(b => b.bottom)),
    };
  }
  const overlap = timeline && !(timeline.right <= cr.left || timeline.left >= cr.right || timeline.bottom <= cr.top || timeline.top >= cr.bottom);
  return {promptW: pr ? pr.width / k : 0, lines, ok: controls.every(inside), bottom: (cr.bottom - stage.top) / k,
    figureTop: fig ? (fig.top - stage.top) / k : null, figureBottom: fig ? (fig.bottom - stage.top) / k : null,
    minInputHeight: inputs.length ? Math.min(...inputs.map(b => b.height)) : null,
    minInputWidth: inputs.length ? Math.min(...inputs.map(b => b.width)) : null,
    minHitWidth: hits.length ? Math.min(...hits.map(b => b.width)) : null,
    minHitHeight: hits.length ? Math.min(...hits.map(b => b.height)) : null,
    timelineOverlap: !!overlap};
}
"""

FEEDBACK_OVERLAPS = r"""
() => {
  const fb = document.querySelector('.card .fb');
  if (!fb || !fb.textContent.trim()) return [];
  const f = fb.getBoundingClientRect();
  const intersects = r => r.width > 0 && r.height > 0 && !(r.right <= f.left || r.left >= f.right || r.bottom <= f.top || r.top >= f.bottom);
  const targets = [
    ...document.querySelectorAll('.reliable-transport-figure text, .card .head, .card .head *, .card .body, .card .body *, .card .acts, .card .acts *'),
  ];
  return targets
    .filter(e => intersects(e.getBoundingClientRect()))
    .map(e => ({tag: e.tagName.toLowerCase(), text: e.textContent.trim(), className: e.className?.baseVal ?? e.className ?? ''}));
}
"""

STATE = r"""
() => {
  const r = S.route;
  const controls = [...r.el.querySelectorAll('.fault-option')];
  const data = r.data.getBoundingClientRect();
  const ack = r.ack.getBoundingClientRect();
  const position = e => { const m=e.transform.baseVal.consolidate()?.matrix; return m ? {x:m.e,y:m.f} : {x:0,y:0}; };
  const dp = position(r.data), ap = position(r.ack);
  return {
    fault: r.v.fault,
    sends: +r.sendValue.textContent,
    duplicates: +r.duplicateValue.textContent,
    deliveries: +r.deliveryValue.textContent,
    completion: r.completion,
    completionText: r.completionValue.textContent,
    rootLabel: r.el.getAttribute('aria-label'),
    live: r.controls[0].getAttribute('aria-disabled') === 'false',
    tabIndices: controls.map(e => e.getAttribute('tabindex')),
    checked: controls.map(e => e.getAttribute('aria-checked')),
    radioGroup: (() => { const e=controls[0]?.parentElement; return e ? {role:e.getAttribute('role'), label:e.getAttribute('aria-label')} : null; })(),
    pointerEvents: r.hits.map(e => getComputedStyle(e).pointerEvents),
    touchAction: r.hits.map(e => getComputedStyle(e).touchAction),
    data: {x: dp.x, y: dp.y, opacity: +r.data.getAttribute('opacity'), label: r.data.textContent.trim(), screenWidth: data.width},
    ack: {x: ap.x, y: ap.y, opacity: +r.ack.getAttribute('opacity'), label: r.ack.textContent.trim(), screenWidth: ack.width},
    lossOpacity: +getComputedStyle(r.el.querySelector('path[stroke="#b54a3a"]').parentElement).opacity,
    discardOpacity: +getComputedStyle(r.el.querySelector('.discard-mark')).opacity,
    phase: r.el.dataset.phase,
    stageRole: document.getElementById('stage').getAttribute('role'),
    nodes: [...r.el.querySelectorAll('.route-node')].map(e => { const b=e.getBoundingClientRect(); return {left:b.left,right:b.right,top:b.top,bottom:b.bottom,width:b.width}; }),
    api: ['v','el','data','ack','sendValue','duplicateValue','deliveryValue','completionValue','controls','hits','pose','at','set','live','nudge','focus','onChange','phase'].every(k => k in r),
  };
}
"""


def oracle(fault):
    return {
        0: {"sends": 1, "duplicates": 0, "deliveries": 1, "completion": 40},
        1: {"sends": 2, "duplicates": 0, "deliveries": 1, "completion": 100},
        2: {"sends": 2, "duplicates": 1, "deliveries": 1, "completion": 100},
    }[fault]


def expected_at(fault, ms):
    sends = 2 if fault in (1, 2) and ms >= 60 else 1
    duplicates = 1 if fault == 2 and ms >= 80 else 0
    if fault == 0:
        deliveries = 1 if ms >= 20 else 0
    elif fault == 1:
        deliveries = 1 if ms >= 80 else 0
    else:
        deliveries = 1 if ms >= 20 else 0
    completion = 40 if fault == 0 and ms >= 40 else 100 if fault != 0 and ms >= 100 else None
    return {"sends": sends, "duplicates": duplicates, "deliveries": deliveries, "completion": completion}


def expected_pose(fault, ms):
    lerp = lambda a, b, q: a + (b - a) * q
    p = expected_at(fault, ms)
    p.update(dataX=360.0, dataOpacity=0, dataText="DATA 0", ackX=680.0, ackOpacity=0,
             lossOpacity=0, discardOpacity=0, receiverOpacity=0, appOpacity=0, phase="complete")
    if fault == 0:
        if ms < 20:
            p.update(dataX=lerp(360, 680, ms / 20), dataOpacity=1, phase="data-in-flight")
        elif ms < 40:
            p.update(ackX=lerp(680, 360, (ms - 20) / 20), ackOpacity=1,
                     receiverOpacity=1, appOpacity=1,
                     phase="data-delivered" if ms < 22 else "ack-in-flight")
    elif fault == 1:
        if ms < 12:
            p.update(dataX=lerp(360, 520, ms / 12), dataOpacity=1 if ms < 8 else 1 - (ms - 8) / 4,
                     lossOpacity=1 if ms >= 8 else 0,
                     phase="first-data-in-flight" if ms < 8 else "data-lost")
        elif ms < 60:
            p.update(lossOpacity=.45, phase="waiting-timeout")
        elif ms < 80:
            p.update(dataX=lerp(360, 680, (ms - 60) / 20), dataOpacity=1, phase="retransmit")
        elif ms < 100:
            p.update(ackX=lerp(680, 360, (ms - 80) / 20), ackOpacity=1,
                     receiverOpacity=1, appOpacity=1,
                     phase="retransmit-delivered" if ms < 82 else "ack-in-flight")
    else:
        if ms < 20:
            p.update(dataX=lerp(360, 680, ms / 20), dataOpacity=1, phase="data-in-flight")
        elif ms < 34:
            p.update(ackX=lerp(680, 520, (ms - 20) / 14),
                     ackOpacity=1 if ms < 30 else 1 - (ms - 30) / 4,
                     lossOpacity=1 if ms >= 30 else 0, receiverOpacity=1, appOpacity=1,
                     phase="ack-in-flight" if ms < 30 else "ack-lost")
        elif ms < 60:
            p.update(lossOpacity=.45, receiverOpacity=.6, appOpacity=.6, phase="waiting-timeout")
        elif ms < 80:
            p.update(dataX=lerp(360, 680, (ms - 60) / 20), dataOpacity=1, dataText="重复 DATA 0",
                     receiverOpacity=.6, appOpacity=.6, phase="duplicate-in-flight")
        elif ms < 100:
            p.update(dataX=680.0, dataOpacity=1 if ms < 82 else 0, dataText="重复 DATA 0",
                     ackX=lerp(680, 360, (ms - 80) / 20), ackOpacity=1,
                     discardOpacity=1 if ms >= 82 else 0, receiverOpacity=1, appOpacity=1,
                     phase="duplicate-received" if ms < 82 else "duplicate-discarded")
    return p


def assert_value(got, want, row, key):
    if isinstance(want, float):
        assert math.isclose(got, want, rel_tol=0, abs_tol=1e-4), (row, key, want)
    else:
        assert got == want, (row, key, want)


def assert_state(s, fault):
    want = oracle(fault)
    assert s["api"], s
    assert s["fault"] == fault, s
    assert s["sends"] == want["sends"], s
    assert s["duplicates"] == want["duplicates"], s
    assert s["deliveries"] == want["deliveries"], s
    assert s["completion"] == want["completion"], s
    assert s["completionText"] == f"{want['completion']} ms", s
    assert s["checked"] == ["true" if i == fault else "false" for i in range(3)], s
    assert FAULT_NAMES[fault] in s["rootLabel"], s


async def open_beat(pg, bid):
    await pg.evaluate("id => seek(BEATS.findIndex(b => b.id === id), false)", bid)
    await pg.wait_for_timeout(180)


async def check_card(pg, bid):
    m = await pg.evaluate(CARD)
    assert m is not None, bid
    assert m["promptW"] > 400 and m["lines"] <= 4 and m["ok"] and m["bottom"] <= 901, (bid, m)
    if m["figureTop"] is not None:
        assert m["figureTop"] >= -1 and m["figureBottom"] <= 901, (bid, m)
    if bid == "q1":
        assert m["minInputHeight"] >= 24, (bid, m)
        assert m["minInputWidth"] >= 24, (bid, m)
        assert not m["timelineOverlap"], (bid, m)
    if bid in ("lab", "q2", "final1"):
        assert m["minHitWidth"] >= 24 and m["minHitHeight"] >= 24, (bid, m)


async def option_center(pg, fault):
    return await pg.evaluate("""fault => {
      const e = S.route.controls[fault];
      const b = e.getBoundingClientRect();
      return {x: b.left + b.width / 2, y: b.top + b.height / 2};
    }""", fault)


async def click_option(pg, fault):
    point = await option_center(pg, fault)
    await pg.mouse.click(point["x"], point["y"])


async def touch_option(pg, fault):
    point = await pg.evaluate("""fault => {
      const b = S.route.hits[fault].getBoundingClientRect();
      return {x: b.left + b.width / 2, y: b.top + b.height / 2};
    }""", fault)
    await pg.touchscreen.tap(point["x"], point["y"])
    await pg.wait_for_timeout(50)


async def main():
    narration = json.loads((ROOT / "content/computer-networks/ch03/narration.zh.json").read_text(encoding="utf-8"))
    assert set(narration["beats"]) == set(BEAT_IDS)
    assert "计时器在数据发出时就开始计时" in narration["beats"]["timeout"]
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
        await pg.wait_for_timeout(250)
        assert abs((await pg.evaluate("P.t")) - t1) < .05, "pause holds"
        await pg.evaluate("t => { P.t = t; evalTo(t); }", t1 + .2)
        assert abs((await pg.evaluate("P.t")) - t1 - .2) < .05, "seek sets clock"

        for i, bid in enumerate(BEAT_IDS):
            if bid in ASK_IDS:
                continue
            dur = await pg.evaluate(f"TIMINGS['{bid}'].dur")
            for t in (round(dur * .55, 2), round(dur - .25, 2)):
                assert await pg.evaluate(SAME_FRAME, [i, t]), (bid, t, "seek differs from stepped frame")

        await open_beat(pg, "lab")
        protocol = await pg.evaluate("""() => {
          const r = S.route;
          const times = [0, 10, 19, 20, 30, 39, 40, 59, 60, 79, 80, 82, 99, 100];
          const out = [];
          const position = e => { const m=e.transform.baseVal.consolidate()?.matrix; return m ? m.e : 0; };
          for (let fault = 0; fault < 3; fault++) {
            r.set(fault);
            for (const ms of times) {
              const a = r.pose(ms), b = r.pose(ms);
              r.at(ms);
              out.push({fault, ms, pure: JSON.stringify(a) === JSON.stringify(b), pose:a,
                sends:+r.sendValue.textContent, duplicates:+r.duplicateValue.textContent,
                deliveries:+r.deliveryValue.textContent, completion:r.completion,
                dataX:position(r.data), ackX:position(r.ack), dataLabel:r.data.textContent.trim(), rootPhase:r.el.dataset.phase,
                dataOpacity:+r.data.getAttribute('opacity'), ackOpacity:+r.ack.getAttribute('opacity'),
                lossOpacity:+getComputedStyle(r.el.querySelector('path[stroke="#b54a3a"]').parentElement).opacity,
                discardOpacity:+getComputedStyle(r.el.querySelector('.discard-mark')).opacity,
                receiverOpacity:(() => { const e=r.el.querySelector('circle[stroke="#d96c3f"]'); return {value:+getComputedStyle(e).opacity, valid:e.hasAttribute('opacity') && !e.hasAttribute('o')}; })(),
                appOpacity:(() => { const e=r.el.querySelector('circle[stroke="#247ba0"]'); return {value:+getComputedStyle(e).opacity, valid:e.hasAttribute('opacity') && !e.hasAttribute('o')}; })(),
                timeoutOpacity:+getComputedStyle(r.el.querySelector('line[stroke="#b54a3a"]')).opacity,
                packetGap:r.ack.getBoundingClientRect().top - r.data.getBoundingClientRect().bottom,
                discardOverlap:(() => {
                  const d = r.data.getBoundingClientRect();
                  const mark = r.el.querySelector('.discard-mark');
                  const m = mark.getBoundingClientRect();
                  return !(d.right <= m.left || d.left >= m.right || d.bottom <= m.top || d.top >= m.bottom);
                })()});
            }
          }
          return out;
        }""")
        for row in protocol:
            assert row["pure"], row
            want = expected_pose(row["fault"], row["ms"])
            dom = {key: row[key] for key in ("sends", "duplicates", "deliveries", "completion", "dataX", "ackX",
                                             "dataOpacity", "ackOpacity", "lossOpacity", "discardOpacity")}
            dom.update(dataText=row["dataLabel"], phase=row["rootPhase"], receiverOpacity=row["receiverOpacity"]["value"],
                       appOpacity=row["appOpacity"]["value"])
            for key, value in want.items():
                assert_value(row["pose"][key], value, row, f"pose.{key}")
                assert_value(dom[key], value, row, f"dom.{key}")
            for key in ("receiverOpacity", "appOpacity"):
                assert row[key]["valid"], row
            assert row["timeoutOpacity"] == (.25 if row["fault"] == 0 else 1), row
            if row["fault"] == 2 and row["ms"] == 80:
                assert row["packetGap"] >= 0, row
                assert not row["discardOverlap"], row
        for fault in range(3):
            await pg.evaluate("fault => S.route.set(fault)", fault)
            assert_state(await pg.evaluate(STATE), fault)

        for vw, vh in [(1280, 800), (1920, 1080), (390, 844)]:
            await pg.set_viewport_size({"width": vw, "height": vh})
            for bid in ("q1", "lab", "q2", "final1", "finish"):
                await open_beat(pg, bid)
                await check_card(pg, bid)
                if vw == 390 and bid == "q1":
                    await pg.locator(".card input.box").fill("20")
                    await pg.keyboard.press("Enter")
                    await pg.wait_for_timeout(150)
                    assert "还不对" in await pg.locator(".card .fb").inner_text()
                    await check_card(pg, bid)
                    await pg.locator(".card input.box").fill("40")
                    await pg.keyboard.press("Enter")
                    await pg.wait_for_timeout(150)
                    assert "正确" in await pg.locator(".card .fb").inner_text()
                    await check_card(pg, bid)
                if bid != "finish":
                    state = await pg.evaluate(STATE)
                    stage = await pg.locator("#stage").bounding_box()
                    assert len(state["nodes"]) == 3, (bid, state["nodes"])
                    for node in state["nodes"]:
                        assert node["width"] > 0 and node["left"] >= stage["x"] - 1 and node["right"] <= stage["x"] + stage["width"] + 1, (bid, node)
                        assert node["top"] >= stage["y"] - 1 and node["bottom"] <= stage["y"] + stage["height"] + 1, (bid, node)

        await pg.set_viewport_size({"width": 320, "height": 568})
        await open_beat(pg, "q1")
        await check_card(pg, "q1")
        await pg.evaluate("restart()")
        await pg.wait_for_timeout(100)
        await pg.set_viewport_size({"width": 1440, "height": 900})
        await open_beat(pg, "q1")
        q1 = await pg.evaluate(STATE)
        assert q1["completionText"] == "? ms" and "完成时间 40" not in q1["rootLabel"], q1
        await pg.locator(".card input.box").fill("20")
        await pg.keyboard.press("Enter")
        assert "还不对" in await pg.locator(".card .fb").inner_text()
        await pg.locator(".card input.box").fill("40")
        await pg.keyboard.press("Enter")
        assert "正确" in await pg.locator(".card .fb").inner_text()
        assert (await pg.evaluate("SCORE['c-rtt']"))["right"] == 0
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(150)
        assert await pg.evaluate("BEATS[P.i].id") == "timeout"

        await open_beat(pg, "normal")
        await pg.evaluate("t => evalTo(t)", await pg.evaluate("TIMINGS.normal.marks.data") + .1)
        early = await pg.evaluate(STATE)
        assert early["deliveries"] == 0 and early["completion"] is None, early
        await pg.evaluate("t => evalTo(t)", await pg.evaluate("TIMINGS.normal.marks.done") + .1)
        done = await pg.evaluate(STATE)
        assert_state(done, 0)

        await open_beat(pg, "dataLoss")
        await pg.evaluate("t => evalTo(t)", await pg.evaluate("TIMINGS.dataLoss.marks.lost") + .2)
        lost = await pg.evaluate(STATE)
        assert lost["deliveries"] == 0 and lost["completion"] is None, lost
        await pg.evaluate("t => evalTo(t)", await pg.evaluate("TIMINGS.dataLoss.marks.delivered") + .2)
        delivered = await pg.evaluate(STATE)
        assert delivered["deliveries"] == 1 and delivered["duplicates"] == 0 and delivered["completion"] is None, delivered

        await open_beat(pg, "timeout")
        for at, expected_ms in [(.2, 0)] + [
            (await pg.evaluate("mark => TIMINGS.timeout.marks[mark]", mark), ms)
            for mark, ms in [("wait", 10), ("timeout", 60)]
        ]:
            await pg.evaluate("t => { P.t=t; evalTo(t); }", at)
            cursor_x = await pg.evaluate("+S.route.el.querySelector('line[stroke=\"#202b33\"][stroke-width=\"4\"]').getAttribute('x1')")
            assert abs((cursor_x - 300) / 10 - expected_ms) < .2, (at, expected_ms, cursor_x)

        await open_beat(pg, "ackLoss")
        for mark, offset, duplicates, data_opacity, ack_opacity, discard_opacity, phase in [
            ("duplicate", -.01, 0, 1, 0, 0, "duplicate-in-flight"),
            ("duplicate", .01, 1, 1, 1, 0, "duplicate-received"),
            ("discard", -.01, 1, 1, 1, 0, "duplicate-received"),
            ("discard", .01, 1, 0, 1, 1, "duplicate-discarded"),
        ]:
            at = await pg.evaluate("mark => TIMINGS.ackLoss.marks[mark]", mark) + offset
            await pg.evaluate("t => { P.t=t; evalTo(t); }", at)
            frame = await pg.evaluate(STATE)
            assert frame["deliveries"] == 1 and frame["duplicates"] == duplicates, (mark, offset, frame)
            assert frame["data"]["opacity"] == data_opacity and frame["discardOpacity"] == discard_opacity, (mark, offset, frame)
            assert frame["ack"]["opacity"] == ack_opacity and frame["phase"] == phase, (mark, offset, frame)
            assert "重复" in frame["data"]["label"], frame

        await open_beat(pg, "lab")
        lab_state = await pg.evaluate(STATE)
        assert_state(lab_state, 0)
        assert lab_state["radioGroup"] == {"role": "radiogroup", "label": "选择链路故障"}, lab_state
        assert await pg.locator(".card.playground").count() == 1
        before_scores = await pg.evaluate("Object.keys(SCORE).sort()")
        await pg.locator(".fault-option").first.focus()
        await pg.keyboard.press("ArrowRight")
        assert_state(await pg.evaluate(STATE), 1)
        await pg.keyboard.press("End")
        assert_state(await pg.evaluate(STATE), 2)
        await pg.keyboard.press("Home")
        assert_state(await pg.evaluate(STATE), 0)
        assert await pg.evaluate("Object.keys(SCORE).sort()") == before_scores
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(150)
        assert await pg.evaluate("BEATS[P.i].id") == "q2"

        await open_beat(pg, "q2")
        await click_option(pg, 2)
        assert_state(await pg.evaluate(STATE), 2)
        await pg.get_by_role("button", name="检查 Enter").click()
        assert "正确" in await pg.locator(".card .fb").inner_text()
        locked = await pg.evaluate(STATE)
        assert not locked["live"] and locked["tabIndices"] == ["-1", "-1", "-1"], locked
        assert locked["pointerEvents"] == ["none", "none", "none"] and locked["touchAction"] == ["auto", "auto", "auto"], locked
        assert locked["stageRole"] == "img", locked

        await pg.set_viewport_size({"width": 390, "height": 844})
        await open_beat(pg, "q2")
        await touch_option(pg, 2)
        touched = await pg.evaluate(STATE)
        assert_state(touched, 2)
        assert touched["live"] and await pg.evaluate("document.activeElement === S.route.controls[2]"), touched
        await pg.get_by_role("button", name="检查 Enter").click()
        assert "正确" in await pg.locator(".card .fb").inner_text()
        assert not (await pg.evaluate(STATE))["live"]

        await pg.set_viewport_size({"width": 1440, "height": 900})
        await pg.evaluate("restart()")
        await pg.wait_for_timeout(100)
        await open_beat(pg, "q2")
        await click_option(pg, 0)
        await pg.get_by_role("button", name="检查 Enter").click()
        assert "还不对" in await pg.locator(".card .fb").inner_text()
        await click_option(pg, 2)
        await pg.get_by_role("button", name="检查 Enter").click()
        assert (await pg.evaluate("SCORE['c-ack-loss']"))["right"] == 0
        await open_beat(pg, "q2")
        await click_option(pg, 2)
        await pg.get_by_role("button", name="检查 Enter").click()
        assert (await pg.evaluate("SCORE['c-ack-loss']"))["right"] == 0
        await pg.evaluate("restart()")
        await pg.wait_for_timeout(100)
        await open_beat(pg, "q2")
        await click_option(pg, 2)
        await pg.get_by_role("button", name="检查 Enter").click()
        assert (await pg.evaluate("SCORE['c-ack-loss']"))["right"] == 1
        await open_beat(pg, "q2")
        await click_option(pg, 0)
        await pg.get_by_role("button", name="检查 Enter").click()
        await pg.keyboard.press("S")
        answer = await pg.locator(".card .fb").inner_text()
        assert "答案：" in answer and "确认丢失" in answer, answer
        assert_state(await pg.evaluate(STATE), 2)

        await open_beat(pg, "q2")
        await pg.locator(".fault-option").first.focus()
        await pg.keyboard.press("Shift+ArrowRight")
        await pg.wait_for_timeout(150)
        assert await pg.evaluate("BEATS[P.i].id") == "wrap"

        await open_beat(pg, "final1")
        await click_option(pg, 0)
        await pg.get_by_role("button", name="检查 Enter").click()
        assert "还不对" in await pg.locator(".card .fb").inner_text()
        assert (await pg.evaluate("SCORE['p-fault-state']")) == {"right": 0, "total": 1}
        await click_option(pg, 1)
        await pg.get_by_role("button", name="检查 Enter").click()
        assert (await pg.evaluate("SCORE['p-fault-state']")) == {"right": 0, "total": 1}

        await open_beat(pg, "final1")
        await click_option(pg, 0)
        await pg.get_by_role("button", name="检查 Enter").click()
        assert "还不对" in await pg.locator(".card .fb").inner_text()
        await pg.keyboard.press("S")
        answer = await pg.locator(".card .fb").inner_text()
        assert "答案：" in answer and "2 次发送" in answer and "0 次重复" in answer and "1 次应用交付" in answer and "100 ms" in answer, answer
        assert_state(await pg.evaluate(STATE), 1)
        assert not (await pg.evaluate(STATE))["live"]
        assert (await pg.evaluate("SCORE['p-fault-state']")) == {"right": 0, "total": 1}

        await pg.evaluate("restart()")
        await pg.wait_for_timeout(100)
        await open_beat(pg, "final1")
        await click_option(pg, 1)
        assert_state(await pg.evaluate(STATE), 1)
        await pg.get_by_role("button", name="检查 Enter").click()
        assert (await pg.evaluate("SCORE['p-fault-state']")) == {"right": 1, "total": 1}
        await open_beat(pg, "final1")
        await click_option(pg, 0)
        await pg.get_by_role("button", name="检查 Enter").click()
        assert (await pg.evaluate("SCORE['p-fault-state']")) == {"right": 1, "total": 1}

        await open_beat(pg, "final1")
        await click_option(pg, 1)
        await pg.get_by_role("button", name="检查 Enter").click()
        feedback = await pg.locator(".card .fb").inner_text()
        assert "正确" in feedback and "2 次发送" in feedback and "0 次重复" in feedback and "1 次应用交付" in feedback and "100 ms" in feedback, feedback
        assert not await pg.evaluate(FEEDBACK_OVERLAPS), await pg.evaluate(FEEDBACK_OVERLAPS)
        assert await pg.locator(".card .fb").evaluate("e => e.scrollHeight <= e.clientHeight + 1")
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(180)
        assert await pg.evaluate("BEATS[P.i].id") == "finish" and await pg.is_visible(".card.fin")
        finish = await pg.locator(".card.fin").inner_text()
        assert "第 3 章完成" in finish and "本章练习：第一次就答对 1 / 1。" in finish, finish
        assert 3 in (await pg.evaluate("JSON.parse(localStorage.getItem(BOOK_PROGRESS_KEY))"))["done"]

        assert not errs, errs
        known = [w for w in warnings if "rel=expect #bar" in w]
        other = [w for w in warnings if "rel=expect #bar" not in w]
        assert not other, other
        print(f"{URL} (12 beats, {os.environ.get('BROWSER', 'chromium')}): protocol oracle, deterministic replay, cards, input, locks, scoring, reveal and restart - passed")
        print(f"console: {len(known)} known rel=expect #bar warnings; {len(other)} other warnings; {len(errs)} errors")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())

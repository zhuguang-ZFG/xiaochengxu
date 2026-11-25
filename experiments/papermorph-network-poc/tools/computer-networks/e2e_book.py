"""Acceptance checks for the private three-chapter book and its navigation.

    URL=http://localhost:8765/computer-networks/ uv run --with playwright tools/computer-networks/e2e_book.py
    BROWSER=firefox URL=http://localhost:8765/computer-networks/ uv run --with playwright tools/computer-networks/e2e_book.py
"""
import asyncio
import os
from pathlib import Path
import sys
from urllib.parse import urljoin

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".qoder" / "skills" / "papermorph" / "scripts"))
from browsers import answers, exe, firefox, missing

URL = os.environ.get("URL", "http://localhost:8765/computer-networks/").rstrip("/") + "/"
CHAPTERS = [
    (1, "链路速率与时延", "../ch02/"),
    (2, "存储转发：一跳一跳地等", "../ch03/"),
    (3, "可靠传输：丢了怎么办", None),
]


async def open_beat(pg, bid):
    await pg.evaluate("id => seek(BEATS.findIndex(b => b.id === id), false)", bid)
    await pg.wait_for_timeout(180)


async def check_contents(pg):
    await pg.goto(URL + "#contents")
    await pg.wait_for_selector("#ch03")
    cards = await pg.locator("#units a.ch").evaluate_all(
        "els => els.map(e => ({id:e.id, href:e.getAttribute('href'), "
        "number:e.querySelector('b').textContent.trim(), title:e.querySelector('span').textContent.trim(), "
        "minutes:e.querySelector('small').textContent.trim()}))"
    )
    assert cards == [
        {"id": f"ch{n:02d}", "href": f"ch{n:02d}/", "number": str(n), "title": title, "minutes": "4 分钟"}
        for n, title, _ in CHAPTERS
    ], cards
    assert await pg.locator("#units .unit").count() == 3
    assert await pg.locator("#units .unit-art").count() == 3
    assert await pg.locator("#prog").inner_text() == "3 章"
    assert "3 章" in await pg.locator("#meta").inner_text()
    assert (await pg.locator("#cover h1").inner_text()).replace("\n", "") == "计算机网络三章互动课"
    lede = await pg.locator("#cover .lede").inner_text()
    assert all(topic in lede for topic in ("链路速率", "存储转发", "可靠传输")), lede
    assert "三章" in await pg.title()
    for width, height in [(1440, 900), (390, 844), (320, 568)]:
        await pg.set_viewport_size({"width": width, "height": height})
        await pg.goto(URL + "#contents")
        await pg.wait_for_timeout(200)
        assert await pg.evaluate("document.documentElement.scrollWidth <= innerWidth"), (width, "horizontal overflow")
        boxes = await pg.locator("#units a.ch").evaluate_all("els => els.map(e => e.getBoundingClientRect().toJSON())")
        assert len(boxes) == 3 and all(b["width"] >= 24 and b["height"] >= 24 for b in boxes), (width, boxes)


async def check_next(pg, n, title, next_href):
    chapter_url = URL + f"ch{n:02d}/"
    await pg.goto(chapter_url)
    await pg.wait_for_function("typeof BEATS !== 'undefined'")
    await pg.keyboard.press("Space")
    await pg.wait_for_timeout(120)
    await pg.keyboard.press("Space")
    chapter = await pg.evaluate("CHAPTER")
    assert chapter["number"] == n and chapter["title"] == title, chapter
    assert chapter.get("next") == next_href, chapter
    await open_beat(pg, "finish")
    if next_href is None:
        assert await pg.get_by_role("button", name="下一章 Enter").count() == 0
        assert await pg.get_by_role("button", name="再看一遍 Enter").count() == 1
        return
    button = pg.get_by_role("button", name="下一章 Enter")
    assert await button.count() == 1
    expected = urljoin(chapter_url, next_href)
    async with pg.expect_navigation(wait_until="domcontentloaded"):
        await button.click()
    assert pg.url == expected, (pg.url, expected)
    await pg.wait_for_function("typeof BEATS !== 'undefined'")
    assert await pg.evaluate("CHAPTER.number") == n + 1


async def check_cards(pg):
    for n, title, _ in CHAPTERS:
        await pg.goto(URL + f"#ch{n:02d}")
        await pg.wait_for_selector(f"#ch{n:02d}")
        await pg.locator(f"#ch{n:02d}").click()
        await pg.wait_for_url(URL + f"ch{n:02d}/")
        await pg.wait_for_function("typeof BEATS !== 'undefined'")
        assert await pg.evaluate("CHAPTER.number") == n


async def main():
    browser_name = os.environ.get("BROWSER", "chromium")
    answers(URL)
    async with async_playwright() as p:
        b = await (p.firefox.launch(**firefox()) if browser_name == "firefox" else p.chromium.launch(**exe()))
        pg = await b.new_page(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
        errors, absent = [], []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: m.type == "error" and errors.append(m.text))
        missing(pg, absent.append)
        await check_contents(pg)
        await check_cards(pg)
        for n, title, next_href in CHAPTERS:
            await check_next(pg, n, title, next_href)
        await b.close()
    assert not absent, absent
    assert not errors, errors
    print(f"{browser_name}: 3 chapter cards, responsive contents, card entry and completion navigation passed; "
          "0 missing files, 0 console errors, 0 page errors")


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(asyncio.run(main()))

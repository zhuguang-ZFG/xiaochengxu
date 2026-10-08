# -*- coding: utf-8 -*-
"""仓库一致性校验脚本（本地与 CI 共用）。

检查项：
1. 元数据：每篇文档 frontmatter 字段完整；category 与所在目录一致
2. 图片引用：所有 ![...](...) 指向存在文件
3. 相对链接：所有 [..](相对路径) 指向存在文件
4. 目录序号：docs 各分类目录序号连续（1,2,3...）
5. 孤儿资产：docs/assets/ 下无未被引用的文件
6. JSON 合法性：示例工程与配置文件的 json 可解析
7. JS 语法：示例工程 js 可被 node 解析（python 侧仅做括号粗查，CI 用 node）

用法：python tools/check_repo.py
退出码：0 = 全部通过；1 = 存在问题
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"
CONTRACT_NAME = "_契约.md"

META_FIELDS = ["title", "description", "category", "tags", "difficulty", "reading_time", "updated"]
CATEGORY_DIR = {
    "00-学习路线": "学习路线", "01-入门": "入门", "02-基础": "基础", "03-进阶": "进阶",
    "04-云开发": "云开发", "05-发布": "发布", "06-实战": "实战", "07-资源": "资源",
}

errors = []


def md_files():
    return [f for f in DOCS.rglob("*.md") if f.name != CONTRACT_NAME]


def check_metadata():
    for f in md_files():
        t = f.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n", t, re.S)
        if not m:
            errors.append(f"{f.relative_to(ROOT)}: 缺 YAML frontmatter")
            continue
        yaml = m.group(1)
        for field in META_FIELDS:
            if not re.search(rf"^{field}:", yaml, re.M):
                errors.append(f"{f.relative_to(ROOT)}: 缺字段 {field}")
        cat = re.search(r"^category: (.+)$", yaml, re.M)
        if cat:
            dirname = f.parent.name
            expected = CATEGORY_DIR.get(dirname)
            if expected and cat.group(1) != expected:
                errors.append(f"{f.relative_to(ROOT)}: category={cat.group(1)} 与目录 {dirname} 不一致（应为 {expected}）")


def check_images():
    for f in md_files() + [ROOT / "README.md"]:
        t = f.read_text(encoding="utf-8")
        for m in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", t):
            target = m.group(1)
            if target.startswith(("http", "//")):
                continue
            if not (f.parent / target).resolve().exists():
                errors.append(f"{f.relative_to(ROOT)}: 图片断链 -> {target}")


def check_links():
    for f in md_files() + [ROOT / "README.md"]:
        t = f.read_text(encoding="utf-8")
        for m in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", t):
            link = m.group(1)
            if link.startswith(("http", "#", "mailto:")):
                continue
            target = link.split("#")[0]
            if not target:
                continue
            if not (f.parent / target).resolve().exists():
                errors.append(f"{f.relative_to(ROOT)}: 相对链接断链 -> {link}")


def check_sequence():
    from collections import defaultdict
    seq = defaultdict(list)
    for f in DOCS.rglob("*.md"):
        if f.name == CONTRACT_NAME:
            continue
        m = re.match(r"(\d+)-", f.name)
        if m:
            seq[f.parent.name].append(int(m.group(1)))
    for dirname, nums in sorted(seq.items()):
        nums.sort()
        expected = list(range(1, len(nums) + 1))
        if nums != expected:
            errors.append(f"docs/{dirname}: 序号非连续 {nums}（应为 {expected}）")


def check_orphans():
    referenced = set()
    for f in md_files() + [ROOT / "README.md"]:
        t = f.read_text(encoding="utf-8")
        for m in re.finditer(r"assets/([^)\s]+)", t):
            referenced.add(m.group(1))
    for a in ASSETS.iterdir():
        if not a.is_file():
            continue
        if a.name not in referenced:
            errors.append(f"孤儿资产（未被任何文档引用）: docs/assets/{a.name}")


def check_gif_size():
    """契约硬限制：动画 GIF 单文件 ≤ 200KB"""
    for g in ASSETS.glob("*.gif"):
        size = g.stat().st_size
        if size > 200 * 1024:
            errors.append(f"{g.name}: {size} bytes 超过 200KB 上限（契约视觉资产规范）")


def check_example_structure():
    """示例工程结构一致性：app.json 页面/云函数与磁盘文件对应"""
    ex = ROOT / "examples" / "todo-miniprogram"
    if not ex.exists():
        return
    app = ex / "app.json"
    try:
        cfg = json.loads(app.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"examples/todo-miniprogram/app.json 非法: {e}")
        return
    for p in cfg.get("pages", []):
        if not (ex / f"{p}.wxml").exists():
            errors.append(f"示例工程 app.json 页面无对应文件: {p}")
    # tabBar 图标（若有）
    tab = cfg.get("tabBar", {}).get("list", [])
    for item in tab:
        for key in ("iconPath", "selectedIconPath"):
            ic = item.get(key)
            if ic and not (ex / ic.lstrip("/")).exists():
                errors.append(f"示例工程 tabBar 图标缺失: {ic}")
    # 云函数目录
    cf_root = cfg.get("cloudfunctionRoot", "").strip("/")
    if cf_root:
        cdir = ex / cf_root
        if not cdir.is_dir():
            errors.append(f"示例工程 cloudfunctionRoot 目录缺失: {cf_root}")
        for fn in cdir.iterdir():
            if fn.is_dir() and not (fn / "index.js").exists():
                errors.append(f"示例工程云函数缺 index.js: {fn.name}")


def check_json():
    for f in (ROOT / "examples").rglob("*.json"):
        try:
            json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"{f.relative_to(ROOT)}: JSON 非法 -> {e}")


def check_js_syntax():
    """括号粗查（CI 会用 node --check 做严格校验）"""
    for f in (ROOT / "examples").rglob("*.js"):
        code = f.read_text(encoding="utf-8")
        stripped = re.sub(r'"[^"]*"|\'[^\']*\'|`[^`]*`|//[^\n]*|/\*.*?\*/', "", code, flags=re.S)
        for o, c in [("{", "}"), ("(", ")"), ("[", "]")]:
            if stripped.count(o) != stripped.count(c):
                errors.append(f"{f.relative_to(ROOT)}: JS 括号不匹配 {o}={stripped.count(o)} {c}={stripped.count(c)}")


def check_fences_language():
    """契约：代码块必须标注语言（开围栏 ```lang 非空），且所有围栏闭合"""
    for f in md_files() + [ROOT / "README.md"]:
        t = f.read_text(encoding="utf-8")
        in_fence = False
        for i, line in enumerate(t.splitlines(), 1):
            m = re.match(r"^```(\S*)\s*$", line)
            if not m:
                continue
            if not in_fence:
                if not m.group(1):
                    errors.append(f"{f.relative_to(ROOT)}:{i}: 代码块未标注语言（应 ```js / ```wxml / ```text 等）")
                in_fence = True
            else:
                in_fence = False
        if in_fence:
            errors.append(f"{f.relative_to(ROOT)}: 代码块未闭合")


def check_crossref_order():
    """教学顺序 = README 表格顺序；每篇「上一篇/下一篇」必须指向顺序中的相邻篇"""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    order = []  # (路径, 标题)
    in_table = False
    for line in readme.splitlines():
        if line.startswith("| 阶段 |"):
            in_table = True
            continue
        if in_table and line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            m = re.search(r"\[([^\]]+)\]\(([^)]+)\)", cells[1]) if len(cells) >= 2 else None
            if m and "---" not in cells[0]:
                order.append((str((ROOT / m.group(2)).resolve()), m.group(1)))

    for f in md_files():
        if f.parent.name == "00-学习路线":
            continue
        t = f.read_text(encoding="utf-8")
        rel = f.relative_to(ROOT)
        try:
            idx = next(i for i, (p, _) in enumerate(order) if p == str(f.resolve()))
        except StopIteration:
            errors.append(f"{rel}: 不在 README 教学顺序表格中")
            continue
        prev = re.search(r"^- 本库上一篇：\[([^\]]+)\]\(([^)]+)\)", t, re.M)
        nxt = re.search(r"^- 本库下一篇：\[([^\]]+)\]\(([^)]+)\)", t, re.M)
        if prev:
            target = str((f.parent / prev.group(2).split("#")[0]).resolve())
            if idx == 0:
                errors.append(f"{rel}: 是教学第一篇，却声明了上一篇 -> {prev.group(2)}")
            elif target != order[idx - 1][0]:
                errors.append(f"{rel}: 上一篇指向 {prev.group(2)}，教学顺序应为 {order[idx-1][1]}")
        if nxt:
            target = str((f.parent / nxt.group(2).split("#")[0]).resolve())
            if idx == len(order) - 1:
                errors.append(f"{rel}: 是教学末篇，却声明了下一篇 -> {nxt.group(2)}")
            elif target != order[idx + 1][0]:
                errors.append(f"{rel}: 下一篇指向 {nxt.group(2)}，教学顺序应为 {order[idx+1][1]}")


def check_external_links():
    """外链 HTTP 状态校验（默认关闭：CI/第三方站点网络波动不应阻断校验；
    需要时用 --external 显式启用）"""
    import urllib.request, ssl, concurrent.futures
    ctx = ssl.create_default_context()
    links = {}
    for f in md_files() + [ROOT / "README.md"]:
        t = f.read_text(encoding="utf-8")
        for m in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", t):
            u = m.group(1)
            if u.startswith(("http://", "https://")):
                links.setdefault(u, f.relative_to(ROOT))

    def check(u):
        for _ in range(2):  # 失败重试一次
            try:
                req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
                    return u, r.status
            except Exception:
                continue
        return u, None

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for u, st in ex.map(check, links):
            if st is None or st >= 400:
                errors.append(f"{links[u]}: 外链异常 -> {u} (HTTP {st})")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--external", action="store_true",
                        help="启用外链 HTTP 状态校验（默认关闭，CI 稳定优先）")
    args = parser.parse_args()
    check_metadata()
    check_images()
    check_links()
    check_sequence()
    check_orphans()
    check_gif_size()
    check_example_structure()
    check_json()
    check_js_syntax()
    check_fences_language()
    check_crossref_order()
    if args.external:
        check_external_links()
    if errors:
        print(f"❌ {len(errors)} 个问题:")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    print(f"✅ 全部通过（{len(md_files())} 篇文档）")


if __name__ == "__main__":
    main()

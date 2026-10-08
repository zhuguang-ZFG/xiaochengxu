# -*- coding: utf-8 -*-
"""仓库一致性校验脚本（本地与 CI 共用）。

检查项：
1. 元数据：每篇文档 frontmatter 字段完整；category 与所在目录一致
2. 图片引用：所有 ![...](...) 指向存在文件
3. 相对链接：所有 [..](相对路径) 指向存在文件
4. 目录序号：docs 各分类目录序号连续（1,2,3...）
5. 孤儿资产：docs/assets/ 下（含子目录）无未被引用的文件
6. 视觉资产硬限制：GIF ≤200KB、教学视频 MP4 ≤3MB 且命名合规
7. JSON 合法性：示例工程与配置文件的 json 可解析
8. JS 语法：示例工程 js 可被 node 解析（python 侧仅做括号粗查，CI 用 node）

用法：python tools/check_repo.py
退出码：0 = 全部通过；1 = 存在问题
"""
import json
import pathlib
import re
import sys

# Windows 控制台默认 GBK，print ✅/❌ 会抛 UnicodeEncodeError——
# 导致"检查其实全部通过，却以 traceback 非零退出"。统一把 stdout 切到 UTF-8。
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"
CONTRACT_NAME = "_契约.md"

GIF_LIMIT = 200 * 1024          # 契约：单个动画 GIF ≤ 200KB
VIDEO_LIMIT = 3 * 1024 * 1024   # 契约：单集教学视频 ≤ 3MB

META_FIELDS = ["title", "description", "category", "tags", "difficulty", "reading_time", "updated"]
CATEGORY_DIR = {
    "00-学习路线": "学习路线", "01-入门": "入门", "02-基础": "基础", "03-进阶": "进阶",
    "04-云开发": "云开发", "05-发布": "发布", "06-实战": "实战", "07-资源": "资源",
}

errors = []


def md_files():
    """教学正文（排除写作契约本身）——元数据类检查用"""
    return [f for f in DOCS.rglob("*.md") if f.name != CONTRACT_NAME]


def all_md_files():
    """仓库内全部 Markdown（含写作契约与根目录文档）——链接/图片类检查用。

    此前只扫 docs/ 正文 + README.md，导致 CONTRIBUTING.md、CHANGELOG.md
    里的断链完全无人校验。
    """
    return sorted(DOCS.rglob("*.md")) + sorted(ROOT.glob("*.md"))


FENCE_RE = re.compile(r"^[ \t]{0,3}```.*?^[ \t]{0,3}```", re.S | re.M)
FENCE_LINE_RE = re.compile(r"^[ \t]{0,3}```(\S*)\s*$")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def strip_code(text):
    """剥掉围栏代码块与行内代码，再抽取链接。

    契约与 CONTRIBUTING 里存在大量「用法示例」形式的链接，例如
    `![说明](../assets/screen-hello.png)`、`../assets/videos/video-NN-slug.mp4`，
    它们并非真实引用，不剥离会产生成片误报断链。先剥围栏再剥行内代码
    （围栏行本身由反引号构成，顺序反了会剥不干净）。

    围栏必须允许最多 3 个空格缩进：契约把示例写在列表项里（缩进 2 空格），
    锚定行首 `^``` ` 会配不上对，导致块内示例被当成真实链接。
    """
    return INLINE_CODE_RE.sub("", FENCE_RE.sub("", text))


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
    for f in all_md_files():
        t = strip_code(f.read_text(encoding="utf-8"))
        for m in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", t):
            target = m.group(1)
            if target.startswith(("http", "//")):
                continue
            if not (f.parent / target).resolve().exists():
                errors.append(f"{f.relative_to(ROOT)}: 图片断链 -> {target}")


def check_links():
    for f in all_md_files():
        t = strip_code(f.read_text(encoding="utf-8"))
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
    # 递归遍历：assets/ 下的子目录（如 videos/）同样纳入孤儿检查
    for a in sorted(ASSETS.rglob("*")):
        if not a.is_file():
            continue
        rel = a.relative_to(ASSETS).as_posix()
        if rel not in referenced:
            errors.append(f"孤儿资产（未被任何文档引用）: docs/assets/{rel}")


def check_gif_size():
    """契约硬限制：动画 GIF 单文件 ≤ 200KB"""
    for g in ASSETS.glob("*.gif"):
        size = g.stat().st_size
        if size > GIF_LIMIT:
            errors.append(f"{g.name}: {size} bytes 超过 200KB 上限（契约视觉资产规范）")


def check_video_assets():
    """契约硬限制：教学视频存放 docs/assets/videos/，命名 video-*.mp4，单集 ≤ 3MB"""
    vdir = ASSETS / "videos"
    if not vdir.is_dir():
        return
    for v in sorted(vdir.iterdir()):
        if not v.is_file():
            continue
        rel = f"docs/assets/videos/{v.name}"
        if v.suffix.lower() != ".mp4":
            errors.append(f"{rel}: 契约规定 videos/ 下只放 MP4 教学视频")
            continue
        if not v.name.startswith("video-"):
            errors.append(f"{rel}: 文件名须以 video- 前缀开头（契约命名规范）")
        size = v.stat().st_size
        if size > VIDEO_LIMIT:
            errors.append(f"{rel}: {size} bytes 超过 3MB 上限（契约视觉资产规范）")


# 文件名 token：长后缀必须排在短后缀前面，否则 "app.json" 会被 "app.js" 抢先匹配
FILE_TOKEN_RE = re.compile(r"[\w/.-]*\.(?:wxss|wxml|json|js|wxss)\b")
# 显式标记为「节选/要点」的块不与工程文件做全等比对
EXCERPT_MARK_RE = re.compile(r"要点|节选|片段|省略|仅列")
# 只有源码语言的块才可能与工程文件逐行对应；bash/text 等是操作指令或目录树，
# 其上下文里出现的文件名（如 `node --test .../index.js`）不构成节选关系。
SOURCE_LANGS = {"js", "javascript", "wxml", "wxss", "css", "json"}


def _norm_code(text):
    """归一化用于比对：去掉首尾空白、空行、行尾空格与文件头注释行。

    示例工程的文件头注释（`// pages/index/index.js`、`<!-- ... -->`）是工程惯例，
    教程为省版面不写，不应算作漂移；因此两侧都忽略开头的纯注释行。
    """
    out = []
    for ln in text.strip().splitlines():
        s = ln.rstrip()
        t = s.strip()
        if not t:
            continue
        if t.startswith("//") or t.startswith("<!--") or t.startswith("/*"):
            if not out:      # 仅忽略块首的注释行
                continue
        out.append(t)
    return out


def _example_files():
    ex = ROOT / "examples" / "todo-miniprogram"
    if not ex.is_dir():
        return {}
    return {f.relative_to(ex).as_posix(): f for f in ex.rglob("*") if f.is_file()}


def check_example_sync():
    """实战篇内联的代码块必须与 examples/ 工程文件一致。

    README 与教程都声称「代码与教程逐行对应」，但此前无任何机制校验，
    实测已出现漂移（app.json 漏 sitemapLocation 等）。此处把该声明变成不变量：
    教程中未标注「要点/节选」的源码块，必须与工程文件逐行一致（忽略缩进与文件头注释）。

    仅在**确实引用了该示例工程**的文档里生效：入门/基础/进阶各篇也会出现
    `app.json`、`index.js` 等同名代码块，但那是各自独立的教学示例
    （如 `我的小程序`、`pages/detail/detail`），与示例工程无关，按文件名
    全局匹配会把它们全部误判为漂移。判定依据是文档正文是否提到工程目录名。
    """
    files = _example_files()
    if not files:
        return
    by_name = {}
    for rel in files:
        by_name.setdefault(rel.rsplit("/", 1)[-1], []).append(rel)

    # 只检查引用了示例工程的文档：实战篇 + 工程自身 README
    scope = [DOCS / "06-实战", ROOT / "examples" / "todo-miniprogram"]
    candidates = []
    for base in scope:
        if base.is_dir():
            candidates.extend(sorted(base.rglob("*.md")))

    for art in candidates:
        text = art.read_text(encoding="utf-8")
        if "todo-miniprogram" not in text:
            continue
        lines = text.splitlines()
        try:
            rel_art = art.relative_to(ROOT)
        except ValueError:
            rel_art = art

        in_fence = False
        lang = ""
        buf = []
        start = 0
        section = ""
        for i, ln in enumerate(lines):
            if not in_fence:
                h = re.match(r"^##\s+(.*)$", ln)
                if h:
                    section = h.group(1)
            m = FENCE_LINE_RE.match(ln)
            if m and not in_fence:
                in_fence, lang, buf, start = True, m.group(1), [], i
                continue
            if ln.strip() == "```" and in_fence:
                in_fence = False
                if lang not in SOURCE_LANGS:   # 目录树、命令行等非源码块
                    continue
                ctx = "\n".join(lines[max(0, start - 8):start])
                toks = FILE_TOKEN_RE.findall(ctx)
                if not toks:
                    continue
                token = toks[-1]
                cands = [token] if token in files else by_name.get(token, [])
                if not cands:
                    continue
                if len(cands) > 1:       # index.js 同时命中云函数与页面，按章节消歧
                    want_cloud = ("云函数" in section) or ("cloud" in section.lower())
                    cands = [c for c in cands if ("cloudfunctions/" in c) == want_cloud] or cands
                target = cands[0]
                if EXCERPT_MARK_RE.search(ctx):   # 明确标注为节选，不与全文比对
                    continue
                disk = files[target].read_text(encoding="utf-8")
                if _norm_code("\n".join(buf)) != _norm_code(disk):
                    errors.append(
                        f"{rel_art}:{start + 1}: 内联代码块与工程文件不一致 -> "
                        f"examples/todo-miniprogram/{target}（该块未标注「要点/节选」）")
                continue
            if in_fence:
                buf.append(ln)


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
    """契约：代码块必须标注语言（开围栏 ```lang 非空），且所有围栏闭合。

    围栏识别允许最多 3 空格缩进（CommonMark）：契约把示例围栏写在列表项里，
    锚定行首会漏掉它们，既漏报「未标注语言」也漏报「未闭合」。
    """
    for f in all_md_files():
        t = f.read_text(encoding="utf-8")
        in_fence = False
        for i, line in enumerate(t.splitlines(), 1):
            m = FENCE_LINE_RE.match(line)
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
    check_video_assets()
    check_example_sync()
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

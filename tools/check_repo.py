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
9. API 真实性：正文与示例代码里的 `wx.<name>` 必须存在于官方 API 名单；
   Promise 断言：不能把支持 Promise 风格的接口说成回调式，也不能 `await` 不返回 Promise 的接口

用法：python tools/check_repo.py
      python tools/check_repo.py --update-api-list   # 刷新第 9 项的官方名单
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


def example_md_files():
    """示例工程内的 Markdown（工程 README 等）——同样要受链接/语言校验约束"""
    ex = ROOT / "examples"
    return sorted(ex.rglob("*.md")) if ex.is_dir() else []


def all_md_files():
    """仓库内全部 Markdown（含写作契约、根目录文档、示例工程文档）——链接/图片/围栏类检查用。

    此前只扫 docs/ 正文 + README.md，导致 CONTRIBUTING.md、CHANGELOG.md
    里的断链完全无人校验；示例工程的 README 同样在扫描范围之外。
    """
    return sorted(DOCS.rglob("*.md")) + sorted(ROOT.glob("*.md")) + example_md_files()


def reference_md_files():
    """可作为「资产引用来源」的 Markdown。

    与 all_md_files() 的区别是排除写作契约：契约里的 `assets/...` 是格式示例
    而非真实引用，计入会让孤儿检查失效。
    """
    return md_files() + sorted(ROOT.glob("*.md")) + example_md_files()


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
    for f in reference_md_files():
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


# ---------- API 真实性 / Promise 断言 ----------

API_INDEX_URL = "https://developers.weixin.qq.com/miniprogram/dev/api/"
# 官方 TypeScript 声明（由官方文档生成）：既是第二个名称来源，也是「哪些接口不传回调即返回 Promise」的唯一机读来源
TYPINGS_URL = "https://raw.githubusercontent.com/wechat-miniprogram/api-typings/master/types/wx/lib.wx.api.d.ts"
# 名单随工具走而不随被扫描的仓库走：自测会把 ROOT 指到临时目录
_DATA = pathlib.Path(__file__).resolve().parent / "data"
API_LIST_FILE = _DATA / "wx-api-names.txt"        # 真实存在的一级 wx.<name>
PROMISE_LIST_FILE = _DATA / "wx-api-promise.txt"  # 其中不传 success/fail/complete 即返回 Promise 的
# 两个官方来源都没有、但确实存在的名字写在这里并说明理由；目前为空
# （wx.cloud / wx.worklet 等命名空间来自 typings 的 interface Wx 成员）
EXTRA_API_NAMES = set()
# 一级标识符：官方 API 全部以小写字母开头，`wx.API 速查索引` 这类标题不会误中
API_NAME_RE = re.compile(r"\bwx\.[a-z][A-Za-z0-9_]*")
# 行内含此标记则跳过本节两项检查：用于把虚构 API / 错误断言当反面例子写出来的句子（CHANGELOG、契约）
API_IGNORE_MARK = "api-ignore"
# 对接口 Promise 能力的「平铺式否定」。故意不收「需自行封装 / 用 Promise 包装」：带版本条件的
# 正确说法（「基础库低于 2.10.2 需自行用 Promise 包装」）也含这些词，收进来会把正确的话报成错的
CALLBACK_CLAIM_RE = re.compile(r"回调式|回调风格|没有(?:原生)?\s*Promise|无(?:原生)?\s*Promise|不支持\s*Promise|不返回\s*Promise")
# `await wx.xxx(`：要求一级名字后紧跟 `(`，所以 `await wx.cloud.callFunction(` 不在范围内
# （云开发接口确实返回 Promise，但二级名字不校验，见 check_api_names 文档串）
AWAIT_RE = re.compile(r"\bawait\s+(wx\.[a-z][A-Za-z0-9_]*)\s*\(")


def extract_api_names(html):
    """从官方 API 索引页抽取一级 `wx.<name>`（去重排序）"""
    return sorted(set(API_NAME_RE.findall(html)))


def extract_promise_apis(dts):
    """从官方 TypeScript 声明里抽取 `interface Wx` 的成员，以及其中返回 Promise 的方法。

    返回 (members, promise)，都带 `wx.` 前缀、去重排序。判定依据是返回类型是否为
    `PromisifySuccessResult<...>`——这个类型就是官方对「不含 success/fail/complete 时
    返回 Promise」这条规则的编码；`wx.request` 等返回 RequestTask 的接口自然不在其中。
    已用 28 个接口的文档页「以 Promise 风格调用：支持/不支持」标注交叉核对，全部一致。
    """
    t = re.sub(r"/\*\*.*?\*/", "", dts, flags=re.S)   # JSDoc 里的示例代码会干扰括号与缩进
    i = t.find("    interface Wx {")
    if i < 0:
        return [], []
    wx = t[i:t.find("\n    }", i)]
    starts = [(m.start(), m.group(1)) for m in re.finditer(r"\n        ([a-z][A-Za-z0-9_]*)\s*[<(:]", wx)]
    members, promise = set(), set()
    for k, (pos, name) in enumerate(starts):
        chunk = wx[pos:starts[k + 1][0] if k + 1 < len(starts) else len(wx)]
        members.add("wx." + name)
        rets = re.findall(r"\)\s*:\s*([^\n]+)", chunk)   # 最后一个 "): 类型" 才是方法返回类型
        if rets and rets[-1].strip().startswith("PromisifySuccessResult"):
            promise.add("wx." + name)
    return sorted(members), sorted(promise)


def _fetch(url):
    import urllib.request, ssl
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60, context=ssl.create_default_context()) as r:
        return r.read().decode("utf-8", errors="replace")


def _write_list(path, header, names):
    path.parent.mkdir(parents=True, exist_ok=True)
    # newline 固定 LF：write_text 默认跟平台走，Windows 上会写出 CRLF，同一份名单两个平台字节不同
    path.write_text(header + "\n".join(names) + "\n", encoding="utf-8", newline="\n")
    print(f"已写入 {path.relative_to(ROOT)}：{len(names)} 个")


def update_api_list():
    """抓取官方 API 索引页 + 官方 typings，重写两份名单（需要网络；平时不跑，名单随仓库提交）"""
    index_names = extract_api_names(_fetch(API_INDEX_URL))
    members, promise = extract_promise_apis(_fetch(TYPINGS_URL))
    # 页面改版/抓到错误页时只会抽出零星几个名字；宁可失败也不写出残缺名单，
    # 否则下一次校验会把全库的真实 API 都报成虚构
    if len(index_names) < 300 or len(members) < 300 or len(promise) < 100:
        raise SystemExit(f"抽取结果可疑（索引页 {len(index_names)} / typings 成员 {len(members)} / "
                         f"Promise {len(promise)}），疑似抓取失败，未写入")
    # 两个来源互有遗漏（索引页缺 wx.requestOrderPayment、wx.cloud；typings 缺若干新接口），取并集
    names = sorted(set(index_names) | set(members))
    _write_list(API_LIST_FILE, (
        "# 微信小程序官方 API 名单（一级 `wx.<name>` 标识符），供 check_repo.py 校验 API 真实性\n"
        "# 由 `python tools/check_repo.py --update-api-list` 生成，请勿手改。来源取并集：\n"
        f"#   官方 API 索引页 {API_INDEX_URL}（{len(index_names)} 个）\n"
        f"#   官方 typings interface Wx 成员 {TYPINGS_URL}（{len(members)} 个）\n"
        "# 两个来源都没有、但确实存在的名字改 check_repo.py 的 EXTRA_API_NAMES 并写明理由\n"
        f"# 共 {len(names)} 个\n"), names)
    _write_list(PROMISE_LIST_FILE, (
        "# 不传 success/fail/complete 即返回 Promise 的接口（基础库 2.10.2 起），供 check_repo.py 校验 Promise 断言\n"
        "# 由 `python tools/check_repo.py --update-api-list` 生成，请勿手改。来源：\n"
        f"#   官方 typings 中返回 PromisifySuccessResult 的方法 {TYPINGS_URL}\n"
        "# 不在此名单的真实接口要么是同步接口，要么本身返回任务对象（request/uploadFile/downloadFile/connectSocket）\n"
        f"# 共 {len(promise)} 个\n"), promise)


def _load_list(path):
    if not path.is_file():
        raise SystemExit(f"缺少名单 {path}，先跑 python tools/check_repo.py --update-api-list")
    names = set()
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            names.add(ln)
    return names


def load_api_names():
    return _load_list(API_LIST_FILE) | EXTRA_API_NAMES


def load_promise_apis():
    return _load_list(PROMISE_LIST_FILE)


def _api_scan_files():
    """全部 Markdown + 示例工程源码（工程里的 API 名拼错同样是读者照抄的对象）"""
    files = list(all_md_files())
    ex = ROOT / "examples"
    if ex.is_dir():
        files += sorted(f for f in ex.rglob("*") if f.suffix in (".js", ".wxml"))
    return files


def check_api_names():
    """正文与示例代码里出现的每个 `wx.<name>` 都必须是官方真实存在的 API。

    教程里出现过虚构 API（Skyline 篇的 worklet `animate()`、速查索引里把
    npm 包 miniprogram-api-promise 的能力写成了 `wx.` 下的接口），读者照着写
    就是运行时报错，而链接/语法类检查对此毫无感知。名单来自官方 API 索引页与
    官方 typings（`--update-api-list` 刷新），名单之外一律报错；确需把虚构名
    当反面例子写出来的，在该行加 `<!-- api-ignore -->`。

    只校验一级标识符：`wx.cloud.xxx` 只看到 `wx.cloud`。云开发 API 的官方
    索引不在同一页，二级名单另抓的收益不抵维护成本，这里明说而不是假装覆盖。
    """
    known = load_api_names()
    for f in _api_scan_files():
        text = f.read_text(encoding="utf-8", errors="replace")
        for i, ln in enumerate(text.splitlines(), 1):
            if API_IGNORE_MARK in ln:
                continue
            for name in sorted(set(API_NAME_RE.findall(ln))):
                if name not in known:
                    errors.append(
                        f"{f.relative_to(ROOT)}:{i}: `{name}` 不在官方 API 名单"
                        "（确为新 API 则 --update-api-list 刷新；反面例子在行尾加 <!-- api-ignore -->）")


def check_promise_claims():
    """正文对接口 Promise 能力的断言，以及代码里的 `await wx.xxx(`，必须与官方一致。

    实战篇曾写「showModal 是回调式 API，用 Promise 包装再 await，否则 confirm 拿不到」，
    而示例工程正是 `await wx.showModal(...)`——逐行一致校验抓不到，因为它只比代码文本，
    不比正文对代码的断言。这里把两种可机读的形态变成不变量：

    1. 行内对某接口作「回调式 / 没有 Promise / 不支持 Promise」的平铺否定，而该接口在
       Promise 名单里 → 报错。只认平铺否定，不认「需自行封装」这类词：带版本条件的正确
       说法也会用到它们
    2. `await wx.xxx(` 而 xxx 不在 Promise 名单里 → 报错：同步接口 await 了也拿不到
       更多东西，request/uploadFile 这类返回任务对象的接口 await 到的是任务对象不是结果

    反方向（说某个不返回 Promise 的接口「返回 Promise」）故意不查：最正确的那几句话
    （「异步 API 返回 Promise，只有 wx.request 等例外」）恰好同一行同时含两者，按行查必误报。
    """
    known = load_api_names()
    promise = load_promise_apis()
    stray = promise - known
    if stray:   # 两份名单必须同源刷新；手改或只刷了一份会在这里露馅
        raise SystemExit(f"Promise 名单含名称名单之外的名字 {sorted(stray)[:3]}…，两份名单不同步，重新 --update-api-list")
    for f in _api_scan_files():
        text = f.read_text(encoding="utf-8", errors="replace")
        for i, ln in enumerate(text.splitlines(), 1):
            if API_IGNORE_MARK in ln:
                continue
            if CALLBACK_CLAIM_RE.search(ln):
                for name in sorted(set(API_NAME_RE.findall(ln))):
                    if name in promise:
                        errors.append(
                            f"{f.relative_to(ROOT)}:{i}: 说 `{name}` 是回调式/没有 Promise，但官方标注"
                            "「以 Promise 风格调用：支持」（不传 success/fail/complete 即返回 Promise，基础库 2.10.2 起）")
            for name in AWAIT_RE.findall(ln):
                if name not in promise and name in known:
                    errors.append(
                        f"{f.relative_to(ROOT)}:{i}: `await {name}(...)` 拿不到结果——该接口不返回 Promise"
                        "（同步接口，或 request/uploadFile 这类本身返回任务对象的接口）")


def check_external_links():
    """外链 HTTP 状态校验（默认关闭：CI/第三方站点网络波动不应阻断校验；
    需要时用 --external 显式启用）"""
    import urllib.request, ssl, concurrent.futures
    ctx = ssl.create_default_context()
    links = {}
    for f in reference_md_files():
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
    parser.add_argument("--update-api-list", action="store_true",
                        help="抓取官方 API 索引页与官方 typings，刷新 tools/data/ 下的两份名单后退出（需要网络）")
    args = parser.parse_args()
    if args.update_api_list:
        update_api_list()
        return
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
    check_api_names()
    check_promise_claims()
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

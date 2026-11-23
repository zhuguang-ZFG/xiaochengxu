# -*- coding: utf-8 -*-
"""变异测试：把校验脚本的修复逐条还原成修复前写法，确认自测会变红。

目的：证明 tools/test_*.py 真的能抓住这些缺陷，而不是碰巧全绿。
全程在临时目录操作，不改动仓库里的真实文件。

每项变异是四元组：(目标脚本, 说明, 修复后的写法, 修复前的写法)。
目标脚本决定跑哪个自测文件、以及断言哪个源文件未被改动。
被测脚本 `import` 的同目录模块要登记进 `DEPS`：自测在临时目录里跑，依赖没跟过去
就是 `ModuleNotFoundError`，而性质 2 会正确地把它判成「自测没跑起来」而不是「抓到了」。

三条不能破的性质，破一条这个脚本就从「证据」退化成「装饰」：
1. **自测文件必须复制进临时目录**。它按 __file__ 找同目录的被测脚本；只在原地跑
   仓库里的原版，变异就是无效的。曾漏了这一行，每项都因「找不到自测文件」以退出码
   2 结束，被计成「变红」——20/20 全绿，其实一次自测都没跑过（25 秒 vs 0.9 秒）。
2. **必须看到 unittest 的测试汇总**（`Ran N tests in X.XXXs`，写在 stderr）。没有
   汇总说明自测没跑起来，退出码非零只是崩了，不算「抓到了」。
3. **锚点未命中必须计入失败**。锚点是源码里的字面文本，重构后失配就意味着该项
   修复从未被验证；静默跳过会让捕获数悄悄少一个，而退出码仍是非零（CI 红），
   却没人说得清为什么红。
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile

# 同 check_repo.py：Windows 控制台默认 GBK，print ✅/❌ 会抛 UnicodeEncodeError，
# 使变异测试在本地以 traceback 退出（CI 跑 Linux/UTF-8，一直掩盖着这个差异）。
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TOOLS = pathlib.Path(__file__).resolve().parent

# 目标脚本 → 对应的自测文件
TARGETS = {
    "check_repo.py": "test_check_repo.py",
    "check_assets_fresh.py": "test_assets_fresh.py",
    "gen_videos.py": "test_gen_videos.py",
    "gen_mermaid.py": "test_gen_mermaid.py",
    "mermaid_source.py": "test_mermaid_source.py",
    "mermaid/install-browser.js": "test_gen_mermaid.py",
}

# 被测脚本 import 的同目录模块（临时目录里没有 site-packages 之外的来源，必须复制）。
# 也包括自测**当数据读**的同目录文件：test_gen_videos.py 的字形扫描要读
# gen_animations/gen_diagrams/gen_statics，缺一个就是 FileNotFoundError，
# 于是每次变异都因「自测崩了」变红——25/25 全绿里混着假捕获。
DEPS = {
    "check_repo.py": ["mermaid_source.py"],
    "gen_videos.py": ["render.py", "gen_animations.py", "gen_diagrams.py", "gen_statics.py"],
    # 自测会读 package.json / lockfile 核对版本，临时目录里缺了它们，
    # 每次变异都会因 FileNotFoundError 变红，全绿里全是假捕获。
    "gen_mermaid.py": ["mermaid_source.py", "mermaid/package.json",
                       "mermaid/package-lock.json", "mermaid/pin_sans_serif.mjs"],
    "mermaid/install-browser.js": ["mermaid/package.json",
                                   "mermaid/package-lock.json"],
}

MUTATIONS = [
    # ---- check_repo.py ----
    (
        "check_repo.py",
        "序号连续性检查形同虚设（缺号无人发现）",
        "        if nums != expected:",
        "        if False:",
    ),
    (
        "check_repo.py",
        "孤儿检查不递归（iterdir 看不到 videos/）",
        'sorted(ASSETS.rglob("*"))',
        'sorted(ASSETS.iterdir())',
    ),
    (
        "check_repo.py",
        "根目录文档不在扫描范围（CONTRIBUTING/CHANGELOG 断链漏检）",
        'sorted(DOCS.rglob("*.md")) + sorted(ROOT.glob("*.md"))',
        'sorted(DOCS.rglob("*.md"))',
    ),
    (
        "check_repo.py",
        "不剥离代码块（契约里的用法示例被当成真实链接）",
        'return INLINE_CODE_RE.sub("", FENCE_RE.sub("", text))',
        'return text',
    ),
    (
        "check_repo.py",
        "围栏正则锚定行首（漏掉列表项里缩进 2 空格的围栏）",
        'FENCE_LINE_RE = re.compile(r"^[ \\t]{0,3}',
        'FENCE_LINE_RE = re.compile(r"^',
    ),
    (
        "check_repo.py",
        "源码块状态标注检查形同虚设（不标也能过）",
        'CODE_STATUS_LANGS = {"js", "javascript", "wxml", "xml", "css", "wxss", "json", "yaml", "bash"}',
        'CODE_STATUS_LANGS = set()',
    ),
    (
        "check_repo.py",
        "状态标注与代码块之间不再要求空行（标注紧贴围栏也放行）",
        "                    if i - marker_idx < 2:",
        "                    if False:",
    ),
    (
        "check_repo.py",
        "非法状态词被当成缺标注（错误提示指错方向）",
        '                if prev.startswith("*代码状态：") or prev.startswith("> 代码状态："):',
        "                if False:",
    ),
    (
        "check_repo.py",
        "可运行块与工程文件漂移不报（逐行一致校验被绕过）",
        '                    if status == "可运行":',
        "                    if False:",
    ),
    (
        "check_repo.py",
        "完整文件标成片段/示意也放行（用标注逃避同步比对）",
        '                    if status in ("片段", "示意", "反例"):\n                        if same:',
        '                    if status in ("片段", "示意", "反例"):\n                        if False:',
    ),
    (
        "check_repo.py",
        "未引用示例工程的文章也参与比对（按文件名全局匹配的老毛病复发）",
        "            if pname not in text:\n                continue",
        "            if False:\n                continue",
    ),
    (
        "check_repo.py",
        "非源码块也参与比对（bash 命令行被当成源码节选）",
        "if lang not in SOURCE_LANGS:",
        'if lang == "text":',
    ),
    (
        "check_repo.py",
        "「要点/节选」豁免失效（摘要块被当成全文漂移）",
        "if EXCERPT_MARK_RE.search(ctx):",
        "if False:",
    ),
    (
        "check_repo.py",
        "示例工程文档不在扫描范围（工程 README 的断链/裸围栏漏检）",
        'return sorted(DOCS.rglob("*.md")) + sorted(ROOT.glob("*.md")) + example_md_files()',
        'return sorted(DOCS.rglob("*.md")) + sorted(ROOT.glob("*.md"))',
    ),
    (
        "check_repo.py",
        "API 名单检查形同虚设（名单之外的名字不报）",
        "                if name not in known:",
        "                if False:",
    ),
    (
        "check_repo.py",
        "API 正则不限小写开头（`wx.API 速查索引` 这类标题被误报）",
        'API_NAME_RE = re.compile(r"\\bwx\\.[a-z][A-Za-z0-9_]*")',
        'API_NAME_RE = re.compile(r"\\bwx\\.[A-Za-z][A-Za-z0-9_]*")',
    ),
    (
        "check_repo.py",
        "示例工程源码不在 API 名单检查范围（工程里拼错的 API 漏检）",
        '        files += sorted(f for f in ex.rglob("*") if f.suffix in (".js", ".wxml"))',
        '        pass',
    ),
    (
        "check_repo.py",
        "名单文件缺失时静默按空名单继续（真实 API 全部被报成虚构，而非说清「名单没了」）",
        '        raise SystemExit(f"缺少名单 {path}，先跑 python tools/check_repo.py --update-api-list")',
        "        return set()",
    ),
    (
        "check_repo.py",
        "回调式断言检查形同虚设（把支持 Promise 的接口说成回调式不报）",
        "                    if name in promise:",
        "                    if False:",
    ),
    (
        "check_repo.py",
        "await 检查形同虚设（await 同步接口 / 任务对象接口不报）",
        "                if name not in promise and name in known:",
        "                if False:",
    ),
    (
        "check_repo.py",
        "把「包装」也当成否定断言（带版本条件的正确说法被误报）",
        '不返回\\s*Promise")',
        '不返回\\s*Promise|包装")',
    ),
    (
        "check_repo.py",
        "两份名单不同步检查失效（只刷了一份/手改了一份也放行）",
        "    if stray:",
        "    if False:",
    ),
    (
        "check_repo.py",
        "MP4 完整性检查失效（渲染中断留下的 48 字节空壳被放行）",
        "        if size <= VIDEO_LIMIT and not _mp4_is_complete(v):",
        "        if False:",
    ),
    (
        "check_repo.py",
        "MP4 box 长度不再校验（moov 之后被截断的文件照样判为完整）",
        "        if size < 8 or off + size > end:",
        "        if False:",
    ),
    (
        "check_repo.py",
        "文档时长与成片时长的容差放到离谱（写 60 秒实际 75 秒也放行）",
        "            elif abs(actual - claimed) > 0.5:",
        "            elif abs(actual - claimed) > 0.5 * claimed:",
    ),
    (
        "check_repo.py",
        "读不出时长时静默放过（mdhd 解析一坏，整条时长核对就隐形）",
        "            if actual is None:",
        "            if False:",
    ),
    (
        "check_repo.py",
        "README 视频总表的行数不再核对（新增一集不写进表格也没人管）",
        "    if len(rows) != n_videos:",
        "    if False:",
    ),
    (
        "check_repo.py",
        "README 指标表的数字不再与仓库计数比对（「57 个」那种过期数又能活下来）",
        "        elif tuple(int(x) for x in m.groups()) != want:",
        "        elif False:",
    ),
    # ---- check_repo.py 中文排版 ----
    (
        "check_repo.py",
        "围栏代码块不屏蔽（代码里的直引号、半角标点被当成正文）",
        "        if TYPO_FENCE_RE.match(line):",
        "        if False:",
    ),
    (
        "check_repo.py",
        "正文排版规则整段跳过（所有违规都不再报）",
        "            for label, rx, hint in TYPO_RULES:\n                if rx.search(line):",
        "            for label, rx, hint in TYPO_RULES:\n                if False:",
    ),
    (
        "check_repo.py",
        "术语大小写规则整段跳过（appid/AppId 不再统一为 AppID）",
        "            for canonical, rx, hint in TYPO_TERMS:\n                if rx.search(line):",
        "            for canonical, rx, hint in TYPO_TERMS:\n                if False:",
    ),
    (
        "check_repo.py",
        "行内代码紧贴中文不再报（代码与中文之间不留空隙）",
        "            if TYPO_CJK_RE.match(before) or TYPO_CJK_RE.match(after):",
        "            if False:",
    ),
    (
        "check_repo.py",
        "未闭合的全角括号不再报（半截括号漏到成书）",
        "    for ch, lineno in stack:",
        "    for ch, lineno in []:",
    ),
    (
        "check_repo.py",
        "忽略标记失效（带 <!-- typography-ignore --> 的行照样被报）",
        "        for lineno, line in enumerate(masked.split(\"\\n\"), 1):\n            if ignored(lineno):",
        "        for lineno, line in enumerate(masked.split(\"\\n\"), 1):\n            if False:",
    ),
    (
        "check_repo.py",
        "图片 alt 题注检查形同虚设（空 alt 的裸图漏到电子书）",
        "                if not m.group(1).strip():",
        "                if False:",
    ),
    (
        "check_repo.py",
        "表题后必须紧跟表格的检查形同虚设（孤立表题照样放行）",
        "            if (j + 1 >= len(lines)\n"
        "                    or not TABLE_HEADER_RE.match(lines[j][1])\n"
        "                    or not TABLE_RULE_RE.match(lines[j + 1][1])):",
        "            if False:",
    ),
    (
        "check_repo.py",
        "Mermaid 输出资产缺失不报（成书时图位空着）",
        "        if not block.asset_path.is_file():",
        "        if False:",
    ),
    # ---- check_assets_fresh.py ----
    (
        "check_assets_fresh.py",
        "不校验工作区是否干净（以重跑前状态为基准 → 漏提交时假通过）",
        "    if before:",
        "    if False:",
    ),
    (
        "check_assets_fresh.py",
        "不清空资产目录（「脚本已不再产出」的漂移方向测不到）",
        "    clear_assets()",
        "    pass",
    ),
    (
        "check_assets_fresh.py",
        "生成脚本失败被当成成功（渲染崩了却继续比对）",
        "        if r.returncode != 0:",
        "        if False:",
    ),
    (
        "check_assets_fresh.py",
        "工具链不符也继续比对（非 pinned ffmpeg 的字节被误报成资产漂移）",
        "    if drift:",
        "    if False:",
    ),
    # ---- gen_videos.py ----
    (
        "gen_videos.py",
        "字幕折行只比最宽行、不比行数（退化成一行的一个字）",
        "                cost = (nl + 1, max(w, mx), sq + w * w)",
        "                cost = (max(w, mx), sq + w * w)",
    ),
    (
        "gen_videos.py",
        "折行不再把标识符当整体（cloud.getWXContext() 会被劈成两截）",
        r'_ATOM_RE = re.compile(r"[A-Za-z0-9+._()$/\[\]*-]+|\s+|.")',
        '_ATOM_RE = re.compile(r".")',
    ),
    (
        "gen_videos.py",
        "折行不再受可用宽度约束（字幕画出画面右边界）",
        "                if w > max_px and j - 1 > i:",
        "                if False and j - 1 > i:",
    ),
    (
        "gen_videos.py",
        "字形探针认不出 .notdef（缺字形的字符被当成画得出来，豆腐块漏到成片）",
        "        if (m.size, bytes(m)) == _NOTDEF:",
        "        if False:",
    ),
    (
        "gen_videos.py",
        "成片直接写进资产目录（渲染被打断就留下 48 字节空壳）",
        "           tmp]",
        "           str(out)]",
    ),
    # ---- gen_mermaid.py ----
    (
        "gen_mermaid.py",
        "写作契约被卷进渲染扫描（契约里的 Mermaid 示例让生成脚本直接崩溃）",
        "    return sorted(p for p in pathlib.Path(docs_root).rglob(\"*.md\")\n"
        "                  if p.name != CONTRACT_NAME)",
        "    return sorted(p for p in pathlib.Path(docs_root).rglob(\"*.md\"))",
    ),
    (
        "gen_mermaid.py",
        "Windows 管道默认 cp1252，打印中文路径以 UnicodeEncodeError 非零退出",
        "if hasattr(sys.stdout, \"reconfigure\"):\n"
        "    try:\n"
        "        sys.stdout.reconfigure(encoding=\"utf-8\", errors=\"replace\")\n"
        "    except Exception:\n"
        "        pass",
        "if False:\n"
        "    pass",
    ),
    (
        "gen_mermaid.py",
        "渲染退回 PATH 上的 mmdc（不再用 tools/mermaid 锁定的 CLI）",
        "    return [node_exe(), \"--import\", PIN_SANS_SERIF.as_uri(),\n"
        "            str(mmdc_js())] + [",
        "    return [\"mmdc\"] + [",
    ),
    (
        "gen_mermaid.py",
        "字体固定钩子不再预加载（Arial 版本差异重新影响时序图布局）",
        "    return [node_exe(), \"--import\", PIN_SANS_SERIF.as_uri(),\n"
        "            str(mmdc_js())] + [",
        "    return [node_exe(), str(mmdc_js())] + [",
    ),
    (
        "gen_mermaid.py",
        "钩子拿到整条字体栈而不是首个字体（sans-serif 映射到无效族名）",
        "    first = family.split(\",\")[0].strip().strip(\"\\\"'\")",
        "    first = family",
    ),
    (
        "gen_mermaid.py",
        "根级测量字体缺失（时序图退回 Trebuchet/Verdana 默认栈，runner 缺字体即漂移）",
        '    "fontFamily": FONT_FAMILY,\n',
        "",
    ),
    (
        "gen_mermaid.py",
        "根级测量字体改成固定 Arial（字体栈被绕开时毫无察觉）",
        '    "fontFamily": FONT_FAMILY,',
        '    "fontFamily": "Arial",',
    ),
    (
        "gen_mermaid.py",
        "测量字体放回 sequence 死字段（被根 fontFamily 覆盖，等于没钉）",
        '    "sequence": {"useMaxWidth": False},',
        '    "sequence": {"useMaxWidth": False, "messageFontFamily": FONT_FAMILY},',
    ),
    (
        "gen_mermaid.py",
        "测量字体环境变量未传给 mmdc（钩子启动即退出）",
        "    env[SANS_SERIF_ENV] = theme_font_family()",
        "    env[SANS_SERIF_ENV] = \"Arial\"",
    ),
    (
        "gen_mermaid.py",
        "依赖版本不符也继续渲染（lockfile 被绕过时毫无察觉）",
        "        if got != want:",
        "        if False:",
    ),
    (
        "gen_mermaid.py",
        "浏览器发现不再核对版本（任意 Chrome 都能生成资产）",
        "            if PINNED_BROWSER in candidate.as_posix() and candidate.is_file():",
        "            if candidate.is_file():",
    ),
    (
        "gen_mermaid.py",
        "浏览器版本退回 latest（资产随浏览器更新漂移）",
        'PINNED_BROWSER = "157.0.8103.78"',
        'PINNED_BROWSER = "latest"',
    ),
    (
        "mermaid/install-browser.js",
        "浏览器安装目录退回相对路径（CI 首次解压即失败）",
        'path.join(dir, ".browser")',
        '".browser"',
    ),
    # ---- mermaid_source.py ----
    (
        "mermaid_source.py",
        "未标记的 Mermaid 块被静默跳过（电子书里只剩一行代码说明）",
        "        if MERMAID_OPEN_RE.match(line):",
        "        if False:",
    ),
    (
        "mermaid_source.py",
        "同一输出资产被多处声明不报（后一个标记覆盖前图，成书图错位）",
        "            if block.asset_path in seen:",
        "            if False:",
    ),
]


def main():
    print("=== 变异测试：还原每个修复后，自测是否变红 ===")
    originals = {name: (TOOLS / name).read_text(encoding="utf-8") for name in TARGETS}

    caught = 0
    stale = 0
    for target, label, fixed, broken in MUTATIONS:
        if fixed not in originals[target]:
            # 锚点命中不了：不是「无害跳过」，而是这个修复已经不在代码里，
            # 自测也因此从未验证过它。必须显式计入失败，否则会像 2026-10-09
            # 的一幕：重构把 guard 从 `"todo-miniprogram" not in text` 换成
            # `pname not in text`，锚点悄悄失配，caught 19/20 直接让 CI 变红。
            stale += 1
            print(f"  ❌ 锚点未命中（该项修复未被验证）: {label}")
            continue
        with tempfile.TemporaryDirectory() as td:
            td = pathlib.Path(td)
            for name in TARGETS:
                (td / name).parent.mkdir(parents=True, exist_ok=True)
                (td / name).write_text(originals[name], encoding="utf-8")
            (td / target).write_text(
                originals[target].replace(fixed, broken, 1), encoding="utf-8")
            # 自测文件同样要在 td 里跑：它按 __file__ 找同目录的被测脚本，
            # 放在外面跑的是仓库里的原版，变异等于没变。
            # 曾少了这一行——每项都因「文件不存在」退出码 2 被计成「变红」，
            # 20/20 全绿其实一次自测都没跑过。
            test_file = TARGETS[target]
            shutil.copy(TOOLS / test_file, td / test_file)
            for dep in DEPS.get(target, []):
                # 依赖可能在子目录（如 mermaid/package.json），先建父目录
                (td / dep).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(TOOLS / dep, td / dep)
            r = subprocess.run(
                [sys.executable, test_file], cwd=td,
                capture_output=True, text=True, encoding="utf-8", errors="replace")
            out = (r.stdout or "") + (r.stderr or "")
            # unittest 的汇总写在 stderr；没有汇总就说明自测根本没跑起来，
            # 那退出码非零只是崩了，不能当作「抓到了」的证据。
            ran = "Ran " in out and " tests in " in out
            if not ran:
                caught += 0
                print(f"  ❌ 自测没跑起来（退出码 {r.returncode}，无测试汇总）: {label}")
                print(f"     {out.strip()[-300:]}")
                continue
            red = r.returncode != 0
            caught += red
            print(f"  {'✅ 变红（自测能抓到）' if red else '❌ 仍绿（自测抓不到！）'}  {label}")

    print(f"\n{caught}/{len(MUTATIONS)} 项变异被自测捕获"
          + (f"，{stale} 项锚点未命中（等于未验证）" if stale else ""))
    intact = all((TOOLS / n).read_text(encoding="utf-8") == s for n, s in originals.items())
    print(f"仓库内被变异的脚本均未被改动: {intact}")
    return 0 if caught == len(MUTATIONS) and intact else 1


if __name__ == "__main__":
    sys.exit(main())

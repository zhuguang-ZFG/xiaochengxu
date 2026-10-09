# -*- coding: utf-8 -*-
"""变异测试：把校验脚本的修复逐条还原成修复前写法，确认自测会变红。

目的：证明 tools/test_*.py 真的能抓住这些缺陷，而不是碰巧全绿。
全程在临时目录操作，不改动仓库里的真实文件。

每项变异是四元组：(目标脚本, 说明, 修复后的写法, 修复前的写法)。
目标脚本决定跑哪个自测文件、以及断言哪个源文件未被改动。
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
}

MUTATIONS = [
    # ---- check_repo.py ----
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
        "示例工程同步检查形同虚设（永不比对）",
        'if _norm_code("\\n".join(buf)) != _norm_code(disk):',
        'if False:',
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
                (td / name).write_text(originals[name], encoding="utf-8")
            (td / target).write_text(
                originals[target].replace(fixed, broken, 1), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, TARGETS[target]], cwd=td,
                capture_output=True, text=True, encoding="utf-8", errors="replace")
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

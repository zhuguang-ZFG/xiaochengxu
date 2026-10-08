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
        "按文件名全局匹配（未引用示例工程的文章也被误判漂移）",
        'if "todo-miniprogram" not in text:',
        'if False:',
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
    for target, label, fixed, broken in MUTATIONS:
        if fixed not in originals[target]:
            print(f"  跳过（锚点未命中）: {label}")
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

    print(f"\n{caught}/{len(MUTATIONS)} 项变异被自测捕获")
    intact = all((TOOLS / n).read_text(encoding="utf-8") == s for n, s in originals.items())
    print(f"仓库内被变异的脚本均未被改动: {intact}")
    return 0 if caught == len(MUTATIONS) and intact else 1


if __name__ == "__main__":
    sys.exit(main())

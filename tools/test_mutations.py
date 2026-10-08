# -*- coding: utf-8 -*-
"""变异测试：把 check_repo.py 的修复逐条还原成修复前写法，确认自测会变红。

目的：证明 tools/test_check_repo.py 真的能抓住这些缺陷，而不是碰巧全绿。
全程在临时目录操作，不改动仓库里的真实文件。
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile

TOOLS = pathlib.Path(__file__).resolve().parent
ORIG = (TOOLS / "check_repo.py").read_text(encoding="utf-8")

# 每项：(说明, 修复后的写法, 修复前的写法)
MUTATIONS = [
    (
        "孤儿检查不递归（iterdir 看不到 videos/）",
        'sorted(ASSETS.rglob("*"))',
        'sorted(ASSETS.iterdir())',
    ),
    (
        "根目录文档不在扫描范围（CONTRIBUTING/CHANGELOG 断链漏检）",
        'sorted(DOCS.rglob("*.md")) + sorted(ROOT.glob("*.md"))',
        'sorted(DOCS.rglob("*.md"))',
    ),
    (
        "不剥离代码块（契约里的用法示例被当成真实链接）",
        'return INLINE_CODE_RE.sub("", FENCE_RE.sub("", text))',
        'return text',
    ),
    (
        "围栏正则锚定行首（漏掉列表项里缩进 2 空格的围栏）",
        'FENCE_LINE_RE = re.compile(r"^[ \\t]{0,3}',
        'FENCE_LINE_RE = re.compile(r"^',
    ),
]


def main():
    print("=== 变异测试：还原每个修复后，自测是否变红 ===")
    caught = 0
    for label, fixed, broken in MUTATIONS:
        if fixed not in ORIG:
            print(f"  跳过（锚点未命中）: {label}")
            continue
        with tempfile.TemporaryDirectory() as td:
            td = pathlib.Path(td)
            shutil.copy(TOOLS / "test_check_repo.py", td / "test_check_repo.py")
            (td / "check_repo.py").write_text(
                ORIG.replace(fixed, broken, 1), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "test_check_repo.py"], cwd=td,
                capture_output=True, text=True, errors="replace")
            red = r.returncode != 0
            caught += red
            print(f"  {'✅ 变红（自测能抓到）' if red else '❌ 仍绿（自测抓不到！）'}  {label}")

    print(f"\n{caught}/{len(MUTATIONS)} 项变异被自测捕获")
    intact = (TOOLS / "check_repo.py").read_text(encoding="utf-8") == ORIG
    print(f"仓库内 check_repo.py 未被改动: {intact}")
    return 0 if caught == len(MUTATIONS) and intact else 1


if __name__ == "__main__":
    sys.exit(main())

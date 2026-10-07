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


def main():
    check_metadata()
    check_images()
    check_links()
    check_sequence()
    check_orphans()
    check_json()
    check_js_syntax()
    if errors:
        print(f"❌ {len(errors)} 个问题:")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    print(f"✅ 全部通过（{len(md_files())} 篇文档）")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""mermaid_source.py 的自测（零第三方依赖）。

守护的是「Mermaid 源码 + 预渲染图」这条链的入口：
- 标记和 Mermaid 块必须成对出现，不能悄悄漏掉；
- 标记里的资产路径必须可解析、不能重复；
- 电子书导出时的物化结果只能是独占一段的图片，不能再残留围栏。
"""
import pathlib
import sys
import unittest

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mermaid_source as ms  # noqa: E402


class ParseTest(unittest.TestCase):
    def setUp(self):
        self.path = pathlib.Path("docs/03-进阶/demo.md")

    def test_标记与块成对时解析出题注和源码(self):
        text = """# 标题

<!-- figure: ../assets/diagram-login-flow.png | 登录态时序图 -->
```mermaid
sequenceDiagram
  A->>B: hi
```

正文
"""
        blocks = ms.parse_text(text, self.path)
        self.assertEqual(len(blocks), 1)
        b = blocks[0]
        self.assertEqual(b.line_no, 3)
        self.assertEqual(b.asset_rel, "../assets/diagram-login-flow.png")
        self.assertEqual(b.asset_path, (self.path.parent / b.asset_rel).resolve())
        self.assertEqual(b.caption, "登录态时序图")
        self.assertEqual(b.source, "sequenceDiagram\n  A->>B: hi")
        self.assertEqual(text[b.start:b.end],
                         '<!-- figure: ../assets/diagram-login-flow.png | 登录态时序图 -->\n'
                         '```mermaid\nsequenceDiagram\n  A->>B: hi\n```\n')

    def test_标记和块之间允许空行(self):
        text = ("<!-- figure: ../assets/diagram-x.png | 图题 -->\n\n"
                "```mermaid\nflowchart LR\n  A --> B\n```\n")
        blocks = ms.parse_text(text, self.path)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].source, "flowchart LR\n  A --> B")

    def test_未标记的_mermaid_块必须报错(self):
        text = "```mermaid\nflowchart LR\n  A --> B\n```\n"
        with self.assertRaisesRegex(ms.MermaidError, "未标记"):
            ms.parse_text(text, self.path)

    def test_标记后不是_mermaid_块必须报错(self):
        text = ("<!-- figure: ../assets/diagram-x.png | 图题 -->\n"
                "```js\nconsole.log(1)\n```\n")
        with self.assertRaisesRegex(ms.MermaidError, "Mermaid"):
            ms.parse_text(text, self.path)

    def test_标记后没有块必须报错(self):
        text = "<!-- figure: ../assets/diagram-x.png | 图题 -->\n"
        with self.assertRaisesRegex(ms.MermaidError, "Mermaid"):
            ms.parse_text(text, self.path)

    def test_未闭合的_mermaid_块必须报错(self):
        text = ("<!-- figure: ../assets/diagram-x.png | 图题 -->\n"
                "```mermaid\nflowchart LR\n  A --> B\n")
        with self.assertRaisesRegex(ms.MermaidError, "闭合"):
            ms.parse_text(text, self.path)

    def test_空题注必须报错(self):
        text = ("<!-- figure: ../assets/diagram-x.png |   -->\n"
                "```mermaid\nflowchart LR\n  A --> B\n```\n")
        with self.assertRaisesRegex(ms.MermaidError, "题注"):
            ms.parse_text(text, self.path)

    def test_资产必须是相对的_png(self):
        for asset in ("C:/tmp/diagram-x.png", "../assets/diagram-x.svg"):
            text = (f"<!-- figure: {asset} | 图题 -->\n"
                    "```mermaid\nflowchart LR\n  A --> B\n```\n")
            with self.assertRaises(ms.MermaidError):
                ms.parse_text(text, self.path)

    def test_代码块里的标记不算数(self):
        text = ("```markdown\n"
                "<!-- figure: ../assets/diagram-x.png | 图题 -->\n"
                "```mermaid\nflowchart LR\n  A --> B\n```\n"
                "```\n"
                "正文\n")
        self.assertEqual(ms.parse_text(text, self.path), [])

    def test_多张图按出现顺序返回(self):
        text = ("<!-- figure: ../assets/diagram-a.png | 图 A -->\n"
                "```mermaid\nflowchart LR\n  A --> B\n```\n"
                "中间正文\n"
                "<!-- figure: ../assets/diagram-b.png | 图 B -->\n"
                "```mermaid\nflowchart LR\n  B --> C\n```\n")
        blocks = ms.parse_text(text, self.path)
        self.assertEqual([b.asset_rel for b in blocks],
                         ["../assets/diagram-a.png", "../assets/diagram-b.png"])
        self.assertEqual([b.line_no for b in blocks], [1, 7])

    def test_不同文件重复输出同一资产必须报错(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "a.md").write_text(
                "<!-- figure: ../assets/diagram-x.png | 图 A -->\n"
                "```mermaid\nflowchart LR\n  A --> B\n```\n", encoding="utf-8")
            (root / "b.md").write_text(
                "<!-- figure: ../assets/diagram-x.png | 图 B -->\n"
                "```mermaid\nflowchart LR\n  B --> C\n```\n", encoding="utf-8")
            with self.assertRaisesRegex(ms.MermaidError, "重复"):
                ms.scan_paths([root / "a.md", root / "b.md"])


class MaterializeTest(unittest.TestCase):
    def test_物化成独占一段的图片(self):
        path = pathlib.Path("docs/03-进阶/demo.md")
        text = ("前文\n\n"
                "<!-- figure: ../assets/diagram-login-flow.png | 登录态时序图 -->\n"
                "```mermaid\nsequenceDiagram\n  A->>B: hi\n```\n"
                "\n后文\n")
        out, blocks = ms.materialize(text, path)
        self.assertEqual(len(blocks), 1)
        self.assertIn("![登录态时序图](../assets/diagram-login-flow.png)", out)
        self.assertNotIn("```mermaid", out)
        self.assertNotIn("<!-- figure:", out)
        self.assertIn("前文", out)
        self.assertIn("后文", out)

    def test_题注里的方括号被转义(self):
        path = pathlib.Path("docs/03-进阶/demo.md")
        text = ("<!-- figure: ../assets/diagram-x.png | 图 [A] -->\n"
                "```mermaid\nflowchart LR\n  A --> B\n```\n")
        out, _ = ms.materialize(text, path)
        self.assertIn(r"![图 \[A\]](../assets/diagram-x.png)", out)

    def test_没有标记时原样返回(self):
        path = pathlib.Path("docs/03-进阶/demo.md")
        text = "# 标题\n\n```js\nconst a = 1\n```\n"
        out, blocks = ms.materialize(text, path)
        self.assertEqual(out, text)
        self.assertEqual(blocks, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)

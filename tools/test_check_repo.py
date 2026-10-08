# -*- coding: utf-8 -*-
"""check_repo.py 的自测（零依赖，标准库 unittest）。

为什么需要它：本次排查发现的 check_repo.py 缺陷**全部是"静默放行"型**——
校验器不报错，CI 显示绿灯，但检查根本没生效（孤儿检查不递归、根目录文档
不在扫描范围、代码块示例被当成真实链接、围栏正则锚定行首漏掉缩进围栏）。
这类 bug 靠"跑一遍看有没有报错"是发现不了的，必须用构造用例反证。

用法：
    python -m unittest discover -s tools -p "test_*.py"
    python tools/test_check_repo.py
"""
import pathlib
import sys
import tempfile
import unittest

# Windows 控制台默认 GBK，unittest 打印中文用例名会乱码（不影响断言，但本地没法读）
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import check_repo as chk  # noqa: E402


class CheckRepoTest(unittest.TestCase):
    """每个用例在临时目录里搭一个迷你仓库，替换 chk 的路径全局后调用检查函数。"""

    def setUp(self):
        self._orig = (chk.ROOT, chk.DOCS, chk.ASSETS, chk.errors)
        self.addCleanup(self._restore)

    def _restore(self):
        chk.ROOT, chk.DOCS, chk.ASSETS, chk.errors = self._orig

    def fixture(self, files):
        """files: {相对路径: 文本内容或 None（None 表示写二进制占位文件）}"""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = pathlib.Path(tmp.name)
        for rel, content in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            if content is None:
                p.write_bytes(b"\0")
            else:
                p.write_text(content, encoding="utf-8")
        chk.ROOT, chk.DOCS = root, root / "docs"
        chk.ASSETS = chk.DOCS / "assets"
        chk.errors = []
        return root

    def run_checks(self, *names):
        for n in names:
            getattr(chk, n)()
        return list(chk.errors)

    # ---------- 孤儿资产：必须递归子目录 ----------

    def test_孤儿检查覆盖子目录(self):
        self.fixture({
            "docs/assets/videos/video-01.mp4": None,   # 无人引用
            "README.md": "# 标题\n",
        })
        errs = self.run_checks("check_orphans")
        self.assertTrue(any("video-01.mp4" in e for e in errs),
                        f"子目录里的未引用资产必须被报出，实际: {errs}")

    def test_子目录资产被引用则不报(self):
        self.fixture({
            "docs/assets/videos/video-01.mp4": None,
            "docs/01-入门/01-x.md": "见 [视频](../assets/videos/video-01.mp4)\n",
            "README.md": "# 标题\n",
        })
        errs = self.run_checks("check_orphans")
        self.assertEqual(errs, [], f"已引用的资产不应报孤儿，实际: {errs}")

    # ---------- 链接：必须覆盖根目录文档 ----------

    def test_链接检查覆盖根目录文档(self):
        self.fixture({
            "CONTRIBUTING.md": "[坏了](./不存在的文件.md)\n",
            "README.md": "# 标题\n",
        })
        errs = self.run_checks("check_links")
        self.assertTrue(any("CONTRIBUTING.md" in e for e in errs),
                        f"根目录文档的断链必须被报出，实际: {errs}")

    def test_changelog断链也能发现(self):
        self.fixture({"CHANGELOG.md": "[坏了](docs/没有这个.md)\n"})
        errs = self.run_checks("check_links")
        self.assertTrue(any("CHANGELOG.md" in e for e in errs),
                        f"CHANGELOG 断链必须被报出，实际: {errs}")

    # ---------- 链接：代码块里的示例不能误报 ----------

    def test_围栏代码块内示例不误报(self):
        self.fixture({
            "docs/_契约.md": (
                "# 契约\n\n"
                "```markdown\n"
                "> [示例](../assets/videos/video-NN-slug.mp4)\n"
                "```\n"
            ),
        })
        errs = self.run_checks("check_links", "check_images")
        self.assertEqual(errs, [], f"围栏内示例路径不应报断链，实际: {errs}")

    def test_缩进围栏内示例不误报(self):
        """列表项内的围栏缩进 2 空格（CommonMark 允许 ≤3）——锚定行首会配不上对。"""
        self.fixture({
            "docs/_契约.md": (
                "# 契约\n\n"
                "- 引用格式：\n\n"
                "  ```markdown\n"
                "  [标题](../assets/videos/video-NN-slug.mp4)\n"
                "  ```\n"
            ),
        })
        errs = self.run_checks("check_links")
        self.assertEqual(errs, [], f"缩进围栏内示例不应报断链，实际: {errs}")

    def test_行内代码内示例不误报(self):
        self.fixture({
            "docs/_契约.md": "用 `![说明](../assets/screen-hello.png)` 引用图片\n",
        })
        errs = self.run_checks("check_images", "check_links")
        self.assertEqual(errs, [], f"行内代码里的示例不应报断链，实际: {errs}")

    def test_围栏外的真实断链仍要报(self):
        """剥离逻辑不能矫枉过正：代码块外的真断链必须照报。"""
        self.fixture({
            "docs/01-入门/01-x.md": (
                "```text\n[示例](./假的.md)\n```\n\n"
                "[真断链](./真的不存在.md)\n"
            ),
        })
        errs = self.run_checks("check_links")
        self.assertTrue(any("真的不存在.md" in e for e in errs),
                        f"围栏外的真实断链必须报出，实际: {errs}")
        self.assertFalse(any("假的.md" in e for e in errs),
                         f"围栏内的不应报出，实际: {errs}")

    # ---------- 围栏语言标注：缩进围栏同样要检查 ----------

    def test_缩进围栏未标语言要报(self):
        self.fixture({
            "docs/_契约.md": "- 示例：\n\n  ```\n  裸代码块\n  ```\n",
        })
        errs = self.run_checks("check_fences_language")
        self.assertTrue(any("未标注语言" in e for e in errs),
                        f"缩进围栏未标语言必须报出，实际: {errs}")

    def test_缩进围栏已标语言不报(self):
        self.fixture({
            "docs/_契约.md": "- 示例：\n\n  ```js\n  const a = 1;\n  ```\n",
        })
        errs = self.run_checks("check_fences_language")
        self.assertEqual(errs, [], f"已标语言的缩进围栏不应报，实际: {errs}")

    def test_围栏未闭合要报(self):
        self.fixture({"docs/01-入门/01-x.md": "```js\nconst a = 1;\n"})
        errs = self.run_checks("check_fences_language")
        self.assertTrue(any("未闭合" in e for e in errs),
                        f"未闭合围栏必须报出，实际: {errs}")

    # ---------- 视频资产规范 ----------

    def test_视频命名不合规要报(self):
        self.fixture({"docs/assets/videos/clip.mp4": None})
        errs = self.run_checks("check_video_assets")
        self.assertTrue(any("video-" in e for e in errs),
                        f"非 video- 前缀必须报出，实际: {errs}")

    def test_视频非mp4要报(self):
        self.fixture({"docs/assets/videos/video-01.gif": None})
        errs = self.run_checks("check_video_assets")
        self.assertTrue(any("MP4" in e for e in errs),
                        f"videos/ 下的非 MP4 必须报出，实际: {errs}")

    def test_视频超限要报(self):
        self.fixture({"docs/assets/videos/video-01.mp4": None})
        orig = chk.VIDEO_LIMIT
        chk.VIDEO_LIMIT = 0          # 任何文件都超限
        self.addCleanup(setattr, chk, "VIDEO_LIMIT", orig)
        errs = self.run_checks("check_video_assets")
        self.assertTrue(any("超过 3MB 上限" in e or "3MB" in e for e in errs),
                        f"超限必须报出，实际: {errs}")

    def test_gif超限要报(self):
        self.fixture({"docs/assets/demo-x.gif": None})
        orig = chk.GIF_LIMIT
        chk.GIF_LIMIT = 0
        self.addCleanup(setattr, chk, "GIF_LIMIT", orig)
        errs = self.run_checks("check_gif_size")
        self.assertTrue(any("200KB" in e for e in errs),
                        f"GIF 超限必须报出，实际: {errs}")

    # ---------- 示例工程与教程同步（实战篇声称「逐行对应」） ----------

    EXAMPLE_APP_JSON = '{\n  "pages": ["pages/index/index"],\n  "sitemapLocation": "sitemap.json"\n}\n'

    def test_示例工程漂移要报(self):
        """教程块漏了工程文件里真实存在的字段——这正是历史上发生过的漂移。"""
        self.fixture({
            "examples/todo-miniprogram/app.json": self.EXAMPLE_APP_JSON,
            "docs/06-实战/01-x.md": (
                "# 实战\n\n本工程位于 examples/todo-miniprogram。\n\n"
                "### app.json\n\n"
                "```json\n"
                '{\n  "pages": ["pages/index/index"]\n}\n'
                "```\n"
            ),
        })
        errs = self.run_checks("check_example_sync")
        self.assertTrue(any("不一致" in e and "app.json" in e for e in errs),
                        f"教程与工程文件的真实漂移必须报出，实际: {errs}")

    def test_示例工程一致不报(self):
        self.fixture({
            "examples/todo-miniprogram/app.json": self.EXAMPLE_APP_JSON,
            "docs/06-实战/01-x.md": (
                "# 实战\n\n本工程位于 examples/todo-miniprogram。\n\n"
                "### app.json\n\n```json\n" + self.EXAMPLE_APP_JSON + "```\n"
            ),
        })
        errs = self.run_checks("check_example_sync")
        self.assertEqual(errs, [], f"逐行一致的块不应报漂移，实际: {errs}")

    def test_未引用示例工程的文章不参与比对(self):
        """入门/基础各篇也有 `app.json` 等同名块，但那是独立的教学示例。

        按文件名全局匹配会把它们全部误判为漂移（实测 18 处误报）。
        """
        self.fixture({
            "examples/todo-miniprogram/app.json": self.EXAMPLE_APP_JSON,
            "docs/06-实战/02-另一个实战.md": (
                "# 另一个实战\n\n与示例工程无关的独立项目。\n\n"
                "### app.json\n\n```json\n{\n  \"pages\": [\"pages/detail/detail\"]\n}\n```\n"
            ),
        })
        errs = self.run_checks("check_example_sync")
        self.assertEqual(errs, [], f"未引用示例工程的文章不应参与比对，实际: {errs}")

    def test_非源码块不参与比对(self):
        """bash 块是操作指令，上下文里的 `index.js` 不构成节选关系。"""
        self.fixture({
            "examples/todo-miniprogram/pages/index/index.js": "Page({ data: { a: 1 } })\n",
            "docs/06-实战/01-x.md": (
                "# 实战\n\n本工程位于 examples/todo-miniprogram。\n\n"
                "### 单元测试\n\n页面 `index.js` 的测试：\n\n"
                "```bash\nnode --test examples/todo-miniprogram/tests/*.test.js\n```\n"
            ),
        })
        errs = self.run_checks("check_example_sync")
        self.assertEqual(errs, [], f"bash 块不应与源码文件比对，实际: {errs}")

    def test_标注要点的块豁免(self):
        self.fixture({
            "examples/todo-miniprogram/pages/index/index.wxss": ".page { padding: 24rpx; }\n.other { color: red; }\n",
            "docs/06-实战/01-x.md": (
                "# 实战\n\n本工程位于 examples/todo-miniprogram。\n\n"
                "### index.wxss（要点）\n\n```css\n.page { padding: 24rpx; }\n```\n"
            ),
        })
        errs = self.run_checks("check_example_sync")
        self.assertEqual(errs, [], f"标注「要点」的节选块应豁免，实际: {errs}")

    # ---------- strip_code 行为 ----------

    def test_strip_code_行为(self):
        src = (
            "行内 `[a](./x.md)` 保留\n"
            "```js\n[b](./y.md)\n```\n"
            "  ```\n  [c](./z.md)\n  ```\n"
            "[d](./real.md)\n"
        )
        out = chk.strip_code(src)
        for gone in ("./x.md", "./y.md", "./z.md"):
            self.assertNotIn(gone, out, f"{gone} 应被剥离")
        self.assertIn("./real.md", out, "代码块外的链接必须保留")


if __name__ == "__main__":
    unittest.main(verbosity=2)

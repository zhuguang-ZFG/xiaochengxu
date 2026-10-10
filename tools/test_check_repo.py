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

# Windows 控制台默认 GBK，unittest 打印中文用例名会乱码（不影响断言，但本地没法读）。
# unittest 把用例名写到 stderr 而非 stdout，两个流都要切。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
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

    # ---------- 序号：目录内必须连续 ----------

    def test_序号非连续要报(self):
        """缺号会让「下一篇」链接断，读者按 01/03 顺序读会漏一篇。"""
        self.fixture({
            "docs/01-入门/01-a.md": "# a\n",
            "docs/01-入门/03-c.md": "# c\n",
            "README.md": "# 标题\n",
        })
        errs = self.run_checks("check_sequence")
        self.assertTrue(any("序号非连续" in e for e in errs),
                        f"序号缺号必须报出，实际: {errs}")

    def test_序号连续不报(self):
        self.fixture({
            "docs/01-入门/01-a.md": "# a\n",
            "docs/01-入门/02-b.md": "# b\n",
            "README.md": "# 标题\n",
        })
        errs = self.run_checks("check_sequence")
        self.assertEqual(errs, [], f"连续序号不应报，实际: {errs}")

    def test_契约文件不参与序号检查(self):
        """_契约.md 无序号，计入后每个目录都会误报缺号。"""
        self.fixture({
            "docs/_契约.md": "# 契约\n",
            "docs/02-基础/01-a.md": "# a\n",
            "README.md": "# 标题\n",
        })
        errs = self.run_checks("check_sequence")
        self.assertEqual(errs, [], f"契约文件不应参与序号检查，实际: {errs}")

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

    # 渲染中断留下的空壳：ffmpeg 已建出文件，进程被 kill 时只剩 ftyp+free+mdat 头。
    # 体积检查对它完全瞎（48 字节 < 3MB），播放器却打不开。
    SHELL_48 = bytes.fromhex(
        "000000206674797069736f6d0000020069736f6d69736f32617663316d703431"
        "0000000866726565"
        "000000006d646174")

    @staticmethod
    def _box(kind, payload=b""):
        """一个合法的 ISO-BMFF 顶层 box：4 字节长度 + 4 字节类型 + 载荷"""
        return (len(payload) + 8).to_bytes(4, "big") + kind + payload

    def _write(self, root, rel, data):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p

    def test_视频缺moov要报(self):
        """48 字节空壳必须报出——这是 v2.4.3 提交前 13 集里 4 集的真实状态。"""
        root = self.fixture({})
        self._write(root, "docs/assets/videos/video-02-intro.mp4", self.SHELL_48)
        errs = self.run_checks("check_video_assets")
        self.assertTrue(any("moov" in e for e in errs),
                        f"缺 moov 的空壳必须报出，实际: {errs}")

    def test_视频含moov不报(self):
        """探针不能把正常视频判成空壳：moov 在文件头（faststart）或在文件尾都算完整。"""
        mdat = self._box(b"mdat", b"\x11" * 40)
        for tag, blob in (
                ("头", self._box(b"ftyp", b"isom") + self._box(b"moov", b"\x22" * 20) + mdat),
                ("尾", self._box(b"ftyp", b"isom") + mdat + self._box(b"moov", b"\x22" * 20))):
            root = self.fixture({})
            self._write(root, "docs/assets/videos/video-01-roadmap.mp4", blob)
            errs = self.run_checks("check_video_assets")
            self.assertEqual([e for e in errs if "moov" in e], [],
                             f"moov 在文件{tag}却被误报: {errs}")

    def test_载荷里出现moov字样不算完整(self):
        """按 box 走，而不是在字节流里搜 `moov` 四个字节。

        这个文件根本没有 moov，只有 mdat 载荷，而载荷里故意嵌了 `moov` 字样——
        「在头尾 64KB 里搜字节」的写法会把它判成完整，于是坏视频照样发布。
        """
        root = self.fixture({})
        self._write(root, "docs/assets/videos/video-05-component.mp4",
                    self._box(b"ftyp", b"isom") + self._box(b"mdat", b"xxmoov" + b"\x00" * 40))
        errs = self.run_checks("check_video_assets")
        self.assertTrue(any("moov" in e for e in errs),
                        f"载荷里的 moov 字样不该被当成索引，实际: {errs}")

    def test_box声明比文件长要报(self):
        """写到一半被截断：faststart 的文件 moov 在前面，光查「有没有 moov」会漏。"""
        root = self.fixture({})
        blob = (self._box(b"ftyp", b"isom") + self._box(b"moov", b"\x22" * 20)
                + self._box(b"mdat", b"\x33" * 200))
        self._write(root, "docs/assets/videos/video-07-perf.mp4", blob[:-120])
        errs = self.run_checks("check_video_assets")
        self.assertTrue(any("moov" in e for e in errs),
                        f"截断的文件必须报出，实际: {errs}")

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

    # ---------- 示例工程内的 Markdown 同样在扫描范围 ----------

    def test_示例工程README未标语言要报(self):
        self.fixture({
            "examples/todo-miniprogram/README.md": "## 目录\n\n```\n裸代码块\n```\n",
        })
        errs = self.run_checks("check_fences_language")
        self.assertTrue(any("未标注语言" in e for e in errs),
                        f"示例工程 README 的代码块语言必须被检查，实际: {errs}")

    def test_示例工程README断链要报(self):
        self.fixture({
            "examples/todo-miniprogram/README.md": "[坏了](./不存在.md)\n",
        })
        errs = self.run_checks("check_links")
        self.assertTrue(any("不存在.md" in e for e in errs),
                        f"示例工程 README 的断链必须被报出，实际: {errs}")

    # ---------- API 真实性（正文/示例代码里的 wx.<name> 必须真实存在） ----------

    API_LIST = "# 夹具名单\n\nwx.showModal\nwx.request\nwx.getStorageSync\nwx.cloud\n"
    PROMISE_LIST = "# 夹具：不传回调即返回 Promise 的\nwx.showModal\n"

    def api_fixture(self, files, promise_list=None):
        """迷你仓库 + 两份夹具名单。名单文件随工具走而非随仓库走，所以单独指过去；
        不能依赖仓库里的真实名单——变异测试只把两个脚本拷进临时目录。"""
        root = self.fixture(files)
        data = root / "tools" / "data"
        data.mkdir(parents=True, exist_ok=True)
        (data / "wx-api-names.txt").write_text(self.API_LIST, encoding="utf-8")
        (data / "wx-api-promise.txt").write_text(
            self.PROMISE_LIST if promise_list is None else promise_list, encoding="utf-8")
        for attr, name in (("API_LIST_FILE", "wx-api-names.txt"), ("PROMISE_LIST_FILE", "wx-api-promise.txt")):
            self.addCleanup(setattr, chk, attr, getattr(chk, attr))
            setattr(chk, attr, data / name)
        return root

    def test_虚构API要报(self):
        """速查索引里真出现过：把 npm 包的能力写成了 `wx.` 下的接口。"""
        self.api_fixture({"docs/01-入门/01-x.md": "用 `wx.promisify` 转 Promise\n"})
        errs = self.run_checks("check_api_names")
        self.assertTrue(any("wx.promisify" in e and "01-x.md:1" in e for e in errs),
                        f"名单之外的 API 名必须报出（带行号），实际: {errs}")

    def test_真实API不报_含云开发命名空间(self):
        self.api_fixture({
            "docs/01-入门/01-x.md": (
                "```js\nconst { confirm } = await wx.showModal({ title: 'x' });\n"
                "wx.cloud.callFunction({ name: 'todo' });\n```\n"
                "官方：https://developers.weixin.qq.com/miniprogram/dev/api/ui/interaction/wx.showModal.html\n"
            ),
        })
        errs = self.run_checks("check_api_names")
        self.assertEqual(errs, [], f"名单内的 API（含 wx.cloud 命名空间）不应报，实际: {errs}")

    def test_标题里的wx_API不误报(self):
        """`wx.API 速查索引` 是标题用语不是接口；官方 API 全部小写开头。"""
        self.api_fixture({"docs/00-学习路线/02-x.md": "# wx.API 速查索引\n\n40+ 个 `wx.*` API\n"})
        errs = self.run_checks("check_api_names")
        self.assertEqual(errs, [], f"大写开头的非接口用语不应报，实际: {errs}")

    def test_api_ignore标记豁免(self):
        """CHANGELOG 记录「删掉了虚构 API」时必然要写出那个名字。"""
        self.api_fixture({"CHANGELOG.md": "- 删除虚构的 `wx.promisify` <!-- api-ignore -->\n"})
        errs = self.run_checks("check_api_names")
        self.assertEqual(errs, [], f"带 api-ignore 标记的行应豁免，实际: {errs}")

    def test_示例工程源码里的拼错API要报(self):
        self.api_fixture({"examples/todo-miniprogram/pages/index/index.js": "wx.showModel({ title: 'x' });\n"})
        errs = self.run_checks("check_api_names")
        self.assertTrue(any("wx.showModel" in e and "index.js" in e for e in errs),
                        f"示例工程源码里拼错的 API 必须报出，实际: {errs}")

    def test_名单文件缺失要明确报错而非假通过(self):
        self.api_fixture({"docs/01-入门/01-x.md": "wx.request\n"})
        chk.API_LIST_FILE = chk.API_LIST_FILE.with_name("不存在.txt")
        with self.assertRaises(SystemExit, msg="名单缺失必须显式失败，否则空名单会把一切放行或全报"):
            chk.check_api_names()

    def test_抽取官方名单(self):
        """抓取逻辑：去重、排序、同样只认小写开头的一级标识符。"""
        html = ('<a href="/api/ui/wx.showModal.html">wx.showModal</a> wx.API '
                'wx.request wx.showModal wx.cloud.callFunction')
        self.assertEqual(chk.extract_api_names(html), ["wx.cloud", "wx.request", "wx.showModal"])

    # ---------- Promise 断言（正文说某接口「回调式」/ 代码 await 某接口，必须与官方一致） ----------

    def test_回调式断言命中支持Promise的接口要报(self):
        """实战篇真出现过的原话形态。"""
        self.api_fixture({"docs/06-实战/01-x.md":
                          "6. **wx.showModal 用 async/await**：showModal 是回调式 API，用 Promise 包装再 await。\n"})
        errs = self.run_checks("check_promise_claims")
        self.assertTrue(any("wx.showModal" in e and "回调式" in e for e in errs),
                        f"把支持 Promise 风格的接口说成回调式必须报出，实际: {errs}")

    def test_带版本条件的正确说法不误报(self):
        """修正后的避坑 #6 原文：含「自行用 Promise 包装」但有版本前提，是对的。
        检查若把「包装/封装」也当否定断言，这句正确的话就会被报错。"""
        self.api_fixture({"docs/06-实战/01-x.md": (
            "6. **`await wx.showModal(...)` 拿不到 `confirm`**：异步 API 不传 success/fail/complete 时直接返回 Promise，"
            "拿不到的两种情况：基础库低于 2.10.2（需自行用 Promise 包装），或传了回调又去 await。\n")})
        errs = self.run_checks("check_promise_claims")
        self.assertEqual(errs, [], f"带版本条件的正确说法不应报，实际: {errs}")

    def test_对任务对象接口的回调式断言不报(self):
        self.api_fixture({"docs/03-进阶/03-x.md": "`wx.request` 是回调式 API，没有原生 Promise 版本，本身返回 RequestTask。\n"})
        errs = self.run_checks("check_promise_claims")
        self.assertEqual(errs, [], f"对确实不返回 Promise 的接口说回调式是对的，实际: {errs}")

    def test_await不返回Promise的接口要报(self):
        self.api_fixture({"docs/03-进阶/03-x.md": "```js\nconst res = await wx.request({ url });\n```\n"})
        errs = self.run_checks("check_promise_claims")
        self.assertTrue(any("await wx.request" in e for e in errs),
                        f"await 返回任务对象的接口必须报出，实际: {errs}")

    def test_await同步接口要报(self):
        self.api_fixture({"examples/todo-miniprogram/app.js": "const v = await wx.getStorageSync('k');\n"})
        errs = self.run_checks("check_promise_claims")
        self.assertTrue(any("await wx.getStorageSync" in e and "app.js" in e for e in errs),
                        f"示例工程里 await 同步接口必须报出，实际: {errs}")

    def test_await支持Promise的接口与二级云开发接口不报(self):
        self.api_fixture({"docs/06-实战/01-x.md": (
            "```js\nconst { confirm } = await wx.showModal({ title: 'x' });\n"
            "const r = await wx.cloud.callFunction({ name: 'todo' });\n```\n")})
        errs = self.run_checks("check_promise_claims")
        self.assertEqual(errs, [], f"await 名单内接口 / 二级云开发接口不应报，实际: {errs}")

    def test_await虚构接口不重复报(self):
        """拼错的名字由 check_api_names 报「不存在」；这里再报「不返回 Promise」是误导。"""
        self.api_fixture({"docs/06-实战/01-x.md": "```js\nawait wx.showModel({});\n```\n"})
        errs = self.run_checks("check_promise_claims")
        self.assertEqual(errs, [], f"不存在的接口不应由 Promise 检查再报一次，实际: {errs}")

    def test_api_ignore同样豁免Promise断言(self):
        self.api_fixture({"CHANGELOG.md": "- 教程曾写「`wx.showModal` 是回调式 API」 <!-- api-ignore -->\n"})
        errs = self.run_checks("check_promise_claims")
        self.assertEqual(errs, [], f"带 api-ignore 的引用原话应豁免，实际: {errs}")

    def test_两份名单不同步要明确报错(self):
        self.api_fixture({"docs/01-入门/01-x.md": "x\n"}, promise_list="wx.showModal\nwx.notInNames\n")
        with self.assertRaises(SystemExit, msg="Promise 名单含名称名单之外的名字说明两份名单不同源，必须显式失败"):
            chk.check_promise_claims()

    def test_抽取Promise名单(self):
        """typings 解析：剥 JSDoc（含示例代码）、按成员切块、看最后一个「): 类型」。"""
        dts = (
            "declare namespace WechatMiniprogram {\n"
            "    interface Wx {\n"
            "        /** [wx.showModal(Object object)](https://x/wx.showModal.html)\n"
            "         *\n"
            "wx.showModal({ success(res) { console.log(res) } })\n"
            "         */\n"
            "        showModal<T extends ShowModalOption = ShowModalOption>(\n"
            "            option: T\n"
            "        ): PromisifySuccessResult<T, ShowModalOption>\n"
            "        request<\n"
            "            T extends string | IAnyObject | ArrayBuffer = string\n"
            "        >(option: RequestOption<T>): RequestTask\n"
            "        getStorageSync<T = any>(key: string): T\n"
            "        onError(callback: (res: Error) => void): void\n"
            "        cloud: WxCloud\n"
            "    }\n"
            "}\n"
        )
        members, promise = chk.extract_promise_apis(dts)
        self.assertEqual(members, ["wx.cloud", "wx.getStorageSync", "wx.onError", "wx.request", "wx.showModal"])
        self.assertEqual(promise, ["wx.showModal"])

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

    # ---------- 随堂测验校验 ----------

    def test_quiz_format_通过(self):
        self.fixture({
            "docs/01-入门/01-test.md": (
                "---\ntitle: t\ndescription: d\ncategory: 入门\ntags: []\ndifficulty: ★☆☆☆☆\nreading_time: 1 min\nupdated: 2026-01-01\n---\n"
                "# Test\n## 为什么读这篇\nx\n## 正文\nx\n## 常见错误 / 避坑\n1. a\n2. b\n"
                "## 随堂测验\n\n**Q1**: 问题？\n- [ ] A. a\n- [ ] B. b\n- [ ] C. c\n- [ ] D. d\n\n<details><summary>答案</summary>\n\n**B**. 解释\n\n</details>\n\n"
                "**Q2**: 问题2？\n- [ ] A. a\n- [ ] B. b\n- [ ] C. c\n- [ ] D. d\n\n<details><summary>答案</summary>\n\n**A**. 解释\n\n</details>\n\n"
                "**Q3**: 问题3？\n- [ ] A. a\n- [ ] B. b\n- [ ] C. c\n- [ ] D. d\n\n<details><summary>答案</summary>\n\n**B**. 解释\n\n</details>\n\n"
                "## 验证\n- [ ] x\n## 延伸阅读\n- x\n"
            ),
        })
        chk.check_quiz_format()
        self.assertEqual(chk.errors, [])

    def test_quiz_format_缺失(self):
        self.fixture({
            "docs/01-入门/01-test.md": (
                "---\ntitle: t\ndescription: d\ncategory: 入门\ntags: []\ndifficulty: ★☆☆☆☆\nreading_time: 1 min\nupdated: 2026-01-01\n---\n"
                "# Test\n## 为什么读这篇\nx\n## 正文\nx\n## 常见错误 / 避坑\n1. a\n2. b\n## 验证\n- [ ] x\n"
            ),
        })
        chk.check_quiz_format()
        self.assertTrue(any("随堂测验" in e for e in chk.errors))

    def test_quiz_format_题目太少(self):
        self.fixture({
            "docs/01-入门/01-test.md": (
                "---\ntitle: t\ndescription: d\ncategory: 入门\ntags: []\ndifficulty: ★☆☆☆☆\nreading_time: 1 min\nupdated: 2026-01-01\n---\n"
                "# Test\n## 常见错误 / 避坑\n1. a\n2. b\n"
                "## 随堂测验\n\n**Q1**: 问题？\n- [ ] A. a\n\n<details><summary>答案</summary>\n\n**A**. 解释\n\n</details>\n\n"
                "## 验证\n- [ ] x\n"
            ),
        })
        chk.check_quiz_format()
        self.assertTrue(any("只有 1 题" in e for e in chk.errors))

    def test_quiz_format_元文章豁免(self):
        self.fixture({
            "docs/00-学习路线/01-test.md": (
                "---\ntitle: t\ndescription: d\ncategory: 学习路线\ntags: []\ndifficulty: ★☆☆☆☆\nreading_time: 1 min\nupdated: 2026-01-01\n---\n"
                "# Test\n## 正文\nx\n## 验证\n- [ ] x\n"
            ),
        })
        chk.check_quiz_format()
        self.assertEqual(chk.errors, [])

    # ---------- PROGRESS.md 同步校验 ----------

    def test_progress_sync_通过(self):
        self.fixture({
            "README.md": "| 阶段 | 文章 |\n|---|---|\n| 认知 | [认识小程序](docs/01-入门/01-test.md) |\n",
            "PROGRESS.md": "- [ ] [认识小程序](docs/01-入门/01-test.md)\n",
            "docs/01-入门/01-test.md": "---\ntitle: t\ndescription: d\ncategory: 入门\ntags: []\ndifficulty: ★☆☆☆☆\nreading_time: 1 min\nupdated: 2026-01-01\n---\n",
        })
        chk.check_progress_sync()
        self.assertEqual(chk.errors, [])

    def test_progress_sync_缺失(self):
        self.fixture({
            "README.md": "| 阶段 | 文章 |\n|---|---|\n| 认知 | [认识小程序](docs/01-入门/01-test.md) |\n",
            "PROGRESS.md": "# 进度\n",
            "docs/01-入门/01-test.md": "---\ntitle: t\ndescription: d\ncategory: 入门\ntags: []\ndifficulty: ★☆☆☆☆\nreading_time: 1 min\nupdated: 2026-01-01\n---\n",
        })
        chk.check_progress_sync()
        self.assertTrue(any("缺少" in e for e in chk.errors))

    def test_progress_sync_不存在(self):
        self.fixture({
            "README.md": "| 阶段 | 文章 |\n|---|---|\n",
        })
        chk.check_progress_sync()
        self.assertTrue(any("PROGRESS.md 不存在" in e for e in chk.errors))

    # ---------- FAQ 格式校验 ----------

    def test_faq_format_通过(self):
        self.fixture({
            "docs/00-学习路线/03-FAQ.md": (
                "---\ntitle: FAQ\ndescription: d\ncategory: 学习路线\ntags: []\ndifficulty: ★☆☆☆☆\nreading_time: 10 min\nupdated: 2026-01-01\n---\n"
                "# FAQ\n**Q1**: 问题？\n<details><summary>回答</summary>\n答案\n</details>\n"
            ),
        })
        chk.check_faq_format()
        self.assertEqual(chk.errors, [])

    def test_faq_format_不存在不报错(self):
        self.fixture({})
        chk.check_faq_format()
        self.assertEqual(chk.errors, [])

    def test_faq_format_缺元数据(self):
        self.fixture({
            "docs/00-学习路线/03-FAQ.md": "# FAQ\n**Q1**: 问题？\n<details><summary>回答</summary>\n答案\n</details>\n",
        })
        chk.check_faq_format()
        self.assertTrue(any("frontmatter" in e for e in chk.errors))

    # ---------- 架构决策表校验 ----------

    def test_architecture_table_通过(self):
        self.fixture({
            "docs/06-实战/01-test.md": (
                "# Test\n### 架构决策复盘\n"
                "| 决策 | 选它 | 放弃什么 | 什么情况会推翻 |\n|---|---|---|---|\n"
                "| A | B | C | D |\n"
            ),
        })
        chk.check_architecture_table()
        self.assertEqual(chk.errors, [])

    def test_architecture_table_列名错误(self):
        self.fixture({
            "docs/06-实战/01-test.md": (
                "# Test\n### 架构决策复盘\n"
                "| 决策 | 好处 | 局限 | 后续演进 |\n|---|---|---|---|\n"
                "| A | B | C | D |\n"
            ),
        })
        chk.check_architecture_table()
        self.assertTrue(any("列名须为" in e for e in chk.errors))

    def test_architecture_table_缺失(self):
        self.fixture({
            "docs/06-实战/01-test.md": "# Test\n## 正文\nx\n",
        })
        chk.check_architecture_table()
        self.assertTrue(any("架构决策复盘" in e for e in chk.errors))

    # ---------- 踩坑回顾表校验 ----------

    def test_pitfall_table_通过(self):
        self.fixture({
            "docs/06-实战/01-test.md": (
                "# Test\n### 踩坑回顾\n"
                "| 症状 | 原因 | 修复 |\n|---|---|---|\n"
                "| A | B | C |\n"
            ),
        })
        chk.check_pitfall_table()
        self.assertEqual(chk.errors, [])

    def test_pitfall_table_列名错误(self):
        self.fixture({
            "docs/06-实战/01-test.md": (
                "# Test\n### 踩坑回顾\n"
                "| 问题 | 原因 | 解决 |\n|---|---|---|\n"
                "| A | B | C |\n"
            ),
        })
        chk.check_pitfall_table()
        self.assertTrue(any("列名须为" in e for e in chk.errors))

    def test_pitfall_table_缺失(self):
        self.fixture({
            "docs/06-实战/01-test.md": "# Test\n## 正文\nx\n",
        })
        chk.check_pitfall_table()
        self.assertTrue(any("踩坑回顾" in e for e in chk.errors))

    # ---------- 延伸阅读校验 ----------

    def test_extended_reading_通过(self):
        self.fixture({
            "docs/01-入门/01-test.md": (
                "---\ntitle: t\ndescription: d\ncategory: 入门\ntags: []\ndifficulty: ★☆☆☆☆\nreading_time: 1 min\nupdated: 2026-01-01\n---\n"
                "# Test\n## 延伸阅读\n- [官方](https://developers.weixin.qq.com/miniprogram/dev/framework/)\n"
            ),
        })
        chk.check_extended_reading()
        self.assertEqual(chk.errors, [])

    def test_extended_reading_缺官方链接(self):
        self.fixture({
            "docs/01-入门/01-test.md": (
                "---\ntitle: t\ndescription: d\ncategory: 入门\ntags: []\ndifficulty: ★☆☆☆☆\nreading_time: 1 min\nupdated: 2026-01-01\n---\n"
                "# Test\n## 延伸阅读\n- [上一篇](../02-基础/01-test.md)\n"
            ),
        })
        chk.check_extended_reading()
        self.assertTrue(any("官方文档链接" in e for e in chk.errors))

    def test_extended_reading_缺失(self):
        self.fixture({
            "docs/01-入门/01-test.md": (
                "---\ntitle: t\ndescription: d\ncategory: 入门\ntags: []\ndifficulty: ★☆☆☆☆\nreading_time: 1 min\nupdated: 2026-01-01\n---\n"
                "# Test\n## 正文\nx\n"
            ),
        })
        chk.check_extended_reading()
        self.assertTrue(any("延伸阅读" in e for e in chk.errors))

    def test_depth_sections_通过(self):
        self.fixture({
            "docs/02-基础/01-test.md": (
                "---\ntitle: t\ndescription: d\ncategory: 基础\ntags: []\ndifficulty: ★☆☆☆☆\nreading_time: 1 min\nupdated: 2026-01-01\n---\n"
                "# Test\n## 为什么这样设计\nsome content\n## 延伸阅读\n- [官方](https://developers.weixin.qq.com/miniprogram/dev/framework/)\n"
            ),
        })
        chk.check_depth_sections()
        self.assertEqual(chk.errors, [])

    def test_depth_sections_缺深度(self):
        self.fixture({
            "docs/02-基础/01-test.md": (
                "---\ntitle: t\ndescription: d\ncategory: 基础\ntags: []\ndifficulty: ★☆☆☆☆\nreading_time: 1 min\nupdated: 2026-01-01\n---\n"
                "# Test\n## 基本用法\nsome content\n## 延伸阅读\n- [官方](https://developers.weixin.qq.com/miniprogram/dev/framework/)\n"
            ),
        })
        chk.check_depth_sections()
        self.assertTrue(any("深度段落" in e for e in chk.errors))

    def test_depth_sections_例外目录(self):
        self.fixture({
            "docs/07-资源/01-test.md": (
                "---\ntitle: t\ndescription: d\ncategory: 资源\ntags: []\ndifficulty: ★☆☆☆☆\nreading_time: 1 min\nupdated: 2026-01-01\n---\n"
                "# Test\n## 资源列表\nsome content\n"
            ),
        })
        chk.check_depth_sections()
        self.assertEqual(chk.errors, [])


    def test_depth_sections_样板标题不算深度(self):
        """只有「为什么读这篇」样板标题的文章应报错——防止深度校验形同虚设"""
        self.fixture({
            "docs/02-基础/01-test.md": (
                "---\ntitle: t\ndescription: d\ncategory: 基础\ntags: []\ndifficulty: ★☆☆☆☆\nreading_time: 1 min\nupdated: 2026-01-01\n---\n"
                "# Test\n## 为什么读这篇\nsome content\n## 延伸阅读\n- [官方](https://developers.weixin.qq.com/miniprogram/dev/framework/)\n"
            ),
        })
        chk.check_depth_sections()
        self.assertTrue(any("深度段落" in e for e in chk.errors))

    def test_depth_sections_样板加真实深度(self):
        """有「为什么读这篇」但也有真正深度标题的文章应通过"""
        self.fixture({
            "docs/02-基础/01-test.md": (
                "---\ntitle: t\ndescription: d\ncategory: 基础\ntags: []\ndifficulty: ★☆☆☆☆\nreading_time: 1 min\nupdated: 2026-01-01\n---\n"
                "# Test\n## 为什么读这篇\nsome content\n## 冷启动机制\ndetail\n## 延伸阅读\n- [官方](https://developers.weixin.qq.com/miniprogram/dev/framework/)\n"
            ),
        })
        chk.check_depth_sections()
        self.assertEqual(chk.errors, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)

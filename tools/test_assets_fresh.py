# -*- coding: utf-8 -*-
"""check_assets_fresh.py 的自测（零依赖，标准库 unittest）。

这个脚本最容易写错的地方是**比对基准**：
- 正确：以 HEAD 为基准——重跑后 `git status` 必须干净
- 错误：以「重跑前的工作区」为基准——那么「本地跑过脚本但忘了提交」时
  两次快照相同，脚本会报通过，而仓库里提交的恰恰是旧资产

后者是一个**假通过**，比不检查更糟：它会给漂移盖上合格章。所以下面的用例
两个方向都断言——该报的必须报，不该报的必须不报。

脚本是 git 驱动的，因此每个用例在临时目录里 `git init` 一个迷你仓库，
把 check_assets_fresh.py 与四个桩生成脚本放进去再跑。

用法：python tools/test_assets_fresh.py
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TOOLS = pathlib.Path(__file__).resolve().parent

# 桩生成脚本：把固定内容写进 docs/assets/，替代真实的 PIL 渲染
STUB = """\
import pathlib
d = pathlib.Path(__file__).resolve().parent.parent / "docs" / "assets"
d.mkdir(parents=True, exist_ok=True)
for name, content in {files!r}.items():
    (d / name).write_text(content, encoding="utf-8")
"""
GENERATORS = ["gen_statics.py", "gen_diagrams.py", "gen_animations.py", "gen_videos.py"]


def git(repo, *args):
    return subprocess.run(["git", "-c", "core.autocrlf=false", *args],
                          cwd=repo, capture_output=True, text=True, errors="replace")


class AssetsFreshTest(unittest.TestCase):
    def build(self, committed, produced):
        """committed: {文件名: 内容} 提交进仓库；produced: {文件名: 内容} 桩脚本产出"""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = pathlib.Path(tmp.name)

        git(repo, "init", "-q")
        git(repo, "config", "user.email", "t@example.com")
        git(repo, "config", "user.name", "t")

        (repo / "tools").mkdir()
        (repo / "docs" / "assets").mkdir(parents=True)
        shutil.copy(TOOLS / "check_assets_fresh.py", repo / "tools" / "check_assets_fresh.py")
        stub = STUB.format(files=produced)
        for name in GENERATORS:
            (repo / "tools" / name).write_text(stub, encoding="utf-8")
        for fname, content in committed.items():
            (repo / "docs" / "assets" / fname).write_text(content, encoding="utf-8")

        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "init")
        return repo

    def run_check(self, repo):
        # 显式 utf-8：子进程会把自己的 stdout 切到 UTF-8，而 Windows 上父进程
        # 默认按 GBK 解码，不指定就会把输出读成乱码（断言随之失败）
        return subprocess.run(
            [sys.executable, "tools/check_assets_fresh.py"],
            cwd=repo, capture_output=True, text=True,
            encoding="utf-8", errors="replace")

    # ---------- 一致：必须通过 ----------

    def test_已提交与脚本输出一致时通过(self):
        repo = self.build({"a.txt": "SAME"}, {"a.txt": "SAME"})
        r = self.run_check(repo)
        self.assertEqual(r.returncode, 0, f"应通过，实际:\n{r.stdout}\n{r.stderr}")
        self.assertIn("一致", r.stdout)

    # ---------- 漂移：必须报出 ----------

    def test_内容漂移要报(self):
        """仓库里提交的是旧版本，脚本现在产出新内容。"""
        repo = self.build({"a.txt": "OLD"}, {"a.txt": "NEW"})
        r = self.run_check(repo)
        self.assertEqual(r.returncode, 1, f"漂移必须报出，实际:\n{r.stdout}")
        self.assertIn("a.txt", r.stdout)

    def test_新增未提交要报(self):
        repo = self.build({}, {"a.txt": "NEW"})
        r = self.run_check(repo)
        self.assertEqual(r.returncode, 1, f"脚本新产出的文件未提交，必须报出:\n{r.stdout}")

    def test_消失要报(self):
        """仓库里提交了某资产，但脚本已不再产出它。"""
        repo = self.build({"a.txt": "X"}, {"a.txt": "X"})
        # 提交一个脚本不会写的文件
        (repo / "docs" / "assets" / "gone.txt").write_text("X", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "add gone")
        r = self.run_check(repo)
        self.assertEqual(r.returncode, 1, f"脚本不再产出的资产必须报出:\n{r.stdout}")
        self.assertIn("gone.txt", r.stdout)

    # ---------- 基准正确性：这一组是核心 ----------

    def test_工作区不干净时拒绝比对(self):
        """有未提交改动时基准不成立，必须拒绝而不是给个结论。"""
        repo = self.build({"a.txt": "SAME"}, {"a.txt": "SAME"})
        (repo / "docs" / "assets" / "a.txt").write_text("DIRTY", encoding="utf-8")
        r = self.run_check(repo)
        self.assertEqual(r.returncode, 1, f"工作区脏时必须拒绝比对:\n{r.stdout}")
        self.assertIn("基准不成立", r.stdout)

    def test_本地已跑过脚本但忘了提交_不能误判通过(self):
        """这就是「以重跑前状态为基准」会踩的假通过。

        工作区里的资产已经是脚本输出（内容与重跑结果相同），但它没提交——
        仓库里 HEAD 上还是旧的。以 HEAD 为基准就必须拒绝；若拿重跑前的工作区
        当基准，两次快照相同，会报「一致」，给漂移盖上合格章。
        """
        repo = self.build({"a.txt": "OLD"}, {"a.txt": "NEW"})
        (repo / "docs" / "assets" / "a.txt").write_text("NEW", encoding="utf-8")
        r = self.run_check(repo)
        self.assertNotEqual(r.returncode, 0,
                            f"未提交的「已重跑」状态不能算通过，实际:\n{r.stdout}")
        self.assertIn("基准不成立", r.stdout)

    def test_拒绝比对时不执行生成脚本(self):
        """拒绝时不应白跑几十秒的渲染。"""
        repo = self.build({"a.txt": "SAME"}, {"a.txt": "SAME"})
        (repo / "docs" / "assets" / "a.txt").write_text("DIRTY", encoding="utf-8")
        r = self.run_check(repo)
        self.assertNotIn("重新生成", r.stdout,
                         f"基准不成立时不应开始生成，实际:\n{r.stdout}")

    def test_生成脚本失败要报(self):
        repo = self.build({"a.txt": "SAME"}, {"a.txt": "SAME"})
        (repo / "tools" / "gen_diagrams.py").write_text(
            "import sys\nsys.exit(3)\n", encoding="utf-8")
        r = self.run_check(repo)
        self.assertEqual(r.returncode, 1, f"生成脚本失败必须报出:\n{r.stdout}")
        self.assertIn("gen_diagrams.py", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)

# -*- coding: utf-8 -*-
"""定位本机 Edge，供 PDF 打印使用。

Mermaid 预渲染不再用本机 Edge：它固定在 tools/mermaid 的 Chrome for Testing
版本，见 gen_mermaid.py 与 tools/mermaid/package.json。
"""
import os
import pathlib
import shutil


def find_edge():
    candidates = [
        os.environ.get("EDGE_PATH"),
        shutil.which("msedge"),
        shutil.which("microsoft-edge"),
        shutil.which("microsoft-edge-stable"),
        "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
        "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
        "/usr/bin/microsoft-edge",
        "/usr/bin/microsoft-edge-stable",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ]
    for candidate in candidates:
        if candidate and pathlib.Path(candidate).is_file():
            return str(candidate)
    return None

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kb_brief - 为每个 project_memory.md 生成一份索引摘要。

会话只读索引（小），需要细节时再读全文或跑 kb_search（快）。

规则（2026-11-15 起）：
    - 顶部「## 0. 当前状态」块**整块置顶**、不摘要、不截断；
    - --check 多一条：状态块的版本号落后于全文最新 vNN 时判过期。

用法:
    py -3.13 Tools/kb/kb_brief.py
    py -3.13 Tools/kb/kb_brief.py --root D:/data
    py -3.13 Tools/kb/kb_brief.py --check    # 摘要旧或状态块版本落后时返回 1
"""

import argparse
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

NL = chr(10)
SKIP = ("node_modules", ".git", "build", "__pycache__", ".venv", "dist", "MDK-ARM", "Objects")
NAME = "project_memory.md"
OUT = "project_memory.index.md"
DEFAULT_ROOTS = [
    "D:/data",
    "D:/My_project",
    str(Path.home() / "Documents" / "deepseek-harness" / "default-workspace"),
]


def read(p):
    raw = p.read_bytes()
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_sections(text):
    title = ""
    sections = []
    cur = None
    for line in text.splitlines():
        if line.startswith("# ") and not title:
            title = line[2:].strip()
        elif line.startswith("## "):
            cur = {"name": line[3:].strip(), "items": []}
            sections.append(cur)
        elif cur is not None and line.strip():
            s = line.strip()
            if set(s) <= set("|-: "):
                if cur["items"] and cur["items"][-1].startswith("|"):
                    cur["items"].pop()
                continue
            cur["items"].append(s)
    return title, sections


def is_state(name):
    n = name.replace(" ", "")
    return n.startswith("0.") or n.startswith("当前状态")


def skim(items, limit=2, width=90):
    out = []
    for s in items:
        t = s.lstrip("|").strip()
        while t.startswith("- "):
            t = t[2:].strip()
        t = " ".join(t.replace("**", "").split())
        if t.startswith("#"):
            continue
        out.append(t[:width])
        if len(out) >= limit:
            break
    return out


def version_of(text):
    # 只认独立出现的 vNN（≥2 位），排除 说明_v01.md / 文件v2.py 这类文件名
    pat = r"(?<![A-Za-z0-9_])v(\d{2,4})(?![0-9])"
    return max((int(v) for v in re.findall(pat, text, re.IGNORECASE)), default=None)


def build(mem_path, text):
    title, sections = parse_sections(text)
    state = [s for s in sections if is_state(s["name"])]
    rest = [s for s in sections if not is_state(s["name"])]
    lines = ["# %s — 记忆索引" % (title or mem_path.parent.name), ""]
    lines.append("> 由 project_memory.md 自动生成，勿手改；全文 %d 行，需要细节时再读。" % len(text.splitlines()))
    lines.append("")
    for sec in state:
        lines.append("## %s（当前状态，覆盖式，优先信这一块）" % sec["name"])
        for item in skim(sec["items"], limit=999, width=400):
            lines.append("- %s" % item)
        lines.append("")
    for sec in rest:
        n = len(sec["items"])
        if n == 0:
            continue
        lines.append("## %s（%d 条）" % (sec["name"], n))
        for item in skim(sec["items"]):
            lines.append("- %s" % item)
    return NL.join(lines) + NL


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    roots = [args.root] if args.root else DEFAULT_ROOTS
    mems, seen = [], set()
    for r in roots:
        base = Path(r)
        if not base.is_dir():
            print("[brief] 跳过不存在的根 %s" % base)
            continue
        for mem in base.rglob(NAME):
            if any(part in SKIP for part in mem.parts):
                continue
            key = str(mem.resolve())
            if key in seen:
                continue
            seen.add(key)
            mems.append(mem)

    made, stale, lagging = 0, [], []
    for mem in mems:
        text = read(mem)
        out = mem.with_name(OUT)
        _, sections = parse_sections(text)
        state = [s for s in sections if is_state(s["name"])]
        if args.check:
            if not out.is_file() or out.stat().st_mtime < mem.stat().st_mtime:
                stale.append(str(mem))
                continue
            if state:
                sv = version_of(NL.join(state[0]["items"]))
                rest_text = NL.join(NL.join(s["items"]) for s in sections if not is_state(s["name"]))
                lv = version_of(rest_text)
                if sv and lv and sv < lv:
                    lagging.append("%s（状态块 v%d < 最新 v%d）" % (mem, sv, lv))
            continue
        out.write_text(build(mem, text), encoding="utf-8", newline=NL)
        made += 1

    if args.check:
        if stale:
            print("[brief] %d 个项目摘要过期：" % len(stale))
            for s in stale:
                print("  - %s" % s)
        if lagging:
            print("[brief] %d 个状态块版本落后：" % len(lagging))
            for s in lagging:
                print("  - %s" % s)
        if stale or lagging:
            return 1
        print("[brief] 全部最新")
        return 0

    print("[brief] 生成 %d 份索引摘要" % made)
    return 0


if __name__ == "__main__":
    sys.exit(main())

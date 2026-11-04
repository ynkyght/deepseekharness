#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kb_brief - 为每个 project_memory.md 生成一份 20 行左右的索引摘要。

会话只读索引（小），需要细节时再读全文或跑 kb_search（快）。

用法:
    py -3.13 Tools/kb/kb_brief.py --root D:/data
    py -3.13 Tools/kb/kb_brief.py --check    # 有项目摘要比全文旧时返回 1
"""

import argparse
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


def build(mem_path, text):
    title, sections = parse_sections(text)
    lines = ["# %s — 记忆索引" % (title or mem_path.parent.name), ""]
    lines.append("> 由 project_memory.md 自动生成，勿手改；全文 %d 行，需要细节时再读。" % len(text.splitlines()))
    lines.append("")
    for sec in sections:
        n = len(sec["items"])
        if n == 0:
            continue
        lines.append("## %s（%d 条）" % (sec["name"], n))
        for item in skim(sec["items"]):
            lines.append("- %s" % item)
    return NL.join(lines) + NL


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="D:/data")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    base = Path(args.root)
    if not base.is_dir():
        print("[brief] 找不到 %s" % base)
        return 2

    made, stale = 0, []
    for mem in base.rglob(NAME):
        if any(part in SKIP for part in mem.parts):
            continue
        text = read(mem)
        out = mem.with_name(OUT)
        if args.check:
            if not out.is_file() or out.stat().st_mtime < mem.stat().st_mtime:
                stale.append(str(mem))
            continue
        out.write_text(build(mem, text), encoding="utf-8", newline=NL)
        made += 1

    if args.check:
        if stale:
            print("[brief] %d 个项目摘要过期：" % len(stale))
            for s in stale:
                print("  - %s" % s)
            return 1
        print("[brief] 全部最新")
        return 0

    print("[brief] 生成 %d 份索引摘要" % made)
    return 0


if __name__ == "__main__":
    sys.exit(main())

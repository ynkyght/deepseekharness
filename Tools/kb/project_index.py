#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""project_index - 扫描各项目的 project_memory.md，生成跨项目索引。

用法:
    py -3.13 Tools/kb/project_index.py
    py -3.13 Tools/kb/project_index.py --root D:/data --out Docs/跨项目索引.md
    py -3.13 Tools/kb/project_index.py --check     # 输出比输入旧时返回 1
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

NL = chr(10)
KB = Path(__file__).resolve().parents[2]
CHIP_RE = re.compile("STM32[A-Za-z0-9]+|GD32[A-Za-z0-9]+|ESP32-[A-Za-z0-9]+|STC8[A-Za-z0-9]+|nRF[0-9A-Za-z]+")
SKIP_DIRS = ("node_modules", ".git", "build", "__pycache__", ".venv", "dist")


def read(p):
    return p.read_text(encoding="utf-8", errors="replace")


def clean(line):
    line = line.strip()
    if line.startswith("|"):
        line = line.strip("|").strip()
    line = line.replace("**", "")
    return " ".join(line.split())


def pick(lines, limit=6, width=110):
    out = []
    for line in lines:
        if not line.strip():
            continue
        if set(line.strip()) <= set("|-: "):
            continue
        t = clean(line)
        if not t or t.startswith("#"):
            continue
        if t.startswith("功能") and "引脚" in t:
            continue
        out.append(t[:width])
        if len(out) >= limit:
            break
    return out


def parse(mem_path):
    text = read(mem_path)
    title = ""
    sections = {}
    cur = None
    for line in text.splitlines():
        if line.startswith("# ") and not title:
            title = line[2:].strip()
        elif line.startswith("## "):
            cur = line[3:].strip()
            sections[cur] = []
        elif cur is not None:
            sections[cur].append(line)

    def sec(*keys):
        for name, lines in sections.items():
            if any(k in name for k in keys):
                return lines
        return []

    m = CHIP_RE.search(text)
    return {
        "name": mem_path.parent.name,
        "title": title or mem_path.parent.name,
        "dir": str(mem_path.parent),
        "chip": m.group(0) if m else "",
        "pins": pick(sec("引脚", "总线")),
        "pits": pick(sec("坑")),
        "iface": pick(sec("接口", "约定")),
        "mtime": mem_path.stat().st_mtime,
    }


def collect(root, max_depth=8):
    found = []
    base = Path(root)
    for p in base.rglob("project_memory.md"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if len(p.relative_to(base).parts) > max_depth:
            continue
        if p.parent.resolve() == KB.resolve():
            continue
        try:
            found.append(parse(p))
        except Exception as exc:
            print("[idx] 跳过 %s: %s" % (p, exc))
    return sorted(found, key=lambda d: d["name"])


def build(items):
    out = ["# 跨项目索引", "",
           "> 由 Tools/kb/project_index.py 自动汇总各项目的 project_memory.md，请勿手改。",
           "> 生成时间：%s　项目数：%d" % (datetime.now().strftime("%Y-%m-%d %H:%M"), len(items)), "",
           "| 项目 | 芯片 | 引脚 | 坑 | 接口 | 更新 |", "|---|---|---|---|---|---|"]
    for d in items:
        out.append("| %s | %s | %d | %d | %d | %s |" % (
            d["name"], d["chip"] or "—", len(d["pins"]), len(d["pits"]), len(d["iface"]),
            datetime.fromtimestamp(d["mtime"]).strftime("%Y-%m-%d")))
    out.append("")
    for d in items:
        out.append("## %s" % d["name"])
        out.append("")
        if d["title"] and d["title"] != d["name"]:
            out.append("- 标题：%s" % d["title"])
        out.append("- 路径：%s" % d["dir"])
        if d["chip"]:
            out.append("- 芯片：%s" % d["chip"])
        for label, key in (("引脚/总线", "pins"), ("踩过的坑", "pits"), ("接口约定", "iface")):
            if d[key]:
                out.append("- %s：" % label)
                for line in d[key]:
                    out.append("  - %s" % line)
        out.append("")
    return NL.join(out) + NL


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="D:/data")
    ap.add_argument("--out", default="Docs/跨项目索引.md")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    items = collect(args.root)
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = KB / out_path

    if args.json:
        print(json.dumps({"projects": items}, ensure_ascii=False, indent=2))
        return 0

    if args.check:
        if not out_path.is_file():
            print("[idx] 缺少 %s" % out_path)
            return 1
        newest = max((d["mtime"] for d in items), default=0)
        if out_path.stat().st_mtime < newest:
            print("[idx] 索引比源文件旧，请重新生成")
            return 1
        print("[idx] 索引是最新的（%d 个项目）" % len(items))
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build(items), encoding="utf-8")
    print("[idx] 已汇总 %d 个项目 → %s" % (len(items), out_path))
    for d in items:
        print("  - %-28s %-12s 引脚%d 坑%d" % (d["name"][:28], d["chip"] or "—", len(d["pins"]), len(d["pits"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())

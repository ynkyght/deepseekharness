#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kb_sync - 扫描 Docs/*.md，生成 Docs/INDEX.md，并检查知识库缺口。

用法:
    py -3.13 Tools/kb/kb_sync.py           # 生成索引 + 打印报告
    py -3.13 Tools/kb/kb_sync.py --check   # 只检查，有缺口返回 1
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
ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "Docs"
MEM = ROOT / "project_memory.md"
INDEX = DOCS / "INDEX.md"

DATE_RE = re.compile("(20[0-9]{2})[-_年]?([0-9]{1,2})[-_月]?([0-9]{1,2})")
SRC_RE = re.compile("来源|依据|参考")


def read_text(p):
    return p.read_text(encoding="utf-8", errors="replace")


def find_date(name, text):
    for src in (name, NL.join(text.splitlines()[:20])):
        m = DATE_RE.search(src)
        if m:
            y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
            if 1 <= mo <= 12 and 1 <= d <= 31:
                return "%s-%02d-%02d" % (y, mo, d)
    return ""


def parse_doc(path):
    text = read_text(path)
    lines = text.splitlines()
    title, headings = "", []
    for line in lines:
        if not title and line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("## "):
            headings.append(line[3:].strip())
    return {
        "file": path.name,
        "title": title or path.stem,
        "date": find_date(path.name, text),
        "headings": headings[:3],
        "chars": len(text),
        "has_src": bool(SRC_RE.search(text)),
        "mtime": path.stat().st_mtime,
    }


def build_index(docs):
    docs = sorted(docs, key=lambda d: (d["date"] or "0000-00-00", d["file"]), reverse=True)
    out = ["# Docs 索引", "",
           "> 本文件由 Tools/kb/kb_sync.py 生成，请勿手改。",
           "> 生成时间：%s　文档数：%d" % (datetime.now().strftime("%Y-%m-%d %H:%M"), len(docs)), "",
           "| 日期 | 整理稿 | 主题 | 字数 |", "|---|---|---|---|"]
    for d in docs:
        topic = "；".join(d["headings"]) if d["headings"] else d["title"]
        topic = topic.replace("|", "/")[:60]
        out.append("| %s | [%s](%s) | %s | %d |" % (d["date"] or "—", d["file"], d["file"], topic, d["chars"]))
    out.append("")
    return NL.join(out) + NL


def gap_report(docs):
    mem = read_text(MEM) if MEM.is_file() else ""
    gaps = []
    for d in docs:
        if d["file"] not in mem:
            gaps.append(("未进 project_memory", d["file"]))
        if not d["date"]:
            gaps.append(("缺日期", d["file"]))
        if d["title"] == Path(d["file"]).stem:
            gaps.append(("缺一级标题", d["file"]))
        if not d["has_src"]:
            gaps.append(("缺来源标注", d["file"]))
    if mem:
        for ref in sorted(set(re.findall("Docs/([^ ()]+[.]md)", mem))):
            if not (DOCS / ref).is_file():
                gaps.append(("project_memory 引用了不存在的整理稿", ref))
        if docs and MEM.stat().st_mtime < max(d["mtime"] for d in docs):
            gaps.append(("project_memory 比最新整理稿旧", "需要补结论"))
    else:
        gaps.append(("缺少 project_memory.md", "先建骨架"))
    return gaps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if not DOCS.is_dir():
        DOCS.mkdir(parents=True, exist_ok=True)
    docs = [parse_doc(p) for p in sorted(DOCS.glob("*.md")) if p.name != "INDEX.md"]
    gaps = gap_report(docs)
    if not args.check:
        INDEX.write_text(build_index(docs), encoding="utf-8")
    if args.json:
        print(json.dumps({"docs": docs, "gaps": gaps}, ensure_ascii=False, indent=2))
        return 1 if (gaps and args.check) else 0
    print("[kb] 整理稿 %d 篇｜缺口 %d 条" % (len(docs), len(gaps)))
    for kind, name in gaps:
        print("  - %-30s %s" % (kind, name))
    if not args.check:
        print("[kb] 已写入 %s" % INDEX.relative_to(ROOT))
    return 1 if (gaps and args.check) else 0


if __name__ == "__main__":
    sys.exit(main())

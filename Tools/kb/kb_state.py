#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kb_state - 给每个 project_memory.md 补齐「## 0. 当前状态」块并校验版本。

为什么需要：project_memory.md 只追加，完成的事不会从旧条目里消失；检索与摘要
都会先撞到旧的详细条目。状态块是**覆盖式**的唯一入口，优先级高于其余内容。

用法:
    py -3.13 Tools/kb/kb_state.py            # 给缺状态块的项目生成骨架（不动已有块）
    py -3.13 Tools/kb/kb_state.py --check    # 缺块 / 版本落后 → 返回 1
    py -3.13 Tools/kb/kb_state.py --root D:/data
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

NL = chr(10)
SKIP = ("node_modules", ".git", "build", "__pycache__", ".venv", "dist", "MDK-ARM", "Objects")
NAME = "project_memory.md"
HEAD = "## 0. 当前状态"
VER_RE = re.compile(r"(?<![A-Za-z0-9_])v(\d{2,4})(?![0-9])", re.IGNORECASE)
DATE_RE = re.compile(r"20\d{2}-\d{1,2}-\d{1,2}")
OPEN_RE = re.compile(r"未解|遗留|待决|待定|待验证|未决|TODO|待批准|待确认")
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


def max_ver(text):
    return max((int(v) for v in VER_RE.findall(text)), default=None)


def find_state(lines):
    for i, ln in enumerate(lines):
        if ln.startswith("## "):
            name = ln[3:].strip()
            if name.replace(" ", "").startswith("0.") or name.startswith("当前状态"):
                return i
    return None


def latest_section(lines):
    """返回 (标题, 起始行号, 该节正文行列表)，取最后一个 ## 2026 日期节。"""
    idx = None
    for i, ln in enumerate(lines):
        if ln.startswith("## ") and re.search(r"20\d{2}-\d{1,2}-\d{1,2}", ln):
            idx = i
    if idx is None:
        for i, ln in enumerate(lines):
            if ln.startswith("## "):
                idx = i
    if idx is None:
        return None, 0, []
    body = []
    for ln in lines[idx + 1:]:
        if ln.startswith("## "):
            break
        body.append(ln)
    return lines[idx][3:].strip(), idx + 1, body


def newest_bullet(lines):
    """正文里最新一条带日期的条目，作为「一句话」的草稿。"""
    for ln in reversed(lines):
        s = ln.strip()
        if s.startswith("- ") and DATE_RE.search(s[:40]):
            return " ".join(s[2:].replace("**", "").split())[:110]
    return ""


STATE_FIELD_RE = re.compile(r"^- \*\*(版本|一句话|未决|已结案|更新)\*\*")


def open_items(lines, limit=3):
    out = []
    for ln in reversed(lines):
        s = ln.strip()
        if not s.startswith("- "):
            continue
        if STATE_FIELD_RE.match(s) or "kb_state.py 自动生成" in s:
            continue
        if OPEN_RE.search(s):
            out.append(" ".join(s[2:].replace("**", "").split())[:100])
        if len(out) >= limit:
            break
    return out


def skeleton(lines, rel_name):
    title, start, body = latest_section(lines)
    text = NL.join(lines)
    ver = max_ver(text)
    ver_txt = "v%d" % ver if ver else "（正文无 vN 版本号）"
    when = ""
    m = DATE_RE.search(title or "")
    if m:
        when = m.group(0)
    one = newest_bullet(lines)
    last_rec = DATE_RE.search(one) if one else None
    opens = open_items(lines)
    closed_n = len(re.findall(r"归零|清零|已解决|已关闭", text))
    stamp = when or (last_rec.group(0) if last_rec else "")
    out = [
        HEAD,
        "",
        "- **版本**：%s%s" % (ver_txt, ("（%s）" % stamp if stamp else "")),
        "- **一句话**：%s" % (one or "（请补一句当前结论）"),
        "- **未决**：%s" % ("；".join(opens) if opens else "（正文未标「未解/遗留」，请人工确认）"),
        "- **已结案（旧清单勿再引用）**：正文含「归零/清零/已解决」记录 %d 条；旧清单请以最新日期节为准" % closed_n,
        "- **更新**：%s｜本块**只覆盖不追加**，由 kb_state.py 自动生成骨架" % date.today().isoformat(),
        "",
    ]
    return out


def _skeleton_old(lines, rel_name):
    title, start, body = latest_section(lines)
    text = NL.join(lines)
    ver = max_ver(text)
    ver_txt = "v%d" % ver if ver else "（正文无版本号，请补）"
    when = ""
    if title:
        m = DATE_RE.search(title)
        when = m.group(0) if m else ""
    closed = "（请补：哪些旧清单/旧结论已被哪个版本解决，写明「旧清单勿再引用」）"
    open_items = []
    for ln in body:
        s = ln.strip()
        if not s.startswith("- "):
            continue
        if OPEN_RE.search(s):
            open_items.append(" ".join(s.replace("**", "").split())[:120])
        if len(open_items) >= 3:
            break
    open_txt = ("；".join(open_items) if open_items
                else "（正文最新节未标「未解/遗留」，请人工确认）")
    out = [
        HEAD,
        "",
        "- **版本**：%s%s｜最新一节：%s" % (ver_txt, (" (%s)" % when if when else ""), title or "(无)"),
        "- **一句话**：（自动生成的骨架，请用一句话改写成当前结论）",
        "- **未决**：%s" % open_txt,
        "- **已结案（旧清单勿再引用）**：%s" % closed,
        "- **更新**：%s｜本块**只覆盖不追加**，由 kb_state.py 自动生成骨架" % date.today().isoformat(),
        "",
    ]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--force", action="store_true", help="重写由 kb_state 自动生成的骨架块")
    args = ap.parse_args()

    roots = [args.root] if args.root else DEFAULT_ROOTS
    mems, seen = [], set()
    for r in roots:
        base = Path(r)
        if not base.is_dir():
            continue
        for mem in base.rglob(NAME):
            if any(part in SKIP for part in mem.parts):
                continue
            key = str(mem.resolve())
            if key in seen:
                continue
            seen.add(key)
            mems.append(mem)

    missing, lagging, created = [], [], []
    for mem in mems:
        lines = read(mem).splitlines()
        si = find_state(lines)
        ver_all = max_ver(NL.join(lines))
        if si is None:
            missing.append(str(mem))
            if not args.check:
                block = skeleton(lines, mem.parent.name)
                insert_at = next((j for j, l in enumerate(lines) if l.startswith("## ")), len(lines))
                new = lines[:insert_at] + block + lines[insert_at:]
                mem.write_text(NL.join(new) + NL, encoding="utf-8", newline=NL)
                created.append(str(mem))
            continue
        end = next((j for j in range(si + 1, len(lines)) if lines[si + 1:][j - si - 1].startswith("## ")), len(lines))
        block_text = NL.join(lines[si:end])
        if args.force and not args.check and "由 kb_state.py 自动生成骨架" in block_text:
            new = lines[:si] + skeleton(lines, mem.parent.name) + lines[end:]
            mem.write_text(NL.join(new) + NL, encoding="utf-8", newline=NL)
            created.append(str(mem))
            continue
        ver_state = max_ver(NL.join(lines[si:si + 12]))
        if ver_state and ver_all and ver_state < ver_all:
            lagging.append("%s（状态块 v%d < 最新 v%d）" % (mem, ver_state, ver_all))

    if args.check:
        if missing:
            print("[state] %d 个项目缺状态块：" % len(missing))
            for s in missing:
                print("  - %s" % s)
        if lagging:
            print("[state] %d 个状态块版本落后：" % len(lagging))
            for s in lagging:
                print("  - %s" % s)
        if missing or lagging:
            return 1
        print("[state] %d 个项目状态块齐全且最新" % len(mems))
        return 0

    if created:
        print("[state] 生成 %d 个状态块：" % len(created))
        for s in created:
            print("  - %s" % s)
    if lagging:
        print("[state] %d 个状态块版本落后（请整块重写）：" % len(lagging))
        for s in lagging:
            print("  - %s" % s)
    if not created and not lagging:
        print("[state] 无需改动（%d 个项目）" % len(mems))
    return 0


if __name__ == "__main__":
    sys.exit(main())

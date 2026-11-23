#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kb_search - SQLite FTS5 全文检索：只做索引层，源文件仍是 Markdown。

用法:
    py -3.13 Tools/kb/kb_search.py --rebuild      # 重建索引（默认扫 DEFAULT_ROOTS）
    py -3.13 Tools/kb/kb_search.py DM9000 地址     # 搜索（多个词按 AND）
    py -3.13 Tools/kb/kb_search.py --stats        # 看索引规模
"""

import argparse
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

KB = Path(__file__).resolve().parents[2]
DB = KB / "Tools" / "kb" / "kb.db"
SKIP_DIRS = ("node_modules", ".git", "build", "__pycache__", ".venv", "dist", "MDK-ARM", "Objects")
# 默认索引根：知识库自身 + 机械项目 + DSH 会话工作目录（各项目 Docs/ 与 project_memory.md）
DEFAULT_ROOTS = [
    "D:/data",
    "D:/My_project",
    str(Path.home() / "Documents" / "deepseek-harness" / "default-workspace"),
]


def is_cjk(ch):
    return "\u4e00" <= ch <= "\u9fff"


def seg(text):
    """CJK 拆成单字、ASCII 保持整词，供 FTS5 unicode61 使用。"""
    out, run = [], []
    for ch in text:
        if is_cjk(ch):
            if run:
                out.append("".join(run)); run = []
            out.append(ch)
        elif ch.isalnum() or ch in "_-":
            run.append(ch)
        else:
            if run:
                out.append("".join(run)); run = []
    if run:
        out.append("".join(run))
    return " ".join(out)


def state_block(path):
    """取 project_memory.md 顶部「## 0. 当前状态」块；没有则返回空串。"""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    lines = text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith("## "):
            name = ln[3:].strip()
            if name.replace(" ", "").startswith("0.") or name.startswith("当前状态"):
                start = i
                break
    if start is None:
        return ""
    out = [lines[start]]
    for ln in lines[start + 1:]:
        if ln.startswith("## "):
            break
        out.append(ln)
    return NL.join(out).strip()


def read(p):
    raw = p.read_bytes()
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def tidy(s):
    out = []
    for i, ch in enumerate(s):
        if ch == " " and 0 < i < len(s) - 1 and is_cjk(s[i - 1]) and is_cjk(s[i + 1]):
            continue
        out.append(ch)
    return re.sub(r"\s+", " ", "".join(out))


def collect(roots):
    items, seen = [], set()
    for root in roots:
        base = Path(root)
        if not base.is_dir():
            continue
        for p in base.rglob("*.md"):
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            name = p.name.lower()
            in_docs = p.parent.name.lower() == "docs"
            is_mem = p.name == "project_memory.md"
            if not (in_docs or is_mem):
                continue
            key = str(p.resolve())
            if key in seen:
                continue
            seen.add(key)
            text = read(p)
            title = ""
            for line in text.splitlines():
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
            items.append({
                "path": key,
                "project": p.parent.name if in_docs else p.parent.name,
                "title": title or p.stem,
                "kind": "memory" if is_mem else "doc",
                "mtime": p.stat().st_mtime,
                "text": text,
            })
    return items


def open_db(readonly=False):
    """检索只读打开：DSH 沙箱只放行 workspace，写 D 盘会被拒，
    而 WAL 模式需要目录写权限，所以检索一律用只读 URI。"""
    db_uri = DB.as_posix()
    if readonly:
        for suffix in ("?mode=ro&immutable=1", "?mode=ro"):
            try:
                con = sqlite3.connect("file:" + db_uri + suffix, uri=True)
                con.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()
                return con
            except sqlite3.Error:
                pass
        return sqlite3.connect(str(DB))
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB))
    try:
        con.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        pass
    return con


def rebuild(roots):
    items = collect(roots)
    con = open_db()
    con.executescript("""
        DROP TABLE IF EXISTS docs;
        DROP TABLE IF EXISTS docs_fts;
        CREATE TABLE docs (
            id INTEGER PRIMARY KEY,
            path TEXT UNIQUE, project TEXT, title TEXT, kind TEXT,
            mtime REAL, seg TEXT
        );
        CREATE VIRTUAL TABLE docs_fts USING fts5(seg, content='docs', content_rowid='id');
    """)
    con.executemany(
        "INSERT INTO docs(path, project, title, kind, mtime, seg) VALUES(?,?,?,?,?,?)",
        [(d["path"], d["project"], d["title"], d["kind"], d["mtime"], seg(d["text"])) for d in items])
    con.execute("INSERT INTO docs_fts(rowid, seg) SELECT id, seg FROM docs")
    con.commit()
    print("[search] 索引 %d 个文件 → %s" % (len(items), DB))
    return 0


def search(terms, limit=12):
    con = open_db(readonly=True)
    phrase = '"' + " ".join(seg(t).replace("-", " ") for t in terms) + '"'
    sql = """SELECT d.path, d.project, d.title, d.kind,
                    snippet(docs_fts, 0, '[', ']', ' … ', 14) AS snip
             FROM docs_fts f JOIN docs d ON d.id = f.rowid
             WHERE docs_fts MATCH ? ORDER BY rank LIMIT ?"""
    rows = con.execute(sql, (phrase, limit)).fetchall()
    if not rows:
        loose = " AND ".join(seg(t).replace("-", " ") for t in terms)
        rows = con.execute(sql, (loose, limit)).fetchall()
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("terms", nargs="*")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--root", action="append", default=None)
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--status", action="store_true", help="只输出各项目的当前状态块")
    args = ap.parse_args()

    roots = args.root or DEFAULT_ROOTS
    if args.rebuild:
        try:
            return rebuild(roots)
        except (sqlite3.OperationalError, PermissionError, OSError) as e:
            print("[search] 重建索引需要写 %s，当前进程被沙箱限制：%s" % (DB, e))
            print("[search] 请到普通 PowerShell（沙箱外）运行：py -3.13 Tools/kb/kb_search.py --rebuild")
            return 3
    if not DB.is_file():
        print("[search] 还没有索引，先跑 --rebuild")
        return 2
    if args.status:
        seen, printed = set(), 0
        for r in (args.root or DEFAULT_ROOTS):
            base = Path(r)
            if not base.is_dir():
                continue
            for mem in base.rglob("project_memory.md"):
                if any(part in SKIP_DIRS for part in mem.parts):
                    continue
                key = str(mem.resolve())
                if key in seen:
                    continue
                seen.add(key)
                blk = state_block(mem)
                if not blk:
                    continue
                print(NL + blk)
                printed += 1
        print(NL + "[search] 输出 %d 个项目的当前状态" % printed)
        return 0
    if args.stats or not args.terms:
        con = open_db(readonly=True)
        n, t = con.execute("SELECT COUNT(*), SUM(LENGTH(seg)) FROM docs").fetchone()
        print("[search] 文件 %d 个，索引文本 %d 字符，库 %s" % (n, t or 0, DB))
        return 0

    rows = search(args.terms, args.limit)
    print("[search] %s → %d 条" % (" ".join(args.terms), len(rows)))
    shown = set()
    for path, project, title, kind, snip in rows:
        mem = str(Path(path).with_name("project_memory.md"))
        if mem not in shown:
            shown.add(mem)
            blk = state_block(mem)
            if blk:
                print(NL + "【当前状态 · %s】" % project)
                print(blk)
    for path, project, title, kind, snip in rows:
        print(NL + "- [%s] %s  (%s)" % (kind, title, project))
        print("  %s" % path)
        print("  %s" % tidy(snip)[:260])
    return 0


NL = chr(10)
if __name__ == "__main__":
    sys.exit(main())

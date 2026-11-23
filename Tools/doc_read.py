#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""doc_read.py - 一次性写好、长期复用的文档读取器（不要再为每份文档新建 py）。

用法:
  py -3.13 D:/data/知识库/Tools/doc_read.py <文件> [选项]

通用选项:
  --meta            只打印元信息（类型/大小/页数/行数/sheet 名），不打印正文
  --lines A:B       只输出抽取结果的行范围（1 基，可写 100: 、 :120）
  --grep PAT        只输出包含 PAT 的行（不区分大小写），默认带 2 行上下文
  -C N              --grep 的上下文行数（默认 2，0 = 只要匹配行）
  --max N           最多输出 N 行（默认 0 = 不限）
  --out FILE        把结果写到文件（大文档/要留证据时用）
  --enc ENC         文本文件强制编码（默认自动: utf-8 -> gb18030 -> 猜测）

按类型:
  --pages A:B       PDF 页范围（1 基，默认全部）
  --png A:B         把 PDF 页渲染成 PNG（配合 read_image 看扫描件），默认输出到同目录
  --png-out DIR     PNG 输出目录
  --sheets          只列 xlsx 的 sheet 名 + 行列数

支持: pdf / docx / pptx / xlsx / csv / tsv / html / txt / md / json / 各类源码。
旧版 .doc .xls .ppt 不支持，请另存为 docx/xlsx/pptx（或先导出 PDF）。
"""
import sys, os, re, io, csv, html, zipfile, argparse

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


# ---------- 通用 ----------
def decode_bytes(b: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    try:
        from charset_normalizer import from_bytes
        best = from_bytes(b).best()
        if best is not None:
            return str(best)
    except Exception:
        pass
    return b.decode("utf-8", errors="replace")


def strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    return s.replace("\xa0", " ")


def tidy(line: str) -> str:
    return re.sub(r"[ \t]+", lambda m: " " if len(m.group(0)) == 1 else "  ", line).rstrip()


# ---------- PDF ----------
def _pymupdf():
    """优先 pymupdf（新名字），回落 fitz（老安装）。"""
    try:
        import pymupdf
        return pymupdf
    except ImportError:
        import fitz
        return fitz


def extract_pdf(path, pages=None):
    fitz = _pymupdf()
    doc = fitz.open(path)
    n = doc.page_count
    a, b = pages if pages else (1, n)
    a = max(1, min(a, n)); b = max(a, min(b, n))
    parts, empty = [], []
    for i in range(a - 1, b):
        t = doc[i].get_text("text")
        if not t.strip():
            empty.append(i + 1)
        parts.append("--- page %d/%d ---\n%s" % (i + 1, n, t.rstrip()))
    doc.close()
    txt = "\n\n".join(parts)
    if empty:
        txt += "\n\n[提示] 第 %s 页无文本层（多半是扫描页/纯图片），用 --png A:B 渲染后看图。" % ",".join(map(str, empty[:20]))
    meta = {"type": "pdf", "pages": n, "empty_pages": empty}
    return txt, meta


def render_pdf_png(path, pages, outdir):
    fitz = _pymupdf()
    doc = fitz.open(path)
    n = doc.page_count
    a, b = pages
    a = max(1, min(a, n)); b = max(a, min(b, n))
    outdir = outdir or os.path.dirname(os.path.abspath(path))
    made = []
    for i in range(a - 1, b):
        pix = doc[i].get_pixmap(dpi=150)
        p = os.path.join(outdir, "%s_p%d.png" % (os.path.splitext(os.path.basename(path))[0], i + 1))
        pix.save(p)
        made.append(p)
    doc.close()
    return made


# ---------- DOCX ----------
_W_TBL = re.compile(r"<w:tbl>.*?</w:tbl>", re.S)


def _docx_table(block):
    rows = []
    for tr in re.findall(r"<w:tr[ >].*?</w:tr>", block, re.S):
        cells = []
        for tc in re.findall(r"<w:tc>.*?</w:tc>", tr, re.S):
            s = tc.replace("</w:p>", " ")
            s = re.sub(r"<w:tab[^>]*/>", "\t", s)
            s = tidy(strip_tags(s)).strip()
            cells.append(s)
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def extract_docx(path):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    tables = []

    def repl(m):
        tables.append(_docx_table(m.group(0)))
        return "\n@@TBL%d@@\n" % (len(tables) - 1)

    xml = _W_TBL.sub(repl, xml)
    xml = re.sub(r"<w:tab[^>]*/>", "\t", xml)
    xml = re.sub(r"<w:br[^>]*/>", "\n", xml)
    xml = re.sub(r"</w:p>", "\n", xml)
    txt = strip_tags(xml)
    for i, t in enumerate(tables):
        txt = txt.replace("@@TBL%d@@" % i, t)
    lines = [tidy(l) for l in txt.split("\n")]
    # 压掉多余空行（连续 2 个以上留 1 个）
    out, blank = [], 0
    for l in lines:
        if not l.strip():
            blank += 1
            if blank > 1:
                continue
        else:
            blank = 0
        out.append(l)
    meta = {"type": "docx", "tables": len(tables), "images": sum(1 for n in names if n.startswith("word/media/"))}
    return "\n".join(out), meta


# ---------- PPTX ----------
def extract_pptx(path):
    with zipfile.ZipFile(path) as z:
        slides = [n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)]
        slides.sort(key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))
        parts = []
        for i, n in enumerate(slides, 1):
            xml = z.read(n).decode("utf-8", "replace")
            xml = re.sub(r"</a:p>", "\n", xml)
            body = tidy(strip_tags(xml))
            parts.append("--- slide %d ---\n%s" % (i, "\n".join(x for x in body.split("\n") if x.strip())))
    return "\n\n".join(parts), {"type": "pptx", "slides": len(slides)}


# ---------- XLSX ----------
def extract_xlsx(path, sheets_only=False):
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True, data_only=True)
    meta, parts = {"type": "xlsx", "sheets": []}, []
    for ws in wb.worksheets:
        info = {"name": ws.title, "rows": ws.max_row, "cols": ws.max_column}
        meta["sheets"].append(info)
        if sheets_only:
            continue
        rows = []
        for row in ws.iter_rows(values_only=True):
            cells = ["" if c is None else str(c) for c in row]
            while cells and cells[-1] == "":
                cells.pop()
            rows.append("\t".join(cells))
        while rows and not rows[-1].strip():
            rows.pop()
        parts.append("--- sheet: %s (rows=%s cols=%s) ---\n%s" % (ws.title, ws.max_row, ws.max_column, "\n".join(rows)))
    wb.close()
    if sheets_only:
        parts = ["--- sheet: %s (rows=%s cols=%s) ---" % (s["name"], s["rows"], s["cols"]) for s in meta["sheets"]]
    return "\n\n".join(parts), meta


# ---------- 其它 ----------
def extract_html(path):
    raw = decode_bytes(open(path, "rb").read())
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)</(p|div|tr|li|h[1-6])>", "\n", raw)
    raw = re.sub(r"(?i)<br[^>]*/?>", "\n", raw)
    raw = re.sub(r"(?i)</t[dh]>", "\t| ", raw)
    return strip_tags(raw), {"type": "html"}


def extract_csv(path, delim=None):
    raw = decode_bytes(open(path, "rb").read())
    d = delim or ("\t" if path.lower().endswith((".tsv", ".tab")) else ",")
    rows = list(csv.reader(io.StringIO(raw), delimiter=d))
    return "\n".join("\t".join(r) for r in rows), {"type": "csv", "rows": len(rows)}


def extract_text(path, enc=None):
    b = open(path, "rb").read()
    return (b.decode(enc) if enc else decode_bytes(b)), {"type": "text"}


EXTRACTORS = {
    ".pdf": "pdf", ".docx": "docx", ".pptx": "pptx", ".xlsx": "xlsx", ".xlsm": "xlsx",
    ".html": "html", ".htm": "html", ".csv": "csv", ".tsv": "csv", ".tab": "csv",
}


def parse_range(s, default=None):
    if not s:
        return default
    a, _, b = s.partition(":")
    a = int(a) if a.strip() else (default[0] if default else 1)
    b = int(b) if b.strip() else (default[1] if default else 10 ** 9)
    return (a, b)


def main(argv):
    ap = argparse.ArgumentParser(add_help=True, description="通用文档读取器（pdf/docx/pptx/xlsx/csv/html/text）")
    ap.add_argument("path")
    ap.add_argument("--meta", action="store_true")
    ap.add_argument("--lines")
    ap.add_argument("--grep")
    ap.add_argument("-C", type=int, default=2)
    ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--out")
    ap.add_argument("--enc")
    ap.add_argument("--pages")
    ap.add_argument("--png")
    ap.add_argument("--png-out")
    ap.add_argument("--sheets", action="store_true")
    ap.add_argument("--delim")
    a = ap.parse_args(argv)

    path = a.path
    if not os.path.isfile(path):
        print("[错误] 文件不存在: %s" % path, file=sys.stderr)
        return 2

    ext = os.path.splitext(path)[1].lower()
    if ext in (".doc", ".xls", ".ppt"):
        print("[错误] %s 是旧版二进制 Office 格式，本脚本不支持。请另存为 %sx 或导出 PDF。" % (ext, ext), file=sys.stderr)
        return 3

    kind = EXTRACTORS.get(ext, "text")

    if a.png:
        try:
            made = render_pdf_png(path, parse_range(a.png, (1, 1)), a.png_out)
        except Exception as e:
            print("[错误] PDF 渲染失败: %s" % e, file=sys.stderr)
            return 4
        print("\n".join(made))
        return 0

    try:
        if kind == "pdf":
            text, meta = extract_pdf(path, parse_range(a.pages))
        elif kind == "docx":
            text, meta = extract_docx(path)
        elif kind == "pptx":
            text, meta = extract_pptx(path)
        elif kind == "xlsx":
            text, meta = extract_xlsx(path, a.sheets)
        elif kind == "html":
            text, meta = extract_html(path)
        elif kind == "csv":
            text, meta = extract_csv(path, a.delim)
        else:
            text, meta = extract_text(path, a.enc)
    except Exception as e:
        print("[错误] 解析失败 (%s): %s: %s" % (kind, type(e).__name__, e), file=sys.stderr)
        return 4

    meta.update({"file": os.path.abspath(path), "bytes": os.path.getsize(path)})
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    meta["lines"] = len(lines)

    if a.meta:
        import json
        print(json.dumps(meta, ensure_ascii=False, indent=2))
        return 0

    # 行号化
    numbered = ["%5d| %s" % (i, l) for i, l in enumerate(lines, 1)]

    if a.grep:
        pat = re.compile(a.grep, re.I)
        hit = [i for i, l in enumerate(lines) if pat.search(l)]
        if not hit:
            print("[无匹配] %r in %s" % (a.grep, path))
            return 1
        keep = set()
        for i in hit:
            keep.update(range(max(0, i - a.C), min(len(lines), i + a.C + 1)))
        out, prev = [], -2
        for i in sorted(keep):
            if i != prev + 1:
                out.append("      ...")
            out.append(numbered[i])
            prev = i
        numbered = out
    elif a.lines:
        s, e = parse_range(a.lines, (1, len(lines)))
        numbered = numbered[max(0, s - 1):e]

    if a.max and len(numbered) > a.max:
        numbered = numbered[:a.max] + ["      ... (已截断，共 %d 行，用 --lines/--grep 或 --max 0)" % len(lines)]

    body = "\n".join(numbered)
    head = "[%s] %s  (%d 行, %.1f KB)" % (meta.get("type"), os.path.basename(path), meta["lines"], meta["bytes"] / 1024.0)

    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(head + "\n\n" + body + "\n")
        print("[写出] %s  (%d 行)" % (os.path.abspath(a.out), len(numbered)))
        return 0

    print(head)
    print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

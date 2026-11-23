#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_board - 抓 GitHub Trending（日/周/月），生成一个可离线浏览的榜单页面。

用法:
    py -3.13 Tools/trending/build_board.py            # 生成 board.html
    py -3.13 Tools/trending/build_board.py --open     # 生成并打开
"""

import argparse
import html
import json
import re
import sys
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

KB = Path(__file__).resolve().parents[2]
OUT = KB / "Tools" / "trending" / "board.html"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

TAG_RE = re.compile("<[^>]+>")
WS_RE = re.compile(r"\s+")


def fetch(since):
    url = "https://github.com/trending?since=" + since
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def clean(s):
    s = TAG_RE.sub(" ", s)
    s = html.unescape(s)
    return WS_RE.sub(" ", s).strip()


def parse(page):
    items = []
    for block in re.split(r'<article class="Box-row"', page)[1:]:
        h2 = re.search(r"<h2[^>]*>(.*?)</h2>", block, re.S)
        scope = h2.group(1) if h2 else block
        m = re.search(r'href="/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)"', scope)
        if not m:
            continue
        owner, repo = m.group(1), m.group(2)
        if repo in ("trending", "stargazers", "forks"):
            continue
        desc_m = re.search(r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>(.*?)</p>', block, re.S)
        desc = clean(desc_m.group(1)) if desc_m else ""
        lang_m = re.search(r'itemprop="programmingLanguage"[^>]*>([^<]+)<', block)
        lang = clean(lang_m.group(1)) if lang_m else "未知"
        total_m = re.search(r'/stargazers"[^>]*>(.*?)</a>', block, re.S)
        total = clean(total_m.group(1)) if total_m else ""
        total = re.sub(r"[^0-9,]", "", total)
        period_m = re.search(r"([\d,]+)\s+stars\s+this\s+(day|week|month)", clean(block))
        period = period_m.group(1) if period_m else ""
        items.append({
            "owner": owner, "repo": repo, "desc": desc, "lang": lang,
            "stars": total, "period": period,
            "url": "https://github.com/%s/%s" % (owner, repo),
        })
    return items


def category(repo):
    d = (repo["repo"] + " " + repo["desc"] + " " + repo["lang"]).lower()
    rules = [
        ("AI / 大模型", ["llm", "gpt", "ai", "agent", "model", "diffusion", "transformer", "rag", "speech", "vision"]),
        ("嵌入式 / 系统", ["kernel", "driver", "embedded", "firmware", "rtos", "bootloader", "peripheral", "mcu", "c "]),
        ("开发工具", ["cli", "tool", "editor", "ide", "debug", "compiler", "linter", "formatter", "build"]),
        ("前端 / 界面", ["react", "vue", "css", "ui", "component", "tailwind", "frontend", "browser"]),
        ("数据 /  infra", ["database", "sql", "storage", "kafka", "queue", "infra", "cluster", "server"]),
        ("安全", ["security", "exploit", "vuln", "auth", "encrypt", "pentest"]),
    ]
    for name, keys in rules:
        if any(k in d for k in keys):
            return name
    return "其他"


def build(boards):
    for items in boards.values():
        for r in items:
            r["cat"] = category(r)
    payload = json.dumps(boards, ensure_ascii=False)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    tpl = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>GitHub 趋势榜单</title>
<style>
:root{--bg:#0d1117;--card:#161b22;--line:#30363d;--fg:#e6edf3;--mut:#8b949e;--acc:#2f81f7;--ok:#3fb950}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
header{position:sticky;top:0;background:#010409ee;backdrop-filter:blur(8px);border-bottom:1px solid var(--line);padding:14px 20px;z-index:5}
h1{font-size:18px;margin:0 0 10px}
.bar{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
button,select,input{background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:6px 10px;font-size:13px}
button.on{background:var(--acc);border-color:var(--acc);color:#fff}
input{min-width:220px}
main{max-width:1100px;margin:0 auto;padding:18px 20px 60px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
.card h3{margin:0 0 6px;font-size:15px}
.card h3 a{color:var(--acc);text-decoration:none}
.desc{color:var(--mut);font-size:13px;min-height:38px}
.meta{display:flex;gap:12px;flex-wrap:wrap;color:var(--mut);font-size:12px;margin-top:10px}
.tag{border:1px solid var(--line);border-radius:999px;padding:1px 8px}
.cat{color:var(--ok)}
.empty{color:var(--mut);text-align:center;padding:60px 0}
</style></head><body>
<header>
<h1>GitHub 趋势榜单 <span style="color:var(--mut);font-weight:400;font-size:12px">生成于 __NOW__</span></h1>
<div class="bar" id="periods"></div>
<div class="bar" style="margin-top:8px">
  <select id="lang"></select>
  <div class="bar" id="cats"></div>
  <input id="q" placeholder="搜索仓库 / 描述…">
</div>
</header>
<main><div class="grid" id="grid"></div><div class="empty" id="empty" style="display:none">没有匹配的仓库</div></main>
<script>
const DATA = __DATA__;
let since='weekly', lang='', cat='', q='';
const PERIODS=[['daily','今日'],['weekly','本周'],['monthly','本月']];
function uniq(a){return [...new Set(a)].sort()}
function render(){
  const list=(DATA[since]||[]);
  const langs=uniq(list.map(r=>r.lang));
  const cats=uniq(list.map(r=>r.cat));
  document.getElementById('periods').innerHTML=PERIODS.map(([k,t])=>
    '<button data-p="'+k+'" class="'+(k===since?'on':'')+'">'+t+'</button>').join('');
  document.getElementById('lang').innerHTML='<option value="">全部语言</option>'+
    langs.map(l=>'<option '+(l===lang?'selected':'')+'>'+l+'</option>').join('');
  document.getElementById('cats').innerHTML='<button data-c="" class="'+(cat===''?'on':'')+'">全部分类</button>'+
    cats.map(c=>'<button data-c="'+c+'" class="'+(c===cat?'on':'')+'">'+c+'</button>').join('');
  const rows=list.filter(r=>(!lang||r.lang===lang)&&(!cat||r.cat===cat)&&
    (!q|| (r.owner+'/'+r.repo+' '+r.desc).toLowerCase().includes(q.toLowerCase())));
  document.getElementById('grid').innerHTML=rows.map(r=>
    '<div class="card"><h3><a href="'+r.url+'" target="_blank" rel="noopener">'+r.owner+'/'+r.repo+'</a></h3>'+
    '<div class="desc">'+(r.desc||'（无描述）')+'</div>'+
    '<div class="meta"><span class="tag">'+r.lang+'</span><span class="cat">'+r.cat+'</span>'+
    '<span>★ '+(r.stars||'?')+'</span>'+(r.period?'<span style="color:var(--ok)">+'+r.period+'</span>':'')+'</div></div>').join('');
  document.getElementById('empty').style.display=rows.length?'none':'block';
}
document.addEventListener('click',e=>{
  const p=e.target.dataset.p, c=e.target.dataset.c;
  if(p){since=p;render()}
  if(c!==undefined){cat=c;render()}
});
document.getElementById('lang').addEventListener('change',e=>{lang=e.target.value;render()});
document.getElementById('q').addEventListener('input',e=>{q=e.target.value;render()});
render();
</script></body></html>"""
    tpl = tpl.replace("__NOW__", now).replace("__DATA__", payload)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(tpl, encoding="utf-8", newline="\n")
    return OUT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--open", action="store_true")
    args = ap.parse_args()
    boards = {}
    for since in ("daily", "weekly", "monthly"):
        try:
            items = parse(fetch(since))
        except Exception as exc:
            print("[board] %s 抓取失败: %s" % (since, exc))
            items = []
        boards[since] = items
        print("[board] %-7s %d 个仓库" % (since, len(items)))
    out = build(boards)
    print("[board] 已生成 %s" % out)
    if args.open:
        webbrowser.open(out.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())

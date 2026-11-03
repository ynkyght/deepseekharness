# 知识库

把散落的资料整理成**可检索、可追溯**的知识条目。

## 目录约定

    inbox/      原始资料，只读。整理前先放这里，整理时不改动原件。
    Docs/       整理稿。一篇资料一个文件，命名 YYYY-MM-DD-主题.md
    Docs/INDEX.md   索引，由脚本生成，不要手改
    project_memory.md  知识条目总表：结论 + 依据 + 适用边界
    Tools/kb/kb_sync.py  重新生成索引、检查缺口

## 一次整理的流程

1. 把资料丢进 inbox/
2. 说「整理 inbox 里的 xxx」
3. 生成 Docs/YYYY-MM-DD-主题.md（整理稿）
4. 把结论抽进 project_memory.md（带来源）
5. 跑 py -3.13 Tools/kb/kb_sync.py，--check 通过才算完

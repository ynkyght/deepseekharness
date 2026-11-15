# 知识库项目记忆

> 用途：每次开会话先读这一页，知道库里有什么、怎么找。
> 规则：只收可验证的知识；每条带来源；不确定标「待验证」。

最后更新：2026-11-15

---

## 0. 当前状态

- **状态**：检索可用 —— 203 个文件 / 2,142,419 字符；索引默认三根 `D:/data` + `D:/My_project` + DSH 工作目录
- **收尾顺序**：kb_sync → kb_brief → kb_search --rebuild（每日 18:00 定时任务）；2026-11-15 起 kb_brief 会把「## 0. 当前状态」整块置顶并校验版本落后
- **未决**：① 水母缸「设计说明_v01.md / 仿真计划_v01.md」不在 Docs/ 下，未入索引；② mouse 项目尚无 project_memory.md；③ 中文单字回退仍有检索噪音
- **更新**：2026-11-15｜本块**只覆盖不追加**

## 一、这个库是什么

把零散资料（手册、教程、聊天记录、截图、网页）整理成能直接查的结论。

- 原始资料：`inbox/`（只读）
- 整理稿：`Docs/YYYY-MM-DD-主题.md`
- 索引：`Docs/INDEX.md`（脚本生成）
- 检索索引（SQLite FTS5）：`Tools/kb/kb.db`，默认扫三个根：`D:/data`、`D:/My_project`、DSH 工作目录 `~/Documents/deepseek-harness/default-workspace`
- 收录规则：只收各项目 `Docs/`（`docs/`）目录下的 `*.md` 与 `project_memory.md`；项目根目录散放的 md 不进索引
- 本文件：结论总表

## 二、已收录主题

| 主题 | 整理稿 | 主要结论 | 更新日期 |
|---|---|---|---|
| F4/H7 总线差异 | [2026-11-04-F4与H7的FSMC-FMC差异.md](Docs/2026-11-04-F4与H7的FSMC-FMC差异.md) | 地址以代码为准；umfTarg 会让 .sct 失效；DMA 缓冲别放 CCM | 2026-11-04 |

## 三、关键结论

> 格式：结论 → 依据（整理稿文件名）→ 适用边界

1. **地址注释不可信，以代码宏为准** → 依据：Docs/2026-11-04-F4与H7的FSMC-FMC差异.md → 边界：任何"注释与代码冲突"的场景
2. **`.sct` 改了不生效**，先查 `uvprojx` 的 `umfTarg` → 依据：同上 → 边界：Keil 工程同时存在分散加载与 Target 对话框配置时
3. **DMA 缓冲区不要放 CCM/TCM** → 依据：F407 project_memory 坑 #2 → 边界：F4/F7/H7 带 DMA 的外设
4. **外置 RAM 段必须 UNINIT + zero_init** → 依据：V7 project_memory 坑 #7 → 边界：SDRAM/外部 SRAM 被 C 启动代码清零时
5. **沙箱内跑 kb_search.py 报 `unable to open database file`** → 现象：DSH 会话里执行检索直接 traceback、退出码 1；根因：`open_db()` 里的 `PRAGMA journal_mode=WAL` 要写 `D:\data`，DSH 沙箱只放行 workspace，SQLite 只读打开同样需要目录写权限；修法：检索一律用 `file:...?mode=ro&immutable=1` 只读 URI，WAL 只在 `--rebuild` 时设置 → 依据：Tools/kb/kb_search.py（2026-11-08 实测：默认连接 FAIL、`mode=ro` FAIL、`immutable=1` OK）→ 边界：任何在 DSH 沙箱内跑、库或所在目录不可写的脚本
6. **kb_search 的索引根默认只有 `D:/data`，其他盘符/目录的项目查不到** → 现象：`kb_search 水母缸` 返回 0 条、`HARO` 只 1 条，但文件确实存在；根因：`roots = args.root or ["D:/data"]` 写死单一根，而 haluo 在 `D:\My_project`，bus_servo / 水母缸 / can-debug / MechDog 在 DSH 工作目录；修法：改为 `DEFAULT_ROOTS = ["D:/data", "D:/My_project", Path.home()/"Documents/deepseek-harness/default-workspace"]`，`--root` 仍可覆盖 → 依据：Tools/kb/kb_search.py（2026-11-15 实测：173 → 203 个文件，水母缸 0→1、舵机 协议 0→6、HARO 1→3）→ 边界：新建在别的盘符/目录的项目仍要 `--root` 追加或改 DEFAULT_ROOTS；项目根目录散放的 md（如水母缸\设计说明_v01.md）不会被收录，需放进该项目 `Docs/`

7. **「当前状态」必须独立于流水账，且整块置顶** → 现象：v143 已归零的 6 项遗留仍在被引用，且实际版本已到 v149；根因：project_memory 只追加、kb_brief 每节只摘最旧 2 条、kb_search 每文件只出 1 条片段 → 修法：每项目加 `## 0. 当前状态`（覆盖式 6 行）+ kb_brief 整块置顶并校验版本落后 + kb_search `--status` 与命中先贴状态 + project_index 三根 → 依据：Docs/2026-11-15-问题状态实时归纳方案.md（2026-11-15 实测：12 份摘要 / 12 个项目状态块齐全 / 跨项目索引 5→11 个项目 / 索引 207 文件 / lag 单元测试 exit 1；kb_state.py 自动补骨架，收尾四件套）→ 边界：状态块需人工覆盖维护；未加状态块的项目仍会退化为流水账

## 四、待整理 / 待验证

- [ ] inbox/ 里还有哪些没整理（跑 kb_sync 会列出来）

## 五、命名与目录约定

| 项 | 规则 |
|---|---|
| 整理稿命名 | `YYYY-MM-DD-主题.md`，主题用短语，不加空格 |
| 一篇资料 | 一篇整理稿，不合并多篇 |
| 来源标注 | 每篇整理稿开头写「来源：原文件名 / 获取时间」 |
| 条目编号 | 本文件不编号，按主题分节；主题超过 20 条时另开文件 |

## 六、已失效

（过期结论移到这里，注明失效时间与原因）

# 学习状态同步到仓库（2026-11-05）

## 1. 问题

学习与答题记录只写进 `data/testbridge.db`，而 `.gitignore` 第 11 行 `data/*.db`
把这个文件排除在外。结果是：

- 换一台机器 clone 仓库，`/progress`、`/concepts`、`/review` 全空；
- 清掉本地库就永久丢失答题记录；
- 仓库里没有任何一条可审计的学习轨迹。

`tb evidence-export` / `evidence-import` 已经存在（JSONL、按 `id` 幂等），但它们是
一次性手工命令，没有约定落盘位置，也不会自动发生。

## 2. 目标

1. 学习状态以**纯文本、可 diff、可合并**的形式进入 git：`data/state/`。
2. 每提交一次练习，快照自动更新；启动 Web 时自动把快照并回数据库。
3. 两台机器各自学习后，git 合并两边快照不丢事件。
4. 派生状态（mastery / review）仍然只由证据重建，不从快照直接写。
5. SQLite 本身继续不入库（二进制、不可 diff），`data/artifacts/` 里的产出物也不入库。

## 3. 边界与不变量

- **证据是唯一事实来源。** 快照只是证据日志的另一种序列化，不是第二本账。
- **追加式 + 幂等。** 事件按 `id` 去重；导入是集合并集，重复导入计数为 0。
- **确定性排序。** 写出时按 `(created_at, id)` 升序，新事件落在文件末尾，
  git 才能把两台机器的提交合并成“各追加一段”。
- **派生表可重建。** 导入后调用既有 `rebuild_state`，不把 mastery / review 写进快照。
- **个人资料最后写入者胜。** `goal.json` / `target-jd.json` 用既有 `updated_at`
  比较，旧快照不会覆盖更新的本地设置。
- **不新增网络依赖、不改 `tb/1` 契约、不写掌握度。**

## 4. 快照布局

```
data/state/
  evidence.jsonl       # 所有 learner 的证据事件，一行一条，按 (created_at, id) 升序
  goal.json            # 单条 learner 目标：target_role / weekly_hours / daily_minutes /
                       # concept_overrides / updated_at
  target-jd.json       # 目标 JD（存在时）：source_text / requirements / weights / updated_at
  manifest.json        # schema=1、事件数、learner 列表、最后事件时间（由内容决定，不写生成时间）
```

文件名固定，内容稳定，因此没有变化时 `git status` 保持干净。

## 5. 合并语义

| 数据 | 写入 | 读取 | 并发冲突 |
|---|---|---|---|
| evidence | 并集（DB 权威覆盖同 id） | 按 id 幂等插入 | 正常情况是两边各自追加，git 自动合并 |
| goal | 覆盖，写 DB 的 `updated_at` | 快照 `updated_at` 更新才覆盖 | 后同步者胜 |
| target-jd | 同上 | 同上 | 同上 |
| mastery / review | 不写 | 导入后 `rebuild_state` 重建 | 不冲突 |

同一行被两边同时改写的极端情况需要人工解冲突；事件 id 不同即安全。

## 6. 接口

### 模块

新增 `src/testbridge/sync.py`（顶层组合层，不放进 `learning/`：它需要同时读
evidence、learning 与 career 三个存储，放进引擎包会破坏
`test_engine_does_not_import_career` 边界测试）。

- `resolve_state_dir(db_path, override=None)`：默认 `db_path.parent / "state"`；
  `TESTBRIDGE_STATE_DIR` 覆盖；值为 `0/off/false/no` 时关闭同步。
- `import_state(db_path, state_dir)`：导入证据并合并个人资料。
- `export_state(db_path, state_dir, learner_id="local")`：DB ∪ 旧快照 → 排序 → 原子写。
- `sync_state(...)`：先导入再导出，返回合并报告。

### CLI

```
tb state-export --db data/testbridge.db --dir data/state
tb state-import --db data/testbridge.db --dir data/state --pack content-packs/<id>
tb state-sync   --db data/testbridge.db --dir data/state --pack content-packs/<id>
```

`state-import` / `state-sync` 带 `--pack` 时重建派生状态。

### Web

- `create_app(..., state_dir=None)`：`None` 走 `resolve_state_dir`。
- 启动时 `import_state`，有新事件则 `rebuild_state`。
- `EvidenceStore.on_append` 回调：每次证据写入（练习、产出物、AI 讲评、面试确认）
  都导出快照；导出失败不阻断提交，错误记录到 `app.state.sync_status` 并在
  `/progress` 顶部提示。
- 因为快照目录默认由 DB 路径推出，测试用 `tmp_path/*.db` 时快照落在 `tmp_path/state`，
  不会读到或写坏仓库里的真实快照。

## 7. 明确不做

- 不做云同步、多用户、远端 API；同步渠道就是 git。
- 不入库 SQLite 文件、`data/artifacts/` 二进制、Tutor 对话、投递记录。
- 不新增“阅读进度”证据类型：当前引擎没有课程浏览记录，本次只同步已存在的状态。
- 不做冲突自动解冲突：同一行被两机改写的概率极低，交给 git。

## 8. 验收

- 新库 `state-import` 后事件数、掌握度、复习卡与导出前一致（`rebuild-state` 可复现）。
- 连续两次 `state-sync` 不产生 diff。
- 两个独立 DB 导出到同一目录后导入第三个空库，事件为并集且无重复。
- `pytest` 全绿（含 P1/P2 无回归）。
- `data/state/` 未被 `.gitignore` 命中，真实快照可提交。
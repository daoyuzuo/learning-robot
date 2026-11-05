# 学习状态同步实施计划（2026-11-05）

**目标：** 学习/答题记录以可提交快照进入仓库，并在启动与提交时自动双向同步。

**设计：** [2026-11-05-state-sync-design.md](../specs/2026-11-05-state-sync-design.md)

## Task 1：存储钩子

- `EvidenceStore.append` 增加可选 `on_append` 回调（构造参数 + 属性）；`import_jsonl`
  直接走 `_insert`，因此不会递归触发。
- `LearningStore.goal_updated_at(learner_id)` 暴露既有 `goal.updated_at`，用于比较快照。
- 测试：`tests/test_evidence_store.py` 补回调只在新行插入时触发、导入不触发。

## Task 2：快照模块

- 新增 `src/testbridge/sync.py`：`resolve_state_dir`、`import_state`、`export_state`、
  `sync_state`。
- 写文件用同目录临时文件 + `os.replace`，`newline="\n"`，UTF-8。
- 测试：`tests/test_state_sync.py` —— 并集、幂等、排序、脏行 warning、goal/target
  的 `updated_at` 优先级、manifest 稳定性、`TESTBRIDGE_STATE_DIR=0` 关闭。

## Task 3：CLI

- `state-export` / `state-import` / `state-sync`，`--pack` 时重建派生状态。
- 测试：`tests/test_cli_state.py` —— 退出码与输出、未知目录不抛 traceback。

## Task 4：Web 自动同步

- `create_app` 增加 `state_dir`；启动导入 + 重建；`store.on_append` 导出。
- 导出异常写入 `app.state.sync_status`，`/progress` 显示快照目录与错误。
- 测试：`tests/test_state_sync_web.py` —— 提交后快照出现该事件；新建应用指向同一
  `state_dir` 的空库时 `/progress` 能看到该事件；导出失败时提交仍 200。

## Task 5：真实数据与提交

- `tb state-sync --db data/testbridge.db --dir data/state --pack content-packs/robot-quality-system`
- 确认 `git check-ignore data/state/evidence.jsonl` 无输出，提交并推送。

## Task 6：文档

- `ROADMAP.md` 当前期节 + 文档索引；`README.md` 增加“学习记录同步”一节；
  `CLAUDE.md` 注明 `data/state/` 是可提交快照。

## 验收

```
pytest -q
tb validate content-packs/robot-quality-system
tb state-sync --db data/testbridge.db --dir data/state --pack content-packs/robot-quality-system
git status --porcelain
```
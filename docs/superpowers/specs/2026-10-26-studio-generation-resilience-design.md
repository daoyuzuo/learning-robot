# Studio 生成可靠性加固（Generation Resilience）

- 状态：Implemented，2026-10-26
- 范围：跨课 ID、LLM 瞬时失败重试、跨进程 `interrupted`、生成超时
- 上游：[P3.1 内容工作台](2026-10-25-p3.1-content-studio-design.md)、
  [P3.4 多模块与批量](2026-10-25-p3.4-multi-module-batch-design.md)、
  [P3.5 内容演进](2026-10-26-p3.5-content-evolution-design.md)
- 路线图：[ROADMAP](../../ROADMAP.md)

---

## 1. 背景

用真实模型生成 `robot-quality-system`（2 模块 × 4 课）时遇到四类问题：

1. 模型在多节课复用 `EX-1` / `DOC-001`，第二课写盘时触发全局 ID 冲突，批量在第 3 课失败。
2. 单次写课超过默认 30 秒，触发 `ReadTimeout`；上游偶发 5xx 时没有重试。
3. 另一个开发服务共用 `drafts/`，启动时把正在运行的课标记为 `failed(interrupted)`。
4. 手工调高 `TESTBRIDGE_LLM_TIMEOUT` 只对当前终端有效，重启后回到 30 秒。

这些都属于作者层（`studio/`）与 LLM 客户端可靠性，不改变内容契约、判分、掌握度或调度。

## 2. 决策

### 2.1 跨课 ID：写盘时确定性命名空间

- 模型输出仍按课局部校验（课内重复仍报错）。
- 写课时若练习/资源 ID 已被其它课占用，追加 `{lesson_id}-` 前缀；
  仍冲突时追加 `-2`、`-3`。
- HTML 中 `data-tb-exercise` 与 `data-tb-resource` 同步改名，manifest 引用保持一致。
- 只改冲突项，单课输出不受影响；`replace=True` 先释放旧课 ID，再按同样规则命名。
- 不通过提示词要求模型自造全局唯一 ID：模型不可信，确定性兜底更可靠。

### 2.2 LLM 瞬时失败：客户端重试一次

- 重试范围：超时、连接错误、状态码 `408/425/429/500/502/503/504`。
- 401/403/400 等确定性错误不重试。
- 超时重试使用更长截止时间：`min(config.timeout × 3, 300s)`；
  其它瞬时失败等待 1 秒后重试。
- 每次 `complete()` 最多 2 次尝试；仍失败则保留原有
  `TutorTimeoutError` / `TutorUpstreamError` 语义。
- 生成类请求可安全重试：不会写账本、不会产生学习证据。
- `retry_delay=0` 供测试使用，默认 1 秒。

### 2.3 跨进程 `interrupted`：记录 owner 与 pid

- `DraftStore` 每个实例有 `instance_id`；`set_step(status="running")`
  在步骤上记录 `owner` 与 `pid`，结束时清除。
- 启动时 `mark_interrupted()` 只把“没有存活 owner”的 running 步骤改为
  `failed(interrupted)`：
  - owner 是另一个仍存活的进程 → 保留；
  - owner 已退出、属于本进程的旧实例、或旧格式无 owner → 标记中断。
- Windows 通过 `OpenProcess` + `GetExitCodeProcess` 判断存活；
  其它平台用 `os.kill(pid, 0)`。
- 目的：共用 `drafts/` 的两个开发服务不再互相打断；崩溃后的残留仍会清理。

### 2.4 超时配置

- 保留 `TESTBRIDGE_LLM_TIMEOUT` 默认 30 秒，不改变 P2.2 契约。
- 文档建议内容生成设置 90 秒；Windows 用户环境持久化为 90 秒，
  新开的终端与服务自然继承。客户端超时重试再提供 3 倍兜底。

## 3. 非目标

- 不提升 prompt 版本（提示词未改，仍为 `studio/2`）。
- 不改 `tb/1` 内容契约、质量门禁规则、判分、掌握度、调度。
- 不做跨机器任务锁、任务取消、断点续写。
- 不重试 200 但内容不可解析的响应；该错误仍由现有解析重试处理。
- 不自动清理其它进程的草稿文件。

## 4. 测试

| 层 | 覆盖 |
|---|---|
| 写课 | 跨课练习/资源 ID 加前缀；HTML 两个 data 属性同步；`replace` 释放旧 ID |
| 批量 Web | 两课固定 ID 时批量成功且 ID 唯一 |
| 客户端 | 502/429 重试成功；5xx 两次后报错；401 不重试；超时重试并用更长 deadline |
| 草稿存储 | running 记录 owner/pid；完成后清除；存活它进程保留；死进程/同进程旧实例标记中断 |
| 回归 | 全量 `pytest` 672 passed，3 deselected |

## 5. 验收

（实测，2026-10-26）

- [x] 两次写课使用相同 `EX-1/DOC-1` 时，第二节自动命名为
      `L-EXEC-002-EX-1` / `L-EXEC-002-DOC-1`，HTML 挂载点同步。
- [x] 批量写两课固定 ID 时 `started=2`、`batch=done`，练习 ID 唯一。
- [x] 首次 502 或 429 后重试成功；连续 503 两次后抛 `TutorUpstreamError`；
      401 只请求一次；首次超时后以 3 倍 deadline 重试。
- [x] 另一存活进程拥有的 running 步骤不被启动清理；死进程与同进程旧实例被标记中断。
- [x] 全量测试：`672 passed, 3 deselected`。

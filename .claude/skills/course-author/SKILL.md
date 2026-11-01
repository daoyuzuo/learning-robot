---
name: course-author
description: Use when creating or revising a TestBridge course pack from a topic, syllabus, or reference material. The framework only validates, renders, and tracks learning; the coding AI writes content-packs directly.
---

# TestBridge 课程作者

框架不生成课程。你在 `content-packs/` 里直接写 `tb/1` 内容包；框架只负责契约校验、
渲染和学习运行时。先读 `references/content-contract.md` 与 `references/authoring-guide.md`。

## 什么时候用

- 用户要新建一门课、扩写/重写某门课、调整课程结构或习题。
- 用户给了主题、课程大纲、参考资料、岗位目标或现有课程包。
- 不要在框架里寻找隐藏的生成器；没有 `/studio`，没有内部 LLM 流水线。

## 工作方式

1. **先看现状**：`tb list content-packs`，阅读目标包或 `tests/fixtures/packs/sample-sensors`
   作为格式参考。旧包存在时先确认要保留哪些 ID；改 concept/exercise ID 会影响学习证据。
2. **问清楚意图**：课程边界（必须覆盖/明确不讲）、学完能做什么、已有基础、目标场景、
   深度/时长、评估方式。用户没说清楚时先问，不要套固定表单。
3. **查官方/权威资料**：用你自己的 WebSearch/WebFetch 查标准、官方文档、官方仓库。
   只把真实存在的 URL 写进 `resources.yaml`；记录 `license`、`last_verified`、`why`。
   不要用模型记忆编造标准号或链接。
4. **设计结构**：模块数、每模块课数、单课分钟、深度由你按内容判断，不设上限。
   先给用户一个简短结构提案；确认后写文件。大纲条目/顺序/边界是作者约束，不要静默删除。
5. **写内容**：新包用 `tb scaffold <id> --dir content-packs --title "..."` 生成合法骨架，
   再替换占位概念/课/练习/资源；也可以直接按契约写。
6. **校验循环**：
   - `tb validate content-packs/<id>` —— 硬契约；必须 0 error。
   - `tb depth content-packs/<id>` —— 深度门禁；必须 0 error。
   - `tb quality content-packs/<id>` —— 可选建议；按需改进，不绕过 validate/depth。
   - `tb build content-packs/<id> --out dist` —— 渲染检查。
   - 交付时给出 `tb serve content-packs/<id> --port 8000 --open`。
7. **不要做**：不要修改 `src/testbridge/` 的引擎/契约代码来迁就内容；不要写 `draft`/Studio
   字段；不要把答案写进课程 HTML；不要虚构资源 URL；不要把未验证的第三方内容当官方来源。

## 必须遵守的硬契约

完整细节见 `references/content-contract.md`。最低要求：

- 每个内容文件带 `schema: tb/1`。
- 课程是 HTML 片段 + `<script id="tb-manifest">` JSON；练习定义在 `exercises.yaml`，
  课程只引用 exercise ID，并在正文放空的 `<div data-tb-exercise="...">` 挂载点。
- 概念图 `concepts.yaml`，资源 `resources.yaml`；模块 `modules/<id>/module.yaml`。
- 每课至少 2 道练习；每个概念至少被 1 道练习覆盖；练习 level 不低于概念 target_level。
- 内容按不可信输入处理：只用允许的 HTML 标签，禁止 script/style/iframe/事件属性；
  外部资源用 `resources.yaml`，不要直接嵌外部图片。
- 通过 `tb validate` 后再交付；框架不会替你修正契约错误。

## 深度契约

每课必须达到 `tb depth` 的默认阈值：

| 级别 | 最少字数 | 最少 `<h2>` | 最少表格/图 | 最少练习 |
|---|---|---|---|---|
| L1 | 1,200 | 3 | 0 | 2 |
| L2 | 2,000 | 4 | 0 | 2 |
| L3 | 3,500 | 6 | 1 | 2 |
| L4 | 4,500 | 7 | 1 | 2 |

“字数”是正文去标签、去空白后的字符数，不含 manifest。`tb depth` 失败时不要交付；
先补工程场景、方法步骤、数字实例、判定证据、误区或检查表，不要灌水。

## 弱约束（由你判断，不是框架强制）

- 先建立课程地图，再写单课；每课围绕一个可检验的学习成果。
- 优先官方标准/官方文档/官方仓库；资源可信度不足时明确告诉作者。
- 练习要覆盖概念与常见误区；避免只考记忆；不要泄漏答案。
- 课程量按内容需要决定；不要为了“看起来整齐”硬压成固定模块数/课数。
- 结构变化、ID 变化、资源替换都会影响学习证据；交付时说明影响。

## 交付格式

简短说明：课程包路径、模块/课结构、官方来源与缺口、`tb validate` 结果、下一步命令。

# 机器人测试与质量体系 Lesson Briefs

每课一页的依据。正文重写以本文件为准；Mission 见 [MISSION.md](MISSION.md)，
来源见 [RESOURCES.md](RESOURCES.md)。

## L-001-001 测试策略的输入与边界

- **Tangible win:** 为一个机器人版本写清 in/out/TBD 范围表和排除项责任链。
- **Primary source:** R-29119-2 —— 对照测试管理级过程，写范围、环境和门禁。
- **Retrieval:** 你现在项目的测试范围主要依据什么？哪些输入没有被记录？
- **Worked example:** 6 周配送机器人改版：3 人、40 台现场设备、只改规划器；
  从五类输入推出必测 9 项、抽样 4 项、不测 2 项。
- **Exercises:** O1→EX-001-01（风险驱动深度），O2→EX-001-02（五类输入）。
- **Misconception:** “只改了规划器就只测规划器”；接口不变不等于下游行为不变。
- **Figure/table:** 五类输入表 + 排除项责任表。
- **Minutes:** 50

## L-001-002 风险分级与风险驱动测试

- **Tangible win:** 用五维风险矩阵给机器人场景排序，并把等级换成测试预算。
- **Primary source:** R-ISO-12100 —— 借用危险识别、风险估计和风险降低流程。
- **Retrieval:** L-001-001 的五类输入是什么？排除项必须写哪四样？
- **Worked example:** 协作臂 + AGV 工作站：人从侧面进入指数 48，分配 40 台时和
  12 个注入场景；语音音量指数 5，只做 2 小时抽检。
- **Exercises:** O1→EX-002-01（五维分级），O2→EX-002-02（协作场景分级）。
- **Misconception:** 只按发生概率分级，低估低概率高严重度事件。
- **Figure/table:** 五维分级表 + 指数映射表。
- **Minutes:** 50

## L-001-003 测试分层、左移与右移

- **Tangible win:** 为导航软件写四层测试的进入判据、通过判据和归属负责人。
- **Primary source:** R-29119-2 —— 动态测试级过程和管理级评审。
- **Retrieval:** 风险分级的三维是什么？高风险项应分配什么测试深度？
- **Worked example:** 2000 条自动化用例仍漏现场问题；把“窄通道、接口单位、行人横穿、
  现场验收”分到四层并各写一条判据。
- **Exercises:** O1→EX-003-01（左移活动），O2→EX-003-02（四层判据）。
- **Misconception:** 单元覆盖率 80% 就说明分层做得好。
- **Figure/table:** 分层示意图 + 每层判据表。
- **Minutes:** 50

## L-001-004 版本准入、准出与策略落地

- **Tangible win:** 写一份含 blocker、critical、已知问题、回滚和风险接受人的发布记录。
- **Primary source:** R-29119-2 —— 测试管理级的监控、控制和报告活动。
- **Retrieval:** 四层测试各回答什么问题？左移和右移各把什么活动提前/延后？
- **Worked example:** 97% 执行率、95% 通过率、3 个 blocker 的版本：2 个必修、1 个书面接受、
   2 个 critical 升级、回滚演练通过后才发。
- **Exercises:** O1→EX-004-01（准出依据），O2→EX-004-02（准出清单）。
- **Misconception:** 通过率 95% 就可以发；失败项里可能包含 blocker。
- **Figure/table:** 准出清单 + 发布决策记录模板。
- **Minutes:** 45

## L-001-005 测试设计方法工具箱

- **Tangible win:** 为自动泊车组合等价类、边界值、状态迁移、场景法和组合测试。
- **Primary source:** R-29119-4 —— 各测试技术的定义和覆盖准则。
- **Retrieval:** 判定表适合什么形状的问题？状态迁移必须覆盖哪四类路径？
- **Worked example:** 6 参数 × 5 水平 = 15,625 组合；配对压到 30–40 条，安全关键组合
   全组合后约 200–300 条。
- **Exercises:** O1→EX-005-01（边界值），O2→EX-005-02（泊车多方法），
  O3→EX-005-03（组合测试）。
- **Misconception:** 配对测试可以替代安全关键组合和边界值。
- **Figure/table:** 方法选择表 + 组合规模对比表。
- **Minutes:** 55

## L-001-006 任务链、长尾场景与故障注入

- **Tangible win:** 为“转弯中行人横穿”设计含注入点、观测、降级和恢复判据的实验。
- **Primary source:** R-29119-4 —— 场景法和基于缺陷的测试设计。
- **Retrieval:** 边界值取哪些点？状态迁移要覆盖哪些非法路径？
- **Worked example:** t=0 行人进入、t=40 ms 感知输出、t=80 ms 规划重算、t=120 ms 控制减速、
  t=200 ms 停止；逐段观察延迟和遮挡放大。
- **Exercises:** O1→EX-006-01（五节点），O2→EX-006-02（动态障碍注入）。
- **Misconception:** 每个模块单测通过，整机任务链就一定没问题。
- **Figure/table:** 任务链图 + 失效传播时间线。
- **Minutes:** 55

## L-001-007 测试预言与量化指标

- **Tangible win:** 为 SLAM 定义指标、阈值、样本量、分位数和失败判定。
- **Primary source:** R-29119-4 —— 预言与测试条件的组织方式。
- **Retrieval:** 任务链五个节点是什么？故障注入实验必须记录哪些字段？
- **Worked example:** 20 次延迟样本：均值 123 ms、P95 约 140 ms、最大 500 ms；
  同一个系统在“均值”和“单次阈值”下结论不同。
- **Exercises:** O1→EX-007-01（蜕变预言），O2→EX-007-02（SLAM 指标）。
- **Misconception:** 没有报错就算通过；没有 oracle 的测试只是操作。
- **Figure/table:** 预言类型表 + 指标口径对比表。
- **Minutes:** 55

## L-002-001 缺陷分类、复现与证据链

- **Tangible win:** 把一条“偶发避障失败”写成可独立复现的证据链和分诊结论。
- **Primary source:** R-ISTQB —— defect、failure、severity、priority 的统一定义。
- **Retrieval:** L-001-007 的五类预言是什么？单次阈值和 N 次统计各适合什么？
- **Worked example:** 20 次中 3 次复现，均在转弯角速度 >0.6 rad/s；日志显示感知延迟 120 ms、
  控制延迟 80 ms。
- **Exercises:** O1→EX-008-01（缺陷类别），O2→EX-008-02（复现证据链）。
- **Misconception:** “无法复现”可以关闭缺陷；应该记录尝试条件和下一步计划。
- **Figure/table:** 十类缺陷表 + 缺陷单模板。
- **Minutes:** 50

## L-002-002 根因分析：5Why、鱼骨、8D 与 FTA

- **Tangible win:** 对“急停后仍移动 10 cm”做假设—验证—纠正闭环。
- **Primary source:** R-ISTQB —— 缺陷分析与根因相关术语。
- **Retrieval:** 十类缺陷是什么？严重度和优先级有什么区别？
- **Worked example:** 5 条假设：状态机过滤 80 ms、制动器慢、负载超预期、地面湿滑、
  指令未撤销；每条给预测和验证方法。
- **Exercises:** O1→EX-009-01（5Why vs FTA），O2→EX-009-02（急停根因）。
- **Misconception:** 更换制动器让问题暂时消失，就等于找到根因。
- **Figure/table:** 方法对比表 + 故障树示例。
- **Minutes:** 55

## L-002-003 逃逸分析与缺陷预防

- **Tangible win:** 用五个追问修补需求、用例、环境、门禁和评审缺口。
- **Primary source:** R-29119-2 —— 测试过程监控与改进。
- **Retrieval:** 5Why 和 FTA 的区别？根因分析的三个层次是什么？
- **Worked example:** 充电重试缺陷：需求没写重试、用例只测成功、测试桩型号不同、
  门禁只看成功率、变更评审没查兼容性。
- **Exercises:** O1→EX-010-01（逃逸核心问题），O2→EX-010-02（改进闭环）。
- **Misconception:** 只补一条用例就算完成逃逸分析。
- **Figure/table:** 五类逃逸原因表 + 改进记录模板。
- **Minutes:** 45

## L-002-004 覆盖率：需求、代码、场景、风险与接口

- **Tangible win:** 为配送机器人设定五类覆盖目标、度量来源和责任人。
- **Primary source:** R-29119-2 —— 测试条件与覆盖的组织。
- **Retrieval:** 四层测试各回答什么问题？风险分级如何影响测试深度？
- **Worked example:** 需求 100%、代码 85%、场景 60%、风险 70%、接口 90%：
  单看前两项像可以发，组合后发现地下车库和雨雾场景缺失。
- **Exercises:** O1→EX-011-01（覆盖类型），O2→EX-011-02（配送机器人覆盖计划）。
- **Misconception:** 代码覆盖率 85% 就说明测试充分。
- **Figure/table:** 五类覆盖表 + 覆盖目标矩阵。
- **Minutes:** 50

## L-002-005 回归策略与版本准入

- **Tangible win:** 按影响分析写分层回归计划、时间预算和回滚方案。
- **Primary source:** R-29119-2 —— 回归与测试管理过程。
- **Retrieval:** 五类覆盖率是什么？准出清单里的 blocker 和 critical 怎么区分？
- **Worked example:** 1,800 条用例 × 8 分钟 = 240 人时；4 人全量需 10 天，
  核心 + 抽样只需约 2.8 天。
- **Exercises:** O1→EX-012-01（blocker 定义），O2→EX-012-02（回归与回滚）。
- **Misconception:** 全量回归等于安全；时间不够时高风险项反而最后跑。
- **Figure/table:** 回归分层表 + 时间预算表。
- **Minutes:** 50

## L-002-006 实验设计：重复次数、样本量与置信区间

- **Tangible win:** 为 98% 抓取成功率设计分层样本量、置信区间和变异控制。
- **Primary source:** R-ISO-9283 —— 性能试验的重复与条件记录。
- **Retrieval:** 均值、P95、worst-case 各回答什么？为什么安全指标不能取平均？
- **Worked example:** p=98%、e=±2% 时 n≈188；分 3 材质 × 3 重量共 9 层，每层至少 21 次。
- **Exercises:** O1→EX-013-01（样本量因素），O2→EX-013-02（抓取实验）。
- **Misconception:** 跑 50 次成功 49 次就证明 98% 达标。
- **Figure/table:** 样本量速查表 + 变异来源表。
- **Minutes:** 55

## L-002-007 Flakiness、基线与趋势分析

- **Tangible win:** 定位 Flakiness 来源，建立基线并用趋势图判断异常。
- **Primary source:** R-ISO-18646-2 —— 导航试验的重复条件和指标口径。
- **Retrieval:** 样本量取决于哪些因素？置信区间和置信水平有什么区别？
- **Worked example:** 导航用例 30 天失败率 15%；单独跑降到 3%、串行 4%、固定种子 2%，
  失败时感知 P95 从 80 ms 升到 180 ms。
- **Exercises:** O1→EX-014-01（Flakiness 来源），O2→EX-014-02（P95 选择），
  O3→EX-014-03（趋势分析产出物）。
- **Misconception:** 重跑通过就可以关闭不稳定用例。
- **Figure/table:** 来源表 + 排查决策树 + 基线字段。
- **Minutes:** 55

## L-003-001 通用测试标准地图：29119 与 ISTQB

- **Tangible win:** 把 29119/ISTQB 映射到项目活动、产物和裁剪记录。
- **Primary source:** R-29119-2 —— 测试过程的层级和活动。
- **Retrieval:** 29119-2 和 29119-4 分别管什么？ISTQB 能替代产品符合性吗？
- **Worked example:** 120 条需求 → 240 条用例；核心回归按 45 s/条约 3 小时。
- **Exercises:** O1→EX-015-01（29119 范围），O2→EX-015-02（标准映射）。
- **Misconception:** “团队有 ISTQB 认证”等于“产品符合 29119”。
- **Figure/table:** 29119 分部表 + 标准映射模板。
- **Minutes:** 45

## L-003-002 汽车与工业软件标准族

- **Tangible win:** 为 OTA/诊断功能组合 ASPICE、26262、21448、21434、14229、11898。
- **Primary source:** R-ISO-26262 —— 功能安全与 ASIL 的基准。
- **Retrieval:** ASPICE 评估的是什么？26262 和 21448 的区别？
- **Worked example:** OTA 包 800 MB、升级窗口 15 分钟、回滚 30 s、总线负载峰值 70%；
  四个数字分别约束不同标准。
- **Exercises:** O1→EX-016-01（标准族识别），O2→EX-016-02（车载诊断组合）。
- **Misconception:** 做一套测试就能覆盖所有汽车标准。
- **Figure/table:** 标准分工表 + 证据矩阵。
- **Minutes:** 55

## L-003-003 机器人安全标准族：从工业到服务

- **Tangible win:** 为协作臂 + AGV 工作站选标准组合，并列出每项证据。
- **Primary source:** R-ISO-10218-1 —— 工业机器人本体的安全要求。
- **Retrieval:** ISO 12100 在安全标准里起什么作用？协作机器人四种协作方法是什么？
- **Worked example:** 机械臂 ISO 10218-1、工作站 10218-2、人机接触 TS 15066、
  AGV 3691-4、风险评估 12100；逐行写证据和缺口。
- **Exercises:** O1→EX-017-01（安全标准识别），O2→EX-017-02（混合工作站组合）。
- **Misconception:** 协作机器人不需要围栏，所以不需要风险评估。
- **Figure/table:** 标准地图 + 混合工作站证据清单。
- **Minutes:** 60

## L-003-004 功能安全：PL、SIL 与 ASIL 的区别

- **Tangible win:** 为急停功能选 PL 或 SIL，并写出等级推导和验证证据。
- **Primary source:** R-ISO-13849-1 —— PL 的架构、MTTFd、DC、CCF。
- **Retrieval:** ISO 10218-1 和 -2 分别覆盖什么？PL 和 SIL 来自哪个体系？
- **Worked example:** 目标 PL d：MTTFd ≥ 30 年、DC ≥ 90%、30 次急停试验、停车距离 ≤ 0.5 m。
- **Exercises:** O1→EX-018-01（ASIL vs PL/SIL），O2→EX-018-02（PL/SIL 选择）。
- **Misconception:** PL d 可以不加解释地写成 SIL 2。
- **Figure/table:** 三套体系对比图 + 速查表。
- **Minutes:** 55

## L-003-005 机器人性能评价

- **Tangible win:** 按 ISO 9283/18646 写一份可复现的性能试验和报告。
- **Primary source:** R-ISO-9283 —— 位姿/路径精度与重复性试验方法。
- **Retrieval:** 位姿精度和重复性有什么区别？为什么性能报告必须写测试条件？
- **Worked example:** 5 个位姿 × 30 次：右下角 3σ=0.046 mm、最大值 0.051 mm，
  均值通过但最大值超差。
- **Exercises:** O1→EX-019-01（ISO 9283 对象），O2→EX-019-02（性能方案）。
- **Misconception:** 只报一个“重复性 0.05 mm”就足够。
- **Figure/table:** 标准分工表 + 性能数据示例表。
- **Minutes:** 55

## L-003-006 市场准入与认证：CE、UL、CQC 与 CR

- **Tangible win:** 为移动服务机器人列 CE/CQC/CR 认证路径、技术文件和测试证据。
- **Primary source:** R-CE-MACHINERY —— 欧盟机械法规与协调标准入口。
- **Retrieval:** CE 是强制还是自愿？CR 和 CCC 的区别？
- **Worked example:** 12 周认证时间线：1–2 周定标准、3–5 周补文件/测试、6–8 周送样、
  9–10 周工厂检查、11–12 周归档。
- **Exercises:** O1→EX-020-01（认证类型），O2→EX-020-02（CE 路径）。
- **Misconception:** CR 是强制 CCC；CE 是质量认证。
- **Figure/table:** 认证地图 + 时间线 + 资料清单。
- **Minutes:** 45

## L-003-007 综合演练

- **Tangible win:** 为具身智能机器人整合质量、标准、认证、回归和缺口计划。
- **Primary source:** R-ISO-12100 —— 从风险评估串起整套方案。
- **Retrieval:** 高风险项的证据矩阵怎么用？准出、认证、剩余风险怎么连接？
- **Worked example:** 仓储 AMR + 协作臂：风险登记、标准组合、指标字典、
  测试矩阵、认证计划、证据矩阵和 30/60/90 天落地计划。
- **Exercises:** O1→EX-021-01（端到端方案），O2→EX-021-02（方案产出物），
  O3→EX-021-03（自评与 30 天计划）。
- **Misconception:** 综合方案等于把前面 20 课抄一遍，不做取舍。
- **Figure/table:** 九步法 + 证据矩阵 + 30/60/90 计划。
- **Minutes:** 60

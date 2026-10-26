# 《机器人整机/系统测试与 HIL/SIL 测试开发》课程大纲

**课程编号：** RBT-TEST-2026（内部课程编号）  
**课程版本：** 2026-10-25 / v1.0  
**课程类型：** 职业转型专项课程（项目制）  
**建议学时：** 120 学时（12 周 × 10 学时；可按 10–15 小时/周调整为 10–16 周）  
**教学形式：** 讲授/阅读 35%，实验/案例分析 40%，项目与评估 25%  
**授课语言：** 中文（关键术语中英对照）  
**适用对象：** 3 年以上车载/车身电子/嵌入式测试经验，计划转入机器人整机/系统测试或 HIL/SIL 测试开发的学习者

---

## 一、课程简介

本课程面向具备复杂机电系统测试经验、但缺乏机器人领域知识的学习者，目标是建立“机器人整机/系统测试 + HIL/SIL 测试开发”的完整能力结构。课程不培养机器人算法工程师，也不以推导运动学/动力学公式为目标；课程重点是：看懂机器人系统、设计可执行的测试、搭建/使用 HIL/SIL 台架、用总线和故障注入定位问题，并把既有车载测试经验转化为机器人测试证据。

课程以“系统—测试—证据”为主线：先建立机器人系统架构通识（硬件、软件、通信、实时性、安全），再进入测试方法、自动化框架、HIL/SIL、总线通信和故障注入，最后通过 Capstone 把真实车载项目迁移为机器人测试案例。课程强调真实项目、可复现证据和可解释的测试结论，不要求虚构机器人项目经历。

完成课程后，学习者应能够独立设计机器人整机/子系统测试方案，搭建或使用 HIL/SIL 测试环境，编写 Python 测试自动化，分析总线/日志/时序问题，并把测试结果组织成可审计的证据链。

---

## 二、先修要求

| 类别 | 要求 |
|---|---|
| 测试基础 | 理解测试用例、缺陷生命周期、测试报告、版本准入等基本概念 |
| 编程 | 能读写 Python 基础代码（函数、类、文件、异常）；C++ 不要求 |
| 操作系统 | 会基本 Linux 命令（文件、进程、日志、网络） |
| 总线 | 了解 CAN 帧、DBC、CANoe/CAPL 基本使用 |
| 领域 | 不要求机器人/ROS2 基础；有汽车 HIL、诊断、FuSa 经验者优先 |
| 硬件 | 能安全使用低压台架、示波器、万用表；无真实台架者可完成仿真/虚拟台架实验 |

**先修诊断：** 开课前完成 Python、Linux、CAN、测试基础四项自评（0–3 分）；低于 2 分的模块需在课程前两周补足。

---

## 三、学习成果（Course Learning Outcomes）

完成本课程后，学习者能够：

1. **解释机器人系统架构**：说明感知、定位/建图、规划、控制、执行、安全、通信、计算平台之间的数据流与接口关系。
2. **设计风险驱动的测试策略**：针对机器人整机/子系统任务，产出测试策略、测试用例、覆盖模型和准入/准出标准。
3. **定义可量化测试预言**：为机器人非确定性行为设计成功率、误差、延迟、抖动、漂移等指标，并说明统计口径。
4. **编写可维护的 Python 测试自动化**：使用 pytest、数据驱动、日志解析、报告生成和基本并发。
5. **分析并重构测试框架**：解释框架分层、适配器、夹具、断言、证据、调度和 CI 集成；能扩展 CAN/ROS2 适配层。
6. **使用 Linux/日志/网络工具定位问题**：能够从应用、中间件、总线、物理层逐层缩小故障范围。
7. **解释机器人通信架构**：区分 ROS2/DDS、CAN/CANopen、EtherCAT、Ethernet、串口/SPI/I2C 的职责、实时性和测试点。
8. **设计 HIL/SIL 测试方案**：包括 plant model、I/O、传感器/执行器仿真、时间同步、故障注入单元和台架安全。
9. **应用故障注入与功能安全方法**：设计故障模型、注入方法、安全状态/降级验证和证据链，并区分 ISO 26262 与机器人安全标准。
10. **完成项目迁移与表达**：把真实车载项目改写为机器人测试案例，形成可演示的作品集和面试叙事。

---

## 四、课程结构

| 模块 | 名称 | 学时 | 其中实验/案例 | 对应学习成果 |
|---|---|---:|---:|---|
| M0 | 课程导入与能力诊断 | 4 | 2 | CLO1–10（诊断） |
| M1 | 测试、验证与评价体系 | 18 | 8 | CLO2, CLO3, CLO6 |
| M2 | 工程基础：Python / Linux / Git / C++ 阅读 | 20 | 10 | CLO4, CLO6 |
| M3 | 自动化测试与测试框架 | 20 | 10 | CLO4, CLO5 |
| M4 | 机器人系统通识与 ROS2 | 26 | 10 | CLO1, CLO7 |
| M5 | HIL/SIL、总线通信与安全 | 24 | 12 | CLO7, CLO8, CLO9 |
| M6 | 项目迁移、Capstone 与职业表达 | 8 | 8 | CLO10 |
| **合计** |  | **120** | **60** |  |

> 学时可按 10–15 小时/周压缩或扩展；M4/M5 是核心模块，不建议压缩。

---

## 五、模块内容

### M0. 课程导入与能力诊断（4 学时）

**目标：** 建立课程地图，完成个人能力基线，确定主攻方向（整机/系统 vs HIL/SIL 测试开发）。

**内容：**

- 课程目标、考核方式、项目策略与学术规范；
- 机器人测试岗位画像：整机/系统、HIL/SIL、仿真、硬件/部件、算法评测的差异；
- 个人能力诊断：测试方法、Python、Linux、CAN、HIL、ROS2、统计；
- 真实项目盘点：选择 2–3 个可用于迁移的车载项目；
- 制定个人学习契约。

**实验/作业：**

- 完成能力自评表；
- 提交一页《个人能力与项目盘点》。

**考核：** 诊断结果不计入总分，但作为后续作业分层依据。

---

### M1. 测试、验证与评价体系（18 学时）

**目标：** 把“会执行测试”升级为“能设计验证体系、定义指标、评价机器人系统”。

**内容：**

1. **V&V 与 T&E 基础**
   - 验证（Verification）与确认（Validation）；
   - V 模型、测试左移/右移；
   - 测试层级：单元、集成、系统、验收；SIL/HIL/真机/现场。

2. **测试策略与风险分级**
   - 需求可测试性、风险矩阵、测试优先级；
   - 版本准入/准出、回归策略、风险接受。

3. **测试设计方法**
   - 等价类、边界值、判定表、状态迁移、场景法、组合测试；
   - 机器人任务链测试：感知→决策→规划→控制→执行；
   - 长尾场景、动态障碍、传感器失效、通信降级。

4. **测试预言与量化指标**
   - 规格 oracle、参考模型 oracle、蜕变 oracle、统计 oracle；
   - 成功率、终点误差、路径长度、耗时、碰撞率、恢复成功率、延迟、抖动、漂移；
   - 单次阈值 vs N 次统计；均值 vs P95/P99 vs worst-case。

5. **覆盖率与缺陷管理**
   - 需求覆盖、代码覆盖、场景覆盖、风险覆盖、接口覆盖；
   - 缺陷分类、RCA、逃逸分析、证据链；
   - 缺陷生命周期与质量度量。

6. **实验设计与统计**
   - 重复次数、样本量、置信区间、flakiness；
   - 变异来源：环境、负载、温度、传感器噪声、操作者；
   - 指标可视化：箱线图、P95/P99、漂移曲线、热力图。

7. **标准与评价地图**
   - 通用：ISO/IEC/IEEE 29119、ISTQB 术语；
   - 汽车：ASPICE、ISO 26262、ISO 21434、ISO 14229、ISO 11898；
   - 机器人：ISO 10218-1/-2、ISO/TS 15066、ISO 3691-4、ISO 13482、ISO 12100、ISO 13849-1、IEC 62061/IEC 61508；
   - 机器人测试评价：性能、可靠性、EMC、安全、智能化评价、认证/市场准入；
   - 关键区别：汽车 ASIL vs 机器人 PL/SIL，不能直接等同。

**实验/作业：**

- 把一份真实车载测试计划改写为《机器人整机测试策略》；
- 建立《机器人测试指标字典》；
- 建立《标准适用性地图》；
- 用 2 个真实缺陷做 RCA 改写。

**考核：** 测试策略 40%，指标字典 30%，标准地图 30%。

---

### M2. 工程基础：Python / Linux / Git / C++ 阅读（20 学时）

**目标：** 具备测试开发所需的工程能力；Python 为主，C++ 只要求阅读/修改。

**内容：**

1. **Python 核心**
   - 数据结构、函数、异常、上下文管理器；
   - 类、继承、组合、dataclass；
   - 文件/JSON/YAML/CSV、路径、日志、argparse、subprocess；
   - 类型标注、虚拟环境、依赖管理、代码风格；
   - 并发基础：threading/asyncio（概念与应用场景）。

2. **Python 测试生态**
   - pytest：fixture、parametrize、marker、conftest、插件；
   - mock/fake/stub 的边界；
   - 数据驱动测试、报告生成、覆盖率；
   - 常用库：pandas、numpy、matplotlib、requests、pyserial、python-can。

3. **Linux**
   - 文件/权限/进程/服务；
   - 日志：journalctl、dmesg、tail、grep、awk、sed；
   - 网络：ip、ss、ping、traceroute、tcpdump、iperf3；
   - Shell 脚本、cron、环境变量；
   - Docker 基础：镜像、容器、卷、网络、compose。

4. **Git**
   - branch/commit/merge/rebase、PR、code review、tag；
   - 冲突解决、提交规范、测试数据管理。

5. **C++ 阅读（可选，按目标岗位）**
   - 指针/引用、const、RAII、构造/析构；
   - STL、类、继承、虚函数、模板基本概念；
   - CMake、gtest/gmock 阅读与修改；
   - gdb/lldb 查看崩溃栈。

**实验/作业：**

- CAN 日志解析脚本；
- pytest 测试项目（fixture + 参数化 + 报告）；
- Linux 故障排查 playbook（10 个场景）；
- 读懂并修改一个 ROS2 C++ 测试/节点（可选）。

**考核：** Python 脚本 40%，pytest 项目 30%，Linux playbook 30%。

---

### M3. 自动化测试与测试框架（20 学时）

**目标：** 能解释、重构并扩展既有测试框架；能接入 CI/CD。

**内容：**

1. **框架分层**
   - 用例层、夹具/环境层、适配层、激励层、断言/预言层、证据层、调度层、集成层；
   - 数据与代码分离、配置管理、环境复位。

2. **设计模式与可维护性**
   - Adapter、Factory/Builder、Data-driven、Keyword-driven、Plugin；
   - 反模式：硬编码、隐式等待、全局状态、无清理、断言缺失。

3. **AI 辅助框架的“去黑盒化”**
   - 逐文件回读、依赖分析、数据流；
   - 识别 AI 生成风险：不存在的 API、过度抽象、复制粘贴、异常处理缺失、硬编码路径；
   - 自己重写核心模块、给框架加单元测试、记录设计决策与局限。

4. **机器人适配层**
   - `DutAdapter` 接口设计；
   - CAN mock、ROS2 mock/最小实现；
   - 发布/订阅、服务调用、bag 读取；
   - 明确区分“学习实验”与“生产项目”。

5. **测试数据、证据与报告**
   - 用例数据、日志、bag、截图、波形、报告的统一命名与归档；
   - HTML/Markdown 报告、趋势看板、失败分类。

6. **CI/CD**
   - 流水线：lint → unit → integration → HIL smoke → regression → report；
   - Jenkins/GitLab CI/GitHub Actions 任选其一；
   - pytest 集成、制品归档、失败通知、并行/缓存；
   - HIL 资源锁、夜间回归、flaky test 隔离。

**实验/作业：**

- 画出现有框架架构图；
- 完成一次重构（至少 3 个 commit）并为框架加单元测试；
- 增加 CAN mock 与 ROS2 mock 两个 adapter；
- 建一条可运行的 CI 流水线；
- 写一份框架 README 与局限说明。

**考核：** 架构图 20%，重构 30%，适配层 25%，CI 流水线 25%。

---

### M4. 机器人系统通识与 ROS2（26 学时）

**目标：** 建立机器人系统地图；能看懂 ROS2 数据流、TF、QoS 和仿真；能设计系统级测试。

#### M4.1 机器人系统架构通识（8 学时）

**内容：**

- 机器人分类：工业机械臂、移动机器人/AGV、协作机器人、四足、人形；
- 系统分解：感知、定位/建图、规划、控制、执行、安全、计算、通信；
- 硬件：计算平台、传感器、执行器、电源、机械结构、安全器件；
- 软件：分层架构、状态机、行为树、生命周期、组件组合；
- 通信：ROS2/DDS、CAN/CANopen、EtherCAT、Ethernet、串口/SPI/I2C；
- 实时性与计算：控制周期、抖动、延迟、CPU/GPU 负载；
- 安全：急停、安全 PLC、限速/限力、碰撞检测、安全状态、降级；
- 集成与故障传播：上电、标定、模式切换、异常恢复。

**产出：** 一页《机器人系统框图》，标出 10–15 个测试观测点；一张《子系统—测试点—指标—证据》矩阵。

#### M4.2 ROS2 核心（8 学时）

**内容：**

- Node、Topic、Service、Action、Parameter、Launch；
- Lifecycle、Composition、Executor（概念）；
- ROS2 CLI：node/topic/service/action/param/launch/doctor；
- QoS：reliability/durability/history/depth；
- TF2：坐标系、变换、时间戳；
- rosbag2：录制/回放/截取；
- RViz2、RQt、Foxglove、PlotJuggler；
- DDS 发现、domain ID、multicast/unicast、共享内存。

**产出：** 《ROS2 测试命令速查 + 数据流排查手册》；3 个故障实验（QoS 不匹配、domain 冲突、网络丢包）。

#### M4.3 机器人建模、仿真与导航（6 学时）

**内容：**

- URDF/Xacro、link/joint、TF 树；
- Gazebo/Isaac Sim/MuJoCo 的定位差异；
- 传感器模型、物理参数、场景搭建；
- SLAM/Nav2 测试视角：建图、定位、规划、控制、恢复；
- 指标：定位误差、终点误差、路径长度、耗时、碰撞、重规划、恢复成功率；
- sim2real gap：摩擦、光照、噪声、延迟、执行器差异。

**产出：** Gazebo/TurtleBot3 最小实验（明确标注“学习实验”）；《Nav2 测试场景与指标表》。

#### M4.4 机器人运动/传感基础（4 学时）

**内容：**

- 坐标系与空间变换（概念）；
- 正/逆运动学（概念，不推导）；
- PID：P/I/D 作用、阶跃响应、超调、稳态误差；
- 轨迹跟踪、速度/加速度限制；
- 电机、减速器、编码器、伺服驱动；
- 相机、LiDAR、IMU、力/触觉传感器的测试关注点；
- 标定、时间同步、外参。

**产出：** 《传感器/执行器测试项清单》；能看懂位置/速度/电流曲线并判断振荡、超调、饱和、延迟。

**M4 考核：** 系统框图 30%，ROS2 手册/实验 30%，仿真/导航指标 20%，传感器/执行器清单 20%。

---

### M5. HIL/SIL、总线通信与安全（24 学时）

**目标：** 能设计机器人 HIL/SIL 测试方案，覆盖总线、实时性、故障注入和安全验证。

#### M5.1 HIL/SIL 架构（8 学时）

**内容：**

- SIL、HIL、MIL、真机的区别与分工；
- HIL 台架组成：实时仿真机、I/O 板卡、信号调理、故障注入单元、被测控制器；
- plant model：电机、编码器、执行器、机器人动力学；
- 传感器仿真：相机/LiDAR/IMU/力；
- 测试执行器、报告、资源管理；
- 台架安全：急停、限流、隔离、接地；
- 实时性：周期、抖动、延迟、deadline；
- 时间同步：PTP/IEEE 1588、gPTP/802.1AS、硬件触发。

**产出：** 《机器人关节/控制器 HIL 台架方案》；《实时性/时间同步测试清单》。

#### M5.2 总线与通信（8 学时）

**内容：**

- CAN/CAN FD：帧、ID、DLC、仲裁、错误帧、总线负载、终端电阻；
- DBC、CANoe/CAPL、python-can/SocketCAN；
- UDS：诊断会话、DTC、DID、例程；
- CANopen：PDO/SDO/NMT、心跳；
- Ethernet：IP/子网/VLAN、TCP/UDP、multicast、QoS、PTP；
- 抓包：tcpdump/Wireshark 过滤、延迟/丢包/重传；
- ROS2 DDS over Ethernet：domain、discovery、QoS、共享内存；
- EtherCAT：主/从、PDO/SDO、分布式时钟、CoE、实时性；
- 串口/SPI/I2C/Modbus（按需）。

**产出：** 《CAN/CANopen 测试清单》《Ethernet/DDS 测试清单》《EtherCAT 概念验证记录》；3 个抓包/注入实验。

#### M5.3 故障注入、FuSa 与机器人安全（8 学时）

**内容：**

- 故障模型：传感器（卡死/漂移/噪声/断线/时间戳异常）、执行器（卡死/限幅/过温）、通信（丢包/延迟/乱序/错误帧）、电源（跌落/断电）、环境（温度/振动）；
- 注入方式：硬件 FIU、总线注入、软件注入、环境注入；
- 安全验证：安全状态、降级、告警、恢复、诊断覆盖率；
- FMEA/FTA、故障传播链、残余风险；
- 汽车 ISO 26262/ASIL vs 机器人 ISO 10218/TS 15066/ISO 3691-4/ISO 13849/IEC 61508（PL/SIL）；
- 机器人测试评价：性能、可靠性、EMC、安全、智能化评价、认证/市场准入；
- 证据：注入时间、预期、实际、恢复、残余风险。

**产出：** 《故障注入案例集》（把汽车 FuSa 项目改写为机器人关节/通信/急停场景）；《机器人安全测试清单》。

**M5 考核：** HIL 方案 30%，总线清单/实验 30%，故障注入案例 25%，安全清单 15%。

---

### M6. 项目迁移、Capstone 与职业表达（8 学时）

**目标：** 把真实车载项目转化为机器人测试能力证据，完成可演示的 Capstone。

**内容：**

- 项目盘点：3–5 个真实项目；
- 迁移矩阵：车载活动 → 机器人对应 → 可复用方法 → 差异 → 证据缺口；
- 案例写作：STAR + 证据 + 量化结果 + 迁移反思；
- 简历三版：整机/系统、HIL/测试开发、硬件/部件；
- 面试题库与模拟面试；
- “没有机器人经验”的标准回答；
- AI 使用与学术诚信。

**Capstone（详见第七节）：**

- 以真实车载项目为主证据；
- 可选一个 ROS2/Gazebo 或虚拟 CAN 学习实验，但必须标注“学习实验”；
- 产出测试包 + 10 分钟答辩。

**考核：** 迁移矩阵 20%，3 个案例 30%，Capstone 30%，答辩 20%。

---

## 六、教学安排（建议 12 周）

| 周 | 模块 | 主题 | 实验/作业 |
|---:|---|---|---|
| 1 | M0/M1 | 课程导入、能力诊断、V&V、测试策略 | 能力自评、项目盘点、测试策略草稿 |
| 2 | M1 | 测试设计、oracle、指标、统计、标准地图 | 指标字典、标准地图、RCA 改写 |
| 3 | M2 | Python 核心、pytest 入门 | CAN 日志解析、pytest 练习 |
| 4 | M2 | Linux、Git、网络排查、C++ 阅读（可选） | Linux playbook、Git 仓库 |
| 5 | M3 | 框架分层、架构复盘、重构 | 架构图、重构 commit、框架单测 |
| 6 | M3 | 适配层、报告、CI/CD、flaky test | CAN/ROS2 mock adapter、CI 流水线 |
| 7 | M4 | 机器人系统通识（硬件/软件/通信/安全） | 系统框图、测试点矩阵 |
| 8 | M4 | ROS2 核心、TF/QoS/rosbag、Gazebo、Nav2 | ROS2 手册、3 个故障实验、导航指标 |
| 9 | M5 | HIL/SIL 架构、plant model、I/O、时间同步 | HIL 台架方案、实时性清单 |
| 10 | M5 | CAN/CANopen/UDS、Ethernet/DDS、EtherCAT | 总线测试清单、抓包/注入实验 |
| 11 | M5 | 故障注入、FuSa、机器人安全、测试评价 | 故障注入案例、安全清单 |
| 12 | M6 | 迁移矩阵、案例、Capstone、模拟面试 | Capstone 提交与答辩 |

> 若每周只有 8 小时，建议扩展到 15–16 周，优先保留 M4/M5 的实验。

---

## 七、Capstone：机器人系统测试包

### 7.1 目标

在不虚构机器人项目的前提下，证明学习者具备机器人整机/系统测试与 HIL/SIL 测试开发能力。

### 7.2 必交成果

1. **系统图与测试地图**：机器人系统框图 + 10–15 个观测点/注入点；
2. **测试策略与用例**：至少 15 条用例，覆盖正常、边界、异常、恢复、安全；
3. **测试框架适配**：复用/重构既有框架，提供 CAN mock 与 ROS2 mock 两个 adapter；
4. **HIL/SIL 方案**：关节/控制器 HIL 台架方案，含 I/O、plant model、时间同步、故障注入、台架安全；
5. **故障注入矩阵**：至少 5 类故障（传感器、执行器、通信、电源、环境）；
6. **指标与报告**：至少 5 个指标，含定义、采集方法、通过标准、证据；
7. **真实项目迁移案例**：3 个，每个 1 页，含 STAR、证据、量化结果、迁移反思；
8. **10 分钟答辩**：能讲清“测什么、怎么测、证据在哪、和机器人有什么关系”。

### 7.3 评分 rubric

| 维度 | 权重 | 优秀（90–100） | 合格（60–79） | 不合格（<60） |
|---|---:|---|---|---|
| 系统理解 | 20% | 能解释数据流、接口、故障传播 | 能画出框图，但接口不清 | 只罗列部件 |
| 测试设计 | 25% | 风险驱动、覆盖完整、oracle 清晰 | 有用例，但覆盖/判定一般 | 只写步骤，无判定 |
| 工程实现 | 20% | 框架可运行、可扩展、有测试 | 能跑，但耦合/缺测试 | 不能复现 |
| HIL/SIL/总线 | 20% | 方案完整，含实时性/故障注入/安全 | 有方案，但细节不足 | 只堆概念 |
| 证据与表达 | 15% | 证据链完整，答辩清晰 | 有证据，表达一般 | 无证据/夸大数据 |

### 7.4 学术与项目诚信

- 真实车载项目为主证据；机器人侧实验必须标注“学习实验”；
- 禁止虚构机器人量产经验、指标或缺陷；
- AI 可用于起草/调试，但必须逐行理解、测试、披露；
- 引用课程/公开资料需注明来源。

---

## 八、考核方式

| 考核项 | 权重 | 说明 |
|---|---:|---|
| 诊断与课程参与 | 5% | 能力自评、项目盘点、课堂/讨论参与 |
| 模块实验/作业 | 25% | M1–M5 的实验与产出 |
| 案例作品集 | 25% | 3 个真实项目迁移案例 |
| Capstone | 30% | 机器人系统测试包 |
| 答辩/面试 | 15% | 10 分钟演示 + 问答 |

**通过标准：** 总分 ≥60%，且 Capstone ≥60%，且无学术诚信违规。

---

## 九、参考资源

### 9.1 课程大纲/课程参考

1. Johns Hopkins University, **Robotic Systems Development with ROS 2 (665.785)**：ROS2 架构、节点通信、仿真、软件工程实践、期末项目。  
   <https://ep.jhu.edu/courses/665785-robotic-systems-development-with-ros-2/>
2. Kookmin University, **Operating Systems Practice (ROS2, Fall 2025)**：ROS2、TF2、Gazebo、SLAM、路径规划、真实机器人。  
   <https://mairlab-km.github.io/courses/operating-systems-practice-2025fall>
3. Télécom Paris, **IA712 Mobile Robotics Project**：机器人软件架构、通信协议、软硬件集成、DDS、Nav2。  
   <https://synapses.telecom-paris.fr/catalogue/2025-2026/ue/13715/IA712-projet-robotique-mobile?from=P5291>
4. MIT OpenCourseWare, **2.12 Introduction to Robotics**：机构、动力学、控制、传感器、执行器、嵌入式、导航、腿足/多指/遥操作。  
   <https://ocw.mit.edu/courses/2-12-introduction-to-robotics-fall-2005/pages/syllabus/>
5. Stanford, **CS223A / ME320 Introduction to Robotics**：空间变换、正逆运动学、雅可比、动力学、力控、视觉伺服。  
   <https://cs.stanford.edu/groups/manips/teaching/cs223a/>
6. CMU, **16-311 Introduction to Robotics**：控制、运动学、规划、定位、视觉、神经网络、RL、电机/通信、电池/原型。  
   <https://github.com/CMU-HKN/CMU-ECE-CS-Guide/blob/master/electives/16311.md>
7. **ROS 2: Zero to Robot**：20 章项目制课程，覆盖 ROS2、TF2、Gazebo、ros2_control、Nav2、MoveIt2、多机器人、Jetson/ESP32、CAN/EtherCAT、sim-to-real。  
   <https://zenodo.org/records/21921426>
8. UC Merced, **Mobile Robotics**：ROS2 节点/话题/服务/Action、TF2、rosbag、Nav2。  
   <https://robotics.ucmerced.edu/sites/g/files/ufvvjh1576/f/page/documents/mrtp.pdf>

### 9.2 HIL/SIL 与测试参考

9. Vector Academy, **HIL and SIL Tests with CANoe**：CANoe HIL 环境、VT System、XCP、诊断、CAPL/Python 测试单元、SIL Adapter、CI/CT。  
   <https://academy.vector.com/jp/en/courses/detail/10090/hil-and-sil-tests-with-canoe>
10. NI, **HIL Test Courses**：VeriStand、HIL 系统设计、SLSC、CAN/LIN、Restbus。  
    <https://www.ni.com/en/shop/services/education-services/hil-test-courses.html>
11. Tonex, **Fundamentals of SIL & HIL Testing**：SIL/HIL 原理、测试框架、故障注入、压力测试、行业应用。  
    <https://www.tonex.com/training-courses/fundamentals-of-software-in-the-loop-sil-hardware-in-the-loop-hil-testing-training/>
12. University of Maryland, **ENTE603 Human Robotics Teaming in DTEVV**：自主系统开发、测试与评估、验证与确认。  
    <https://www.academiccatalog.umd.edu/search/?P=ENTE603>
13. ATI, **Applied Test and Evaluation**：T&E 原则、生命周期、验证矩阵、统计测试设计、集成测试、机器人测试挑战。  
    <https://aticourses.com/courses-2/13-applied-test-and-evaluation/>
14. 上海《机器人测试评价体系及关键技术》课程：机器人标准、安全、EMC、可靠性、性能/智能化评价、市场准入。  
    <https://edu.sheitc.sh.gov.cn/course/MDAwMDAwMDA4ZGQ0NjZhODAxOGRkNDZlMTAzOTAwMWE=.htm>

### 9.3 标准与工具文档

- ISO 10218-1/-2（工业机器人安全，2025 版）
- ISO/TS 15066（协作机器人，修订中）
- ISO 3691-4（AGV/无人叉车）
- ISO 13482（个人护理机器人）
- ISO 12100（风险评估）
- ISO 13849-1（PL）、IEC 62061/IEC 61508（SIL）
- ISO 26262（道路车辆功能安全）、ISO 21434（汽车网络安全）
- ROS2 官方文档：<https://docs.ros.org/>
- Gazebo：<https://gazebosim.org/>
- Nav2：<https://docs.nav2.org/>
- EtherCAT Technology Group：<https://www.ethercat.org/>
- CANopen：<https://www.can-cia.org/>
- Wireshark：<https://www.wireshark.org/>

---

## 十、课程政策

### 10.1 AI 使用政策

- 允许使用 AI 辅助查资料、起草代码、解释概念、生成测试数据；
- 所有 AI 生成代码必须逐行理解、运行、测试，并在提交中注明使用范围；
- 不得用 AI 伪造项目经历、测试结果、缺陷或指标；
- 答辩时可能要求解释任意一行代码/任意一个测试判定。

### 10.2 硬件与台架安全

- 真实机器人/电机/台架测试必须在受控环境、低速/空载/限流/急停条件下进行；
- 涉及高压、大电流、运动部件、人机协作的测试，必须由具备资质的人员监督；
- 优先仿真/虚拟台架；无安全条件不做危险实验。

### 10.3 学术诚信与数据隐私

- 引用课程、文档、论文、开源代码需注明来源；
- 公司项目数据需脱敏，遵守保密协议；
- 禁止虚构机器人量产经验或冒用他人项目。

### 10.4 版本与提交

- 所有代码/文档使用 Git 管理；
- 每个模块提交 README、运行说明、证据目录；
- 迟交需提前说明，Capstone 不接受无故迟交。

---

## 附录 A：与公开课程大纲的对照与优化说明

| 公开课程/大纲 | 可借鉴内容 | 本课程处理 |
|---|---|---|
| JHU 665.785 Robotic Systems Development with ROS 2 | ROS2 架构、节点通信、仿真、软件工程实践、期末项目 | 纳入 M4；增加软件架构/生命周期/行为树概念；Capstone 对应期末项目 |
| Kookmin Operating Systems Practice (ROS2) | 周计划：ROS2 → TF2 → Gazebo → 传感器 → SLAM → 路径规划 → 真机 | 纳入 M4；保留“系统→仿真→导航”的顺序，但不要求真机 |
| Télécom Paris IA712 | 机器人软件架构、通信协议、软硬件集成、DDS、Nav2 | 纳入 M4.1/M4.2；增加“软件架构”与“硬件-软件接口”内容 |
| MIT 2.12 / Stanford CS223A / CMU 16-311 | 运动学、动力学、控制、传感器、执行器、实验室/项目 | 只保留测试所需的概念（坐标系、PID、电机/编码器、传感器），不推导公式；保留实验 |
| Vector HIL/SIL with CANoe | HIL 环境、VT System、XCP、诊断、CAPL/Python、SIL Adapter、CI/CT | 纳入 M5；增加 CANoe/CAPL、HIL 测试执行、CI 集成 |
| NI HIL Test Courses | VeriStand、HIL 系统设计、SLSC、CAN/LIN、Restbus | 纳入 M5.1；作为工具选型参考，不绑定厂商 |
| Tonex SIL/HIL Fundamentals | SIL/HIL 原理、测试框架、故障注入、压力测试 | 纳入 M5；增加故障注入矩阵与安全验证 |
| UMD ENTE603 / ATI Applied T&E | V&V、DTEVV、验证矩阵、统计测试设计、集成测试 | 纳入 M1；增加 V&V 语言、验证矩阵、统计 |
| 上海《机器人测试评价体系及关键技术》 | 标准、安全、EMC、可靠性、性能/智能化评价、认证 | 纳入 M1.7/M5.3；增加“机器人测试评价与认证” |
| ROS 2: Zero to Robot / UC Merced Mobile Robotics | ROS2 全链路、TF2、Gazebo、Nav2、ros2_control、sim-to-real | 纳入 M4；增加 ros2_control/MoveIt2 概念（按需） |

**对照后发现的主要优化点（已纳入本大纲）：**

1. **补课程化要素**：课程信息、学时、先修、学习成果、考核、Capstone、课程政策；
2. **补机器人软件架构**：分层、状态机、行为树、生命周期、组件组合、软硬件接口；
3. **补机器人测试评价/认证**：性能、可靠性、EMC、安全、智能化评价、市场准入；
4. **补统计与实验设计**：重复次数、置信区间、flakiness、P95/P99；
5. **补 Capstone 与评分 rubric**：让课程有可验收的最终成果；
6. **补 AI 使用与项目诚信政策**：对应你“AI 辅助搭框架”的实际背景；
7. **调整数学深度**：保留运动学/动力学/控制的概念和测试含义，不要求推导；
8. **明确“真实项目优先、概念实验标注”**：不虚构机器人项目。

---

## 附录 B：车载经验 → 机器人测试迁移矩阵（课程作业模板）

| 车载经验 | 机器人对应 | 可复用方法 | 需要补的差异 | 证据形式 |
|---|---|---|---|---|
| 车身控制器 HIL | 机器人控制器/关节 HIL | 台架、闭环、故障注入、安全状态 | 机器人 I/O、plant model、实时性、EtherCAT | 台架方案、波形、注入记录 |
| CAN/LIN 网络与诊断 | CAN/CANopen/EtherCAT、DDS | 帧分析、DBC、UDS、总线负载、错误帧 | CANopen PDO/SDO、EtherCAT、DDS QoS | 抓包、测试清单、缺陷报告 |
| 传感器/执行器测试 | IMU/相机/LiDAR/编码器/电机 | 量程、精度、漂移、响应、失效模式 | 标定、时间同步、多传感器融合 | 测试数据、曲线、标定记录 |
| EMC/环境/耐久 | 机器人可靠性/环境适应 | 测试矩阵、失效分析、寿命 | 机器人运动工况、安全标准 | 测试计划、失效分析 |
| 故障注入/FuSa | 机器人 HIL 故障注入/安全 | 故障模型、FIU、安全状态、诊断覆盖 | ISO 10218/TS 15066/ISO 3691-4 | 故障矩阵、安全案例 |
| 量产/售后问题 | 机器人 NPI/现场交付 | 8D、RCA、回归、版本管理 | 现场场景、OTA、远程运维 | 复盘报告、回归记录 |
| AI 辅助测试框架 | 机器人测试框架 | 分层、适配器、报告、CI | ROS2/CAN 适配、实时性 | 架构图、代码、CI 记录 |

---

## 附录 C：课程完成检查清单

- [ ] 能画出一页机器人系统框图，标出 10–15 个测试点；
- [ ] 能解释 ROS2 Node/Topic/Service/Action/TF/QoS/rosbag；
- [ ] 能设计 15 条以上机器人系统测试用例，含 oracle 和指标；
- [ ] 能写 pytest 自动化并接入 CI；
- [ ] 能解释并重构一个测试框架；
- [ ] 能设计一个关节/控制器 HIL 台架方案；
- [ ] 能设计 CAN/Ethernet/EtherCAT/DDS 测试清单；
- [ ] 能设计 5 类故障注入并验证安全状态；
- [ ] 能区分 ISO 26262 与机器人安全标准；
- [ ] 能完成 3 个真实项目迁移案例；
- [ ] 能 10 分钟讲清 Capstone，不虚构机器人经验。

---

**课程设计说明：** 本大纲以“机器人系统通识”为骨架，以“测试方法 + 工程基础 + 自动化框架 + HIL/SIL/总线 + 项目迁移”为五条主线。它参考了 JHU、Kookmin、Télécom Paris、MIT、Stanford、CMU 的机器人课程结构，以及 Vector、NI、Tonex 的 HIL/SIL 培训大纲；同时刻意压缩了数学推导和算法开发，把学时留给测试设计、HIL/SIL、总线、故障注入和项目表达。

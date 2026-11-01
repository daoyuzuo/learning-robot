# 5. ROS2 与机器人软件

> 分册索引：[README.md](README.md)　|　标记：**核心** = 目标岗位直接需要；**扩展** = 面试/岗位加分；**可选** = 按方向选学。

## 5.1 ROS2 核心

- Node、Topic、Service、Action、Parameter、Launch
- Lifecycle、Composition、Executor（概念）
- ROS2 CLI：node/topic/service/action/param/launch/doctor
- **核心**

## 5.2 QoS 与 DDS

- reliability/durability/history/depth
- DDS 发现：multicast/unicast、domain ID
- 共享内存/网络传输
- QoS 不匹配的典型现象
- **核心**

## 5.3 TF2 与 URDF

- link/joint、parent/child、base_link
- 静态/动态 TF、时间戳
- URDF/Xacro
- **核心**

## 5.4 工具链

- rosbag2：录制/回放/截取
- RViz2、RQt、Foxglove、PlotJuggler
- **核心**

## 5.5 仿真

- Gazebo/Isaac Sim/MuJoCo 的定位差异
- 场景、传感器模型、物理参数
- sim2real gap：摩擦、光照、噪声、延迟、执行器差异
- **扩展**

## 5.6 导航与 SLAM（测试视角）

- 建图、定位、全局规划、局部规划、恢复
- 指标：定位误差、终点误差、路径长度、耗时、碰撞、重规划、恢复成功率
- 场景：窄通道、动态障碍、死胡同、不可达、低纹理
- **扩展**

## 5.7 ros2_control / MoveIt2（概念）

- controller manager、hardware interface
- 机械臂规划、抓取、手眼标定
- **可选**

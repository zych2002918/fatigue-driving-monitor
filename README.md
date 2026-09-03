# fatigue-driving-monitor

**多源信息融合疲劳驾驶实时预警装置 —— 论文源码级复现**

基于《多源信息融合的疲劳驾驶实时预警装置》技术论文（第二十一届中国研究生电子设计竞赛，大连交通大学，2026-06）从论文规格重建的可运行工程。

**计算机视觉(面部特征) + 驾驶行为(方向盘) 双通道异构信息融合 → 多级预警。**

> ⚠️ 本仓库为竞赛技术论文的开源复现，不含原参赛队任何未公开代码/固件。原作品为硬件实物（STC89C52 + GY-25 + 薄膜压力传感器等）；本工程以 **PC 软件实现视觉通道、以软件模拟行为通道**，并提供 8051 固件参考（`firmware/`）。论文见 `docs/`（或参照原论文）。

---

## 功能

- **视觉通道**（论文第四章）
  - Dlib 68 点人脸关键点 → 实时计算 **EAR**（式 4-1 眼纵横比）与 **MAR**（式 4-2 嘴纵横比）
  - 眨眼计数、闭眼连续帧判定、哈欠事件、哈欠频率
  - Head Pose Estimation（solvePnP）→ 欧拉角 → **瞌睡点头**检测
  - 参数与论文标定一致：`EAR<0.23` 闭眼、`MAR>0.3` 哈欠、`|Pitch|/|Roll|>=20°` 姿态异常、10s 窗口异常占比>30% 判瞌睡
- **行为通道**（论文 3.2.7，软件模拟/可替换）
  - 方向盘握力（压力传感器）、转角（GY-25）、累计驾驶时长
  - 规则：无握力→立即报警；有握力但 3s 无转角→蜂鸣，30s→风扇；驾驶时长超限→语音+声光
- **融合决策**：30 秒窗口内 眨眼/哈欠/点头 计数超限 → 疲劳（SLEEP）报警（论文 5.2 测试口径）
- **GUI**（WxPython，论文图 4-7）：视频预览 + 实时 EAR/MAR/角度 + 事件计数 + 行为通道状态 + 报警日志
- **固件参考**：`firmware/main.c` 8051 C（对照论文引脚与逻辑）
- 无摄像头时可用 **`--headless` / 行为通道脚本** 演示完整报警链路

---

## 快速开始

```bash
# 1. 创建虚拟环境并安装
python -m venv .venv
.venv\Scripts\activate            # Windows
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

#   注：Windows + Python 3.11 下 dlib 无官方 cp311 wheel，requirements
#   自动使用 dlib-bin（预编译）；若 dlib-bin 不可用，也可直接:
#   pip install dlib-bin

# 2. 下载 68 点人脸模型（~100MB）放入 models/
#    http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2
#    （解压得到 shape_predictor_68_face_landmarks.dat）

# 3a. GUI 运行（需摄像头）
python main.py

# 3b. 无摄像头：行为通道报警链路演示（推荐先跑）
python scripts/demo_behavior.py

# 3c. 测试
python -m unittest discover -s tests
```

---

## 目录

```
fatigue-driving-monitor/
├── fatigue/
│   ├── config.py      # 全部阈值（对照论文标定值）
│   ├── features.py    # EAR/MAR 几何计算 + 头部姿态估计
│   ├── vision.py      # Dlib/OpenCV 视觉分析（眨眼/哈欠/瞌睡事件）
│   ├── behavior.py    # 行为通道模拟 + 状态机（论文 3.2.7）
│   ├── fusion.py      # 双通道融合决策
│   ├── alarm.py       # 分级报警输出（蜂鸣/日志/TTS）
│   └── gui.py         # WxPython 可视化界面
├── firmware/main.c    # STC89C52 固件参考（8051 C）
├── scripts/demo_behavior.py  # 无摄像头演示
├── tests/             # 单元测试
├── models/            # 放 shape_predictor_68_face_landmarks.dat
└── main.py            # 入口
```

---

## 复现说明（与论文的对应关系）

| 论文章节 | 本实现 |
|---|---|
| 4.1.1 OpenCV 预处理（灰度/直方图均衡） | `vision.py` gray+equalizeHist |
| 4.2.1 EAR / 式4-1 | `features.eye_aspect_ratio` |
| 4.2.3 MAR / 式4-2 | `features.mouth_aspect_ratio` |
| 4.2.2 闭眼判定（EAR<0.23 连续10帧） | config `eye_ar_thresh/consec_frames` |
| 4.2.4 头部姿态（solvePnP, |Pitch/Roll|>=20°, 10s窗口30%） | `features.estimate_head_pose` |
| 5.2 30s窗口综合判定（眨眼/哈欠/点头） | `fusion.evaluate` 事件计数 |
| 3.2.7 行为通道报警逻辑 | `behavior.BehaviorAnalyzer` |
| 3.2 硬件（STC89C52/GY-25/压力/LCD/ISD1820） | `firmware/main.c` 参考 |

> **复现边界**：原作品硬件行为通道以软件模拟（`SimulatedBehavior`）替代，
> 保证无硬件时全链路可运行；如需真实串口/单片机，替换 `BehaviorSource`
> 并参考 `firmware/`。

---

## 开源说明

本项目是对已发表竞赛论文的**独立复现**，用于作品展示与学习交流，不含原队未公开内容。若需用于新的竞赛投稿/论文，请注意与原文的区分与扩展（改写幅度、新实验），遵守学校与期刊关于重复使用的规定。

MIT License

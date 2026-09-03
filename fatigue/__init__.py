# -*- coding: utf-8 -*-
"""fatigue-driving-monitor 包。

多源信息融合疲劳驾驶实时预警装置 —— 论文源码级复现。
视觉通道(EAR/MAR/头部姿态) + 行为通道(握力/转角/驾驶时长) 双通道融合。
"""
from .config import FatigueConfig, EYE_AR_THRESH, MOUTH_AR_THRESH  # noqa
from .vision import VisionAnalyzer, FrameMetrics  # noqa
from .behavior import SimulatedBehavior, BehaviorAnalyzer, BehaviorSample  # noqa
from .fusion import FusionEngine, FusionStatus  # noqa
from .alarm import WinsoundAlarmer, ConsoleAlarmer  # noqa

__version__ = "1.0.0"

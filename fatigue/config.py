# -*- coding: utf-8 -*-
"""全局阈值与参数配置。

所有阈值均取自《多源信息融合的疲劳驾驶实时预警装置》技术论文
（第二十一届中国研究生电子设计竞赛, 2026-06）第四章的实验标定值，
便于后续按论文口径复现与调参。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# 视觉通道阈值（论文 4.2 节标定）
# ---------------------------------------------------------------------------

#: 眼睛纵横比阈值：EAR < EYE_AR_THRESH 视为闭眼（论文：正常约 0.23，低于 0.23 判定闭合）
EYE_AR_THRESH = 0.23
#: 连续闭眼帧数阈值：连续闭合超过该帧数即可靠判定为疲劳闭眼
EYE_AR_CONSEC_FRAMES = 10

#: 嘴部纵横比阈值：MAR > MOUTH_AR_THRESH 视为哈欠事件（论文：正常人嘴部 MAR 均值 0.3 时为哈欠状态）
MOUTH_AR_THRESH = 0.3

#: 头部姿态异常角阈值（度）：|Pitch| 或 |Roll| >= HEAD_POSE_ANGLE_THRESH 视为异常姿态
HEAD_POSE_ANGLE_THRESH = 20.0
#: 瞌睡点头观察窗口（秒）：论文以 10 秒为观察窗口
HEAD_POSE_WINDOW_SEC = 10.0
#: 窗口内异常姿态累计时长占比阈值：超过 30% 判定瞌睡
HEAD_POSE_ABNORMAL_RATIO = 0.30

#: 眨眼判定：EAR 由低回升记为一次眨眼
BLINK_MIN_LOW_FRAMES = 2

#: 哈欠频率窗口（秒）与报警阈值（次/分钟）
YAWN_WINDOW_SEC = 60.0
YAWN_ALARM_PER_MIN = 5          # 论文 5.2 测试示例约 20 次/30s 远超阈值

#: 综合疲劳判定窗口（论文 5.2 测试：30 秒窗口内统计）
FATIGUE_SCORE_WINDOW_SEC = 30.0
# 30 秒窗口内事件计数报警阈值（论文测试示例：眨眼 11 / 哈欠 20 / 点头 30 -> 判疲劳）
EVENT_BLINK_LIMIT_30S = 25      # 清醒者 30s 内通常 < 15 次
EVENT_YAWN_LIMIT_30S = 6
EVENT_NOD_LIMIT_30S = 8

# ---------------------------------------------------------------------------
# 行为通道阈值（论文 3.2.7 / 5.2 节逻辑）
# ---------------------------------------------------------------------------

#: 无握力 -> 立即报警（蜂鸣 + 风扇）
#: 有握力但 3 秒内无转角变化 -> 蜂鸣；持续 30 秒无变化 -> 加风扇
HANDS_OFF_ALARM = True
NO_STEER_BUZZ_SEC = 3.0
NO_STEER_FAN_SEC = 30.0
#: 累计驾驶时长（秒）阈值，超时强制语音提示停车休息（默认 2 小时）
DRIVE_TIME_LIMIT_SEC = float(os.environ.get("FDM_DRIVE_LIMIT_SEC", 2 * 3600))
#: 模拟转角幅度小于该值视为"无变化"（度）
STEER_ANGLE_EPS_DEG = 1.0

# ---------------------------------------------------------------------------
# 报警分级
# ---------------------------------------------------------------------------

#: 1=提示(蜂鸣短), 2=明显报警(蜂鸣+语音), 3=强制(蜂鸣+语音+风扇)
ALARM_NONE = 0
ALARM_SOFT = 1
ALARM_MED = 2
ALARM_HARD = 3


@dataclass
class FatigueConfig:
    """可覆盖默认阈值的运行时配置（GUI/CLI 可调）。"""

    eye_ar_thresh: float = EYE_AR_THRESH
    eye_ar_consec_frames: int = EYE_AR_CONSEC_FRAMES
    mouth_ar_thresh: float = MOUTH_AR_THRESH
    head_pose_angle_thresh: float = HEAD_POSE_ANGLE_THRESH
    head_pose_window_sec: float = HEAD_POSE_WINDOW_SEC
    head_pose_abnormal_ratio: float = HEAD_POSE_ABNORMAL_RATIO
    yawn_window_sec: float = YAWN_WINDOW_SEC
    yawn_alarm_per_min: float = YAWN_ALARM_PER_MIN
    fatigue_window_sec: float = FATIGUE_SCORE_WINDOW_SEC
    event_blink_limit_30s: int = EVENT_BLINK_LIMIT_30S
    event_yawn_limit_30s: int = EVENT_YAWN_LIMIT_30S
    event_nod_limit_30s: int = EVENT_NOD_LIMIT_30S
    no_steer_buzz_sec: float = NO_STEER_BUZZ_SEC
    no_steer_fan_sec: float = NO_STEER_FAN_SEC
    drive_time_limit_sec: float = DRIVE_TIME_LIMIT_SEC

    #: 是否启用行为通道（模拟/真实）
    enable_behavior: bool = True
    #: 是否启用视觉通道（无摄像头时纯行为/演示）
    enable_vision: bool = True

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}

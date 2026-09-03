# -*- coding: utf-8 -*-
"""多源信息融合决策引擎。

论文第 1/2 章思想：视觉通道 + 行为通道双通道异构融合，
任一通道关键指标超阈值即触发分级预警；综合窗口内事件计数
（眨眼/哈欠/瞌睡点头）支撑疲劳状态综合判定（论文 5.2 测试口径：
30 秒窗口统计眨眼 11 / 哈欠 20 / 点头 30 -> SLEEP 报警）。
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .config import FatigueConfig, ALARM_NONE, ALARM_SOFT, ALARM_MED, ALARM_HARD
from .vision import FrameMetrics, VisionAnalyzer


@dataclass
class FusionStatus:
    """融合后暴露给 UI/输出的状态快照。"""

    timestamp: float = 0.0
    alarm_level: int = ALARM_NONE
    alarm_reason: str = ""
    fatigue: bool = False          # 综合判定是否疲劳（SLEEP）
    window_events: dict = field(default_factory=dict)  # {blink,yawn,nod} in 30s
    vision_active: bool = True
    behavior_active: bool = True
    drive_seconds: float = 0.0
    hands_on: bool = True
    steer_angle: float = 0.0
    ear: float = 0.0
    mar: float = 0.0
    pitch: float = 0.0
    fps: float = 0.0
    #: 行为通道报警等级（由 set_behavior_state 注入）
    _behavior_alarm: int = ALARM_NONE


class FusionEngine:
    """把视觉事件流与行为通道融合，输出报警与疲劳状态。"""

    def __init__(
        self,
        cfg: FatigueConfig,
        vision: Optional[VisionAnalyzer],
        on_alarm: Optional[Callable[[int, str], None]] = None,
    ) -> None:
        self.cfg = cfg
        self.vision = vision
        self.on_alarm = on_alarm or (lambda lvl, reason: None)
        self._lock = threading.Lock()
        self._status = FusionStatus(timestamp=time.time())
        # 融合触发历史
        self._alarm_log: List[dict] = []
        self._last_vision_ts = 0.0
        self._fatigue_start: Optional[float] = None

    # ------------------------------------------------------------------
    def set_behavior_state(
        self, hands_on: bool, steer_angle: float, drive_seconds: float, behavior_alarm: int
    ) -> None:
        with self._lock:
            st = self._status
            st.hands_on = hands_on
            st.steer_angle = steer_angle
            st.drive_seconds = drive_seconds
            st._behavior_alarm = behavior_alarm
            st.behavior_active = True

    def update_vision(self, m: FrameMetrics) -> None:
        with self._lock:
            self._last_vision_ts = time.time()
            st = self._status
            st.ear = m.ear
            st.mar = m.mar
            st.pitch = m.pitch
            st.fps = self.vision.fps if self.vision else 0.0

    def evaluate(self, reason_hint: str = "") -> FusionStatus:
        """基于最新状态执行融合判定。由主循环周期性调用。"""
        with self._lock:
            st = self._status
            st.timestamp = time.time()
            now = st.timestamp

            # --- 视觉通道事件（30 秒窗口计数，论文 5.2 口径） ---
            if self.vision is not None and self.cfg.enable_vision:
                b, y, n = self.vision.counts_in_window(self.cfg.fatigue_window_sec)
                st.window_events = {"blink": b, "yawn": y, "nod": n}
                st.vision_active = True
            else:
                st.window_events = {"blink": 0, "yawn": 0, "nod": 0}
                st.vision_active = False

            # --- 融合判定：视觉疲劳或行为报警任一超阈值即触发 ---
            alarm = ALARM_NONE
            reason = ""
            fatigue = False

            # 1) 视觉综合疲劳：30 秒窗口内多维度事件超限（论文 5.2）
            ev = st.window_events
            if (
                self.cfg.enable_vision
                and self.vision is not None
                and st.vision_active
            ):
                if (
                    ev["yawn"] >= self.cfg.event_yawn_limit_30s
                    or ev["nod"] >= self.cfg.event_nod_limit_30s
                    or ev["blink"] >= self.cfg.event_blink_limit_30s
                ):
                    fatigue = True
                    alarm = max(alarm, ALARM_MED)
                    reason = f"vision fatigue (blink={ev['blink']}, yawn={ev['yawn']}, nod={ev['nod']} in {int(self.cfg.fatigue_window_sec)}s)"

            # 2) 行为通道报警（外部 analyzer 已算好等级）
            #    通过 set_behavior_state 传入的行为等级在外部合并；此处给出提示
            # 3) 单帧强信号：持续闭眼(视觉)单独即可报 MED
            if self.cfg.enable_vision and self.vision is not None:
                if m_ear := getattr(st, "ear", 0.0):
                    if st.ear < self.cfg.eye_ar_thresh * 0.85:
                        alarm = max(alarm, ALARM_MED)
                        reason = "eyes closed sustained (EAR low)"

            # 与外部行为报警做最大合并（由 Controller 调用 set_behavior_alarm）
            if st.behavior_active and getattr(st, "_behavior_alarm", 0):
                ba = st._behavior_alarm
                if ba >= alarm:
                    alarm = ba
                    reason = reason_hint or "behavior alarm"

            st.alarm_level = alarm
            st.alarm_reason = reason
            st.fatigue = fatigue

            # 报警回调（等级变化时触发）
            if alarm != ALARM_NONE:
                self._fire(alarm, reason, now)
            return FusionStatus(**st.__dict__)

    def _fire(self, level: int, reason: str, now: float) -> None:
        self._alarm_log.append({"t": now, "level": level, "reason": reason})
        try:
            self.on_alarm(level, reason)
        except Exception:
            pass

    def snapshot(self) -> FusionStatus:
        with self._lock:
            return FusionStatus(**self._status.__dict__)

    def alarm_log(self, n: int = 20) -> List[dict]:
        with self._lock:
            return list(self._alarm_log[-n:])

# -*- coding: utf-8 -*-
"""视觉通道：基于 Dlib/OpenCV 的疲劳特征实时检测。

对应论文第四章 4.1/4.2：
- 人脸检测：Dlib get_frontal_face_detector
- 68 点关键点：shape_predictor_68_face_landmarks
- 计算 EAR/MAR/头部姿态，做眨眼/哈欠/瞌睡点头的事件累积与时序判定。
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

# cv2/numpy 缺失时视觉通道降级（行为通道/演示仍可运行）
try:
    import cv2
    import numpy as np
    _CV2_OK = True
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore
    np = None  # type: ignore
    _CV2_OK = False

from .config import FatigueConfig
from .features import (
    LEFT_EYE_IDX,
    RIGHT_EYE_IDX,
    extract_eye_mar,
    eye_aspect_ratio,
    mouth_aspect_ratio,
    shape_to_points,
    estimate_head_pose,
)

# 尝试导入 dlib（缺失时视觉通道进入降级模式，由调用方提示）
try:
    import dlib
    _DLIB_OK = True
except Exception:  # pragma: no cover
    dlib = None  # type: ignore
    _DLIB_OK = False


@dataclass
class FrameMetrics:
    """单帧视觉检测结果（时间戳+事件判定）。"""

    timestamp: float = 0.0
    faces: int = 0
    ear: float = 0.0
    mar: float = 0.0
    eye_closed: bool = False
    yawning: bool = False
    pitch: float = 0.0
    yaw: float = 0.0
    roll: float = 0.0
    blink_occurred: bool = False
    yawn_event: bool = False
    nod_event: bool = False
    head_pose_ok: bool = False
    raw: Optional[np.ndarray] = None  # 预留


class VisionAnalyzer:
    """视觉疲劳分析器：对帧执行检测并输出事件流。"""

    def __init__(
        self,
        cfg: FatigueConfig,
        predictor_path: Optional[str] = None,
        on_event: Optional[Callable[[str, int], None]] = None,
    ) -> None:
        self.cfg = cfg
        self.on_event = on_event or (lambda msg, level: None)
        self.predictor_path = predictor_path
        self._lock = threading.Lock()
        self._predictor = None
        self._detector = None
        self._load_models()

        # 时序状态
        self._eye_counter = 0
        self._eye_total_blinks = 0
        self._eye_was_closed = False
        self._mouth_counter = 0
        self._yawn_total = 0
        self._yawn_active = False
        self._last_yawn_ts = 0.0
        self._nod_counter = 0
        self._nod_total = 0
        self._nod_events: List[float] = []     # 事件时间戳
        self._yawn_events: List[float] = []
        self._blink_events: List[float] = []
        # 10 秒窗口头部异常累计
        self._pose_abnormal_start: Optional[float] = None
        self._pose_abnormal_accum = 0.0
        self._last_reset = 0.0
        self._fps = 0.0
        self._t_fps0 = time.time()
        self._frames = 0

    # ------------------------------------------------------------------
    def _load_models(self) -> None:
        if not _DLIB_OK:
            return
        self._detector = dlib.get_frontal_face_detector()
        if self.predictor_path:
            self._predictor = dlib.shape_predictor(self.predictor_path)
        else:
            # 允许用户放置 shape_predictor_68_face_landmarks.dat 在项目根/模型目录
            import os

            cand = [
                os.path.join(os.getcwd(), "models", "shape_predictor_68_face_landmarks.dat"),
                os.path.join(os.path.dirname(__file__), "..", "models", "shape_predictor_68_face_landmarks.dat"),
            ]
            for c in cand:
                if os.path.exists(c):
                    self._predictor = dlib.shape_predictor(c)
                    break

    @property
    def predictor_ready(self) -> bool:
        return self._predictor is not None

    @property
    def dlib_ok(self) -> bool:
        return _DLIB_OK

    # ------------------------------------------------------------------
    def analyze_frame(self, frame_bgr) -> FrameMetrics:
        """对一帧 BGR 图像执行完整分析，返回 FrameMetrics。

        cv2/dlib 缺失或模型未加载时返回空指标（降级不崩溃）。
        """
        t0 = time.time()
        m = FrameMetrics(timestamp=t0)
        if not _CV2_OK or not _DLIB_OK or frame_bgr is None:
            return m
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)  # 论文：自适应直方图均衡化预处理

        rects = self._detector(gray, 0) if self._detector is not None else []
        m.faces = len(rects)
        if len(rects) == 0 or self._predictor is None:
            return self._finalize(m)

        # 取最大人脸
        rect = max(rects, key=lambda r: (r.right() - r.left()) * (r.bottom() - r.top()))
        shape = self._predictor(gray, rect)
        pts = shape_to_points(shape)
        if len(pts) < 68:
            return self._finalize(m)

        # EAR/MAR
        ear_l, ear_r, ear, mar = extract_eye_mar(pts)
        m.ear = float(ear)
        m.mar = float(mar)
        m.eye_closed = ear < self.cfg.eye_ar_thresh
        m.yawning = mar > self.cfg.mouth_ar_thresh

        # 眨眼检测（EAR 由低回升计一次）
        if m.eye_closed:
            self._eye_counter += 1
            self._eye_was_closed = True
        else:
            if self._eye_was_closed and self._eye_counter >= max(1, self.cfg.eye_ar_consec_frames - 6):
                # 论文"连续闭合超10帧可靠判定疲劳"用于疲劳判定；眨眼事件本身用低帧门限
                pass
            if self._eye_was_closed:
                self._eye_total_blinks += 1
                self._blink_events.append(t0)
                m.blink_occurred = True
            self._eye_counter = 0
            self._eye_was_closed = False

        # 哈欠事件（论文：MAR 超阈值记一次事件，消失后压栈）
        if m.yawning:
            if not self._yawn_active:
                self._yawn_active = True
                self._mouth_counter += 1
        else:
            if self._yawn_active:
                self._yawn_active = False
                # 一次哈欠 = 一次"起-落"循环
                self._yawn_total += 1
                self._yawn_events.append(t0)
                m.yawn_event = True

        # 头部姿态
        pose = estimate_head_pose(pts)
        if pose is not None:
            m.yaw, m.pitch, m.roll = pose
            m.head_pose_ok = True
            # 论文 4.2.4：|Pitch|>=20 或 |Roll|>=20 为异常姿态
            abnormal = (abs(m.pitch) >= self.cfg.head_pose_angle_thresh) or (
                abs(m.roll) >= self.cfg.head_pose_angle_thresh
            )
            if abnormal:
                if self._pose_abnormal_start is None:
                    self._pose_abnormal_start = t0
            else:
                if self._pose_abnormal_start is not None:
                    self._pose_abnormal_accum += t0 - self._pose_abnormal_start
                    self._pose_abnormal_start = None

            # 点头事件（向下点头单次超阈值即可记一次粗事件）
            # 更精细：在窗口内统计异常占比（见 finalize 的 nod 判定）
        return self._finalize(m)

    def _finalize(self, m: FrameMetrics) -> FrameMetrics:
        """时序收尾：10 秒窗口内头部异常占比判定瞌睡。"""
        now = time.time()
        # 滚动窗口清理（保留 FATIGUE_WINDOW + HEAD_POSE_WINDOW 内事件）
        cutoff = now - max(60.0, self.cfg.head_pose_window_sec * 3)
        self._blink_events[:] = [t for t in self._blink_events if t > cutoff]
        self._yawn_events[:] = [t for t in self._yawn_events if t > cutoff]
        self._nod_events[:] = [t for t in self._nod_events if t > cutoff]

        # 头部异常事件：用"窗口内出现过超阈值姿态"近似点头计数
        # 论文：10s 窗口内异常累计时长占比 > 30% 判瞌睡
        window = self.cfg.head_pose_window_sec
        # 简化：追踪最近窗口内的异常帧占比（通过 _pose_abnormal_start 状态近似）
        # 这里用一个事件化实现：若当前处于异常态累计超过 window*ratio 即触发一次 nod
        if self._pose_abnormal_start is not None:
            abnormal_dur = self._pose_abnormal_accum + (now - self._pose_abnormal_start)
        else:
            abnormal_dur = self._pose_abnormal_accum
        # 超过 30% 观察窗口 => 计一次瞌睡事件并重置（事件化避免重复计）
        if abnormal_dur >= self.cfg.head_pose_abnormal_ratio * window:
            self._nod_total += 1
            self._nod_events.append(now)
            m.nod_event = True
            self._pose_abnormal_accum = 0.0
            self._pose_abnormal_start = None

        m.timestamp = now
        # FPS
        self._frames += 1
        el = now - self._t_fps0
        if el >= 1.0:
            self._fps = self._frames / el
            self._frames = 0
            self._t_fps0 = now
        return m

    # -- 供 GUI/上层读取的滚动统计 ------------------------------------
    def counts_in_window(self, sec: float = 60.0):
        """返回窗口内 (blink, yawn, nod) 计数。"""
        now = time.time()
        cut = now - sec
        return (
            sum(1 for t in self._blink_events if t > cut),
            sum(1 for t in self._yawn_events if t > cut),
            sum(1 for t in self._nod_events if t > cut),
        )

    def total_blinks(self) -> int:
        with self._lock:
            return self._eye_total_blinks

    @property
    def fps(self) -> float:
        return self._fps

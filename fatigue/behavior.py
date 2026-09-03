# -*- coding: utf-8 -*-
"""行为通道：方向盘握力 + 转角 + 驾驶时长模拟/采集接口。

论文硬件为 STC89C52 + GY-25 姿态传感器 + 薄膜压力传感器（3.2 节）。
本模块提供统一接口：
- BehaviorSource：真实串口/模拟源的上层抽象
- SimulatedBehavior：无硬件时用随机/脚本模拟方向盘行为（供复现演示）
真实固件采集可参考 firmware/ 下 8051 C 代码；Windows 无硬件时
默认使用 SimulatedBehavior，保证完整流程可运行。
"""
from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class BehaviorSample:
    """一次行为采集结果。"""

    timestamp: float
    hands_on: bool = True          # 是否握持方向盘（压力传感器）
    steer_angle_deg: float = 0.0   # 方向盘转角（GY-25 提供，度）
    note: str = ""


class BehaviorSource:
    """行为源接口。子类实现 poll()。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_sample: Optional[BehaviorSample] = None

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def poll(self) -> BehaviorSample:
        raise NotImplementedError

    def last_sample(self) -> Optional[BehaviorSample]:
        with self._lock:
            return self._last_sample

    def _store(self, s: BehaviorSample) -> BehaviorSample:
        with self._lock:
            self._last_sample = s
        return s


class SimulatedBehavior(BehaviorSource):
    """模拟行为源：可编程脚本化驾驶行为。

    通过事件队列注入"松手""转向""恢复"等行为，供测试与演示。
    事件: list[(delay_sec, kind, value)]
      kind in {"hands_off","hands_on","steer","no_steer"}
    """

    def __init__(self, script: Optional[list] = None, seed: Optional[int] = None) -> None:
        super().__init__()
        self.script: list = script or []
        self._rng = random.Random(seed)
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._t0 = 0.0
        self._cursor = 0
        self._hands_on = True
        self._angle = 0.0
        self._mode = "normal"  # normal | hands_off | no_steer

    # -- 生命周期 ----------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._t0 = time.time()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _run(self) -> None:
        while not self._stop.is_set():
            now = time.time() - self._t0
            self._apply_script(now)
            s = self._sample(now)
            self._store(s)
            time.sleep(0.05)  # 20 Hz，接近硬件采集节拍

    def _apply_script(self, now: float) -> None:
        while self._cursor < len(self.script):
            delay, kind, value = self.script[self._cursor]
            if now < delay:
                break
            if kind == "hands_off":
                self._hands_on = False
                self._mode = "hands_off"
            elif kind == "hands_on":
                self._hands_on = True
                self._mode = "normal"
            elif kind == "no_steer":        # 有握力但不再转向（微睡眠）
                self._hands_on = True
                self._mode = "no_steer"
            elif kind == "steer":
                self._hands_on = True
                self._mode = "normal"
                self._angle = float(value)
            self._cursor += 1

    def _sample(self, now: float) -> BehaviorSample:
        if self._mode == "no_steer":
            # 偶发微幅噪声但无有效转角（< 阈值）
            self._angle = self._angle + self._rng.uniform(-0.4, 0.4)
        elif self._mode == "normal" and self._hands_on:
            self._angle = self._angle + self._rng.uniform(-3.0, 3.0)
        return BehaviorSample(
            timestamp=time.time(),
            hands_on=self._hands_on,
            steer_angle_deg=self._angle,
            note=f"mode={self._mode}",
        )


class BehaviorAnalyzer:
    """行为状态机：基于行为样本判断报警等级（论文 3.2.7 执行逻辑）。

    规则（论文原文）：
    1) 无握力信号 -> 蜂鸣 + 风扇（立即，等级 3）
    2) 有握力但连续 N 秒无有效转角 -> 先蜂鸣（等级 2）；超 30 秒 -> 加风扇（等级 3）
    3) 累计驾驶时长达阈值 -> 语音 + 蜂鸣 + 风扇（等级 3）
    """

    def __init__(self, cfg, on_event: Optional[Callable[[str, int], None]] = None) -> None:
        self.cfg = cfg
        self.on_event = on_event or (lambda msg, level: None)
        self._lock = threading.Lock()
        self._last_sample: Optional[BehaviorSample] = None
        self._last_change_t: Optional[float] = None
        self._last_hands_on: Optional[bool] = None
        self._drive_start_t: Optional[float] = None
        self._alarm_level = 0
        self._drive_seconds = 0.0
        self._prev_raised: dict = {}

    def reset(self) -> None:
        with self._lock:
            self._last_sample = None
            self._last_change_t = None
            self._last_hands_on = None
            self._drive_start_t = None
            self._alarm_level = 0
            self._drive_seconds = 0.0
            self._prev_raised.clear()

    def update(self, s: BehaviorSample) -> int:
        """输入一次行为样本，返回当前报警等级(0~3)。"""
        with self._lock:
            if self._drive_start_t is None:
                self._drive_start_t = s.timestamp
            self._drive_seconds = s.timestamp - self._drive_start_t

            # 转角有效变化判断
            angle_changed = False
            if self._last_sample is None:
                angle_changed = True
            else:
                angle_changed = (
                    abs(s.steer_angle_deg - self._last_sample.steer_angle_deg)
                    > self.cfg.STEER_ANGLE_EPS_DEG
                )
            self._last_sample = s

            # 握力状态沿
            if self._last_hands_on is None or self._last_hands_on != s.hands_on:
                # 状态切换视为"变化"，刷新计时基准
                self._last_change_t = s.timestamp
            self._last_hands_on = s.hands_on

            now = s.timestamp
            reason = None
            level = 0

            # 规则 1：无握力立即报警
            if not s.hands_on:
                level = 3
                reason = "hands off (no grip)"
            else:
                # 规则 2：有握力但无转角变化
                if angle_changed:
                    self._last_change_t = now
                idle = 0.0 if self._last_change_t is None else now - self._last_change_t

                if idle >= self.cfg.no_steer_fan_sec:
                    level = 3
                    reason = "no steering over 30s"
                elif idle >= self.cfg.no_steer_buzz_sec:
                    level = 2
                    reason = "no steering over 3s"
                elif self._drive_seconds >= self.cfg.drive_time_limit_sec:
                    level = 3
                    reason = "drive time limit reached"
                else:
                    level = 0

            self._alarm_level = level
            if reason is not None:
                self._raise_once(reason, level, now)
            return level

    def _raise_once(self, reason: str, level: int, now: float) -> None:
        key = reason
        last_t = self._prev_raised.get(key)
        # 同一原因至少间隔 2 秒再报一次，避免刷屏
        if last_t is not None and now - last_t < 2.0:
            return
        self._prev_raised[key] = now
        try:
            self.on_event(f"[behavior] {reason}", level)
        except Exception:
            pass

    @property
    def drive_seconds(self) -> float:
        with self._lock:
            return self._drive_seconds

    @property
    def alarm_level(self) -> int:
        with self._lock:
            return self._alarm_level

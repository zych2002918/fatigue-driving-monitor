# -*- coding: utf-8 -*-
"""报警输出层：多级声光/语音/风扇。

论文硬件：蜂鸣器（P2.2）、继电器风扇（P2.1）、ISD1820 语音模块。
本层在 PC 上用 winsound 蜂鸣 + 可选 TTS 语音播报代替（无硬件时），
并暴露统一 Alarmer 接口：未来接串口/单片机时可替换实现。
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from .config import ALARM_NONE, ALARM_SOFT, ALARM_MED, ALARM_HARD


class BaseAlarmer:
    """报警器接口。"""

    def trigger(self, level: int, reason: str) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        pass


class ConsoleAlarmer(BaseAlarmer):
    """控制台/日志报警（无音频依赖时兜底）。"""

    def __init__(self, log: Optional[Callable[[str], None]] = None) -> None:
        self.log = log or print

    def trigger(self, level: int, reason: str) -> None:
        names = {ALARM_SOFT: "SOFT", ALARM_MED: "MED", ALARM_HARD: "HARD"}
        self.log(f"[ALARM-{names.get(level, level)}] {reason}")


class WinsoundAlarmer(BaseAlarmer):
    """Windows 蜂鸣（winsound），映射论文蜂鸣器行为。"""

    def __init__(
        self,
        log: Optional[Callable[[str], None]] = None,
        use_tts: bool = False,
    ) -> None:
        self.log = log or print
        self.use_tts = use_tts
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def trigger(self, level: int, reason: str) -> None:
        # 只在等级升高/事件触发时蜂鸣（由上层保证去重）
        if level == ALARM_NONE:
            return
        self._beep(level, reason)
        self.log(f"[ALARM-{level}] {reason}")

    def _beep(self, level: int, reason: str) -> None:
        try:
            import winsound

            if level == ALARM_SOFT:
                winsound.Beep(800, 150)
            elif level == ALARM_MED:
                winsound.Beep(1000, 250)
                winsound.Beep(800, 250)
            else:
                # 三连急促
                for _ in range(3):
                    winsound.Beep(1200, 200)
                    time.sleep(0.05)
        except Exception:
            pass  # 无声环境忽略
        if self.use_tts and level >= ALARM_MED:
            self._speak("当前处于疲劳驾驶，请停车休息")

    def _speak(self, text: str) -> None:
        try:
            import pyttsx3

            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception:
            # 无 TTS 引擎则跳过
            self.log(f"[TTS-unavailable] {text}")

    def stop(self) -> None:
        self._stop.set()

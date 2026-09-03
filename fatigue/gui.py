# -*- coding: utf-8 -*-
"""WxPython 桌面 GUI：复现论文图 4-7 的可视化操作界面。

布局（对应论文 4.2.5 / 5.2 图 4-7、5-4~5-6）：
- 顶部：视频源下拉选择 + 视频预览区
- 中部：监测项目勾选（闭眼/哈欠/瞌睡点头）+ 检测时间窗口
- 底部：状态栏（实时 EAR/MAR/头部角度/计数）+ 开始/停止/复位按钮
"""
from __future__ import annotations

import threading
import time
from typing import Optional

import wx

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore

from .config import FatigueConfig
from .fusion import FusionEngine, FusionStatus
from .vision import VisionAnalyzer
from .behavior import BehaviorAnalyzer, BehaviorSource, SimulatedBehavior
from .alarm import WinsoundAlarmer, ConsoleAlarmer

# 避免无 wxPython 时导入失败
try:
    import wx.lib.agw.aui as aui  # noqa
except Exception:  # pragma: no cover
    pass


class VideoSource:
    """视频源抽象：摄像头或静态图片循环。"""

    def __init__(self, kind: str = "camera", path: Optional[str] = None) -> None:
        self.kind = kind
        self.path = path
        self._cap = None

    def open(self) -> bool:
        if self.kind == "camera" and cv2 is not None:
            idx = int(self.path) if self.path else 0
            self._cap = cv2.VideoCapture(idx)
            return self._cap.isOpened()
        elif self.kind == "file" and cv2 is not None:
            self._cap = cv2.VideoCapture(self.path)
            return self._cap.isOpened()
        return False

    def read(self):
        if self._cap is None:
            return False, None
        return self._cap.read()

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


class FatigueFrame(wx.Frame):
    def __init__(
        self,
        cfg: Optional[FatigueConfig] = None,
        predictor_path: Optional[str] = None,
    ) -> None:
        super().__init__(None, title="多源信息融合疲劳驾驶实时预警装置（复现）", size=(1080, 760))
        self.cfg = cfg or FatigueConfig()
        self.predictor_path = predictor_path

        # 依赖就绪检查
        self._warn_missing()

        # 组件
        self.video: Optional[VideoSource] = None
        self.vision: Optional[VisionAnalyzer] = None
        self.behavior_src: Optional[BehaviorSource] = None
        self.behavior_ana: Optional[BehaviorAnalyzer] = None
        self.fusion: Optional[FusionEngine] = None
        self.alarmer = WinsoundAlarmer(log=lambda s: self._log(s), use_tts=False)
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._build_ui()
        self._timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_timer, self._timer)
        self._timer.Start(33)  # ~30fps UI 刷新
        self.Bind(wx.EVT_CLOSE, self._on_close)

    # ------------------------------------------------------------------
    def _warn_missing(self) -> None:
        import importlib

        missing = []
        for mod in ("cv2", "dlib", "wx"):
            try:
                importlib.import_module(mod)
            except Exception:
                missing.append(mod)
        if missing:
            wx.MessageBox(
                f"缺少依赖: {', '.join(missing)}\n请先安装 requirements.txt 中的依赖。",
                "依赖缺失",
                wx.OK | wx.ICON_WARNING,
            )

    def _build_ui(self) -> None:
        pnl = wx.Panel(self)
        sz = wx.BoxSizer(wx.VERTICAL)

        # 视频源区
        top = wx.BoxSizer(wx.HORIZONTAL)
        top.Add(wx.StaticText(pnl, label="视频源:"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 6)
        self.src_choice = wx.Choice(
            pnl,
            choices=["本地摄像头 (0)", "本地摄像头 (1)", "静态演示图", "视频文件..."],
        )
        self.src_choice.SetSelection(0)
        top.Add(self.src_choice, 0, wx.ALL, 6)
        self.btn_start = wx.Button(pnl, label="开始检测")
        self.btn_stop = wx.Button(pnl, label="停止")
        self.btn_stop.Disable()
        top.Add(self.btn_start, 0, wx.ALL, 6)
        top.Add(self.btn_stop, 0, wx.ALL, 6)
        sz.Add(top, 0, wx.EXPAND)

        # 视频预览
        self.video_box = wx.StaticBox(pnl, label="实时视频")
        vbs = wx.StaticBoxSizer(self.video_box, wx.VERTICAL)
        self.preview = wx.StaticBitmap(pnl, size=(960, 480))
        vbs.Add(self.preview, 1, wx.EXPAND | wx.ALL, 6)
        sz.Add(vbs, 1, wx.EXPAND | wx.ALL, 6)

        # 指标栏
        metric = wx.BoxSizer(wx.HORIZONTAL)
        self.txt_state = wx.StaticText(pnl, label="状态: 未开始")
        metric.Add(self.txt_state, 0, wx.ALL, 6)
        self.txt_ear = wx.StaticText(pnl, label="EAR: -")
        metric.Add(self.txt_ear, 0, wx.ALL, 6)
        self.txt_mar = wx.StaticText(pnl, label="MAR: -")
        metric.Add(self.txt_mar, 0, wx.ALL, 6)
        self.txt_pose = wx.StaticText(pnl, label="Pitch: -")
        metric.Add(self.txt_pose, 0, wx.ALL, 6)
        self.txt_cnt = wx.StaticText(pnl, label="眨眼:0 哈欠:0 点头:0")
        metric.Add(self.txt_cnt, 0, wx.ALL, 6)
        sz.Add(metric, 0, wx.EXPAND)

        # 行为栏（模拟）
        behave = wx.BoxSizer(wx.HORIZONTAL)
        behave.Add(wx.StaticText(pnl, label="行为通道(模拟):"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 6)
        self.txt_hands = wx.StaticText(pnl, label="握力: -")
        behave.Add(self.txt_hands, 0, wx.ALL, 6)
        self.txt_angle = wx.StaticText(pnl, label="转角: -")
        behave.Add(self.txt_angle, 0, wx.ALL, 6)
        self.txt_drive = wx.StaticText(pnl, label="驾驶时长: -")
        behave.Add(self.txt_drive, 0, wx.ALL, 6)
        sz.Add(behave, 0, wx.EXPAND)

        # 日志
        self.log = wx.TextCtrl(pnl, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 110))
        sz.Add(self.log, 0, wx.EXPAND | wx.ALL, 6)

        pnl.SetSizer(sz)

        self.btn_start.Bind(wx.EVT_BUTTON, lambda e: self._start())
        self.btn_stop.Bind(wx.EVT_BUTTON, lambda e: self._stop())

    # ------------------------------------------------------------------
    def _start(self) -> None:
        if self._running:
            return
        choice = self.src_choice.GetSelection()
        # 构造视频源
        if choice in (0, 1):
            kind, path = "camera", str(choice)
        elif choice == 2:
            kind, path = "image", ""
            # 找不到静态图时回退
            kind, path = "camera", "0"
        else:
            with wx.FileDialog(self, "选择视频", wildcard="视频文件 (*.mp4;*.avi)|*.mp4;*.avi") as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                kind, path = "file", dlg.GetPath()

        self._log("初始化视觉引擎…")
        self.vision = VisionAnalyzer(self.cfg, predictor_path=self.predictor_path,
                                     on_event=lambda m, l: self._log(m))
        if not self.vision.dlib_ok:
            self._log("[警告] dlib 不可用，视觉通道将受限")
        if not self.vision.predictor_ready:
            self._log("[警告] 未找到 shape_predictor_68_face_landmarks.dat，"
                      "请放入 models/ 目录（见 README）")

        self.fusion = FusionEngine(self.cfg, self.vision,
                                   on_alarm=lambda lvl, rs: self._log(f"[融合报警-{lvl}] {rs}"))
        self.behavior_src = SimulatedBehavior()
        self.behavior_ana = BehaviorAnalyzer(self.cfg, on_event=lambda m, l: self._log(m))

        self.video = VideoSource(kind, path)
        if not self.video.open():
            self._log("[错误] 无法打开视频源")
            return
        self.behavior_src.start()
        self._running = True
        self.btn_start.Disable()
        self.btn_stop.Enable()
        self._log("开始检测…")

    def _stop(self) -> None:
        self._running = False
        if self.behavior_src:
            self.behavior_src.stop()
        if self.video:
            self.video.release()
        self.btn_start.Enable()
        self.btn_stop.Disable()
        self._log("已停止。")

    # -- 主循环（每 ~33ms） ---------------------------------------------
    def _on_timer(self, _evt) -> None:
        if not self._running or self.video is None:
            return
        ok, frame = self.video.read()
        if not ok or frame is None:
            self._log("视频流结束")
            self._stop()
            return

        # 视觉分析
        if self.vision is not None:
            m = self.vision.analyze_frame(frame)
            self.fusion.update_vision(m)
            # 绘制叠加层
            cv2.putText(frame, f"EAR:{m.ear:.2f} MAR:{m.mar:.2f}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.putText(frame, f"Faces:{m.faces} Blinks:{self.vision.total_blinks()}",
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            if m.head_pose_ok:
                cv2.putText(frame, f"Pitch:{m.pitch:.1f} Yaw:{m.yaw:.1f} Roll:{m.roll:.1f}",
                            (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            if m.eye_closed:
                cv2.putText(frame, "EYE CLOSED", (10, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            if m.yawn_event:
                cv2.putText(frame, "YAWN!", (10, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            if m.nod_event:
                cv2.putText(frame, "NOD!", (10, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

        # 行为通道
        s = self.behavior_src.last_sample()
        if s is not None and self.behavior_ana is not None:
            level = self.behavior_ana.update(s)
            if self.fusion is not None:
                self.fusion.set_behavior_state(s.hands_on, s.steer_angle_deg,
                                               self.behavior_ana.drive_seconds, level)
                # 报警交由融合评估触发
                self.alarmer.trigger(level, f"behavior level {level}")
            self.txt_hands.SetLabel(f"握力: {'有' if s.hands_on else '无'}")
            self.txt_angle.SetLabel(f"转角: {s.steer_angle_deg:+.1f}°")
            self.txt_drive.SetLabel(f"驾驶时长: {int(self.behavior_ana.drive_seconds)}s")

        # 融合评估
        if self.fusion is not None:
            st = self.fusion.evaluate()
            self.txt_state.SetLabel(f"状态: {'疲劳(SLEEP)' if st.fatigue else '正常'} 报警:{st.alarm_level}")
            if self.vision is not None:
                ev = st.window_events
                self.txt_ear.SetLabel(f"EAR: {st.ear:.2f}")
                self.txt_mar.SetLabel(f"MAR: {st.mar:.2f}")
                self.txt_cnt.SetLabel(f"30s内 眨眼:{ev['blink']} 哈欠:{ev['yawn']} 点头:{ev['nod']}")

        # 显示帧
        if frame is not None:
            h, w = frame.shape[:2]
            # 缩放到预览
            maxw, maxh = 960, 480
            scale = min(maxw / w, maxh / h, 1.0)
            if scale < 1.0:
                frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            bmp = wx.Bitmap.FromBuffer(w, h, rgb)
            self.preview.SetBitmap(bmp)

    def _log(self, msg: str) -> None:
        def _do():
            if hasattr(self, "log"):
                self.log.AppendText(f"[{time.strftime('%H:%M:%S')}] {msg}\n")

        # 线程安全：wx 需在 UI 线程操作
        if wx.IsMainThread():
            _do()
        else:
            try:
                wx.CallAfter(_do)
            except Exception:
                pass

    def _on_close(self, _evt) -> None:
        self._stop()
        self._timer.Stop()
        self.Destroy()


def main(cfg: Optional[FatigueConfig] = None, predictor_path: Optional[str] = None) -> None:
    app = wx.App(False)
    frm = FatigueFrame(cfg, predictor_path)
    frm.Show()
    app.MainLoop()

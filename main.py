# -*- coding: utf-8 -*-
"""主程序入口（复现论文 MainProgram）。

用法:
    python main.py --gui           # 打开可视化界面（默认）
    python main.py --headless      # 无界面演示：模拟行为 + 可选摄像头
    python main.py --source 0      # 指定摄像头索引
"""
from __future__ import annotations

import argparse
import sys
import time


def _find_predictor() -> str | None:
    import os

    cands = [
        os.path.join("models", "shape_predictor_68_face_landmarks.dat"),
        os.path.join(os.path.dirname(__file__), "models", "shape_predictor_68_face_landmarks.dat"),
    ]
    for c in cands:
        if os.path.exists(c):
            return os.path.abspath(c)
    return None


def run_headless(camera_index: int | None = None) -> int:
    """无 GUI 演示：行为通道模拟 + （可选）摄像头视觉通道。"""
    from fatigue.config import FatigueConfig
    from fatigue.behavior import SimulatedBehavior, BehaviorAnalyzer
    from fatigue.fusion import FusionEngine
    from fatigue.alarm import ConsoleAlarmer

    cfg = FatigueConfig()
    cfg.drive_time_limit_sec = 3600  # 演示用 1 小时

    # 视觉（摄像头可选）
    vision = None
    if camera_index is not None:
        from fatigue.vision import VisionAnalyzer

        predictor = _find_predictor()
        vision = VisionAnalyzer(cfg, predictor_path=predictor,
                                on_event=lambda m, l: print(f"[vision] {m}"))
        if not vision.predictor_ready:
            print("[warn] 缺少 68 点模型，视觉通道无法工作")
            vision = None

    alarmer = ConsoleAlarmer()
    fusion = FusionEngine(cfg, vision, on_alarm=lambda l, r: alarmer.trigger(l, r))
    behavior = SimulatedBehavior(script=[
        (0, "hands_on", None),          # 正常驾驶
        (8, "no_steer", None),          # 8s 后不再转向 -> 触发 3s/30s 规则
    ])
    behavior.start()
    beh = BehaviorAnalyzer(cfg, on_event=lambda m, l: print(f"[behavior] {m}"))

    print("== 疲劳驾驶监测（headless 演示）==")
    print("模拟: 8s 后驾驶员停止转向但保持握力 -> 期望 11s 左右报警(3s规则)")
    t_end = time.time() + 40
    try:
        while time.time() < t_end:
            s = behavior.last_sample()
            if s is not None:
                lvl = beh.update(s)
                fusion.set_behavior_state(s.hands_on, s.steer_angle_deg, beh.drive_seconds, lvl)
                st = fusion.evaluate()
                if st.alarm_level:
                    print(f"[{time.strftime('%H:%M:%S')}] 报警等级={st.alarm_level} reason={st.alarm_reason or 'behavior'}")
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        behavior.stop()
    print("== 演示结束 ==")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="多源信息融合疲劳驾驶实时预警装置（论文复现）")
    ap.add_argument("--gui", action="store_true", help="打开可视化界面")
    ap.add_argument("--headless", action="store_true", help="无界面演示模式")
    ap.add_argument("--source", type=int, default=None, help="摄像头索引（headless 时启用视觉）")
    args = ap.parse_args(argv)

    if args.headless:
        return run_headless(camera_index=args.source)

    # 默认 GUI
    from fatigue.gui import main as gui_main

    gui_main(predictor_path=_find_predictor())
    return 0


if __name__ == "__main__":
    sys.exit(main())

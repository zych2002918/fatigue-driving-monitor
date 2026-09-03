# -*- coding: utf-8 -*-
"""纯行为通道 CLI 演示：无需摄像头/GPU/dlib。

复现论文 3.2.7 行为通道逻辑：
  脚本：0~6s 正常驾驶 -> 8s 起停止转向(no_steer)
  期望：~11s 触发 3s 蜂鸣报警；~38s 触发 30s 风扇报警(脚本 40s 结束)

运行：python scripts/demo_behavior.py
"""
import os
import sys
import time

# 使 scripts/ 下可直接运行（把项目根加入 path）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# GBK 控制台避免中文乱码
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fatigue.config import FatigueConfig
from fatigue.behavior import SimulatedBehavior, BehaviorAnalyzer
from fatigue.fusion import FusionEngine
from fatigue.alarm import ConsoleAlarmer


def main() -> int:
    cfg = FatigueConfig()
    cfg.drive_time_limit_sec = 99999  # 忽略驾驶时长规则，专注 no-steer 逻辑

    last_level = 0
    fusion = FusionEngine(cfg, vision=None, on_alarm=lambda l, r: None)
    beh = BehaviorAnalyzer(cfg, on_event=lambda m, l: None)
    sim = SimulatedBehavior(script=[
        (0, "hands_on", None),
        (8, "no_steer", None),
    ])
    sim.start()

    print("== 疲劳驾驶监测 · 行为通道 CLI 演示 ==")
    print("0~8s 正常转向；8s 起保持握力但停止转向（复现论文 3.2.7 规则）")
    t0 = time.time()
    try:
        while time.time() - t0 < 40:
            s = sim.last_sample()
            if s is not None:
                lvl = beh.update(s)
                fusion.set_behavior_state(s.hands_on, s.steer_angle_deg,
                                          beh.drive_seconds, lvl)
                # 仅在报警等级变化时打印
                if lvl != last_level:
                    reason = {2: "no steering > 3s (buzzer)",
                              3: "no steering > 30s (buzzer+fan)"}.get(lvl, "")
                    if lvl > 0:
                        print(f"[{time.time()-t0:5.1f}s] ALARM level={lvl} {reason} "
                              f"hands={s.hands_on} angle={s.steer_angle_deg:+.1f}")
                    else:
                        print(f"[{time.time()-t0:5.1f}s] 恢复 normal")
                    last_level = lvl
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        sim.stop()
    print("== done ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())

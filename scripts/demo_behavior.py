# -*- coding: utf-8 -*-
"""纯行为通道 CLI 演示：无需摄像头/GPU/dlib。

复现论文 3.2.7 行为通道逻辑：
  脚本：0~6s 正常驾驶 -> 8s 起停止转向(no_steer)
  期望：~11s 触发 3s 蜂鸣报警；~38s 触发 30s 风扇报警(脚本 40s 结束)
"""
import sys
import time

from fatigue.config import FatigueConfig
from fatigue.behavior import SimulatedBehavior, BehaviorAnalyzer, BehaviorSample
from fatigue.fusion import FusionEngine
from fatigue.alarm import ConsoleAlarmer


def main() -> int:
    cfg = FatigueConfig()
    cfg.drive_time_limit_sec = 99999  # 忽略驾驶时长规则，专注 no-steer 逻辑

    fusion = FusionEngine(cfg, vision=None, on_alarm=lambda l, r: print(f"[FUSION] level={l} {r}"))
    beh = BehaviorAnalyzer(cfg, on_event=lambda m, l: print(f"  [event] {m}"))
    sim = SimulatedBehavior(script=[
        (0, "hands_on", None),
        (8, "no_steer", None),
    ])
    sim.start()

    print("== 疲劳驾驶监测 · 行为通道 CLI 演示 ==")
    print("0~8s 正常转向；8s 起保持握力但停止转向")
    t0 = time.time()
    try:
        while time.time() - t0 < 40:
            s = sim.last_sample()
            if s is not None:
                lvl = beh.update(s)
                fusion.set_behavior_state(s.hands_on, s.steer_angle_deg,
                                          beh.drive_seconds, lvl)
                st = fusion.evaluate()
                if st.alarm_level:
                    print(f"[{time.time()-t0:5.1f}s] ALARM level={st.alarm_level} "
                          f"reason={st.alarm_reason or beh_alarm_reason(lvl)} "
                          f"hands={s.hands_on} angle={s.steer_angle_deg:+.1f}")
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        sim.stop()
    print("== done ==")
    return 0


def beh_alarm_reason(level: int) -> str:
    return {2: "no steering > 3s", 3: "no steering > 30s"}.get(level, "")


if __name__ == "__main__":
    sys.exit(main())

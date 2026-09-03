# -*- coding: utf-8 -*-
"""行为通道状态机测试：验证论文 3.2.7 的报警时序规则。"""
import sys
import time
import unittest

sys.path.insert(0, ".")
from fatigue.config import FatigueConfig
from fatigue.behavior import (
    BehaviorAnalyzer,
    BehaviorSample,
    SimulatedBehavior,
)


class TestEARFeature(unittest.TestCase):
    """验证论文式 4-1 EAR 计算（纯几何）。"""

    def test_eye_aspect_ratio_open(self):
        from fatigue.features import eye_aspect_ratio

        # 构造睁眼六点（水平椭圆）
        eye = [(0.0, 10.0), (5.0, 2.0), (10.0, 2.0), (20.0, 10.0),
               (10.0, 18.0), (5.0, 18.0)]
        ear = eye_aspect_ratio(eye)
        self.assertGreater(ear, 0.2)

    def test_eye_aspect_ratio_closed(self):
        from fatigue.features import eye_aspect_ratio

        # 闭合：上下点重合 -> 小值
        eye = [(0.0, 10.0), (5.0, 10.0), (10.0, 10.0), (20.0, 10.0),
               (10.0, 10.0), (5.0, 10.0)]
        ear = eye_aspect_ratio(eye)
        self.assertAlmostEqual(ear, 0.0, places=3)


class TestBehaviorAnalyzer(unittest.TestCase):
    def setUp(self):
        self.cfg = FatigueConfig()

    def test_hands_off_immediate_alarm(self):
        beh = BehaviorAnalyzer(self.cfg)
        s = BehaviorSample(timestamp=time.time(), hands_on=False, steer_angle_deg=0.0)
        lvl = beh.update(s)
        self.assertEqual(lvl, 3, "无握力应立即 3 级报警")

    def test_no_steer_3s_alarm(self):
        beh = BehaviorAnalyzer(self.cfg)
        t0 = time.time()
        # 有握力但转角不动
        for i in range(10):
            s = BehaviorSample(timestamp=t0 + i * 0.5, hands_on=True, steer_angle_deg=10.0)
            beh.update(s)
        s = BehaviorSample(timestamp=t0 + 5.0, hands_on=True, steer_angle_deg=10.0)
        lvl = beh.update(s)
        self.assertGreaterEqual(lvl, 2, "无转角 >3s 应触发蜂鸣(2级)")

    def test_no_steer_30s_fan(self):
        beh = BehaviorAnalyzer(self.cfg)
        t0 = time.time()
        # 模拟持续无转角 35s
        for i in range(0, 71, 2):
            s = BehaviorSample(timestamp=t0 + i, hands_on=True, steer_angle_deg=10.0)
            beh.update(s)
        lvl = beh.alarm_level
        self.assertEqual(lvl, 3, "无转角 >30s 应升级到 3 级(风扇)")

    def test_steer_resets_no_steer(self):
        beh = BehaviorAnalyzer(self.cfg)
        t0 = time.time()
        for i in range(0, 20, 2):
            s = BehaviorSample(timestamp=t0 + i, hands_on=True, steer_angle_deg=10.0)
            beh.update(s)
        # 之后发生转向 -> 清零计时
        s = BehaviorSample(timestamp=t0 + 20, hands_on=True, steer_angle_deg=30.0)
        lvl = beh.update(s)
        self.assertEqual(lvl, 0)


class TestSimulatedBehavior(unittest.TestCase):
    def test_script_events(self):
        sim = SimulatedBehavior(script=[(0.1, "hands_on", None), (1.0, "hands_off", None)])
        sim.start()
        time.sleep(1.8)
        s = sim.last_sample()
        sim.stop()
        self.assertIsNotNone(s)
        self.assertFalse(s.hands_on, "1s 后应处于松手状态")


if __name__ == "__main__":
    unittest.main(verbosity=2)

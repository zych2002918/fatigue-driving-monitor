# -*- coding: utf-8 -*-
"""视觉几何自测：不依赖真实摄像头/人脸模型，验证 EAR/MAR 公式实现。

仅用 numpy/cv2 合成简单椭圆模拟眼/嘴关键点，检查阈值判定与公式。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fatigue.features import eye_aspect_ratio, mouth_aspect_ratio


class TestGeometryFormulas(unittest.TestCase):
    def test_ear_open_eye_high(self):
        # 睁眼：竖直间距大
        pts = [(0, 10), (6, 2), (12, 2), (24, 10), (12, 18), (6, 18)]
        ear = eye_aspect_ratio(pts)
        self.assertGreater(ear, 0.2)

    def test_ear_closed_eye_low(self):
        pts = [(0, 10), (6, 10), (12, 10), (24, 10), (12, 10), (6, 10)]
        ear = eye_aspect_ratio(pts)
        self.assertLess(ear, 0.05)

    def test_mar_open_mouth_high(self):
        # 嘴张：上唇中点(0,5) 与下唇中点(20,25) 竖直距离大，嘴角宽不变
        # 参数 = (top_lip, bottom_lip, left_corner, right_corner)
        pts = [(10, 2), (10, 38), (0, 20), (40, 20)]
        mar = mouth_aspect_ratio(pts)
        self.assertGreater(mar, 0.5)

    def test_mar_closed_mouth_low(self):
        # 嘴闭合：上下唇竖直距离≈0
        pts = [(10, 20), (10, 20), (0, 20), (40, 20)]
        mar = mouth_aspect_ratio(pts)
        self.assertLess(mar, 0.05)

    def test_threshold_direction(self):
        """闭眼应低于 EAR 阈值 0.23；哈欠应高于 MAR 阈值 0.3。"""
        from fatigue.config import EYE_AR_THRESH, MOUTH_AR_THRESH

        closed_eye = [(0, 10), (6, 10), (12, 10), (24, 10), (12, 10), (6, 10)]
        open_mouth = [(10, 2), (10, 38), (0, 20), (40, 20)]
        self.assertLess(eye_aspect_ratio(closed_eye), EYE_AR_THRESH)
        self.assertGreater(mouth_aspect_ratio(open_mouth), MOUTH_AR_THRESH)


if __name__ == "__main__":
    unittest.main(verbosity=2)

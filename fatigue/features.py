# -*- coding: utf-8 -*-
"""面部疲劳特征计算模块。

实现论文 4.2 节定义的几何特征：
- eye_aspect_ratio  (EAR，式 4-1)
- mouth_aspect_ratio(MAR，式 4-2)
- 68 点人脸关键点 -> 左右眼/嘴部关键点索引
"""
from __future__ import annotations

import math
from typing import List, Sequence, Tuple

# 左右眼与嘴部在 68 点（iBUG）模型中的索引（dlib face_utils 标准编号）
LEFT_EYE_IDX: Tuple[int, ...] = (36, 37, 38, 39, 40, 41)
RIGHT_EYE_IDX: Tuple[int, ...] = (42, 43, 44, 45, 46, 47)

# 嘴部关键索引（68 点 iBUG 外唇）：上唇中 51、下唇中 57、左嘴角 48、右嘴角 54
MOUTH_PTS: Tuple[int, ...] = (51, 57, 48, 54)

# 论文 4.2.1 中 EAR/MAR 公式所用的 6 点取法：
# EAR: P1..P6 = 眼角点序列，竖直两点为 P2,P6 与 P3,P5
EAR_VERT_A = (1, 5)   # 左眼: 38,42 / 右眼: 44,46 的通用局部索引
EAR_VERT_B = (2, 4)

Point = Tuple[float, float]


def _euclid(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def eye_aspect_ratio(eye_pts: Sequence[Point]) -> float:
    """式 4-1：EAR = (|P2-P6| + |P3-P5|) / (2*|P1-P4|)。

    eye_pts 为 6 个点（按 dlib 顺序 36..41 / 42..47）。
    返回分母为 0 时返回 0（避免除零）。
    """
    if len(eye_pts) < 6:
        return 0.0
    denom = 2.0 * _euclid(eye_pts[0], eye_pts[3])
    if denom <= 1e-9:
        return 0.0
    num = _euclid(eye_pts[1], eye_pts[5]) + _euclid(eye_pts[2], eye_pts[4])
    return num / denom


def mouth_aspect_ratio(points: Sequence[Point]) -> float:
    """MAR（嘴部纵横比，论文式 4-2 的几何等价实现）。

    论文式 4-2 以 6 个嘴部关键点定义纵横比，但图 4-4 未公开索引表。
    为保证物理语义正确（嘴张 -> MAR 增大；闭合 -> MAR -> 0），
    这里直接用外唇几何量：
        MAR = 上下唇竖直间距(|上唇中-下唇中|) / 嘴角水平宽度
    调用方需传入 68 点全集，或预提取 [上唇中, 下唇中, 左嘴角, 右嘴角]。
    """
    if len(points) < 4:
        return 0.0
    # points = (top_lip, bottom_lip, left_corner, right_corner)
    top, bottom, left, right = points[0], points[1], points[2], points[3]
    width = _euclid(left, right)
    if width <= 1e-9:
        return 0.0
    height = _euclid(top, bottom)
    return height / width


def shape_to_points(shape) -> List[Point]:
    """将 dlib.full_object_detection 转为 [(x,y), ...] 列表。"""
    return [(shape.part(i).x, shape.part(i).y) for i in range(shape.num_parts)]


def points_to_np(points: Sequence[Point]):
    """转为 Nx2 numpy 数组（供 solvePnP 等使用）。"""
    import numpy as np  # 延迟导入，保持无 numpy 也可读结构

    return np.array(points, dtype=np.float64).reshape(-1, 2)


# 头部姿态估计标准 3D 模型（论文 4.2.4 节：以 68 点与标准 3D 模型映射求解欧拉角）
FACE_3D_MODEL: List[Tuple[float, float, float]] = [
    (0.0, 0.0, 0.0),            # 鼻尖 Nose tip
    (0.0, -330.0, -65.0),       # 下巴 Chin
    (-225.0, 170.0, -135.0),    # 左眼左角 Left eye left corner
    (225.0, 170.0, -135.0),     # 右眼右角 Right eye right corner
    (-150.0, -150.0, -125.0),   # 左嘴角 Left mouth corner
    (150.0, -150.0, -125.0),    # 右嘴角 Right mouth corner
]
# 对应 2D 关键点索引（dlib 68 点）
FACE_2D_IDX: List[int] = [30, 8, 36, 45, 48, 54]


def estimate_head_pose(points: Sequence[Point], camera_matrix=None, dist_coeffs=None):
    """基于 solvePnP 估算头部欧拉角（yaw/pitch/roll，弧度 -> 度）。

    返回 (yaw_deg, pitch_deg, roll_deg)；关键点不足或求解失败返回 None。
    """
    try:
        import cv2
        import numpy as np
    except Exception:  # pragma: no cover
        return None

    if len(points) < 55:
        return None
    model_pts = np.array(FACE_3D_MODEL, dtype=np.float64)
    img_pts = np.array([points[i] for i in FACE_2D_IDX], dtype=np.float64)
    # 简易针孔相机模型（论文演示环境标定欠奉时使用近似内参）
    if camera_matrix is None:
        camera_matrix = np.array(
            [[640.0, 0.0, 320.0], [0.0, 640.0, 240.0], [0.0, 0.0, 1.0]],
            dtype=np.float64,
        )
    if dist_coeffs is None:
        dist_coeffs = np.zeros((4, 1), dtype=np.float64)
    ok, rvec, tvec = cv2.solvePnP(model_pts, img_pts, camera_matrix, dist_coeffs)
    if not ok:
        return None
    rot_mat, _ = cv2.Rodrigues(rvec)
    # 旋转矩阵 -> 欧拉角（Yaw/Pitch/Roll）
    sy = math.sqrt(rot_mat[0, 0] ** 2 + rot_mat[1, 0] ** 2)
    singular = sy < 1e-6
    if not singular:
        x = math.atan2(rot_mat[2, 1], rot_mat[2, 2])
        y = math.atan2(-rot_mat[2, 0], sy)
        z = math.atan2(rot_mat[1, 0], rot_mat[0, 0])
    else:
        x = math.atan2(-rot_mat[1, 2], rot_mat[1, 1])
        y = math.atan2(-rot_mat[2, 0], sy)
        z = 0.0
    # 统一转为度：x=pitch, y=yaw, z=roll（近似，配合界面展示）
    return math.degrees(y), math.degrees(x), math.degrees(z)


def extract_eye_mar(points: Sequence[Point]):
    """便捷聚合：返回 (左眼EAR, 右眼EAR, 平均EAR, MAR)。关键点不足时返回 None 元组。"""
    if len(points) < 68:
        return None
    left = [points[i] for i in LEFT_EYE_IDX]
    right = [points[i] for i in RIGHT_EYE_IDX]
    # 嘴部 4 点：上唇中 51 / 下唇中 57 / 左嘴角 48 / 右嘴角 54
    mouth_geo = [points[i] for i in MOUTH_PTS]
    ear_l = eye_aspect_ratio(left)
    ear_r = eye_aspect_ratio(right)
    mar = mouth_aspect_ratio(mouth_geo)
    return ear_l, ear_r, (ear_l + ear_r) / 2.0, mar

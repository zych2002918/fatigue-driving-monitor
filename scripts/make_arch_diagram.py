# -*- coding: utf-8 -*-
"""生成 README 系统架构图（matplotlib，中文 Microsoft YaHei）。

用法: python make_arch_diagram.py --out <output.png> --kind fatigue|industrial
"""
import argparse
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

C_BLUE = "#3B82C4"
C_GREEN = "#5FA96B"
C_ORANGE = "#E8A33D"
C_RED = "#D9534F"
C_GRAY = "#8C8C8C"
C_LIGHT = "#EFF5FA"
C_LIGHTG = "#EFF7F0"
C_LIGHTO = "#FDF3E0"
C_LIGHTR = "#FBEAE9"


def _box(ax, x, y, w, h, text, fc, ec, fs=10, tc="white", bold=False, sub=None):
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
                         fc=fc, ec=ec, lw=1.5)
    ax.add_patch(box)
    if sub:
        ax.text(x + w / 2, y + h * 0.62, text, ha="center", va="center",
                fontsize=fs, color=tc, fontweight="bold" if bold else "normal")
        ax.text(x + w / 2, y + h * 0.30, sub, ha="center", va="center",
                fontsize=fs - 3, color="white", alpha=0.9)
    else:
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=fs, color=tc, fontweight="bold" if bold else "normal")
    return (x, y, w, h)


def _arrow(ax, p1, p2, color=C_GRAY, style="-|>", lw=2.0):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=16,
                                 color=color, lw=lw, shrinkA=2, shrinkB=2))


def fatigue(ax):
    ax.set_xlim(0, 12); ax.set_ylim(0, 8); ax.axis("off")
    ax.set_title("多源信息融合疲劳驾驶实时预警系统架构", fontsize=15, fontweight="bold", pad=14)

    # 数据源
    _box(ax, 0.4, 6.9, 2.4, 0.9, "摄像头 / 视频流", C_BLUE, C_BLUE, sub="OpenCV 采集")
    _box(ax, 0.4, 5.4, 2.4, 0.9, "压力传感器", C_BLUE, C_BLUE, sub="方向盘握力")
    _box(ax, 0.4, 3.9, 2.4, 0.9, "GY-25 姿态传感器", C_BLUE, C_BLUE, sub="转角变化")

    # 通道
    _box(ax, 3.6, 6.5, 2.6, 1.3, "视觉通道", C_GREEN, C_GREEN, sub="EAR/MAR/头部姿态")
    _box(ax, 3.6, 4.2, 2.6, 1.3, "行为通道", C_GREEN, C_GREEN, sub="握力/转角/时长")

    _arrow(ax, (2.8, 7.35), (3.6, 7.1))
    _arrow(ax, (2.8, 5.85), (3.6, 5.2))
    _arrow(ax, (2.8, 4.35), (3.6, 4.75))

    # 分析
    _box(ax, 6.8, 6.5, 2.4, 1.3, "疲劳特征分析", C_ORANGE, C_ORANGE, sub="眨眼/哈欠/点头")
    _box(ax, 6.8, 4.2, 2.4, 1.3, "行为状态机", C_ORANGE, C_ORANGE, sub="3s/30s/时长规则")
    _arrow(ax, (6.2, 7.1), (6.8, 7.1))
    _arrow(ax, (6.2, 5.0), (6.8, 5.0))

    # 融合
    _box(ax, 9.4, 5.3, 2.3, 1.6, "多源融合决策", C_RED, C_RED, fs=12, bold=True,
         sub="30s 窗口事件计数")
    _arrow(ax, (9.2, 6.8), (9.4, 6.3))
    _arrow(ax, (9.2, 5.1), (9.4, 5.9))

    # 输出
    _box(ax, 4.2, 0.7, 3.6, 1.2, "分级预警输出", C_GRAY, C_GRAY, fs=11, sub="蜂鸣 / 语音 / 风扇 / 日志")
    _arrow(ax, (10.5, 5.3), (10.5, 1.9), color=C_RED)
    _arrow(ax, (5.0, 6.5), (4.6, 1.9), color=C_GRAY, style="-")


def industrial(ax):
    ax.set_xlim(0, 12); ax.set_ylim(0, 8); ax.axis("off")
    ax.set_title("智能化工业设施风险检测系统架构", fontsize=15, fontweight="bold", pad=14)

    # 数据源
    _box(ax, 0.3, 6.6, 2.5, 1.1, "无人机巡检", C_BLUE, C_BLUE, sub="定时定点航拍")
    _box(ax, 0.3, 4.9, 2.5, 1.1, "固定摄像头", C_BLUE, C_BLUE, sub="区域持续监控")
    _box(ax, 0.3, 3.2, 2.5, 1.1, "历史图像库", C_BLUE, C_BLUE, sub="同区域不同时间")

    # 预处理
    _box(ax, 3.5, 5.6, 2.3, 1.2, "图像预处理", C_GREEN, C_GREEN, sub="抽帧/配准/增强")

    _arrow(ax, (2.8, 7.1), (3.5, 6.5))
    _arrow(ax, (2.8, 5.4), (3.5, 5.9))
    _arrow(ax, (2.8, 3.7), (3.5, 5.0))

    # 检测
    _box(ax, 3.5, 3.4, 2.3, 1.5, "缺陷检测模型", C_ORANGE, C_ORANGE, sub="YOLO11 改进")
    _arrow(ax, (5.8, 5.6), (5.8, 4.9), color=C_GREEN)

    # 边缘
    _box(ax, 6.5, 4.3, 2.3, 1.5, "边缘计算部署", C_RED, C_RED, sub="ONNX/RKNN/INT8")
    _arrow(ax, (5.8, 4.2), (6.5, 4.9))

    # 应用
    _box(ax, 9.3, 5.0, 2.4, 1.2, "风险预警平台", C_GRAY, C_GRAY, sub="实时告警/复核")
    _box(ax, 9.3, 3.0, 2.4, 1.2, "检测报告", C_GRAY, C_GRAY, sub="时间/位置/类型")
    _arrow(ax, (8.8, 5.1), (9.3, 5.4))
    _arrow(ax, (8.8, 4.6), (9.3, 3.9))

    # 底部闭环
    _box(ax, 3.6, 0.8, 5.2, 1.1, "数据回流 → 模型迭代优化", C_GREEN, C_GREEN, sub="标注/训练/发布闭环")
    _arrow(ax, (10.5, 3.0), (10.5, 1.9), color=C_RED)
    _arrow(ax, (6.2, 0.8), (4.2, 0.8), color=C_GRAY)
    _arrow(ax, (3.6, 1.3), (1.0, 3.2), color=C_GREEN, style="-")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--kind", choices=["fatigue", "industrial"], required=True)
    args = ap.parse_args()
    fig, ax = plt.subplots(figsize=(12, 8), dpi=150)
    if args.kind == "fatigue":
        fatigue(ax)
    else:
        industrial(ax)
    fig.tight_layout()
    fig.savefig(args.out, bbox_inches="tight", facecolor="white")
    print(f"saved {args.out}")


if __name__ == "__main__":
    main()

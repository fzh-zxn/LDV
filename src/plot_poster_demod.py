#!/usr/bin/env python3
"""图2：传统 atan 解调 vs 正交鉴频（交叉相乘）对比示意图。"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from paths import OUT_FIG_POSTER, ensure_dirs
from restore import setup_matplotlib


def draw_box(ax, x, y, w, h, text, fc="#f5f9fc", ec="#2a5a8a", fs=9):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.02,rounding_size=0.06",
            linewidth=1.1,
            edgecolor=ec,
            facecolor=fc,
        )
    )
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs)


def main() -> None:
    setup_matplotlib()
    ensure_dirs()
    out = OUT_FIG_POSTER / "demod_comparison.png"

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    fig.suptitle("图2  解调方法对比", fontsize=13, fontweight="bold", y=0.98)

    # ── 左：传统 atan + 解包裹 ──
    ax = axes[0]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.text(5, 9.35, "传统方法", ha="center", fontsize=11.5, fontweight="bold", color="#8b3030")
    ax.text(5, 8.75, "atan2 → 相位解包裹 → 微分", ha="center", fontsize=9, color="#666")

    # 相位突变曲线
    ax_in = ax.inset_axes([0.08, 0.42, 0.84, 0.32])
    t = np.linspace(0, 4 * np.pi, 800)
    phase = np.arctan2(np.sin(t), np.cos(t) * 0.85)
    # 人为加几处解包裹失败式突变
    phase = np.unwrap(phase)
    jumps = [int(0.22 * len(t)), int(0.48 * len(t)), int(0.71 * len(t))]
    for j in jumps:
        phase[j:] += (np.random.rand() > 0.5) * 3.5 - 1.75
    ax_in.plot(t, phase, color="#c44", lw=1.0)
    ax_in.set_title("包裹相位 / 解包裹后（散斑下易突变）", fontsize=8)
    ax_in.set_xlabel("时间 →", fontsize=7)
    ax_in.set_ylabel("相位", fontsize=7)
    ax_in.tick_params(labelsize=6)
    for spine in ax_in.spines.values():
        spine.set_color("#aaa")

    draw_box(ax, 0.6, 0.55, 3.6, 0.9, "I(t), Q(t)", "#fff0f0", "#a04040")
    draw_box(ax, 4.4, 0.55, 2.0, 0.9, "atan2", "#fff0f0", "#a04040")
    draw_box(ax, 6.8, 0.55, 2.6, 0.9, "unwrap", "#fff0f0", "#a04040")
    ax.annotate(
        "",
        xy=(4.35, 1.0),
        xytext=(4.2, 1.0),
        arrowprops=dict(arrowstyle="-|>", color="#888", lw=1),
    )
    ax.annotate(
        "",
        xy=(6.75, 1.0),
        xytext=(6.45, 1.0),
        arrowprops=dict(arrowstyle="-|>", color="#888", lw=1),
    )
    ax.annotate(
        "",
        xy=(4.2, 1.0),
        xytext=(3.25, 1.0),
        arrowprops=dict(arrowstyle="-|>", color="#888", lw=1),
    )
    ax.text(5, 0.15, "→ 全频带伪峰，微弱振动被淹没", ha="center", fontsize=8.5, color="#8b3030")

    # ── 右：交叉相乘鉴频 ──
    ax = axes[1]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.text(5, 9.35, "本工作：正交鉴频", ha="center", fontsize=11.5, fontweight="bold", color="#1a5a8a")
    ax.text(5, 8.75, "笛卡尔域交叉相乘，不求相位", ha="center", fontsize=9, color="#666")

    draw_box(ax, 3.2, 7.0, 3.6, 0.85, "去均值 I, Q", "#e8f2fa", "#1a5a8a")
    draw_box(ax, 2.0, 5.5, 2.4, 0.85, "差分 dI, dQ", "#e8f2fa", "#1a5a8a")
    draw_box(ax, 5.6, 5.5, 3.2, 0.85, "I·dQ − Q·dI", "#d4e8f8", "#1a5a8a", 8.5)
    draw_box(ax, 2.8, 4.0, 4.4, 0.9, "÷ (I² + Q² + ε)", "#d4e8f8", "#1a5a8a")
    draw_box(ax, 3.0, 2.5, 4.0, 0.85, "振动速度 v(t)", "#c8e6c9", "#2e6b2e", 10)

    for y0, y1 in ((7.42, 6.42), (5.92, 4.95), (4.45, 3.42)):
        ax.add_patch(
            FancyArrowPatch(
                (5, y0),
                (5, y1),
                arrowstyle="-|>",
                mutation_scale=11,
                linewidth=1.1,
                color="#444",
            )
        )
    ax.add_patch(
        FancyArrowPatch(
            (4.0, 5.92),
            (3.2, 5.92),
            arrowstyle="-|>",
            mutation_scale=10,
            linewidth=1.0,
            color="#666",
        )
    )
    ax.add_patch(
        FancyArrowPatch(
            (6.0, 5.92),
            (6.8, 5.92),
            arrowstyle="-|>",
            mutation_scale=10,
            linewidth=1.0,
            color="#666",
        )
    )

    # IQ 示意小图
    ax_iq = ax.inset_axes([0.62, 0.06, 0.34, 0.38])
    th = np.linspace(0, 2 * np.pi, 200)
    ax_iq.plot(0.9 * np.cos(th), 0.7 * np.sin(th), "--", color="#9ab", lw=0.8)
    ax_iq.arrow(0, 0, 0.75, 0.45, head_width=0.06, head_length=0.05, fc="#1a5a8a", ec="#1a5a8a")
    ax_iq.arrow(0, 0, -0.35, 0.82, head_width=0.06, head_length=0.05, fc="#1a5a8a", ec="#1a5a8a")
    ax_iq.text(0.82, 0.52, "I", fontsize=9, color="#1a5a8a")
    ax_iq.text(-0.42, 0.9, "Q", fontsize=9, color="#1a5a8a")
    ax_iq.set_aspect("equal")
    ax_iq.axis("off")
    ax_iq.set_title("复平面", fontsize=7)

    ax.text(2.2, 0.2, "无相位解包裹", ha="center", fontsize=8.5, color="#1a5a8a")

    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"已保存: {out}")


if __name__ == "__main__":
    main()

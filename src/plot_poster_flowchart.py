#!/usr/bin/env python3
"""生成图3：音阶三步 / 人声两步 数据处理流程框图。"""

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from paths import OUT_FIG_POSTER, ensure_dirs
from restore import setup_matplotlib


def draw_box(ax, x, y, w, h, text: str, fc: str, ec: str = "#333") -> None:
    box = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=1.2,
        edgecolor=ec,
        facecolor=fc,
    )
    ax.add_patch(box)
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha="center",
        va="center",
        fontsize=9.5,
        color="#111",
        linespacing=1.35,
    )


def arrow_down(ax, x, y0, y1) -> None:
    ax.add_patch(
        FancyArrowPatch(
            (x, y0),
            (x, y1),
            arrowstyle="-|>",
            mutation_scale=12,
            linewidth=1.2,
            color="#444",
        )
    )


def main() -> None:
    setup_matplotlib()
    ensure_dirs()
    out = OUT_FIG_POSTER / "processing_flowchart.png"

    fig, ax = plt.subplots(figsize=(12, 7.2))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 7.2)
    ax.axis("off")

    # 标题
    ax.text(
        6,
        6.85,
        "图3  数据处理流程（音阶 / 人声并列）",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
    )

    col_w = 4.6
    box_w, box_h = 4.2, 0.72
    x_scale = 0.55
    x_voice = 6.85

    # 列标题
    ax.text(
        x_scale + box_w / 2,
        6.35,
        "音阶信号（MAT 三段拼接）",
        ha="center",
        fontsize=11.5,
        fontweight="bold",
        color="#1a4a7a",
    )
    ax.text(
        x_voice + box_w / 2,
        6.35,
        "人声信号（单段 WAV）",
        ha="center",
        fontsize=11.5,
        fontweight="bold",
        color="#7a3d1a",
    )

    scale_steps = [
        ("Stage 1\n信号还原", "I/Q 按序拼接\n50 ms 接缝淡化"),
        ("", "正交鉴频 · 98% 削峰\n50–5000 Hz 带通"),
        ("", "Fs 标定（中段对齐 1 kHz）\n→ ~500 / 1k / 2k Hz"),
        ("Stage 2\n简单降噪", "前 0.5 s 谱减\n固定带通 300–2500 Hz"),
        ("Stage 3\n最终降噪", "谱减 + 分峰自适应窄带\n按段检测主峰并淡化接缝"),
    ]
    voice_steps = [
        ("① 原始鉴频", "voice_input.wav\n（未降噪）"),
        ("② 人声降噪", "50–2000 Hz 带通\n全段 20% 分位噪声底谱减"),
        ("", "（不用开头 0.5 s 作噪声参考）"),
    ]

    colors_scale = ["#dceaf7", "#dceaf7", "#dceaf7", "#e8f4e8", "#fff0d6"]
    colors_voice = ["#fde8dc", "#fde8dc", "#f5f5f5"]

    y = 5.55
    cy = x_scale + box_w / 2
    for i, ((stage, detail), fc) in enumerate(zip(scale_steps, colors_scale)):
        if stage:
            draw_box(ax, x_scale, y, box_w, box_h, stage, fc, "#1a4a7a")
            y -= 0.85
        draw_box(ax, x_scale, y, box_w, box_h, detail, "#f8fbff", "#5a8ab8")
        if i < len(scale_steps) - 1:
            arrow_down(ax, cy, y, y - 0.18)
        y -= 1.05

    y = 5.55
    cy = x_voice + box_w / 2
    for i, ((stage, detail), fc) in enumerate(zip(voice_steps, colors_voice)):
        draw_box(ax, x_voice, y, box_w, box_h, stage, fc, "#7a3d1a")
        if i < len(voice_steps) - 1:
            arrow_down(ax, cy, y, y - 0.18)
        y -= 0.85
        if detail:
            draw_box(ax, x_voice, y, box_w, box_h, detail, "#fffaf6", "#b87a5a")
            if i < len(voice_steps) - 1:
                arrow_down(ax, cy, y, y - 0.18)
            y -= 1.05

    # 输出标注
    ax.text(
        x_scale + box_w / 2,
        0.35,
        "输出：scale_restored.wav → simple / final.wav",
        ha="center",
        fontsize=8.5,
        color="#555",
    )
    ax.text(
        x_voice + box_w / 2,
        0.35,
        "输出：voice_denoised.wav",
        ha="center",
        fontsize=8.5,
        color="#555",
    )

    # 中间分隔虚线
    ax.plot([6, 6], [0.2, 6.5], ls="--", color="#ccc", lw=1)

    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"已保存: {out}")


if __name__ == "__main__":
    main()

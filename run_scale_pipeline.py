#!/usr/bin/env python3
"""音阶信号：还原 → 简单降噪 → 最终降噪 → 三联图。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from paths import (  # noqa: E402
    FIG_SCALE_TRIPTYCH_SPEC,
    FIG_SCALE_TRIPTYCH_WELCH,
    SCALE_DENOISED_FINAL_WAV,
    SCALE_DENOISED_SIMPLE_WAV,
    SCALE_RESTORED_WAV,
)


def run(cmd: list[str]) -> None:
    print(f"\n>>> {' '.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> None:
    py = sys.executable
    steps = [
        [py, str(SRC / "restore.py")],
        [py, str(SRC / "denoise_scale_simple.py")],
        [py, str(SRC / "denoise.py")],
        [py, str(SRC / "plot_scale_triptych.py")],
    ]
    print(f"仓库根目录: {ROOT}")
    for cmd in steps:
        run(cmd)
    print("\n完成。主要输出:")
    for p in (
        SCALE_RESTORED_WAV,
        SCALE_DENOISED_SIMPLE_WAV,
        SCALE_DENOISED_FINAL_WAV,
        FIG_SCALE_TRIPTYCH_WELCH,
        FIG_SCALE_TRIPTYCH_SPEC,
    ):
        print(f"  {'[OK]' if p.is_file() else '[缺失]'} {p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

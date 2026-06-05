#!/usr/bin/env python3
"""
简单降噪：谱减（前 0.5 s 噪声参考）+ 整段固定带通 300–2500 Hz。
不做多峰自适应，输出 scale_denoised_simple.wav。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from denoise import plot_compare, read_wav, spectral_subtract
from paths import (
    DATA_MAT,
    MAT_SCALE,
    OUT_FIG_SCALE,
    SCALE_DENOISED_SIMPLE_WAV,
    SCALE_RESTORED_WAV,
    ensure_dirs,
)
from restore import bandpass, blend_segment_boundaries, load_concat


def main() -> None:
    p = argparse.ArgumentParser(description="LDV 简单降噪（谱减 + 固定带通）")
    p.add_argument("--mat-dir", type=Path, default=DATA_MAT)
    p.add_argument("--wav-in", type=Path, default=SCALE_RESTORED_WAV)
    p.add_argument("--wav-out", type=Path, default=SCALE_DENOISED_SIMPLE_WAV)
    p.add_argument("--noise-sec", type=float, default=0.5)
    p.add_argument("--alpha", type=float, default=1.8)
    p.add_argument("--beta", type=float, default=0.05)
    p.add_argument("--hp", type=float, default=300.0)
    p.add_argument("--lp", type=float, default=2500.0)
    p.add_argument("--xfade-ms", type=float, default=50.0, help="段间交叉淡化，0=关闭")
    p.add_argument(
        "--compare-fig",
        type=Path,
        default=OUT_FIG_SCALE / "denoise_simple_compare.png",
    )
    p.add_argument("--mats", nargs="+", default=MAT_SCALE)
    p.add_argument("--demod", type=int, default=2)
    p.add_argument(
        "--wav-only",
        action="store_true",
        help="单文件降噪，不使用 MAT 段界（人声等）",
    )
    args = p.parse_args()

    ensure_dirs()
    wav_in = Path(args.wav_in)
    if not wav_in.is_file():
        raise FileNotFoundError(wav_in)

    x, fs = read_wav(wav_in)
    y = spectral_subtract(x, fs, args.noise_sec, args.alpha, args.beta)
    y = bandpass(y, fs, args.hp, args.lp)

    meta: list[tuple[str, int, int]] = []
    if not args.wav_only:
        mat_paths = [args.mat_dir / m for m in args.mats]
        if all(p.is_file() for p in mat_paths):
            _, _, meta = load_concat(mat_paths, args.demod - 1)
            if args.xfade_ms > 0:
                y = blend_segment_boundaries(y, meta, fs, args.xfade_ms / 1000.0)

    y = y - np.mean(y)
    peak = np.max(np.abs(y))
    out = (y / peak if peak > 0 else y).astype(np.float32)
    wav_out = Path(args.wav_out)
    wav_out.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(str(wav_out), int(round(fs)), out)

    print(f"简单降噪: {wav_in.name} → {wav_out.name}")
    print(f"  谱减前 {args.noise_sec} s, 带通 {args.hp:.0f}–{args.lp:.0f} Hz", end="")
    if args.xfade_ms > 0:
        print(f", 段间淡化 {args.xfade_ms:.0f} ms", end="")
    print()

    if args.compare_fig:
        bounds = [i0 / fs for _n, i0, _i1 in meta[1:]]
        plot_compare(
            x,
            y,
            fs,
            bounds,
            Path(args.compare_fig),
        )


if __name__ == "__main__":
    main()

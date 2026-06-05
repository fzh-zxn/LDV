#!/usr/bin/env python3
"""对还原 WAV 画时域 / Welch / 语谱图。"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy import signal
from scipy.io import wavfile

from paths import DATA_MAT, MAT_SCALE, OUT_FIG_SCALE, OUT_WAV, SCALE_RESTORED_WAV, ensure_dirs, resolve_under
from restore import load_concat, peak_frequency, setup_matplotlib


def segment_bounds_from_mats(mat_paths: list[Path], demod_index: int) -> list[tuple[str, float]]:
    """各段分界时间 (s)，需与还原时相同的拼接顺序。"""
    _, _, meta = load_concat(mat_paths, demod_index)
    return [(name, i0) for name, i0, _i1 in meta[1:]]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--wav", type=Path, default=SCALE_RESTORED_WAV)
    p.add_argument("--mat-dir", type=Path, default=DATA_MAT)
    p.add_argument("--fig-dir", type=Path, default=OUT_FIG_SCALE)
    p.add_argument("--mats", nargs="+", default=MAT_SCALE)
    p.add_argument("--demod", type=int, default=2)
    p.add_argument("--fmax", type=float, default=2800.0)
    p.add_argument("--out", type=str, default="restored_spectrum.png")
    p.add_argument("--no-show", action="store_true")
    p.add_argument("--wav-only", action="store_true", help="不读取 MAT 段信息")
    args = p.parse_args()

    setup_matplotlib()
    ensure_dirs()
    wav_path = resolve_under(OUT_WAV, args.wav)
    fs, raw = wavfile.read(str(wav_path))
    y = np.asarray(raw, dtype=np.float64).ravel()
    if np.issubdtype(raw.dtype, np.integer):
        y = y / np.iinfo(raw.dtype).max
    y = y - np.mean(y)
    t = np.arange(y.size) / fs

    bounds: list[float] = []
    mat_paths = [args.mat_dir / m for m in args.mats]
    use_mats = not args.wav_only and all(p.is_file() for p in mat_paths)
    if use_mats:
        for _name, i0 in segment_bounds_from_mats(mat_paths, args.demod - 1):
            bounds.append(i0 / fs)

    win = 2 ** int(np.ceil(np.log2(max(512, int(round(0.08 * fs))))))
    overlap = int(round(win * 0.75))
    nperseg = min(16384, max(1024, y.size // 8))

    fig, axes = plt.subplots(1, 3, figsize=(14, 4), constrained_layout=True)

    axes[0].plot(t, y, "b", lw=0.4)
    for b in bounds:
        axes[0].axvline(b, color="#888", ls="--", lw=0.6)
    axes[0].set_title("时域")
    axes[0].set_xlabel("s")
    axes[0].grid(True, alpha=0.3)

    fre, px = signal.welch(
        y, fs=fs, window="hann", nperseg=nperseg, noverlap=nperseg // 2, nfft=max(win * 2, nperseg)
    )
    axes[1].plot(fre, 10 * np.log10(px + 1e-12), "b")
    axes[1].set_xlim(0, args.fmax)
    axes[1].set_title("Welch 功率谱")
    axes[1].set_xlabel("Hz")
    axes[1].grid(True, alpha=0.3)

    fre2, tt, sxx = signal.spectrogram(y, fs=fs, window="hann", nperseg=win, noverlap=overlap, nfft=win * 2)
    db = 10 * np.log10(sxx + 1e-12)
    vmax = np.percentile(db, 99.0)
    im = axes[2].pcolormesh(tt, fre2, db, shading="auto", cmap="viridis", vmin=vmax - 55, vmax=vmax)
    axes[2].set_ylim(0, args.fmax)
    for b in bounds:
        axes[2].axvline(b, color="w", ls="--", lw=0.5, alpha=0.75)
    axes[2].set_title("语谱图")
    axes[2].set_xlabel("s")
    plt.colorbar(im, ax=axes[2], fraction=0.046, pad=0.04)

    lines = [f"Fs = {fs:.0f} Hz", f"T = {t[-1]:.1f} s"]
    if use_mats:
        _, _, meta = load_concat(mat_paths, args.demod - 1)
        for name, i0, i1 in meta:
            seg = y[i0:i1]
            if seg.size >= 64:
                lines.append(f"{name}: {peak_frequency(seg, fs):.0f} Hz")
    else:
        if y.size >= 64:
            lines.append(f"主峰: {peak_frequency(y, fs):.0f} Hz")
    fig.suptitle("\n".join(lines), fontsize=11)

    out = resolve_under(args.fig_dir, args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"已保存: {out}")
    if args.no_show:
        plt.close(fig)
    else:
        plt.show()


if __name__ == "__main__":
    main()

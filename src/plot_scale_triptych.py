#!/usr/bin/env python3
"""分级处理对比图：Welch + 语谱，支持 2 联或 3 联（海报用）。"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy import signal
from scipy.io import wavfile

from paths import (
    DATA_MAT,
    FIG_SCALE_TRIPTYCH_SPEC,
    FIG_SCALE_TRIPTYCH_WELCH,
    MAT_SCALE,
    OUT_FIG_SCALE,
    OUT_WAV,
    SCALE_DENOISED_FINAL_WAV,
    SCALE_DENOISED_SIMPLE_WAV,
    SCALE_RESTORED_WAV,
    ensure_dirs,
)
from restore import load_concat, setup_matplotlib


def read_wav(path: Path) -> tuple[np.ndarray, float]:
    fs, raw = wavfile.read(str(path))
    y = np.asarray(raw, dtype=np.float64).ravel()
    if np.issubdtype(raw.dtype, np.integer):
        y = y / np.iinfo(raw.dtype).max
    return y - np.mean(y), float(fs)


def main() -> None:
    p = argparse.ArgumentParser(description="2/3 路处理 Welch / 语谱对比图")
    p.add_argument("--wav-dir", type=Path, default=OUT_WAV)
    p.add_argument("--mat-dir", type=Path, default=DATA_MAT)
    p.add_argument("--fig-dir", type=Path, default=OUT_FIG_SCALE)
    p.add_argument(
        "--wavs",
        nargs="+",
        default=[
            SCALE_RESTORED_WAV.name,
            SCALE_DENOISED_SIMPLE_WAV.name,
            SCALE_DENOISED_FINAL_WAV.name,
        ],
        metavar="WAV",
    )
    p.add_argument(
        "--labels",
        nargs="+",
        default=["信号还原（未降噪）", "简单降噪", "最终降噪"],
    )
    p.add_argument("--title", type=str, default="", help="总标题前缀，空=自动")
    p.add_argument(
        "--spec-layout",
        choices=("vertical", "horizontal"),
        default="vertical",
        help="语谱三联排版，默认竖排",
    )
    p.add_argument("--mats", nargs="+", default=MAT_SCALE)
    p.add_argument("--demod", type=int, default=2)
    p.add_argument("--no-mat-bounds", action="store_true", help="不画音阶 MAT 段界竖线（人声等）")
    p.add_argument("--fmin", type=float, default=0.0, help="频率轴下限 (Hz)，语谱纵轴 / Welch 横轴")
    p.add_argument("--fmax", type=float, default=2800.0, help="频率轴上限 (Hz)")
    p.add_argument("--out-welch", type=str, default=FIG_SCALE_TRIPTYCH_WELCH.name)
    p.add_argument("--out-spec", type=str, default=FIG_SCALE_TRIPTYCH_SPEC.name)
    p.add_argument("--dpi", type=int, default=180)
    args = p.parse_args()

    setup_matplotlib()
    ensure_dirs()
    wav_dir = args.wav_dir
    fig_dir = args.fig_dir
    n_panel = len(args.wavs)
    if n_panel not in (2, 3):
        raise ValueError("--wavs 需要 2 或 3 个文件")
    if len(args.labels) != n_panel:
        raise ValueError("--labels 数量须与 --wavs 一致")

    signals: list[np.ndarray] = []
    fs_list: list[float] = []
    for name in args.wavs:
        path = wav_dir / name
        if not path.is_file():
            raise FileNotFoundError(path)
        y, fs = read_wav(path)
        signals.append(y)
        fs_list.append(fs)

    if len(set(round(f) for f in fs_list)) > 1:
        print("警告: 三路 WAV 采样率不一致，语谱/谱图按各自 Fs 计算")
    fs = fs_list[0]

    bounds: list[float] = []
    if not args.no_mat_bounds:
        mat_paths = [args.mat_dir / m for m in args.mats]
        if all(mp.is_file() for mp in mat_paths):
            _, _, meta = load_concat(mat_paths, args.demod - 1)
            bounds = [i0 / fs for _name, i0, _i1 in meta[1:]]

    win = 2 ** int(np.ceil(np.log2(max(512, int(round(0.08 * fs))))))
    overlap = int(round(win * 0.75))
    nperseg = min(16384, max(1024, signals[0].size // 8))

    welch_curves: list[tuple[np.ndarray, np.ndarray]] = []
    spec_data: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
    for y in signals:
        fre, px = signal.welch(
            y,
            fs=fs,
            window="hann",
            nperseg=nperseg,
            noverlap=nperseg // 2,
            nfft=max(win * 2, nperseg),
        )
        welch_curves.append((fre, 10 * np.log10(px + 1e-12)))
        fre2, tt, sxx = signal.spectrogram(
            y, fs=fs, window="hann", nperseg=win, noverlap=overlap, nfft=win * 2
        )
        spec_data.append((fre2, tt, 10 * np.log10(sxx + 1e-12)))

    flo, fhi = args.fmin, args.fmax

    # Welch 纵轴（dB）：仅在 [fmin, fmax] 内按谱峰定标
    w_peak = -np.inf
    w_floor = np.inf
    for fre, db in welch_curves:
        m = (fre >= flo) & (fre <= fhi)
        if not np.any(m):
            continue
        seg = db[m]
        w_peak = max(w_peak, float(np.max(seg)))
        w_floor = min(w_floor, float(np.percentile(seg, 15)))
    w_max = w_peak + 5.0
    w_min = min(w_floor - 8.0, w_max - 75.0)

    # 语谱色标：仅用展示频带内的像素，避免 0–fmin 空区拉偏对比度
    spec_band: list[np.ndarray] = []
    for fre2, _tt, db in spec_data:
        fm = (fre2 >= flo) & (fre2 <= fhi)
        if np.any(fm):
            spec_band.append(db[fm, :].ravel())
    all_spec = np.concatenate(spec_band) if spec_band else np.array([-80.0])
    s_vmax = float(np.percentile(all_spec, 99.0))
    s_vmin = s_vmax - 55.0

    title_pre = args.title or ("LDV 音阶" if n_panel == 3 else "LDV 人声")
    welch_w = 4.5 * n_panel
    fig_w, axes_w = plt.subplots(1, n_panel, figsize=(welch_w, 3.6), constrained_layout=True)
    axes_w = np.atleast_1d(axes_w).ravel()
    for ax, (fre, db), label in zip(axes_w, welch_curves, args.labels):
        ax.plot(fre, db, color="#1f5a9e", lw=0.95)
        ax.set_xlim(flo, fhi)
        ax.set_ylim(w_min, w_max)
        ax.set_title(label, fontsize=11)
        ax.set_xlabel("频率 (Hz)")
        ax.grid(True, alpha=0.25)
        for b in bounds:
            ax.axvline(b, color="#888", ls="--", lw=0.5, alpha=0.6)
    axes_w[0].set_ylabel("功率谱 (dB)")
    fig_w.suptitle(f"{title_pre} — Welch 功率谱（Fs ≈ {fs:.0f} Hz）", fontsize=12)
    fig_dir.mkdir(parents=True, exist_ok=True)
    out_w = fig_dir / args.out_welch
    fig_w.savefig(out_w, dpi=args.dpi, bbox_inches="tight")
    plt.close(fig_w)
    print(f"已保存: {out_w}")

    if args.spec_layout == "vertical":
        fig_s, axes_s = plt.subplots(
            n_panel, 1, figsize=(10.5, 3.2 * n_panel), constrained_layout=True, sharex=True
        )
    else:
        fig_s, axes_s = plt.subplots(1, n_panel, figsize=(welch_w, 3.8), constrained_layout=True)
    axes_s = np.atleast_1d(axes_s).ravel()
    im_last = None
    for ax, (fre2, tt, db), label in zip(axes_s, spec_data, args.labels):
        im_last = ax.pcolormesh(
            tt, fre2, db, shading="auto", cmap="viridis", vmin=s_vmin, vmax=s_vmax
        )
        ax.set_ylim(flo, fhi)
        ax.set_title(label, fontsize=11)
        for b in bounds:
            ax.axvline(b, color="w", ls="--", lw=0.45, alpha=0.75)
    axes_s[0].set_ylabel("频率 (Hz)")
    axes_s[-1].set_xlabel("时间 (s)")
    if im_last is not None:
        fig_s.colorbar(im_last, ax=list(axes_s), fraction=0.02, pad=0.02, label="dB")
    fig_s.suptitle(f"{title_pre} — 语谱图（Fs ≈ {fs:.0f} Hz）", fontsize=12)
    out_s = fig_dir / args.out_spec
    fig_s.savefig(out_s, dpi=args.dpi, bbox_inches="tight")
    plt.close(fig_s)
    print(f"已保存: {out_s}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""人声两步：未降噪 → 带通+全段噪声底谱减；仅出语谱二联图（0–2000 Hz）。"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy import signal
from scipy.io import wavfile

from denoise import denoise_voice, read_wav
from paths import FIG_VOICE_DIPTYCH_SPEC, VOICE_DENOISED_WAV, VOICE_INPUT_WAV, ensure_dirs
from restore import setup_matplotlib


def plot_voice_spec_diptych(
    paths: list[Path],
    labels: list[str],
    fs: float,
    out: Path,
    fmin: float,
    fmax: float,
    dpi: int,
) -> None:
    setup_matplotlib()
    win = 2 ** int(np.ceil(np.log2(max(512, int(round(0.08 * fs))))))
    overlap = int(round(win * 0.75))
    specs: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
    for path in paths:
        y, _ = read_wav(path)
        fre, tt, sxx = signal.spectrogram(
            y, fs=fs, window="hann", nperseg=win, noverlap=overlap, nfft=win * 2
        )
        specs.append((fre, tt, 10 * np.log10(sxx + 1e-12)))

    band_vals = []
    for fre, _tt, db in specs:
        m = (fre >= fmin) & (fre <= fmax)
        if np.any(m):
            band_vals.append(db[m, :].ravel())
    all_db = np.concatenate(band_vals) if band_vals else np.array([-80.0])
    vmax = float(np.percentile(all_db, 99.0))
    vmin = vmax - 55.0

    fig, axes = plt.subplots(2, 1, figsize=(10.5, 6.4), constrained_layout=True, sharex=True)
    im_last = None
    for ax, (fre, tt, db), label in zip(axes, specs, labels):
        im_last = ax.pcolormesh(
            tt, fre, db, shading="auto", cmap="viridis", vmin=vmin, vmax=vmax
        )
        ax.set_ylim(fmin, fmax)
        ax.set_title(label, fontsize=11)
    axes[0].set_ylabel("频率 (Hz)")
    axes[-1].set_xlabel("时间 (s)")
    if im_last is not None:
        fig.colorbar(im_last, ax=axes, fraction=0.02, pad=0.02, label="dB")
    fig.suptitle(f"LDV 人声 — 语谱图（Fs ≈ {fs:.0f} Hz，{fmin:.0f}–{fmax:.0f} Hz）", fontsize=12)
    fig.savefig(out, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"已保存: {out}")


def main() -> None:
    p = argparse.ArgumentParser(description="人声两步降噪（无开头谱减）")
    p.add_argument("--wav-in", type=Path, default=VOICE_INPUT_WAV)
    p.add_argument("--wav-out", type=Path, default=VOICE_DENOISED_WAV)
    p.add_argument("--hp", type=float, default=50.0, help="带通下限 (Hz)，0–2000 显示时建议 50")
    p.add_argument("--lp", type=float, default=2000.0)
    p.add_argument("--alpha", type=float, default=1.5, help="谱减强度")
    p.add_argument("--noise-pct", type=float, default=20.0, help="全段噪声谱估计分位 (%)")
    p.add_argument("--fmin", type=float, default=0.0)
    p.add_argument("--fmax", type=float, default=2000.0)
    p.add_argument("--out-spec", type=Path, default=FIG_VOICE_DIPTYCH_SPEC)
    p.add_argument("--dpi", type=int, default=180)
    args = p.parse_args()

    ensure_dirs()
    wav_in = Path(args.wav_in)
    if not wav_in.is_file():
        raise FileNotFoundError(wav_in)

    x, fs = read_wav(wav_in)
    y = denoise_voice(
        x,
        fs,
        hp_hz=args.hp,
        lp_hz=args.lp,
        alpha=args.alpha,
        noise_percentile=args.noise_pct,
    )
    peak = np.max(np.abs(y))
    out = (y / peak if peak > 0 else y).astype(np.float32)
    wav_out = Path(args.wav_out)
    wav_out.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(str(wav_out), int(round(fs)), out)

    print(f"输入: {wav_in.name}  Fs={fs:.0f} Hz  T={x.size/fs:.2f} s")
    print(
        f"降噪: 带通 {args.hp:.0f}–{args.lp:.0f} Hz + "
        f"全段 {args.noise_pct:.0f}% 分位噪声底谱减 (alpha={args.alpha})"
    )
    print(f"已写入 {wav_out.name}")

    plot_voice_spec_diptych(
        [wav_in, wav_out],
        ["人声（未降噪）", "人声（降噪后）"],
        fs,
        Path(args.out_spec),
        args.fmin,
        args.fmax,
        args.dpi,
    )


if __name__ == "__main__":
    main()

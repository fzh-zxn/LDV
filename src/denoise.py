#!/usr/bin/env python3
"""
LDV 降噪：谱减 + 多峰自适应窄带通。

默认可从 MAT 一条龙（对齐 untitled.m：鉴频→削峰→50–5000 Hz 带通→谱减，
但 Fs 按中间段标定到 ~500/1000/2000 Hz，再做多峰自适应）。
也可对已有 scale_restored.wav 仅做后处理。
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy import signal
from scipy.io import wavfile

from paths import (
    DATA_MAT,
    MAT_SCALE,
    OUT_FIG_SCALE,
    OUT_WAV,
    SCALE_DENOISED_FINAL_WAV,
    SCALE_RESTORED_WAV,
    ensure_dirs,
)
from restore import (
    bandpass,
    blend_segment_boundaries,
    crossfade_join,
    load_concat,
    peak_frequency,
    restore,
    restore_blended,
    setup_matplotlib,
)


@dataclass
class ToneDetect:
    f0_hz: float
    hp_hz: float
    lp_hz: float
    peak_vs_median_db: float
    prominence_db: float


@dataclass
class SegmentReport:
    name: str
    tones: list[ToneDetect]
    used_narrow: bool
    fallback_hp: float = 0.0
    fallback_lp: float = 0.0


@dataclass
class BandpassConfig:
    guard_lo: float = 300.0
    guard_hi: float = 2500.0
    bw_ratio: float = 0.12
    bw_min_hz: float = 60.0
    min_prominence_db: float = 6.0
    min_peak_vs_median_db: float = 5.0
    min_band_hz: float = 80.0
    max_peaks: int = 5


def read_wav(path: Path) -> tuple[np.ndarray, float]:
    fs, raw = wavfile.read(str(path))
    y = np.asarray(raw, dtype=np.float64).ravel()
    if np.issubdtype(raw.dtype, np.integer):
        y = y / np.iinfo(raw.dtype).max
    return y, float(fs)


def spectral_subtract(
    x: np.ndarray,
    fs: float,
    noise_sec: float,
    alpha: float,
    beta: float,
) -> np.ndarray:
    win_len = int(2 ** np.ceil(np.log2(max(256, round(fs / 20)))))
    hop = win_len // 4
    nfft = max(4096, win_len * 2)
    win = signal.windows.hann(win_len, sym=False)

    _, _, zxx = signal.stft(
        x,
        fs=fs,
        window=win,
        nperseg=win_len,
        noverlap=win_len - hop,
        nfft=nfft,
        boundary="zeros",
        padded=True,
    )
    mag = np.abs(zxx)
    phase = np.angle(zxx)

    n_noise = max(1, int(round(noise_sec * fs / hop)))
    noise_mag = np.mean(mag[:, :n_noise], axis=1, keepdims=True)

    mag_sub = np.maximum(mag - alpha * noise_mag, beta * mag)
    floor = np.median(mag_sub, axis=1, keepdims=True)
    mag_clean = np.maximum(
        mag_sub - 0.5 * floor,
        beta * np.median(mag, axis=1, keepdims=True),
    )

    _, y = signal.istft(
        mag_clean * np.exp(1j * phase),
        fs=fs,
        window=win,
        nperseg=win_len,
        noverlap=win_len - hop,
        nfft=nfft,
        boundary=True,
    )
    y = np.asarray(y, dtype=np.float64).ravel()
    if y.size < x.size:
        y = np.pad(y, (0, x.size - y.size))
    else:
        y = y[: x.size]
    return y - np.mean(y)


def _stft_mag_phase(x: np.ndarray, fs: float) -> tuple[np.ndarray, np.ndarray, int, int, int, object]:
    win_len = int(2 ** np.ceil(np.log2(max(256, round(fs / 20)))))
    hop = win_len // 4
    nfft = max(4096, win_len * 2)
    win = signal.windows.hann(win_len, sym=False)
    _, _, zxx = signal.stft(
        x,
        fs=fs,
        window=win,
        nperseg=win_len,
        noverlap=win_len - hop,
        nfft=nfft,
        boundary="zeros",
        padded=True,
    )
    return np.abs(zxx), np.angle(zxx), win_len, hop, nfft, win


def _istft_from_mag_phase(
    mag: np.ndarray,
    phase: np.ndarray,
    fs: float,
    win_len: int,
    hop: int,
    nfft: int,
    win: object,
    n_samples: int,
) -> np.ndarray:
    _, y = signal.istft(
        mag * np.exp(1j * phase),
        fs=fs,
        window=win,
        nperseg=win_len,
        noverlap=win_len - hop,
        nfft=nfft,
        boundary=True,
    )
    y = np.asarray(y, dtype=np.float64).ravel()
    if y.size < n_samples:
        y = np.pad(y, (0, n_samples - y.size))
    else:
        y = y[:n_samples]
    return y - np.mean(y)


def spectral_subtract_noise_floor(
    x: np.ndarray,
    fs: float,
    alpha: float = 1.5,
    beta: float = 0.05,
    noise_percentile: float = 20.0,
) -> np.ndarray:
    """
    人声友好：用全段各频点低分位（默认 20%）估计噪声谱，不依赖开头 0.5 s。
    适合无纯静音前缀、语音占满时长的 LDV 录音。
    """
    mag, phase, win_len, hop, nfft, win = _stft_mag_phase(x, fs)
    noise_mag = np.percentile(mag, noise_percentile, axis=1, keepdims=True)
    mag_sub = np.maximum(mag - alpha * noise_mag, beta * mag)
    floor = np.median(mag_sub, axis=1, keepdims=True)
    mag_clean = np.maximum(
        mag_sub - 0.35 * floor,
        beta * np.median(mag, axis=1, keepdims=True),
    )
    return _istft_from_mag_phase(mag_clean, phase, fs, win_len, hop, nfft, win, x.size)


def denoise_voice(
    x: np.ndarray,
    fs: float,
    hp_hz: float = 50.0,
    lp_hz: float = 2000.0,
    alpha: float = 1.5,
    beta: float = 0.05,
    noise_percentile: float = 20.0,
) -> np.ndarray:
    """带通 0~lp Hz（下限用 hp≥50 实现）+ 全段低分位谱减。"""
    y = bandpass(x, fs, hp_hz, lp_hz)
    y = spectral_subtract_noise_floor(y, fs, alpha, beta, noise_percentile)
    return y - np.mean(y)


def _tone_from_peak(
    fre_m: np.ndarray,
    px_m: np.ndarray,
    idx: int,
    med: float,
    cfg: BandpassConfig,
    prominence_lin: float,
) -> ToneDetect | None:
    peak_pow = float(px_m[idx])
    peak_db = 10 * np.log10(peak_pow / med + 1e-12)
    if peak_db < cfg.min_peak_vs_median_db:
        return None

    f0 = float(fre_m[idx])
    bw = max(cfg.bw_min_hz, f0 * cfg.bw_ratio)
    hp = max(cfg.guard_lo, f0 - bw)
    lp = min(cfg.guard_hi, f0 + bw)
    if lp - hp < cfg.min_band_hz:
        return None

    prom_db = 10 * np.log10(prominence_lin / med + 1e-12) if prominence_lin > 0 else 0.0
    return ToneDetect(
        f0_hz=f0,
        hp_hz=hp,
        lp_hz=lp,
        peak_vs_median_db=peak_db,
        prominence_db=prom_db,
    )


def detect_tones(seg: np.ndarray, fs: float, cfg: BandpassConfig) -> list[ToneDetect]:
    """在守护带内检测所有满足条件的峰（可多个）。"""
    if seg.size < 64:
        return []

    nperseg = min(16384, max(256, seg.size // 2))
    fre, px = signal.welch(seg, fs=fs, window="hann", nperseg=nperseg, noverlap=nperseg // 2)
    mask = (fre >= cfg.guard_lo) & (fre <= cfg.guard_hi)
    if not np.any(mask):
        return []

    fre_m = fre[mask]
    px_m = px[mask]
    med = float(np.median(px_m))
    if med <= 0:
        return []

    min_prom = med * (10 ** (cfg.min_prominence_db / 10) - 1)
    peaks_idx, props = signal.find_peaks(
        px_m,
        prominence=min_prom,
        distance=max(3, int(len(px_m) * 0.02)),
    )

    tones: list[ToneDetect] = []
    if peaks_idx.size > 0:
        order = peaks_idx[np.argsort(px_m[peaks_idx])[::-1]]
        prominences = props.get("prominences", np.zeros(peaks_idx.size))
        prom_map = {int(p): float(prominences[i]) for i, p in enumerate(peaks_idx)}
        for idx in order:
            tone = _tone_from_peak(fre_m, px_m, int(idx), med, cfg, prom_map.get(int(idx), 0.0))
            if tone is not None:
                tones.append(tone)
    else:
        tone = _tone_from_peak(fre_m, px_m, int(np.argmax(px_m)), med, cfg, 0.0)
        if tone is not None:
            tones.append(tone)

    tones.sort(key=lambda t: t.peak_vs_median_db, reverse=True)
    if cfg.max_peaks > 0:
        tones = tones[: cfg.max_peaks]
    return tones


def apply_multiband(seg: np.ndarray, fs: float, tones: list[ToneDetect]) -> np.ndarray:
    """多峰窄带滤波结果叠加（按峰数归一化，避免峰越多幅度越大）。"""
    if not tones:
        return seg
    acc = np.zeros_like(seg)
    for tone in tones:
        acc += bandpass(seg, fs, tone.hp_hz, tone.lp_hz)
    return acc / len(tones)


def adaptive_bandpass(
    v: np.ndarray,
    fs: float,
    meta: list[tuple[str, int, int]],
    cfg: BandpassConfig,
    xfade_sec: float = 0.05,
) -> tuple[np.ndarray, list[SegmentReport]]:
    """逐段多峰检测 → 各峰窄带叠加；段间交叉淡化减轻拼接断裂。"""
    parts: list[np.ndarray] = []
    reports: list[SegmentReport] = []

    for name, i0, i1 in meta:
        seg = v[i0:i1]
        tones = detect_tones(seg, fs, cfg)
        if tones:
            parts.append(apply_multiband(seg, fs, tones))
            reports.append(SegmentReport(name=name, tones=tones, used_narrow=True))
        else:
            parts.append(bandpass(seg, fs, cfg.guard_lo, cfg.guard_hi))
            reports.append(
                SegmentReport(
                    name=name,
                    tones=[],
                    used_narrow=False,
                    fallback_hp=cfg.guard_lo,
                    fallback_lp=cfg.guard_hi,
                )
            )

    out = np.zeros_like(v)
    off = 0
    for part in parts:
        out[off : off + part.size] = part
        off += part.size
    if xfade_sec > 0:
        out = blend_segment_boundaries(out, meta, fs, xfade_sec)
    return out - np.mean(out), reports


def process_from_mat(
    mat_paths: list[Path],
    demod_index: int,
    ref_segment: int,
    ref_hz: float,
    restore_hp: float,
    restore_lp: float,
    clip_pct: float,
    restore_xfade_sec: float,
    noise_sec: float,
    alpha: float,
    beta: float,
    bp_cfg: BandpassConfig,
    bandpass_mode: str,
    denoise_xfade_sec: float,
) -> tuple[np.ndarray, np.ndarray, float, list[tuple[str, int, int]], list[SegmentReport]]:
    """
    untitled.m 风格宽带还原 + 正确 Fs + 前 noise_sec 谱减 + 多峰自适应。
    返回 (宽带还原对照, 降噪结果, Fs, meta, reports)。
    """
    if restore_xfade_sec > 0:
        wide, fs, meta = restore_blended(
            mat_paths,
            demod_index,
            ref_segment,
            ref_hz,
            restore_hp,
            restore_lp,
            clip_pct,
            restore_xfade_sec,
        )
    else:
        wide, fs, meta = restore(
            mat_paths,
            demod_index,
            ref_segment,
            ref_hz,
            restore_hp,
            restore_lp,
            clip_pct,
        )
        wide = wide - np.mean(wide)

    x_ref = wide.copy()
    y = spectral_subtract(wide, fs, noise_sec, alpha, beta)

    reports: list[SegmentReport] = []
    if bandpass_mode == "adaptive":
        y, reports = adaptive_bandpass(y, fs, meta, bp_cfg, xfade_sec=denoise_xfade_sec)
    elif bandpass_mode == "fixed":
        if len(meta) >= 2 and denoise_xfade_sec > 0:
            parts = [
                bandpass(y[i0:i1], fs, bp_cfg.guard_lo, bp_cfg.guard_hi) for _n, i0, i1 in meta
            ]
            y = crossfade_join(parts, int(round(denoise_xfade_sec * fs)))
        else:
            y = bandpass(y, fs, bp_cfg.guard_lo, bp_cfg.guard_hi)
        y = y - np.mean(y)
    elif len(meta) >= 2 and denoise_xfade_sec > 0:
        y = blend_segment_boundaries(y, meta, fs, denoise_xfade_sec)
        y = y - np.mean(y)

    return x_ref, y, fs, meta, reports


def plot_compare(
    x: np.ndarray,
    y: np.ndarray,
    fs: float,
    bounds: list[float],
    save_path: Path,
    fmax: float = 2800.0,
) -> None:
    setup_matplotlib()
    win = 2 ** int(np.ceil(np.log2(max(512, int(round(0.08 * fs))))))
    overlap = int(round(win * 0.75))
    nperseg = min(16384, max(1024, x.size // 8))
    t = np.arange(x.size) / fs

    fig, axes = plt.subplots(2, 2, figsize=(12, 7), constrained_layout=True)

    for col, sig, title in ((0, x, "降噪前"), (1, y, "降噪后")):
        axes[0, col].plot(t, sig, "b", lw=0.35)
        for b in bounds:
            axes[0, col].axvline(b, color="#888", ls="--", lw=0.5)
        axes[0, col].set_title(f"{title} — 时域")
        axes[0, col].set_xlabel("s")
        axes[0, col].grid(True, alpha=0.3)

        fre, px = signal.welch(sig, fs=fs, nperseg=nperseg, noverlap=nperseg // 2)
        axes[1, col].plot(fre, 10 * np.log10(px + 1e-12), lw=0.9)
        axes[1, col].set_xlim(0, fmax)
        axes[1, col].set_title(f"{title} — Welch")
        axes[1, col].set_xlabel("Hz")
        axes[1, col].grid(True, alpha=0.3)

    fre2, tt, sxx0 = signal.spectrogram(x, fs=fs, nperseg=win, noverlap=overlap, nfft=win * 2)
    _, _, sxx1 = signal.spectrogram(y, fs=fs, nperseg=win, noverlap=overlap, nfft=win * 2)
    db0 = 10 * np.log10(sxx0 + 1e-12)
    db1 = 10 * np.log10(sxx1 + 1e-12)
    vmax = max(np.percentile(db0, 99.0), np.percentile(db1, 99.0))

    fig2, ax2 = plt.subplots(2, 1, figsize=(12, 5), constrained_layout=True, sharex=True)
    for ax, db, ttl in zip(ax2, (db0, db1), ("降噪前 — 语谱图", "降噪后 — 语谱图")):
        im = ax.pcolormesh(tt, fre2, db, shading="auto", cmap="viridis", vmin=vmax - 55, vmax=vmax)
        ax.set_ylim(0, fmax)
        for b in bounds:
            ax.axvline(b, color="w", ls="--", lw=0.4, alpha=0.7)
        ax.set_title(ttl)
        ax.set_ylabel("Hz")
    ax2[-1].set_xlabel("s")
    fig2.colorbar(im, ax=ax2[-1], fraction=0.02, pad=0.02)
    fig2.suptitle(f"语谱对比  Fs={fs:.0f} Hz", fontsize=12)
    spec_path = save_path.with_name(save_path.stem + "_spec.png")
    fig2.savefig(spec_path, dpi=150, bbox_inches="tight")
    plt.close(fig2)

    title = "谱减 + 多峰自适应窄带通"
    if save_path.stem.find("simple") >= 0:
        title = "谱减 + 固定带通（简单）"
    elif save_path.stem.find("mat") >= 0:
        title = "MAT 还原(宽带) → 谱减 + 多峰自适应"
    fig.suptitle(title, fontsize=12)
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"已保存对比图: {save_path}, {spec_path.name}")


def main() -> None:
    p = argparse.ArgumentParser(
        description="LDV 降噪：谱减 + 多峰自适应（推荐 --from-mat 对齐 untitled.m 且频率正确）"
    )
    p.add_argument("--mat-dir", type=Path, default=DATA_MAT, help="MAT 目录（--from-mat / 段界）")
    p.add_argument("--wav-dir", type=Path, default=OUT_WAV, help="WAV 输入/输出目录")
    p.add_argument("--fig-dir", type=Path, default=OUT_FIG_SCALE, help="对比图输出目录")
    p.add_argument(
        "--from-mat",
        action="store_true",
        help="从 MAT 直接处理：鉴频+Fs标定+宽带通+谱减+多峰自适应（不必先有 WAV）",
    )
    p.add_argument("--wav-in", type=str, default=SCALE_RESTORED_WAV.name)
    p.add_argument("--wav-out", type=str, default=SCALE_DENOISED_FINAL_WAV.name)
    p.add_argument("--ref-seg", type=int, default=1, help="--from-mat 时 Fs 标定参考段 0/1/2")
    p.add_argument("--ref-hz", type=float, default=1000.0, help="--from-mat 时参考段标称频率")
    p.add_argument("--restore-hp", type=float, default=50.0, help="--from-mat 还原带通下限（同 untitled.m）")
    p.add_argument("--restore-lp", type=float, default=5000.0, help="--from-mat 还原带通上限")
    p.add_argument("--clip-pct", type=float, default=98.0, help="--from-mat 鉴频削峰分位")
    p.add_argument(
        "--restore-xfade-ms",
        type=float,
        default=50.0,
        help="--from-mat 还原阶段段界淡化 (ms)",
    )
    p.add_argument("--noise-sec", type=float, default=0.5)
    p.add_argument("--alpha", type=float, default=1.8)
    p.add_argument("--beta", type=float, default=0.05)
    p.add_argument("--guard-lo", type=float, default=300.0, help="搜索/回退带通下限")
    p.add_argument("--guard-hi", type=float, default=2500.0, help="搜索/回退带通上限")
    p.add_argument("--bw-ratio", type=float, default=0.12, help="窄带半宽 = f0 × 该比例")
    p.add_argument("--bw-min", type=float, default=60.0, help="窄带最小半宽 Hz")
    p.add_argument("--min-prominence-db", type=float, default=8.0, help="find_peaks 突出度 (dB)")
    p.add_argument("--min-peak-db", type=float, default=6.0, help="每峰高于带内中位数 (dB)")
    p.add_argument("--max-peaks", type=int, default=3, help="每段最多保留峰数，0=不限制")
    p.add_argument("--xfade-ms", type=float, default=50.0, help="段间交叉淡化 (ms)，0=关闭")
    p.add_argument(
        "--bandpass",
        choices=("adaptive", "fixed", "off"),
        default="adaptive",
        help="adaptive=按段检测窄带；fixed=固定 guard 带；off=不滤波",
    )
    p.add_argument("--compare-fig", type=str, default="denoise_final_compare.png")
    p.add_argument("--mats", nargs="+", default=MAT_SCALE)
    p.add_argument("--demod", type=int, default=2)
    p.add_argument(
        "--wav-only",
        action="store_true",
        help="单文件降噪，整段处理，不使用 MAT 段界（人声等）",
    )
    args = p.parse_args()

    xfade_sec = args.xfade_ms / 1000.0
    bp_cfg = BandpassConfig(
        guard_lo=args.guard_lo,
        guard_hi=args.guard_hi,
        bw_ratio=args.bw_ratio,
        bw_min_hz=args.bw_min,
        min_prominence_db=args.min_prominence_db,
        min_peak_vs_median_db=args.min_peak_db,
        max_peaks=args.max_peaks,
    )

    ensure_dirs()
    mat_paths = [args.mat_dir / m for m in args.mats]
    reports: list[SegmentReport] = []

    if args.from_mat:
        for path in mat_paths:
            if not path.is_file():
                raise FileNotFoundError(path)
        x, y, fs, meta, reports = process_from_mat(
            mat_paths,
            demod_index=args.demod - 1,
            ref_segment=args.ref_seg,
            ref_hz=args.ref_hz,
            restore_hp=args.restore_hp,
            restore_lp=args.restore_lp,
            clip_pct=args.clip_pct,
            restore_xfade_sec=args.restore_xfade_ms / 1000.0,
            noise_sec=args.noise_sec,
            alpha=args.alpha,
            beta=args.beta,
            bp_cfg=bp_cfg,
            bandpass_mode=args.bandpass,
            denoise_xfade_sec=xfade_sec,
        )
        print("MAT 流程（untitled.m 鉴频+宽带通 + Fs 标定 + 谱减 + 多峰自适应）")
        print(f"  N={y.size}, Fs={fs:.1f} Hz, T={y.size/fs:.2f} s")
        print(f"  Fs 标定：第 {args.ref_seg} 段按 {args.ref_hz:.0f} Hz 对齐")
        for name, i0, i1 in meta:
            print(f"  {name}: 主峰 {peak_frequency(y[i0:i1], fs):.1f} Hz（降噪后）")
    else:
        wav_in = args.wav_dir / args.wav_in
        if not wav_in.is_file():
            raise FileNotFoundError(f"找不到输入: {wav_in}")

        x, fs = read_wav(wav_in)
        n_noise = int(round(args.noise_sec * fs))
        if n_noise >= x.size:
            raise ValueError("noise-sec 过长")

        y = spectral_subtract(x, fs, args.noise_sec, args.alpha, args.beta)
        if args.wav_only:
            meta = [("all", 0, y.size)]
        else:
            meta = []
            if all(p.is_file() for p in mat_paths):
                _, _, meta = load_concat(mat_paths, args.demod - 1)
            else:
                meta = [("all", 0, y.size)]

        if args.bandpass == "adaptive" and meta:
            y, reports = adaptive_bandpass(y, fs, meta, bp_cfg, xfade_sec=xfade_sec)
        elif args.bandpass == "fixed":
            if len(meta) >= 2 and xfade_sec > 0:
                parts = [
                    bandpass(y[i0:i1], fs, args.guard_lo, args.guard_hi) for _n, i0, i1 in meta
                ]
                y = crossfade_join(parts, int(round(xfade_sec * fs)))
            else:
                y = bandpass(y, fs, args.guard_lo, args.guard_hi)
            y = y - np.mean(y)
        else:
            if len(meta) >= 2 and xfade_sec > 0:
                y = blend_segment_boundaries(y, meta, fs, xfade_sec)
            y = y - np.mean(y)

        print(f"输入: {wav_in.name}  Fs={fs:.1f} Hz  T={x.size/fs:.2f} s")

    peak_out = np.max(np.abs(y))
    out = (y / peak_out if peak_out > 0 else y).astype(np.float32)
    wav_out = args.wav_dir / args.wav_out
    wav_out.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(str(wav_out), int(round(fs)), out)

    print(f"谱减: 前 {args.noise_sec} s, alpha={args.alpha}, 带通={args.bandpass}", end="")
    if args.xfade_ms > 0:
        print(f", 降噪段界淡化 {args.xfade_ms:.0f} ms", end="")
    if args.from_mat and args.restore_xfade_ms > 0:
        print(f", 还原段界淡化 {args.restore_xfade_ms:.0f} ms", end="")
    print()
    for r in reports:
        if r.used_narrow:
            parts = [
                f"{t.f0_hz:.0f}Hz[{t.hp_hz:.0f}-{t.lp_hz:.0f}]"
                f"(+{t.peak_vs_median_db:.1f}dB)"
                for t in r.tones
            ]
            print(f"  {r.name}: {len(r.tones)} 峰 → " + ", ".join(parts))
        else:
            print(f"  {r.name}: 无合格峰 → 宽带 {r.fallback_hp:.0f}–{r.fallback_lp:.0f} Hz")
    if args.from_mat:
        print(f"已写入 {wav_out.name}")
    else:
        print(f"已写入 {wav_out.name}（未修改 {args.wav_in}）")

    if args.compare_fig and meta:
        bounds = [i0 / fs for _n, i0, _i1 in meta[1:]]
        compare_fig = args.fig_dir / args.compare_fig
        compare_fig.parent.mkdir(parents=True, exist_ok=True)
        plot_compare(x, y, fs, bounds, compare_fig)


if __name__ == "__main__":
    main()

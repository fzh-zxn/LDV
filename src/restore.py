#!/usr/bin/env python3
"""
LDV 声音还原（全新脚本）

流程：三个 MAT 的 I/Q 按采集顺序拼接 → 正交鉴频 → 削峰 → 带通 → 写 WAV。

关于采样率（避免谱峰变成约 2/3）：
  三段 I/Q 点数不同，直接拼成一条后，不能用「总点数 / 30 s」当 Fs，
  否则三条谱线会整体偏低（约 335 / 670 / 1340 Hz）。
  默认用中间段（1 kHz 附近）自动标定导出 Fs，使主峰对齐标称频率。
"""

from __future__ import annotations

import argparse
import platform
from pathlib import Path

import matplotlib as mpl
import numpy as np
from matplotlib import font_manager
from scipy import signal
from scipy.io import loadmat, wavfile

from paths import DATA_MAT, MAT_SCALE, SCALE_RESTORED_WAV, ensure_dirs


def setup_matplotlib() -> None:
    if platform.system() == "Windows":
        fonts = [Path(r"C:\Windows\Fonts\msyh.ttc"), Path(r"C:\Windows\Fonts\simhei.ttf")]
    else:
        fonts = []
    for path in fonts:
        if path.is_file():
            try:
                font_manager.fontManager.addfont(str(path))
                name = font_manager.FontProperties(fname=str(path)).get_name()
                mpl.rcParams["font.family"] = name
                mpl.rcParams["font.sans-serif"] = [name]
                break
            except OSError:
                pass
    mpl.rcParams["axes.unicode_minus"] = False


def load_iq(mat_path: Path, demod_index: int = 1) -> tuple[np.ndarray, np.ndarray]:
    data = loadmat(str(mat_path), struct_as_record=False, squeeze_me=True)
    sample = data["dev6913"].demods[demod_index].sample
    x = np.asarray(sample.x, dtype=np.float64).ravel()
    y = np.asarray(sample.y, dtype=np.float64).ravel()
    return x, y


def load_concat(
    mat_paths: list[Path], demod_index: int
) -> tuple[np.ndarray, np.ndarray, list[tuple[str, int, int]]]:
    """返回拼接 I/Q 及各段在速度序列中的起止下标（鉴频后长度 = 点数 - 1）。"""
    xs, ys = [], []
    meta: list[tuple[str, int, int]] = []
    iq_off = 0
    vel_off = 0
    for path in mat_paths:
        x, y = load_iq(path, demod_index)
        xs.append(x)
        ys.append(y)
        n_v = x.size - 1
        meta.append((path.name, vel_off, vel_off + n_v))
        vel_off += n_v
        iq_off += x.size
    return np.concatenate(xs), np.concatenate(ys), meta


def bandpass(
    v: np.ndarray,
    fs: float,
    hp_hz: float = 300.0,
    lp_hz: float = 2500.0,
) -> np.ndarray:
    """零相位 Butterworth 带通。"""
    nyq = fs / 2
    hi = min(lp_hz, nyq * 0.99) / nyq
    lo = max(hp_hz, 1.0) / nyq
    if lo >= hi:
        return v
    sos = signal.butter(4, [lo, hi], btype="band", output="sos")
    return signal.sosfiltfilt(sos, v)


def demod_velocity(
    x: np.ndarray,
    y: np.ndarray,
    fs: float,
    hp_hz: float = 50.0,
    lp_hz: float = 5000.0,
    clip_pct: float = 98.0,
) -> np.ndarray:
    xc = x - np.mean(x)
    yc = y - np.mean(y)
    dx = np.diff(xc)
    dy = np.diff(yc)
    xa = xc[:-1]
    ya = yc[:-1]
    v = (xa * dy - ya * dx) / (xa * xa + ya * ya + 1e-12)

    if clip_pct < 100:
        lim = np.percentile(np.abs(v), clip_pct)
        if lim > 0:
            v = np.clip(v, -lim, lim)

    v = bandpass(v, fs, hp_hz, lp_hz)
    return v - np.mean(v)


def _align_phase(tail: np.ndarray, head: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """边界两侧相位对齐：令 head[0] 与 tail[-1] 连续。"""
    if tail.size == 0 or head.size == 0:
        return tail, head
    offset = float(tail[-1] - head[0])
    head = head + offset
    return tail, head


def crossfade_join(parts: list[np.ndarray], n_xfade: int, match_gain: bool = True) -> np.ndarray:
    """多段拼接：边界处余弦交叉淡化，RMS 匹配 + 相位对齐。"""
    if not parts:
        return np.array([], dtype=np.float64)
    if len(parts) == 1 or n_xfade < 4:
        return np.concatenate(parts)

    out = np.asarray(parts[0], dtype=np.float64).copy()
    for nxt in parts[1:]:
        nxt = np.asarray(nxt, dtype=np.float64)
        n = min(n_xfade, out.size // 4, nxt.size // 4)
        if n < 4:
            out = np.concatenate([out, nxt])
            continue

        tail = out[-n:].copy()
        head = nxt[:n].copy()
        if match_gain:
            r_tail = float(np.sqrt(np.mean(tail * tail) + 1e-12))
            r_head = float(np.sqrt(np.mean(head * head) + 1e-12))
            if r_head > 0:
                scale = r_tail / r_head
                head = head * scale
                nxt = nxt * scale
        tail, head = _align_phase(tail, head)

        w = 0.5 * (1.0 - np.cos(np.pi * np.arange(n) / (n - 1)))
        blended = tail * (1.0 - w) + head * w
        out = np.concatenate([out[:-n], blended, nxt[n:]])

    return out


def blend_segment_boundaries(
    v: np.ndarray,
    meta: list[tuple[str, int, int]],
    fs: float,
    xfade_sec: float = 0.04,
) -> np.ndarray:
    """在已有拼接波形上仅淡化段间交界，不改变总长度。"""
    if len(meta) < 2 or xfade_sec <= 0:
        return v
    n_xf = int(round(xfade_sec * fs))
    if n_xf < 4:
        return v
    out = v.copy()
    for (_pname, p0, p1), (_nname, n0, n1) in zip(meta[:-1], meta[1:]):
        b = n0
        a0 = max(p0, b - n_xf)
        b0 = min(n1, b + n_xf)
        n = min(b - a0, b0 - b, n_xf)
        if n < 4:
            continue
        w = 0.5 * (1.0 - np.cos(np.pi * np.arange(n) / (n - 1)))
        left = v[a0 : a0 + n]
        right = v[b : b + n]
        r_l = float(np.sqrt(np.mean(left * left) + 1e-12))
        r_r = float(np.sqrt(np.mean(right * right) + 1e-12))
        if r_r > 0:
            right = right * (r_l / r_r)
        right = right + (left[-1] - right[0]) if right.size else right
        out[a0 : a0 + n] = left * (1.0 - w) + right * w
    return out


def crossfade_at_boundaries(
    v: np.ndarray,
    meta: list[tuple[str, int, int]],
    fs: float,
    xfade_sec: float = 0.04,
    match_gain: bool = True,
) -> np.ndarray:
    """按 meta 切段后拼接并交叉淡化（总长度会略缩短）。"""
    if len(meta) < 2 or xfade_sec <= 0:
        return v
    n_xf = int(round(xfade_sec * fs))
    parts = [v[i0:i1].copy() for _name, i0, i1 in meta]
    return crossfade_join(parts, n_xf, match_gain=match_gain)


def peak_frequency(v: np.ndarray, fs: float, flo: float = 80.0, fhi: float = 4000.0) -> float:
    nperseg = min(16384, max(256, v.size // 2))
    fre, px = signal.welch(v, fs=fs, window="hann", nperseg=nperseg, noverlap=nperseg // 2)
    mask = (fre >= flo) & (fre <= fhi)
    if not np.any(mask):
        return float(fre[np.argmax(px)])
    idx = np.argmax(px[mask])
    return float(fre[mask][idx])


def calibrate_export_fs(
    v: np.ndarray,
    meta: list[tuple[str, int, int]],
    fs_trial: float,
    ref_segment: int,
    ref_hz: float,
) -> float:
    """用参考段主峰把 trial Fs 标到正确比例：Fs_out = Fs_trial × (f_nominal / f_peak)。"""
    name, i0, i1 = meta[ref_segment]
    seg = v[i0:i1]
    f_peak = peak_frequency(seg, fs_trial)
    if f_peak <= 0:
        raise RuntimeError(f"参考段 {name} 主峰检测失败")
    return fs_trial * (ref_hz / f_peak)


def restore(
    mat_paths: list[Path],
    demod_index: int,
    ref_segment: int,
    ref_hz: float,
    hp_hz: float,
    lp_hz: float,
    clip_pct: float,
) -> tuple[np.ndarray, float, list[tuple[str, int, int]]]:
    x, y, meta = load_concat(mat_paths, demod_index)
    n_vel = x.size - 1
    # 先用 trial Fs = N/30 做一次鉴频（与常见 MAT 脚本一致，仅用于估比例）
    fs_trial = n_vel / 30.0
    v = demod_velocity(x, y, fs_trial, hp_hz, lp_hz, clip_pct)
    fs_out = calibrate_export_fs(v, meta, fs_trial, ref_segment, ref_hz)
    return v, fs_out, meta


def restore_blended(
    mat_paths: list[Path],
    demod_index: int,
    ref_segment: int,
    ref_hz: float,
    hp_hz: float,
    lp_hz: float,
    clip_pct: float,
    xfade_sec: float,
) -> tuple[np.ndarray, float, list[tuple[str, int, int]]]:
    """还原并在段界淡化，总长度与拼接鉴频一致（便于按 meta 做自适应降噪）。"""
    v, fs_out, meta = restore(
        mat_paths, demod_index, ref_segment, ref_hz, hp_hz, lp_hz, clip_pct
    )
    if xfade_sec > 0:
        v = blend_segment_boundaries(v, meta, fs_out, xfade_sec)
    return v - np.mean(v), fs_out, meta


def restore_with_xfade(
    mat_paths: list[Path],
    demod_index: int,
    ref_segment: int,
    ref_hz: float,
    hp_hz: float,
    lp_hz: float,
    clip_pct: float,
    xfade_sec: float,
) -> tuple[np.ndarray, float, list[tuple[str, int, int]]]:
    """兼容旧名；与 restore_blended 相同（不再缩短总长度）。"""
    return restore_blended(
        mat_paths,
        demod_index,
        ref_segment,
        ref_hz,
        hp_hz,
        lp_hz,
        clip_pct,
        xfade_sec,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="LDV 声音还原")
    parser.add_argument("--mat-dir", type=Path, default=DATA_MAT, help="MAT 数据目录")
    parser.add_argument("--mats", nargs="+", default=MAT_SCALE)
    parser.add_argument("--demod", type=int, default=2, help="MATLAB demods 下标，默认 2")
    parser.add_argument("--ref-seg", type=int, default=1, help="用于 Fs 标定的段号 0/1/2，默认 1（1 kHz）")
    parser.add_argument("--ref-hz", type=float, default=1000.0, help="参考段标称频率 Hz")
    parser.add_argument("--hp", type=float, default=50.0, help="带通下限 Hz（对照用宽带）")
    parser.add_argument("--lp", type=float, default=5000.0, help="带通上限 Hz")
    parser.add_argument("--clip-pct", type=float, default=98.0)
    parser.add_argument(
        "--wav-out",
        type=Path,
        default=SCALE_RESTORED_WAV,
        help="输出 WAV 路径",
    )
    parser.add_argument("--xfade-ms", type=float, default=50.0, help="段间交叉淡化时长 (ms)，0=关闭")
    args = parser.parse_args()

    ensure_dirs()
    paths = [args.mat_dir / m for m in args.mats]
    for p in paths:
        if not p.is_file():
            raise FileNotFoundError(p)

    v, fs, meta = restore_blended(
        paths,
        demod_index=args.demod - 1,
        ref_segment=args.ref_seg,
        ref_hz=args.ref_hz,
        hp_hz=args.hp,
        lp_hz=args.lp,
        clip_pct=args.clip_pct,
        xfade_sec=args.xfade_ms / 1000.0,
    )

    print("LDV 还原：拼接 I/Q → 鉴频 → 削峰 → 带通")
    if args.xfade_ms > 0:
        print(f"  段间交叉淡化: {args.xfade_ms:.0f} ms")
    print(f"  N={v.size}, Fs={fs:.1f} Hz, T={v.size/fs:.2f} s")
    print(f"  Fs 标定：第 {args.ref_seg} 段按 {args.ref_hz:.0f} Hz 对齐")
    for name, i0, i1 in meta:
        seg = v[i0:i1]
        print(f"  {name}: 主峰 {peak_frequency(seg, fs):.1f} Hz")

    peak = np.max(np.abs(v))
    y = (v / peak if peak > 0 else v).astype(np.float32)
    wav_path = Path(args.wav_out)
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(str(wav_path), int(round(fs)), y)
    print(f"已写入 {wav_path.name}")


if __name__ == "__main__":
    main()

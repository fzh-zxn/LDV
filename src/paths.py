"""项目路径与标准文件名。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
DATA_MAT = ROOT / "data" / "mat"
DATA_WAV = ROOT / "data" / "wav"
OUT_WAV = ROOT / "output" / "wav"
OUT_FIG = ROOT / "output" / "figures"
OUT_FIG_SCALE = OUT_FIG / "scale"
OUT_FIG_VOICE = OUT_FIG / "voice"
OUT_FIG_POSTER = OUT_FIG / "poster"
DOCS = ROOT / "docs"
POSTER = ROOT / "poster"
POSTER_REF = POSTER / "reference"
MATLAB = ROOT / "matlab"

# ── 原始数据 ──
MAT_SCALE = ["scale_seg0.mat", "scale_seg1.mat", "scale_seg2.mat"]
VOICE_INPUT_WAV = DATA_WAV / "voice_input.wav"

# ── 音阶输出 WAV ──
SCALE_RESTORED_WAV = OUT_WAV / "scale_restored.wav"
SCALE_DENOISED_SIMPLE_WAV = OUT_WAV / "scale_denoised_simple.wav"
SCALE_DENOISED_FINAL_WAV = OUT_WAV / "scale_denoised_final.wav"

# ── 人声输出 WAV ──
VOICE_DENOISED_WAV = OUT_WAV / "voice_denoised.wav"

# ── 海报主图（音阶 / 人声）──
FIG_SCALE_TRIPTYCH_WELCH = OUT_FIG_SCALE / "triptych_welch.png"
FIG_SCALE_TRIPTYCH_SPEC = OUT_FIG_SCALE / "triptych_spectrogram.png"
FIG_VOICE_DIPTYCH_SPEC = OUT_FIG_VOICE / "diptych_spectrogram.png"

# ── 文档 ──
DOC_SCRIPT_FULL = DOCS / "讲稿_完整版.md"
DOC_SCRIPT_7MIN = DOCS / "讲稿_7分钟.md"
DOC_FORMULA = DOCS / "公式推导.docx"
DOC_POSTER_TEXT = POSTER / "LDV_海报文字.docx"


def mat_paths(names: list[str] | None = None) -> list[Path]:
    return [DATA_MAT / n for n in (names or MAT_SCALE)]


def resolve_under(base: Path, path: Path | str) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    if p.parent != Path("."):
        return ROOT / p
    return base / p


def ensure_dirs() -> None:
    for d in (
        DATA_MAT,
        DATA_WAV,
        OUT_WAV,
        OUT_FIG_SCALE,
        OUT_FIG_VOICE,
        OUT_FIG_POSTER,
        DOCS,
        POSTER,
        POSTER_REF,
        MATLAB,
    ):
        d.mkdir(parents=True, exist_ok=True)

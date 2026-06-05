# LDV 激光多普勒远程侦听 — 数据处理

正交鉴频 · Fs 标定 · 音阶 / 人声双验证。公式详见 `docs/公式推导.docx`。

## 目录结构

```
stream音阶/
├── run_scale_pipeline.py      # 音阶一键流程
├── src/                       # Python 源码
│   ├── paths.py               # 路径与标准文件名（改这里即可全局生效）
│   ├── restore.py             # MAT → 鉴频 → scale_restored.wav
│   ├── denoise_scale_simple.py
│   ├── denoise.py             # 多峰自适应降噪（库 + 音阶 CLI）
│   ├── denoise_voice.py
│   ├── plot_scale_triptych.py # 海报三联图
│   ├── plot_spectrum.py
│   ├── plot_poster_*.py       # 海报示意图
│   └── tools/                 # 文档生成脚本
├── data/
│   ├── mat/                   # scale_seg0~2.mat
│   └── wav/                   # voice_input.wav
├── output/
│   ├── wav/                   # 生成的音频
│   └── figures/
│       ├── scale/             # 音阶谱图
│       ├── voice/             # 人声谱图
│       └── poster/            # 海报用示意图
├── docs/                      # 讲稿、公式推导
├── poster/                    # 海报 PPT / 文字稿
│   └── reference/             # 参考模板（旧文件）
└── matlab/
    └── scale_pipeline.m
```

## 快速开始

```powershell
cd "c:\Users\33949\Desktop\stream音阶"

# 音阶全流程
python run_scale_pipeline.py

# 人声
python src/denoise_voice.py

# 海报主图（需先跑完音阶 / 人声）
python src/plot_scale_triptych.py
```

## 标准输出文件名

| 文件 | 说明 |
|------|------|
| `output/wav/scale_restored.wav` | 音阶·鉴频后未降噪 |
| `output/wav/scale_denoised_simple.wav` | 音阶·简单降噪 |
| `output/wav/scale_denoised_final.wav` | 音阶·最终降噪 |
| `output/wav/voice_denoised.wav` | 人声·降噪后 |
| `output/figures/scale/triptych_*.png` | 音阶三联图（海报图4/5） |
| `output/figures/voice/diptych_spectrogram.png` | 人声语谱（海报图6） |

## 旧文件名对照

| 旧名 | 新名 |
|------|------|
| `stream_00000.mat` | `data/mat/scale_seg0.mat` |
| `ldv_iq_demodulated(1).wav` | `data/wav/voice_input.wav` |
| `ldv_30s_scale_test.wav` | `scale_restored.wav` |
| `ldv_denoised_simple.wav` | `scale_denoised_simple.wav` |
| `ldv_denoised.wav` | `scale_denoised_final.wav` |
| `ldv_voice_denoised.wav` | `voice_denoised.wav` |
| `ldv_triptych_spec.png` | `scale/triptych_spectrogram.png` |
| `scripts/ldv_restore.py` | `src/restore.py` |
| `run_pipeline.py` | `run_scale_pipeline.py` |
| `untitled.m` | `matlab/scale_pipeline.m` |

## 文档工具

```powershell
python src/tools/build_formula_docx.py
python src/tools/md_to_docx.py
python src/tools/md_to_docx.py 讲稿_7分钟
```

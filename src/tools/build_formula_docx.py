#!/usr/bin/env python3
"""生成 LDV 工作公式推导 Word 文档（LDV_公式推导.docx）。"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor


def _run(p, text: str, *, bold=False, italic=False, size=11, name="宋体", color=None):
    r = p.add_run(text)
    r.bold = bold
    r.italic = italic
    r.font.size = Pt(size)
    r.font.name = name
    if color:
        r.font.color.rgb = color
    return r


def add_title(doc: Document, text: str, level: int = 1) -> None:
    doc.add_heading(text, level=level)


def add_body(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    _run(p, text)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.first_line_indent = Cm(0.74)


def add_bullet(doc: Document, text: str) -> None:
    p = doc.add_paragraph(style="List Bullet")
    _run(p, text)


def add_formula(doc: Document, text: str, note: str = "") -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(p, text, italic=True, size=12, name="Cambria")
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    if note:
        pn = doc.add_paragraph()
        pn.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _run(pn, note, size=9, color=RGBColor(0x66, 0x66, 0x66))


def add_code_ref(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    _run(p, "【实现】", bold=True, size=10)
    _run(p, text, size=10, name="Consolas")


def build_document() -> Document:
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Cm(21.0)
    sec.page_height = Cm(29.7)
    sec.left_margin = Cm(2.5)
    sec.right_margin = Cm(2.5)
    sec.top_margin = Cm(2.5)
    sec.bottom_margin = Cm(2.5)

    # ── 封面 ──
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(t, "基于正交鉴频架构的激光多普勒远程侦听", bold=True, size=18)
    t2 = doc.add_paragraph()
    t2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(t2, "信号处理公式推导与代码实现对照", bold=True, size=16)
    t3 = doc.add_paragraph()
    t3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(t3, "（答辩备查 · 技术附录）", size=12, color=RGBColor(0x55, 0x55, 0x55))
    doc.add_paragraph()

    add_body(
        doc,
        "本文档汇总本课题实验数据处理链路上的主要公式：从外差光路、锁相 I/Q，"
        "到正交鉴频、采样率标定、谱减与窄带降噪。公式编号 (式 n) 仅用于文内引用；"
        "与仓库中 Python/MATLAB 实现一一对应。",
    )

    # ── 0 符号 ──
    add_title(doc, "0  符号与约定", 1)
    symbols = [
        "ω：光场角频率；Ω₁、Ω₂：AOM 射频角频率；ω_IF：拍频（中频）角频率。",
        "φ(t)：由目标振动调制的拍频相位；A(t)：拍频幅值（随散斑起伏）。",
        "I(t)、Q(t)：锁相正交解调后的同相、正交分量。",
        "v(t)：鉴频得到的与表面振动速度成正比的时域序列。",
        "F_s：采样率 (Hz)；N：样本点数；Δt = 1/F_s。",
        "ε：小正数，防止分母为零（代码中取 10⁻¹²）。",
        "α、β：谱减过减系数与谱底保留比例。",
    ]
    for s in symbols:
        add_bullet(doc, s)
    add_body(doc, "离散实现中 d/dt 用一阶差分 diff 近似；带通采用零相位 sosfiltfilt。")

    # ── 1 光学 ──
    add_title(doc, "1  外差光路与 AOM 移频", 1)
    add_body(
        doc,
        "激光器出光角频率 ω。分光后信号臂经 AOM1（−1 级）、AOM2（+1 级）照目标，"
        "单程移频量 Δω_去 = Ω₂ − Ω₁，信号光角频率变为 ω_s = ω − Ω₁ + Ω₂（符号以实际光路为准）。"
        "参考光不经 AOM，角频率 ω_r ≈ ω。",
    )
    add_formula(doc, "Δf_去 = (Ω₂ − Ω₁) / (2π)    （单程频率移）")
    add_formula(doc, "Δf_往返 = 2(Ω₂ − Ω₁) / (2π) = (Ω₂ − Ω₁)/π    （往返同级次）")
    add_body(
        doc,
        "目标法向微振动引起返回光相位调制 φ(t)。信号光与参考光在 PD 上相干叠加，"
        "光电转换后电流含与 |E_r + E_s|² 成正比的直流项与拍频项。",
    )
    add_formula(doc, "E_r(t) = A_r cos(ω_r t)")
    add_formula(doc, "E_s(t) = A_s cos(ω_s t + φ(t))")
    add_formula(doc, "i(t) = R |E_r + E_s|² = I_0 + i_IF(t) + …")
    add_body(
        doc,
        "展开交叉项，拍频分量近似为（只保留差频项）：",
    )
    add_formula(doc, "i_IF(t) ≈ A cos(ω_IF t + φ(t))", "ω_IF = |ω_s − ω_r|，A 与两路振幅有关")
    add_body(
        doc,
        "AOM 的作用：将有用信息调制到固定中频 ω_IF，便于锁相放大器高增益检测相位，"
        "并抑制低频漂移与干涉灵敏度在条纹极值处衰落的影响。",
    )

    # ── 2 锁相 ──
    add_title(doc, "2  锁相放大器与 I/Q 正交解调", 1)
    add_body(doc, "锁相以 cos(ω_IF t) 与 sin(ω_IF t) 为参考，对 i(t) 混频并低通：")
    add_formula(doc, "I(t) = LPF[ i(t) · cos(ω_IF t) ]")
    add_formula(doc, "Q(t) = LPF[ i(t) · sin(ω_IF t) ]")
    add_body(
        doc,
        "当 φ(t) 变化远慢于 ω_IF，且幅值缓变时，低通后近似：",
    )
    add_formula(doc, "I(t) ≈ (A/2) cos φ(t)    ，    Q(t) ≈ (A/2) sin φ(t)")
    add_body(doc, "引入复相量 z(t) = I(t) + jQ(t)，则：")
    add_formula(doc, "z(t) = A(t) e^{jφ(t)}    （极坐标形式）")
    add_body(
        doc,
        "实验采集的 dev6913.demods(k).sample.x / .y 即为离散采样的 I、Q 序列。"
        "至此得到电域数据；后续在数字域完成鉴频与音频还原。",
    )
    add_code_ref(doc, "MAT：untitled.m 读取 X_total, Y_total；Python：ldv_restore.load_iq / load_concat")

    # ── 3 正交鉴频 ──
    add_title(doc, "3  正交鉴频（核心）", 1)
    add_title(doc, "3.1  物理目标：瞬时角频率", 2)
    add_body(
        doc,
        "表面振动通过多普勒效应调制 φ(t)。在干涉测量中，法向速度 v_n(t) 与 dφ/dt 成正比：",
    )
    add_formula(doc, "v_n(t) = (λ / 4π) · dφ/dt", "λ 为有效波长；比例常数与光路配置有关")
    add_body(doc, "数字处理中输出 v(t) ∝ dφ/dt，绝对标度由后续频率标定验证。")

    add_title(doc, "3.2  传统法：atan2 + 解包裹 + 微分", 2)
    add_formula(doc, "φ_w(t) = atan2(Q(t), I(t))    （包裹相位，范围 (−π, π]）")
    add_formula(doc, "φ(t) = unwrap(φ_w(t))")
    add_formula(doc, "v(t) ∝ dφ/dt")
    add_body(
        doc,
        "散斑导致 I、Q 绕原点旋转时 φ_w 在 ±π 处跳变，unwrap 错误会经微分放大为宽频伪峰。"
        "本工作改用下述闭式，避免显式求 φ。",
    )

    add_title(doc, "3.3  推导：对 atan2 求导得交叉相乘", 2)
    add_body(doc, "设 I、Q 可微，φ = atan2(Q, I)。由 φ = arctan(Q/I)（I≠0）：")
    add_formula(doc, "tan φ = Q / I")
    add_body(doc, "两边对 t 求导，用商法则：")
    add_formula(doc, "sec²φ · dφ/dt = (I · Q′ − Q · I′) / I²")
    add_body(doc, "利用 sec²φ = 1 + tan²φ = (I² + Q²) / I²，且 cos²φ = I²/(I²+Q²)，得：")
    add_formula(doc, "dφ/dt = (I · Q′ − Q · I′) / (I² + Q²)                    (式 1)")
    add_body(doc, "此即正交鉴频公式；与 unwrap 后微分在 φ 光滑时等价。")

    add_title(doc, "3.4  复数形式推导（等价）", 2)
    add_body(doc, "z = I + jQ，|z|² = I² + Q²。有：")
    add_formula(doc, "ż = I′ + jQ′")
    add_formula(doc, "Im( z* · ż ) = I Q′ − Q I′")
    add_body(doc, "故：")
    add_formula(doc, "dφ/dt = Im( z* · ż ) / |z|² = (I Q′ − Q I′) / (I² + Q²)    (式 2)")
    add_body(doc, "式 (1)(2) 相同；复数形式说明这是相量在复平面旋转的角速度。")

    add_title(doc, "3.5  去均值、归一化与数值稳定", 2)
    add_body(doc, "实现前对 I、Q 去直流，消除锁相偏置：")
    add_formula(doc, "Ĩ = I − mean(I)    ，    Q̃ = Q − mean(Q)")
    add_body(doc, "鉴频输出（连续时间）：")
    add_formula(doc, "v(t) = ( Ĩ · Q̃′ − Q̃ · Ĩ′ ) / ( Ĩ² + Q̃² + ε )          (式 3)")
    add_body(doc, "分母 Ĩ²+Q̃² 为瞬时幅值平方，起自动增益控制作用；ε 防止散斑深谷时除零。")

    add_title(doc, "3.6  离散实现", 2)
    add_body(doc, "设采样间隔 Δt = 1/F_s，一阶差分：")
    add_formula(doc, "ΔĨ[n] = Ĩ[n+1] − Ĩ[n]    ，    ΔQ̃[n] = Q̃[n+1] − Q̃[n]")
    add_formula(doc, "v[n] = ( Ĩ[n]·ΔQ̃[n] − Q̃[n]·ΔĨ[n] ) / ( Ĩ[n]² + Q̃[n]² + ε )   (式 4)")
    add_body(doc, "输出长度 N−1（diff 少一个点）。野值抑制：对 |v| 取 p 分位（默认 p=98%）对称限幅。")
    add_code_ref(doc, "ldv_restore.demod_velocity；untitled.m 第 21–29 行（注释「与原先一致」）")

    add_title(doc, "3.7  与 MATLAB 原脚本对应", 2)
    add_body(
        doc,
        "组内 MATLAB 脚本已采用式 (4)。Python 复现未改变鉴频核心，"
        "后续改进集中在 Fs 标定、段界淡化与降噪。",
    )

    # ── 4 带通 ──
    add_title(doc, "4  带通滤波", 1)
    add_body(
        doc,
        "鉴频后采用 4 阶 Butterworth 带通，截止频率 f_lo、f_hi（Hz），"
        "经双线性变换得二阶节 SOS，零相位 filtfilt 避免相位畸变：",
    )
    add_formula(doc, "H(s) = 1 / ∏_k (s²/ω_k² + √2·s/ω_k + 1)    （4 阶 = 2 个二阶节级联）")
    add_body(doc, "音阶还原默认 50–5000 Hz；简单降噪 300–2500 Hz；人声 50–2000 Hz。")
    add_code_ref(doc, "ldv_restore.bandpass")

    # ── 5 Fs ──
    add_title(doc, "5  采样率试探与 Fs 标定", 1)
    add_title(doc, "5.1  为何不能直接用 N/30", 2)
    add_body(
        doc,
        "三段 MAT 的 I/Q 点数 N₀、N₁、N₂ 不同，拼接后总点数 N = N₀+N₁+N₂，"
        "实际记录时长 T ≠ 30 s。若强行 F_s = N/30，频率轴整体缩放错误，"
        "谱峰约变为标称值的 2/3。",
    )

    add_title(doc, "5.2  试探 Fs 与主峰检测", 2)
    add_body(doc, "鉴频中间步骤取试探采样率：")
    add_formula(doc, "F_s,trial = (N − 1) / 30")
    add_body(doc, "对参考段（默认中间段，标称 1000 Hz）用 Welch 估计功率谱密度：")
    add_formula(doc, "P_xx(f) = (1/K) Σ_k |X_k(f)|² / (F_s,trial · W)")
    add_body(doc, "在 [80, 4000] Hz 内取 P_xx 最大处为 f_peak。")

    add_title(doc, "5.3  标定公式", 2)
    add_formula(doc, "F_s,out = F_s,trial · (f_nom / f_peak)                    (式 5)")
    add_body(
        doc,
        "f_nom 为已知标称音调（默认 1000 Hz）。标定后导出 WAV 使用 F_s,out；"
        "本课题音阶结果 F_s,out ≈ 13397 Hz，主峰 ≈ 500/1000/2000 Hz。",
    )
    add_code_ref(doc, "ldv_restore.peak_frequency, calibrate_export_fs, restore")

    # ── 6 交叉淡化 ──
    add_title(doc, "6  段间交叉淡化", 1)
    add_body(doc, "三段 MAT 拼接处在鉴频波形上易产生阶跃。在边界两侧各取 n 点，余弦窗：")
    add_formula(doc, "w[k] = 0.5 · (1 − cos(πk/(n−1)))    ，    k = 0,…,n−1")
    add_formula(doc, "y[k] = (1−w[k])·y_left[k] + w[k]·y_right[k]")
    add_body(
        doc,
        "实现中另对两侧做 RMS 匹配与端点相位（幅值）对齐，再混合。默认淡化时长 50 ms。",
    )
    add_code_ref(doc, "ldv_restore.blend_segment_boundaries, crossfade_join")

    # ── 7 谱减 ──
    add_title(doc, "7  谱减降噪", 1)
    add_title(doc, "7.1  STFT", 2)
    add_body(doc, "对信号 x[n] 加 Hann 窗、步长 hop，得短时傅里叶变换：")
    add_formula(doc, "X(m, k) = Σ_n x[n] w[n−m·hop] e^{−j2πkn/N_FFT}")
    add_formula(doc, "|X(m,k)|,  ∠X(m,k)  分别作幅度与相位")

    add_title(doc, "7.2  音阶：前缀噪声参考谱减", 2)
    add_body(doc, "用前 T_noise 秒各帧幅度均值估计噪声谱：")
    add_formula(doc, "N(k) = mean_m |X(m,k)|    ，    m = 0,…,M_noise−1")
    add_formula(doc, "|X̂(m,k)| = max( |X| − α·N(k),  β·|X| )                (式 6)")
    add_body(doc, "再减中值谱底并保留下限：")
    add_formula(doc, "|X_clean| = max( |X̂| − γ·median_m(|X̂|),  β·median(|X|) )")
    add_body(doc, "相位不变，ISTFT 重建。默认 α=1.8，β=0.05，T_noise=0.5 s（简单降噪）。")
    add_code_ref(doc, "ldv_denoise.spectral_subtract；ldv_denoise_simple.py")

    add_title(doc, "7.3  人声：全段低分位噪声谱", 2)
    add_body(doc, "各频点取全时间段幅度分位数（默认 20%）作为噪声谱：")
    add_formula(doc, "N(k) = percentile_20%_m ( |X(m,k)| )")
    add_formula(doc, "|X̂(m,k)| = max( |X| − α·N(k),  β·|X| )    ，    α=1.5")
    add_body(doc, "适用于开头无纯静音段、语音占满时长的录音。")
    add_code_ref(doc, "ldv_denoise.spectral_subtract_noise_floor, denoise_voice")

    # ── 8 多峰窄带 ──
    add_title(doc, "8  多峰自适应窄带（音阶最终降噪）", 1)
    add_body(doc, "对每段 MAT 对应波形单独 Welch，在守护带 [300, 2500] Hz 内找峰。")
    add_body(doc, "第 i 个峰频率 f₀,i，半带宽：")
    add_formula(doc, "BW_i = max(BW_min,  r_bw · f₀,i)    （默认 r_bw=0.12, BW_min=60 Hz）")
    add_formula(doc, "通带_i = [ max(300, f₀,i−BW_i),  min(2500, f₀,i+BW_i) ]")
    add_body(doc, "各峰窄带结果等权叠加：")
    add_formula(doc, "y_seg = (1/P) Σ_{i=1}^{P} BPF_i(x_seg)")
    add_body(doc, "峰检测需满足相对中值功率、prominence 等阈值；无峰时回退守护带宽带通。")
    add_code_ref(doc, "ldv_denoise.detect_tones, apply_multiband, adaptive_bandpass")

    # ── 9 总流程 ──
    add_title(doc, "9  处理链路总览", 1)
    add_body(doc, "音阶标定线：")
    add_formula(
        doc,
        "MAT(I,Q) → 拼接 → v=鉴频(式4) → 削峰 → 带通 → F_s(式5) → 谱减(式6) → 多峰窄带 → WAV",
    )
    add_body(doc, "人声验证线：")
    add_formula(doc, "WAV(v) → 带通 50–2000 Hz → 全段分位谱减 → WAV")
    add_body(doc, "两条线共用式 (4) 鉴频前端；人声输入为已鉴频文件，不再重复 MAT 流程。")

    # ── 10 代码对照 ──
    add_title(doc, "10  公式—代码对照表", 1)
    table = doc.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    hdr[0].text = "公式/步骤"
    hdr[1].text = "函数或脚本"
    hdr[2].text = "默认参数"
    rows = [
        ("式 (4) 正交鉴频", "ldv_restore.demod_velocity", "ε=1e-12, clip 98%"),
        ("带通", "ldv_restore.bandpass", "4 阶 Butterworth, filtfilt"),
        ("式 (5) Fs 标定", "calibrate_export_fs", "ref=中段, f_nom=1000 Hz"),
        ("交叉淡化", "blend_segment_boundaries", "50 ms"),
        ("式 (6) 谱减", "spectral_subtract", "α=1.8, β=0.05, 0.5 s"),
        ("人声谱减", "spectral_subtract_noise_floor", "α=1.5, 20% 分位"),
        ("多峰窄带", "adaptive_bandpass", "bw_ratio=0.12"),
        ("一条龙", "run_pipeline.py / ldv_denoise.py", "见 README"),
        ("MATLAB 原鉴频", "untitled.m L21–29", "与式 (4) 一致"),
    ]
    for a, b, c in rows:
        row = table.add_row().cells
        row[0].text = a
        row[1].text = b
        row[2].text = c
    doc.add_paragraph()

    # ── 11 答辩 ──
    add_title(doc, "11  答辩常见追问（简答）", 1)
    faq = [
        "公式哪里来？式 (1)(2) 为 atan2 或复相量求导的标准结果；式 (4) 为组内 untitled.m 沿用实现。",
        "为何不用 atan？散斑下包裹相位跳变，unwrap 失败；式 (4) 在 (I,Q) 平面直接算角速度。",
        "Fs 能由鉴频直接得到吗？不能。式 (5) 需已知标称频率或硬件时钟。",
        "知道 Fs 还要正交鉴频吗？要。Fs 定标度，鉴频定 I/Q→v(t) 的鲁棒算法。",
        "绝对速度标定？本课题以音阶频率自洽与听感验证为主；绝对标度需额外光学标定。",
    ]
    for i, q in enumerate(faq, 1):
        add_bullet(doc, f"{i}. {q}")

    add_title(doc, "12  建议延伸阅读（概念出处，非必引）", 1)
    refs = [
        "锁相放大器与正交解调：I、Q 为同频正交参考混频低通结果。",
        "瞬时频率/相位导数：通信与雷达中 I/Q 信号标准处理。",
        "激光外差 / 自混合干涉测振：φ 与表面位移、速度关系。",
        "谱减法：Boll 等经典短时谱幅度减除框架。",
    ]
    for r in refs:
        add_bullet(doc, r)

    add_body(
        doc,
        "— 文档完 —  生成脚本：gen_formula_derivation_docx.py；"
        "与代码不一致时以仓库最新实现为准。",
    )
    return doc


def main() -> None:
    from paths import DOC_FORMULA, ensure_dirs

    ensure_dirs()
    out = DOC_FORMULA
    doc = build_document()
    doc.save(str(out))
    print(f"已生成: {out}")


if __name__ == "__main__":
    import _bootstrap  # noqa: F401

    main()

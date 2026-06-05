%% LDV 正交鉴频 → 改进降噪 → 频谱 / 语谱图对比
% 依赖: stream_00000~00002.mat；建议 Signal Processing Toolbox (bandpass / stft)

disp('正在加载并拼接 3 个连续的数据文件...');

here = fileparts(mfilename('fullpath'));
mat_dir = fullfile(here, '..', 'data', 'mat');
out_wav_dir = fullfile(here, '..', 'output', 'wav');
if ~exist(out_wav_dir, 'dir')
    mkdir(out_wav_dir);
end

data0 = load(fullfile(mat_dir, 'scale_seg0.mat'));
data1 = load(fullfile(mat_dir, 'scale_seg1.mat'));
data2 = load(fullfile(mat_dir, 'scale_seg2.mat'));

X0 = data0.dev6913.demods(2).sample.x(:); Y0 = data0.dev6913.demods(2).sample.y(:);
X1 = data1.dev6913.demods(2).sample.x(:); Y1 = data1.dev6913.demods(2).sample.y(:);
X2 = data2.dev6913.demods(2).sample.x(:); Y2 = data2.dev6913.demods(2).sample.y(:);

X_total = [X0; X1; X2];
Y_total = [Y0; Y1; Y2];

total_duration = 30;
Fs = length(X_total) / total_duration;
disp(['拼接完成！总时长 ', num2str(total_duration), ' s，采样率 Fs = ', num2str(Fs, '%.1f'), ' Hz']);

%% ---------- 鉴频（与原先一致）----------
X_c = X_total - mean(X_total);
Y_c = Y_total - mean(Y_total);

dX = diff(X_c);
dY = diff(Y_c);
X_align = X_c(1:end-1);
Y_align = Y_c(1:end-1);
audio_raw = (X_align .* dY - Y_align .* dX) ./ (X_align.^2 + Y_align.^2 + 1e-12);

%% ---------- 降噪参数 ----------
cfg.bp_hz = [50, 5000];          % 音阶有效频带
cfg.clip_pct = 98;               % 分位削峰（抑制鉴频尖峰）
cfg.spec_alpha = 1.8;            % 谱减强度（越大越干净，过大易音乐噪声）
cfg.spec_beta = 0.05;            % 谱底保留比例，防过度挖空
cfg.noise_sec = 0.8;             % 用开头若干秒估计噪声谱（无纯静音时可改 median 模式）
cfg.xfade_ms = 50;               % 段间交叉淡化时长 (ms)，减轻 MAT 拼接断裂；0=关闭

audio_clip = robust_clip(audio_raw, cfg.clip_pct);

% 各段在鉴频序列中的起始下标（1-based，与 Python load_concat 一致）
seg_bounds = [numel(X0), numel(X0) + numel(X1) - 1];
if cfg.xfade_ms > 0
    audio_clip = blend_segment_boundaries(audio_clip, seg_bounds, Fs, cfg.xfade_ms / 1000);
    disp(['已对 ', num2str(numel(seg_bounds)), ' 处拼接缝做 ', num2str(cfg.xfade_ms), ' ms 交叉淡化']);
end

% 旧法：矩形 FFT 带通（频轴按折叠频率处理，比原脚本正确）
audio_legacy = legacy_fft_bandpass(audio_clip, Fs, cfg.bp_hz);

% 新法：零相位 IIR 带通 + STFT 谱减
audio_clean = denoise_pipeline(audio_clip, Fs, cfg);
if cfg.xfade_ms > 0
    audio_clean = blend_segment_boundaries(audio_clean, seg_bounds, Fs, cfg.xfade_ms / 1000);
end

%% ---------- 可视化：波形 / 功率谱 / 语谱图 ----------
win_len = round(Fs / 10);
win_len = max(win_len, 256);
overlap = round(win_len * 0.875);
nfft = max(4096, 2^nextpow2(win_len * 2));

plot_denoise_analysis(audio_raw, audio_clip, audio_legacy, audio_clean, Fs, win_len, overlap, nfft);

%% ---------- 导出 ----------
if max(abs(audio_clean)) > 0
    audio_out = audio_clean / max(abs(audio_clean));
else
    audio_out = audio_clean;
end
wav_out = fullfile(out_wav_dir, 'scale_restored.wav');
audiowrite(wav_out, audio_out, round(Fs));
disp(['已保存: ', wav_out]);

%% ========================================================================
function y = blend_segment_boundaries(x, bounds, Fs, xfade_sec)
% 在已有拼接波形上淡化段间交界（余弦窗 + RMS 匹配 + 相位对齐），不改变总长度。
% bounds: 各后续段起始下标 (1-based)，例如 [numel(X0), numel(X0)+numel(X1)-1]
y = x(:);
if xfade_sec <= 0 || isempty(bounds)
    return;
end
n_xf = max(4, round(xfade_sec * Fs));
for k = 1:numel(bounds)
    b = bounds(k);
    if b < 2 || b > numel(y)
        continue;
    end
    a0 = max(1, b - n_xf);
    b0 = min(numel(y), b + n_xf);
    n = min(b - a0, b0 - b, n_xf);
    if n < 4
        continue;
    end
    w = 0.5 * (1 - cos(pi * (0:n-1).' / (n - 1)));
    left = y(a0:(a0 + n - 1));
    right = y(b:(b + n - 1));
    r_l = sqrt(mean(left.^2) + 1e-12);
    r_r = sqrt(mean(right.^2) + 1e-12);
    if r_r > 0
        right = right * (r_l / r_r);
    end
    right = right + (left(end) - right(1));
    y(a0:(a0 + n - 1)) = left .* (1 - w) + right .* w;
end
end

function y = robust_clip(x, pct)
% 对称分位限幅，抑制鉴频野值
v = sort(abs(x(:)));
k = max(1, round(pct / 100 * numel(v)));
lim = v(k);
y = min(max(x, -lim), lim);
end

function y = legacy_fft_bandpass(x, Fs, bp_hz)
% 旧版矩形带通（折叠频率），仅用于对比
N = numel(x);
f = (0:N-1).' * (Fs / N);
f(f > Fs/2) = f(f > Fs/2) - Fs;
Y = fft(x);
mask = abs(f) < bp_hz(1) | abs(f) > bp_hz(2);
Y(mask) = 0;
y = real(ifft(Y));
end

function y = denoise_pipeline(x, Fs, cfg)
% 零相位带通 + 谱减
x_bp = bandpass_zero_phase(x, Fs, cfg.bp_hz);
y = spectral_subtract(x_bp, Fs, cfg);
if max(abs(y)) > 0
    y = y / max(abs(y));
end
end

function y = bandpass_zero_phase(x, Fs, bp_hz)
if exist('bandpass', 'file') == 2
    y = bandpass(x, bp_hz, Fs, ...
        'ImpulseResponse', 'iir', ...
        'Steepness', 0.9);
    return;
end
% 无工具箱：Hamming 窗平滑频域掩膜
N = numel(x);
f = (0:N-1).' * (Fs / N);
f(f > Fs/2) = f(f > Fs/2) - Fs;
af = abs(f);
trans = 15; % Hz 过渡带宽度
low = 0.5 * (1 + tanh((af - bp_hz(1)) / trans));
high = 0.5 * (1 - tanh((af - bp_hz(2)) / trans));
mask = low .* high;
Y = fft(x) .* mask;
y = real(ifft(Y));
end

function y = spectral_subtract(x, Fs, cfg)
if exist('stft', 'file') ~= 2
    warning('spectral_subtract:NoSTFT', '无 stft，跳过谱减，仅使用带通结果。');
    y = x;
    return;
end

win_len = round(Fs / 20);
win_len = 2^nextpow2(max(win_len, 256));
hop = round(win_len / 4);
win = hann(win_len, 'periodic');

[S, F, ~] = stft(x, Fs, ...
    'Window', win, ...
    'FFTLength', max(4096, 2^nextpow2(win_len * 2)), ...
    'OverlapLength', win_len - hop);

mag = abs(S);
phase = angle(S);

n_noise = max(1, round(cfg.noise_sec * Fs / hop));
noise_mag = mean(mag(:, 1:n_noise), 2);

% 谱减 + 谱底；沿时间维中值再压一层宽带噪声
mag_sub = max(mag - cfg.spec_alpha * noise_mag, cfg.spec_beta * mag);
noise_floor_t = median(mag_sub, 2);
mag_clean = max(mag_sub - 0.5 * noise_floor_t, cfg.spec_beta * median(mag, 2));

S_clean = mag_clean .* exp(1i * phase);
y = real(istft(S_clean, Fs, ...
    'Window', win, ...
    'OverlapLength', win_len - hop));
y = y(:);
n = min(numel(y), numel(x));
y = y(1:n);
if numel(y) < numel(x)
    y(end+1:numel(x)) = 0;
end
end

function plot_denoise_analysis(raw, clip, legacy, clean, Fs, win_len, overlap, nfft)
t = (0:numel(clean)-1) / Fs;
seg = t <= min(5, t(end));

fig = figure('Name', '降噪与频谱分析', 'Position', [60, 60, 1280, 820]);

% --- 时域（前 5 s）---
ax1 = subplot(3, 3, 1);
plot(t(seg), raw(seg), 'Color', [0.55 0.55 0.55]); hold on;
plot(t(seg), clean(seg), 'b', 'LineWidth', 0.9);
hold off; grid on;
title('时域：灰=鉴频原始，蓝=新降噪');
xlabel('时间 (s)'); ylabel('幅度');
legend({'鉴频', '新降噪'}, 'Location', 'best');

ax2 = subplot(3, 3, 2);
plot(t(seg), legacy(seg), 'Color', [0.85 0.45 0.1]); hold on;
plot(t(seg), clean(seg), 'b', 'LineWidth', 0.9);
hold off; grid on;
title('时域：橙=旧矩形带通，蓝=新降噪');
xlabel('时间 (s)'); ylabel('幅度');
legend({'旧法', '新法'}, 'Location', 'best');

% --- Welch 功率谱 ---
nseg = min(numel(clean), round(Fs));
nseg = 2^nextpow2(max(256, min(nseg, round(Fs / 4))));

ax3 = subplot(3, 3, 3);
[px_raw, f] = pwelch(clip, hann(nseg), round(nseg/2), nfft, Fs);
[px_leg, ~] = pwelch(legacy, hann(nseg), round(nseg/2), nfft, Fs);
[px_new, ~] = pwelch(clean, hann(nseg), round(nseg/2), nfft, Fs);
plot(f, 10*log10(px_raw + eps), 'Color', [0.6 0.6 0.6]); hold on;
plot(f, 10*log10(px_leg + eps), 'Color', [0.9 0.5 0.1]);
plot(f, 10*log10(px_new + eps), 'b', 'LineWidth', 1.2);
hold off; grid on; xlim([0 5000]);
title('Welch 功率谱 (dB)');
xlabel('频率 (Hz)'); ylabel('PSD (dB)');
legend({'削峰后', '旧矩形带通', '新降噪'}, 'Location', 'northeast');

% --- 语谱图 2×3 ---
maps = {
    clip,   '语谱图：削峰后（带通前）'
    legacy, '语谱图：旧法矩形 FFT 带通'
    clean,  '语谱图：新法带通 + 谱减'
    };

for k = 1:3
    ax = subplot(3, 3, 3 + k);
    plot_spectrogram(ax, maps{k}{1}, Fs, win_len, overlap, nfft, maps{k}{2});
end

% --- 单帧幅度谱对比（中间时刻）---
ax9 = subplot(3, 3, 9);
mid = round(numel(clean) / 2);
frame_len = win_len;
idx = max(1, mid - floor(frame_len/2)) : min(numel(clean), mid + floor(frame_len/2) - 1);
frame = clean(idx) .* hann(numel(idx));
Nf = 2^nextpow2(max(nfft, numel(frame)));
spec = abs(fft(frame, Nf));
ff = (0:Nf/2) * (Fs / Nf);
plot(ff, 20*log10(spec(1:Nf/2+1) + eps), 'b', 'LineWidth', 1.1); hold on;
frame_l = legacy(idx) .* hann(numel(idx));
spec_l = abs(fft(frame_l, Nf));
plot(ff, 20*log10(spec_l(1:Nf/2+1) + eps), 'Color', [0.9 0.5 0.1]);
hold off; grid on; xlim([0 5000]);
title('中间时刻单帧幅度谱');
xlabel('频率 (Hz)'); ylabel('幅度 (dB)');
legend({'新降噪', '旧法'}, 'Location', 'northeast');

sgtitle(fig, '多普勒 LDV 音阶：降噪对比与频谱分析');
colormap(fig, parula);
linkaxes([ax1, ax2], 'x');
end

function plot_spectrogram(ax, x, Fs, win_len, overlap, nfft, ttl)
axes(ax); %#ok<LAXES>
[S, F, T] = spectrogram(x, hann(win_len, 'periodic'), overlap, nfft, Fs);
S_db = 10 * log10(abs(S) + eps);
imagesc(ax, T, F, S_db);
axis xy;
ylim([0 5000]);
set(ax, 'YDir', 'normal');
title(ttl);
xlabel('时间 (s)'); ylabel('频率 (Hz)');
caxis(ax, [max(S_db(:)) - 70, max(S_db(:))]);
end

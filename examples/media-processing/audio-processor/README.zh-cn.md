# Audio Processor 示例

本示例展示了 `audio-processor` 组件，该组件使用 pedalboard、librosa、soxr 和 pyloudnorm 对音频流串联应用 DSP 变换（时间/速率、EQ、动态、空间、电平、编辑、效果）。

## 概述

该示例基于同一个 `audio-processor` 组件提供二十七个工作流：

1. **Resample Audio** — 改变采样率
2. **Change Speed** — 加速或减速（可保持音高）
3. **Highpass Filter** — 衰减截止频率以下
4. **Lowpass Filter** — 衰减截止频率以上
5. **Bell EQ** — 中心频率窄带提升/切除
6. **Low Shelf EQ** — 拐点以下提升/切除
7. **High Shelf EQ** — 拐点以上提升/切除
8. **Pitch Shift** — 按半音移调（时长不变）
9. **DC Shift** — 移除 DC 偏置 / 施加偏移
10. **Compress Dynamics** — 阈值以上向下压缩
11. **Noise Gate** — 阈值以下衰减
12. **Distortion** — 强力谐波失真
13. **Saturation** — 细腻的谐波着色
14. **Apply Gain** — 按 dB 值增益或衰减
15. **Chorus** — 调制合唱效果
16. **Delay** — 回声/延迟
17. **Add Reverb** — Freeverb 风格房间混响
18. **Normalize (RMS)** — 目标 RMS 电平（dBFS）
19. **Normalize (Peak)** — 目标峰值电平（dBFS）
20. **Normalize (LUFS)** — 目标综合响度与真峰限制
21. **Peak Limit (Hard)** — 线性幅度上限硬削波
22. **Peak Limit (Smooth)** — 带释放时间的平滑限制器
23. **Trim Edges** — 相对峰值裁剪前后静音
24. **Trim Silence** — 切除前后与较长的内部静音
25. **Fade In** — 起始余弦淡入
26. **Fade Out** — 结尾余弦淡出
27. **Anonymize Voice** — 音高/共振峰移位与抖动实现说话人隐蔽

## 准备工作

### 前置要求

- 已安装并在 PATH 中的 model-compose
- Python 3.10+ 及 `pedalboard`、`librosa`、`soxr`、`pyloudnorm`、`torchaudio`（组件首次运行时会自动安装）

### 设置

进入示例目录：
```bash
cd examples/media-processing/audio-processor
```

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```

   服务将在以下地址启动：
   - API 端点：http://localhost:8080/api
   - Web UI：http://localhost:8081

2. **运行工作流：**

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 从下拉菜单选择工作流
   - 上传音频文件并填写参数
   - 点击 "Run Workflow"

   **使用 CLI：**
   ```bash
   # 重采样到 16 kHz
   model-compose run resample --input '{
     "audio": "/path/to/input.wav",
     "sample_rate": 16000
   }'

   # 以 1.5 倍速播放并保持音高
   model-compose run speed --input '{
     "audio": "/path/to/input.wav",
     "speed": 1.5,
     "preserve_pitch": true
   }'

   # 120 Hz 以下衰减（滚降低频轰鸣）
   model-compose run highpass --input '{
     "audio": "/path/to/input.wav",
     "cutoff": 120
   }'

   # 3 kHz 附近窄带 +3 dB 提升
   model-compose run bell --input '{
     "audio": "/path/to/input.wav",
     "frequency": 3000,
     "gain": 3,
     "q": 1.2
   }'

   # 升 2 个半音（时长不变）
   model-compose run pitch-shift --input '{
     "audio": "/path/to/input.wav",
     "semitones": 2
   }'

   # 以 4:1 比例对 -20 dB 以上进行压缩
   model-compose run compressor --input '{
     "audio": "/path/to/input.wav",
     "threshold": -20,
     "ratio": 4
   }'

   # 归一化到 -14 LUFS（流媒体目标）
   model-compose run normalize-lufs --input '{
     "audio": "/path/to/input.wav",
     "level": -14
   }'

   # 以 -40 dBFS 阈值裁剪静音
   model-compose run trim-silence --input '{
     "audio": "/path/to/input.wav",
     "threshold": -40
   }'

   # 用轻微的音高/共振峰移位隐蔽说话人
   model-compose run anonymize --input '{
     "audio": "/path/to/input.wav",
     "pitch_shift": -2,
     "formant_shift": 1.15
   }'
   ```

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=speed" \
     -F "audio=@/path/to/input.wav" \
     -F "speed=1.5" \
     -F "preserve_pitch=true"
   ```

## 组件详情

### Audio Processor 组件

- **类型**：`audio-processor`
- **驱动**：`native`
- **用途**：对 PCM 流应用 DSP 变换。流式方法（gain、EQ 滤波器、compressor、noise-gate、distortion、saturation、chorus、delay、reverb、fade-in、fade-out）按块运行；需要全局统计信息的方法（normalize、peak-limit、trim-edges、trim-silence、speed、pitch-shift、dc-shift、anonymize）会先收集缓冲区再处理。

#### 通用字段

| 字段 | 类型 | 必需 | 默认值 | 说明 |
|-------|------|----------|---------|-------------|
| `method` | string | 是 | - | 支持的动作方法之一（见下方工作流） |
| `audio` | 音频源 | 是 | - | 输入音频（文件路径、上传或上游音频引用） |
| `batch_size` | integer | 否 | `1` | 当输入是列表/流时每批处理的音频数量 |

输出始终是 PCM 流；容器/编解码器由写入结果的一方决定（工作流输出中的 `${output as audio}` 默认触发 WAV 编码）。

## 工作流详情

### 1. Resample Audio

**说明**：使用 soxr 进行流式重采样。音高和时长保持不变，只有采样率标签改变。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `sample_rate` | integer | 是 | - | 目标输出采样率（Hz，例如 `16000`、`44100`、`48000`） |

### 2. Change Speed

**说明**：加速或减慢音频。`preserve_pitch: true` 时时长改变但音高保持不变（相位声码器 time-stretch）。`preserve_pitch: false` 时对波形进行重采样，音高与速度成反比变化——即经典的 chipmunk / 减速效果。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `speed` | number | 是 | - | 播放速度倍数（例如 `2.0` 为两倍速，`0.5` 为半速） |
| `preserve_pitch` | boolean | 否 | `true` | 改变速度时保持原始音高 |

### 3. Highpass Filter

**说明**：衰减截止频率以下的频率。用于去除低频轰鸣或 DC 偏置。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `cutoff` | number | 是 | - | 滤波器截止频率（Hz） |

### 4. Lowpass Filter

**说明**：衰减截止频率以上的频率。用于软化尖锐的高频内容。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `cutoff` | number | 是 | - | 滤波器截止频率（Hz） |

### 5. Bell EQ

**说明**：围绕中心频率提升或切除窄带。Q 越大带宽越窄。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `frequency` | number | 是 | - | 中心频率（Hz） |
| `gain` | number | 是 | - | 中心处增益（dB，正值提升/负值切除） |
| `q` | number | 否 | `0.707` | 带宽；Q 越大越窄 |

### 6. Low Shelf EQ

**说明**：将拐点频率以下整体按固定 dB 值提升或切除。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `frequency` | number | 是 | - | 搁架拐点频率（Hz） |
| `gain` | number | 是 | - | 搁架增益（dB） |
| `q` | number | 否 | `0.707` | 搁架斜率；Q 越大越陡 |

### 7. High Shelf EQ

**说明**：将拐点频率以上整体按固定 dB 值提升或切除。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `frequency` | number | 是 | - | 搁架拐点频率（Hz） |
| `gain` | number | 是 | - | 搁架增益（dB） |
| `q` | number | 否 | `0.707` | 搁架斜率；Q 越大越陡 |

### 8. Pitch Shift

**说明**：按半音数量移调，同时保持时长不变。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `semitones` | number | 是 | - | 移调数量（正值升高，负值降低） |

### 9. DC Shift

**说明**：移除信号的 DC 偏置（平均偏移），并可选择施加固定的 DC 偏移。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `offset` | number | 否 | `0` | 居中后施加的 DC 偏移（-1.0 到 1.0） |

### 10. Compress Dynamics

**说明**：以给定 `ratio` 对 `threshold` 以上部分进行向下压缩。降低较响部分的电平，之后可以将整体推得更响。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `threshold` | number | 否 | `-20` | 触发压缩的阈值（dB） |
| `ratio` | number | 否 | `4` | 压缩比（例如 `4` 表示 4:1） |
| `attack_time` | duration | 否 | `1ms` | 起音时间 |
| `release_time` | duration | 否 | `100ms` | 释放时间 |

### 11. Noise Gate

**说明**：以指定 `ratio` 衰减 `threshold` 以下的信号。清理有用内容之间的低电平噪声。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `threshold` | number | 否 | `-40` | 门衰减阈值（dB） |
| `ratio` | number | 否 | `10` | 向下扩展比 |
| `attack_time` | duration | 否 | `1ms` | 门起音时间 |
| `release_time` | duration | 否 | `100ms` | 门释放时间 |

### 12. Distortion

**说明**：基于驱动的强力失真。有特色的驱动范围通常为 `15`–`40` dB。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `drive` | number | 是 | - | 驱动量（dB，越大越强） |

### 13. Saturation

**说明**：细腻的谐波着色。与 distortion 使用同样的算法，但为柔和的驱动值（`1`–`8` dB）调优。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `drive` | number | 否 | `3` | 柔和着色的驱动量（dB） |

### 14. Apply Gain

**说明**：将信号乘以由 dB 值推导出的线性增益。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `level` | number | 是 | - | 增益（dB，正值提升，负值衰减） |

### 15. Chorus

**说明**：通过混合失谐副本来增厚声音的调制延迟效果。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `rate` | number | 否 | `1.0` | 合唱 LFO 速率（Hz） |
| `depth` | number | 否 | `0.25` | 调制深度（0.0–1.0） |
| `feedback` | number | 否 | `0` | 反馈量（0.0–1.0） |
| `delay` | duration | 否 | `7ms` | 中心延迟时间 |
| `mix` | number | 否 | `0.5` | 干湿比（0.0=干，1.0=湿） |

### 16. Delay

**说明**：带反馈与干湿混合的简单延迟/回声。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `time` | duration | 否 | `500ms` | 延迟时间 |
| `feedback` | number | 否 | `0` | 反馈量（0.0–1.0） |
| `mix` | number | 否 | `0.5` | 干湿比 |

### 17. Add Reverb

**说明**：Freeverb 风格的房间混响，可配置房间大小、阻尼以及干湿混合比例。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `room_size` | number | 否 | `0.5` | 模拟房间大小（0.0–1.0） |
| `damping` | number | 否 | `0.5` | 高频阻尼（0.0–1.0） |
| `wet_level` | number | 否 | `0.33` | 混响信号电平（0.0–1.0） |
| `dry_level` | number | 否 | `0.4` | 干信号电平（0.0–1.0） |
| `width` | number | 否 | `1.0` | 混响的立体声宽度（0.0–1.0） |

### 18. Normalize (RMS)

**说明**：缩放音频，使其 RMS（平均能量）达到目标电平（dBFS），并在增益后施加峰值上限。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `level` | number | 否 | `-20` | 目标 RMS 电平（dBFS） |
| `peak_limit` | number | 否 | `0.85` | 归一化后应用的峰值幅度上限（0.0–1.0） |

### 19. Normalize (Peak)

**说明**：缩放音频，使其最高样本达到目标峰值电平（dBFS）。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `level` | number | 否 | `-1` | 目标峰值电平（dBFS，例如 `-1` 保留 1 dB 余量） |

### 20. Normalize (LUFS)

**说明**：迭代测量并调整增益使综合响度达到目标 LUFS，然后应用真峰值限制器。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `level` | number | 否 | `-14` | 目标综合响度（LUFS） |
| `tolerance` | number | 否 | `0.5` | 校验循环重新迭代前允许的目标偏差（LU） |
| `max_gain` | number | 否 | `30` | 校验循环可施加的最大绝对增益（dB） |
| `true_peak_ceiling` | number | 否 | `-1` | 响度增益后强制施加的真峰值上限（dBTP） |

### 21. Peak Limit (Hard)

**说明**：仅在输入峰值超过线性幅度上限时进行硬削波。快速便宜，但推得过狠会产生削波伪影。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `level` | number | 否 | `0.95` | 峰值幅度上限（0.0–1.0） |

### 22. Peak Limit (Smooth)

**说明**：带释放时间的真峰值限制器（pedalboard `Limiter`）。推得比较狠时也比硬削波干净。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `level` | number | 否 | `-1` | 上限（dBFS，例如 `-1` 保留 1 dB 余量） |
| `release_time` | duration | 否 | `100ms` | 限制器释放时间 |

### 23. Trim Edges

**说明**：相对于信号峰值检测前后静音（阈值单位为 dB below peak）并裁剪。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `threshold` | number | 否 | `40` | 峰值以下的静音阈值（dB） |
| `padding` | duration | 否 | `0ms` | 裁剪缩短后在每端恢复的填充 |

### 24. Trim Silence

**说明**：检测静音窗口，切除前后静音以及超过 `max_internal_silence` 的内部静音。短的余弦淡出用于避免裁剪边界处的爆音。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `window` | duration | 否 | `20ms` | RMS 分析窗口大小 |
| `threshold` | number | 否 | `-40` | 静音阈值（dBFS） |
| `min_silence` | duration | 否 | `200ms` | 保留的最小尾部静音 |
| `max_internal_silence` | duration | 否 | `1s` | 超过此值的内部间隙将被切除 |
| `fade` | duration | 否 | `30ms` | 在裁剪结尾应用的余弦淡出 |

### 25. Fade In

**说明**：在音频开头应用 `sin^2` 余弦曲线。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `duration` | duration | 否 | `500ms` | 淡入时长 |

### 26. Fade Out

**说明**：在音频结尾应用 `cos^2` 曲线。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `duration` | duration | 否 | `500ms` | 淡出时长 |

### 27. Anonymize Voice

**说明**：通过音高移位、共振峰缩放和时间可变的抖动来隐蔽说话人，并可选择在末端加低通以衰减高频说话人线索。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 是 | - | 源音频文件 |
| `pitch_shift` | number | 否 | `-2` | 音高移位（半音） |
| `formant_shift` | number | 否 | `1.15` | 共振峰缩放比（>1 上移） |
| `pitch_jitter` | number | 否 | `0.3` | 随机音高调制深度（半音） |
| `jitter_rate` | number | 否 | `4` | 抖动调制速率（Hz） |
| `lowpass_cutoff` | number | 否 | `6000` | 末端低通截止（Hz，≤0 为禁用） |

## 提示

- **流式 vs collect**：流式方法（`gain`、EQ 滤波器、`compressor`、`noise-gate`、`distortion`、`saturation`、`chorus`、`delay`、`reverb`、`fade-in`、`fade-out`）按块运行，不需要具化整个缓冲区。需要全局统计的方法（`normalize`、`peak-limit`、`trim-edges`、`trim-silence`、`speed`、`pitch-shift`、`dc-shift`、`anonymize`）会先收集输入再处理。
- **`speed` vs `resample` vs `pitch-shift`**：`speed` 改变时长；`resample` 只改变采样率标签（不影响时长或音高）；`pitch-shift` 改变音高并保持时长。
- **`speed` 配合 `preserve_pitch: false`**：纯粹的重采样。加倍速度会使感知音高的周期减半（升一个八度），也就是经典的 chipmunk 效果。
- **`normalize` vs `peak-limit`**：`normalize` 将整个信号缩放到目标电平；`peak-limit` 只降低超过阈值的峰值。
- **LUFS normalize**：运行迭代式的"测量 → 增益 → 真峰值限制"循环。流媒体目标（Spotify/YouTube）使用 `-14`，更有冲击力的母带使用 `-9` 到 `-12`。
- **Trim-silence 调优**：`threshold` 越低（`-50`、`-60`）对静音的判定越严格；`max_internal_silence` 越大保留的自然停顿越多。
- **串联多个方法**：通过 `${jobs.<id>.output}` 串联多个动作，可组合出例如 `trim-silence → compressor → normalize-lufs → fade-in` 之类的流程。

## 故障排查

### 常见问题

1. **缺少依赖（`pedalboard`、`librosa`、`soxr`、`pyloudnorm`）**：组件将它们声明为 setup requirement，并在首次运行时自动安装。如果自动安装失败（离线或受限环境），请在 Python 环境中手动安装它们。
2. **裁剪边界处出现爆音**：增大 `trim-silence` 中的 `fade`（例如 `50ms`），或在裁剪后再显式应用 `fade-out`。
3. **`normalize` 未达到目标 LUFS**：LUFS 循环最多迭代 3 次并遵守 `max_gain`。非常安静的素材可能达到该上限；请提高 `max_gain` 或分阶段归一化。
4. **`speed` 使用非常大的值时有明显伪影**：`preserve_pitch: true` 使用的相位声码器在极端速度下质量会下降。对于远超 `0.5..2.0` 的速度值，请接受伪影，或切换到 `preserve_pitch: false`（基于重采样的加速）。
5. **`distortion` 或 `peak-limit-hard` 听起来很粗糙**：两者都会故意引入非线性失真。如需更柔和的处理，请使用 `saturation`（微弱驱动）或 `peak-limit-smooth`（真峰值限制器）。

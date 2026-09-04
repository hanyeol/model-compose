# 音乐分析器示例

此示例演示如何使用 model-compose 的 `music-analyzer` 组件从音频文件中提取音乐领域属性——节奏、调性、频谱特性以及谐波与打击成分的比例。

## 概述

此示例提供 10 个工作流，每个 metric 一个：

1. **检测节拍与 BPM**（默认）——速度估计、节拍时刻，以及基于周期性的置信度分数
2. **检测音符起始点（Onsets）** ——起音时间戳，附带峰值归一化的强度值
3. **计算局部速度分布**——逐帧的 tempogram；当 BPM 在曲目内发生变化时有用
4. **检测活跃段落** ——基于曲目自身动态范围的响亮段落（silence 检测的语义反面）
5. **检测音乐调性**——通过 Krumhansl 剖面相关性估计 tonic + mode
6. **提取色度（Chroma）** ——随时间变化的 12 维音高类能量
7. **提取 Tonnetz** ——6 维 Harte 音调质心特征
8. **测量频谱亮度** ——以 Hz 为单位的频谱质心
9. **测量频谱平坦度** ——[0, 1] 范围内的音调 vs 噪声比率
10. **测量谐波/打击比率** ——基于 HPSS 的能量分离

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- Python 依赖会在首次运行时自动安装：
  - `librosa`、`numpy`、`soundfile`（`native` 驱动使用）

### 设置

导航到此示例目录：
```bash
cd examples/media-processing/music-analyzer
```

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```

   服务启动后：
   - API 端点：http://localhost:8080/api
   - Web UI：http://localhost:8081

2. **运行工作流：**

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 从下拉菜单中选择工作流
   - 上传音频文件
   - 点击"Run Workflow"按钮

   **使用 CLI：**
   ```bash
   # 节拍与 BPM（默认）
   model-compose run detect-beats --input '{"audio": "/path/to/track.mp3"}'

   # 自定义 BPM 搜索范围
   model-compose run detect-beats --input '{
     "audio": "/path/to/track.mp3",
     "min_bpm": 80,
     "max_bpm": 160
   }'

   # 起始点检测——更紧的最小间隔
   model-compose run detect-onsets --input '{
     "audio": "/path/to/track.mp3",
     "min_gap": "50ms"
   }'

   # 调性检测
   model-compose run detect-key --input '{"audio": "/path/to/track.mp3"}'

   # 活跃段落——更严格的阈值
   model-compose run detect-activity --input '{
     "audio": "/path/to/track.mp3",
     "level": 0.5,
     "min_duration": "1s"
   }'
   ```

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=detect-beats" \
     -F "audio=@/path/to/track.mp3"
   ```

## 组件详情

### Music Analyzer 组件

- **类型**：`music-analyzer`
- **目的**：从音频中提取音乐领域属性——节奏、调性、频谱特性和源分离比率
- **驱动**：
  - `native` —— 基于 librosa 的分析（默认）

对于信号级测量（响度/峰值/增益/削波/静音），请使用 [`audio-analyzer`](../audio-analyzer/)。对于原始特征矩阵（频谱图、波形），请使用 [`audio-feature-extractor`](../audio-feature-extractor/)。

## 工作流详情

### 1. 检测节拍与 BPM

**ID**：`detect-beats`
**Metric**：`beats`

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|-------|------|
| `audio` | file | 是 | - | 要分析的音频文件 |
| `min_bpm` | number | 否 | `60.0` | 跟踪节拍时考虑的最低 BPM |
| `max_bpm` | number | 否 | `200.0` | 跟踪节拍时考虑的最高 BPM |

#### 输出示例

```json
{
  "bpm": 137.2,
  "confidence": 8.94,
  "beats": [
    { "time": 0.44 },
    { "time": 0.88 }
  ]
}
```

`confidence` 接近 1.0 表示输入没有主导周期性；典型音乐通常在 3 以上。

---

### 2. 检测音符起始点

**ID**：`detect-onsets`
**Metric**：`onsets`

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|-------|------|
| `audio` | file | 是 | - | 要分析的音频文件 |
| `min_gap` | duration | 否 | `30ms` | 相邻起始点之间的最小时间 |

#### 输出示例

```json
{
  "onsets": [
    { "time": 0.44, "strength": 0.82 },
    { "time": 1.17, "strength": 0.65 }
  ]
}
```

---

### 3. 计算局部速度分布

**ID**：`compute-tempogram`
**Metric**：`tempogram`

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|-------|------|
| `audio` | file | 是 | - | 要分析的音频文件 |
| `min_bpm` | number | 否 | `60.0` | tempogram 轴的最低 BPM 值 |
| `max_bpm` | number | 否 | `200.0` | tempogram 轴的最高 BPM 值 |

#### 输出示例

```json
{
  "frames": [[0.12, 0.08, "..."], "..."],
  "bpm_axis": [60.0, 62.4, "...", 200.0],
  "fps": 86.13,
  "sample_rate": 44100
}
```

---

### 4. 检测活跃段落

**ID**：`detect-activity`
**Metric**：`activity`

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|-------|------|
| `audio` | file | 是 | - | 要分析的音频文件 |
| `min_duration` | duration | 否 | `0.3s` | 活跃段落的最小持续时间 |
| `level` | number | 否 | `0.35` | 曲目自身安静到响亮范围内的阈值（0.0 = 安静底部，1.0 = 响亮顶部） |

#### 输出示例

```json
{
  "activity": [
    { "start_time": 3.0,  "end_time": 7.04 },
    { "start_time": 12.5, "end_time": 44.8 }
  ]
}
```

空列表表示曲目没有可用于设置阈值的动态范围。

---

### 5. 检测音乐调性

**ID**：`detect-key`
**Metric**：`key`

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|-------|------|
| `audio` | file | 是 | - | 要分析的音频文件 |

#### 输出示例

```json
{
  "key": "C",
  "mode": "major",
  "confidence": 0.10
}
```

`confidence` 是获胜的调性/模式与第二名之间的相关性差距。

---

### 6. 提取色度

**ID**：`extract-chroma`
**Metric**：`chroma`

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|-------|------|
| `audio` | file | 是 | - | 要分析的音频文件 |

#### 输出示例

```json
{
  "frames": [[0.1, 0.05, "...", 0.3], "..."],
  "fps": 86.13,
  "sample_rate": 44100
}
```

每一帧是按 `C, C#, D, D#, E, F, F#, G, G#, A, A#, B` 顺序排列的 12 个音高类能量。

---

### 7. 提取 Tonnetz

**ID**：`extract-tonnetz`
**Metric**：`tonnetz`

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|-------|------|
| `audio` | file | 是 | - | 要分析的音频文件 |

#### 输出示例

```json
{
  "frames": [[0.1, -0.05, "...", 0.2], "..."],
  "fps": 86.30,
  "sample_rate": 44100
}
```

每一帧是 Harte tonnetz 上的 6 个音调质心坐标。

---

### 8. 测量频谱亮度

**ID**：`measure-brightness`
**Metric**：`brightness`

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|-------|------|
| `audio` | file | 是 | - | 要分析的音频文件 |

#### 输出示例

```json
{
  "brightness_hz": 2140.5,
  "frames": [2130.1, 2145.3, "..."],
  "fps": 86.13,
  "sample_rate": 44100
}
```

---

### 9. 测量频谱平坦度

**ID**：`measure-flatness`
**Metric**：`flatness`

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|-------|------|
| `audio` | file | 是 | - | 要分析的音频文件 |

#### 输出示例

```json
{
  "flatness": 0.12,
  "frames": [0.10, 0.13, "..."],
  "fps": 86.13,
  "sample_rate": 44100
}
```

---

### 10. 测量谐波/打击比率

**ID**：`measure-harmonicity`
**Metric**：`harmonicity`

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|-------|------|
| `audio` | file | 是 | - | 要分析的音频文件 |

#### 输出示例

```json
{
  "harmonicity": 0.72,
  "percussivity": 0.28
}
```

## 自定义

### 在多个节奏 metric 之间复用频谱

`beats`、`onsets`、`tempogram`、`activity` 内部消费相同的 onset envelope。当在同一曲目上运行多个 metric 时，用 `audio-feature-extractor` 组件预先计算一次频谱并传给每个 metric，可以跳过冗余的 FFT 计算：

```yaml
components:
  - id: extractor
    type: audio-feature-extractor
    driver: native
    action:
      feature: spectrum
      audio: ${input.audio as file}
      fps: 100
      band_count: 128

  - id: analyzer
    type: music-analyzer
    driver: native
    actions:
      - id: beats
        metric: beats
        spectrum: ${extractor.result}

      - id: onsets
        metric: onsets
        spectrum: ${extractor.result}
```

调性和频谱特性 metric（`key`、`chroma`、`tonnetz`、`brightness`、`flatness`、`harmonicity`）需要原始音频——请直接传入 `audio: ...`。

### 采样率

默认情况下保留文件原生的采样率。若要强制重采样（通常是为了在长曲目上以精度换速度），在 action 上设置 `sample_rate`：

```yaml
actions:
  - id: beats
    metric: beats
    audio: ${input.audio as file}
    sample_rate: 22050
```

### BPM 搜索范围

`beats` 和 `tempogram` 接受 `min_bpm` / `max_bpm`。当流派的速度区间明确时（例如 house/techno 为 `100`–`140`，lo-fi 为 `60`–`90`），缩小范围会有所帮助：

```yaml
actions:
  - id: beats
    metric: beats
    audio: ${input.audio as file}
    min_bpm: 100
    max_bpm: 140
```

### Activity 电平阈值

`activity` 的 `level` 将曲目自身的安静到响亮百分位映射到 `[0, 1]`。提高以仅隔离最响亮的段落（drop、副歌等）；降低以捕获较安静的段落：

```yaml
actions:
  - id: activity
    metric: activity
    audio: ${input.audio as file}
    level: 0.6
    min_duration: 2s
```

若需要基于绝对 dBFS 而非相对阈值，请使用 [`audio-silence-detector`](../audio-silence-detector/)。

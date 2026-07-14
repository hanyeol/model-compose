# 音频特征提取器示例

此示例演示了 `audio-feature-extractor` 组件，展示了 model-compose 如何将音频文件转换为适合驱动可视化（均衡器条、示波器波形等）的每帧特征数组。

## 概述

提供两个工作流：

1. **Spectrum**：每帧基于 FFT 的频段幅度 —— 经典的条形均衡器外观
2. **Waveform**：每帧下采样的时域振幅 —— SoundCloud 风格的波形外观

输出是带有 `frames` 数组的 JSON 载荷。每个条目是一个视频帧的特征向量。下游渲染器（Remotion、D3、canvas、SVG）无需了解音频即可直接使用。

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- 已安装 [ffmpeg](https://ffmpeg.org/) 并在您的 PATH 中可用
- numpy（首次组件运行时自动安装）

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/media-processing/audio-feature-extractor
   ```

2. 验证 ffmpeg 已安装：
   ```bash
   ffmpeg -version
   ```

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 选择 **Spectrum** 或 **Waveform** 工作流
   - 上传音频文件
   - 调整参数
   - 点击 **Run Workflow**
   - 检查 JSON 输出

   **使用 API：**
   ```bash
   # Spectrum（默认工作流）
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: multipart/form-data" \
     -F "audio=@song.mp3" \
     -F "fps=30" \
     -F "band_count=32"

   # Waveform
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: multipart/form-data" \
     -F "workflow_id=waveform" \
     -F "audio=@song.mp3" \
     -F "fps=30" \
     -F "point_count=100"
   ```

   **使用 CLI：**
   ```bash
   model-compose run spectrum --input '{"audio": "path/to/song.mp3", "band_count": 32}'
   model-compose run waveform --input '{"audio": "path/to/song.mp3", "point_count": 100}'
   ```

## 组件详情

### Audio Feature Extractor 组件
- **类型**：`audio-feature-extractor`
- **驱动**：`ffmpeg`（用于将输入解码为单声道 PCM）
- **计算**：numpy（首次运行时延迟安装）
- **用途**：从音频源发出每帧特征向量

组件根据动作上的 `feature` 字段选择计算路径：
- `feature: spectrum` —— FFT + 对数缩放频段 + 峰值百分位归一化
- `feature: waveform` —— 通过每桶的峰值或 RMS 汇总为 N 个数据点的滑动窗口

## 工作流详情

### "Spectrum" 工作流（默认）

**描述**：提取适合条形均衡器可视化的频段频谱。

#### 作业流程

```mermaid
graph TD
    J1((Default<br/>job))
    C1[Spectrum<br/>extractor]
    J1 --> C1
    C1 -.-> |frames: number[][]| J1
    Input((Input)) --> J1
    J1 --> Output((Output))
```

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `audio` | file | Yes | - | 音频源 (mp3, wav, flac, aac, m4a, opus, ogg, ...) |
| `fps` | int | No | `30` | 每秒输出帧数 |
| `band_count` | int | No | `32` | 每帧频段数 |
| `min_frequency` | float | No | `40.0` | 频段网格中包含的最低频率 (Hz) |
| `window_size` | select | No | `2048` | 以采样为单位的 FFT 窗口大小：512、1024、2048、4096 |
| `window_type` | select | No | `hann` | FFT 窗口类型：hann、hamming、blackman |
| `frequency_scale` | select | No | `log` | 频段分布尺度：log、linear |
| `normalize_mode` | select | No | `peak-percentile` | 振幅归一化：peak-percentile、none |

#### 输出格式

```json
{
  "fps": 30,
  "band_count": 32,
  "frame_count": 5400,
  "duration": 180.0,
  "sample_rate": 22050,
  "frames": [[0.22, 0.10, ...], [0.24, 0.13, ...], ...]
}
```

`frames` 中的每个条目是一个视频帧；该条目中的每个值是一个频段的幅度（归一化时为 0..1）。低索引是低音，高索引是高音。

### "Waveform" 工作流

**描述**：提取适合示波器风格可视化的时域振幅波形。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `audio` | file | Yes | - | 音频源 |
| `fps` | int | No | `30` | 每秒输出帧数 |
| `point_count` | int | No | `100` | 每帧数据点数（波形显示分辨率） |
| `window_duration` | string | No | `40ms` | 每帧分析窗口（例如 `40ms`、`0.04s`、`1s`） |
| `summary_mode` | select | No | `peak` | 桶汇总统计：`peak` (max\|amplitude\|) 或 `rms` |
| `rectify` | bool | No | `true` | 如果为 true，返回幅度 (0..1)；如果为 false，保留有符号值 (-1..1) |

#### 输出格式

```json
{
  "fps": 30,
  "point_count": 100,
  "frame_count": 5400,
  "duration": 180.0,
  "sample_rate": 22050,
  "frames": [[0.02, 0.15, 0.34, ...], ...]
}
```

`frames` 中的每个条目是一个视频帧；该条目中的每个值是汇总该帧窗口的一个桶的一个波形数据点（峰值或 RMS）。

## 渲染输出

JSON 输出有意设计为渲染器无关。将其转换为视频的几种选择：

- **Remotion (React)**：将 `frames` 作为 props 传递给 `<Composition>`，并根据 `useCurrentFrame()` 渲染条形/路径。适合离线批量渲染
- **SVG / HTML canvas**：使用数组直接为每帧绘制条形或折线
- **任何其他工具**：JSON 足够小，可以为短剪辑内联嵌入（3 分钟歌曲，30 fps × 32 段约几 MB）

## 提示

- **选择 `band_count`**：16-64 适合条形均衡器。VoyagerFM 使用 32
- **选择 `window_size` (spectrum)**：2048 是一个好的平衡。较大的值提供更精细的频率分辨率但会模糊时间，较小的值则相反
- **`min_frequency` 和 `max_frequency`**：`max_frequency` 默认为奈奎斯特频率 (`sample_rate / 2`)。将 `min_frequency` 提高到 20-40 Hz 以上以跳过听不见的低频轰鸣
- **`normalize_mode: peak-percentile`**：使用第 99 百分位数作为比例。好的默认值。如果需要原始幅度，请设置 `normalize_mode: none`
- **`window_duration` (waveform)**：20-60 ms 典型。较长的窗口会平滑快速瞬态

## 故障排除

### 常见问题

1. **找不到 ffmpeg**：确保 ffmpeg 已安装并在您的 PATH 上 —— 组件调用它将音频解码为 PCM
2. **未安装 numpy**：组件将 numpy 声明为延迟需求；首次运行将通过 pip 安装。如果安装失败，请手动安装：`pip install numpy`
3. **`window_duration` 值被拒绝**：使用 `"40ms"`、`"0.04s"` 之一，或裸数字（解释为秒）
4. **返回零帧**：音频比一个窗口短。减小 `window_size`（spectrum）或 `window_duration`（waveform），或使用更长的输入

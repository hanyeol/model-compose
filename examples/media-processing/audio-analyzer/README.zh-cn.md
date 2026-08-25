# 音频分析示例

此示例演示如何使用 model-compose 的 `audio-analyzer` 组件，检查音频文件的信号级属性（响度、峰值、增益、削波、静音、能量），而无需对音频本身进行任何变换。

## 概述

此示例提供 7 种分析工作流，覆盖所有支持的 metric：

1. **测量响度**：EBU R128 综合响度、响度范围（LRA）以及真峰值
2. **测量峰值**：采样峰值和采样间真峰值（dBTP）
3. **测量增益/余量**：RMS、峰值、余量、峰值因子/平坦因子——用于归一化决策的输入
4. **检测削波**：数字削波计数与比例
5. **检测静音**：静音区域与整体静音比例
6. **测量能量曲线**：活跃比例、峰值、平均响度以及完整的分桶能量曲线
7. **查找最佳 BGM 片段**：扫描能量曲线并返回指定长度的最响亮片段——适用于为固定长度视频挑选音乐轨道中最有冲击力的片段

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- 已安装 FFmpeg（`ffmpeg` 驱动必需）

### 设置

导航到此示例目录：
```bash
cd examples/media-processing/audio-analyzer
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
   - 上传音频文件、调整参数，然后点击"Run Workflow"

   **使用 CLI：**
   ```bash
   # EBU R128 响度（含逐窗口时间线）
   model-compose run measure-loudness --input '{
     "audio": "/path/to/track.wav",
     "target_loudness": -23.0,
     "include_timeline": true
   }'

   # 采样与真峰值
   model-compose run measure-peak --input '{"audio": "/path/to/track.wav"}'

   # RMS / 余量 / 峰值因子
   model-compose run measure-gain --input '{"audio": "/path/to/track.wav"}'

   # 削波计数（阈值单位 dBFS）
   model-compose run detect-clipping --input '{
     "audio": "/path/to/track.wav",
     "threshold": -0.1
   }'

   # 静音区域
   model-compose run detect-silence --input '{
     "audio": "/path/to/track.wav",
     "threshold": -60.0,
     "min_duration": "500ms"
   }'

   # 完整能量分析（曲线 + 活跃比例 + 峰值 + 最佳片段）
   model-compose run measure-energy --input '{
     "audio": "/path/to/music.mp3",
     "threshold": -40.0,
     "segment_duration": 30.0,
     "resolution": "1s"
   }'

   # 相同分析，但仅返回挑选出的片段
   model-compose run find-best-bgm-segment --input '{
     "audio": "/path/to/music.mp3",
     "threshold": -40.0,
     "segment_duration": 30.0
   }'
   ```

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=measure-loudness" \
     -F "audio=@/path/to/track.wav"
   ```

## 组件详情

### 音频分析组件

- **类型**：`audio-analyzer`
- **用途**：测量音频文件的信号级属性并返回紧凑的汇总。用于母带 QA、电平归一化决策、静音修剪，以及任何需要*检查*音频而不进行变换的管线
- **驱动**：
  - `ffmpeg` - 基于 FFmpeg 的分析，使用 `ebur128`、`astats`、`silencedetect`（默认）

## 工作流详情

### 1. 测量响度

**ID**：`measure-loudness`
**描述**：遵循 EBU R128 的综合响度、响度范围以及真峰值

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `audio` | file | 是 | - | 待分析的音频文件 |
| `target_loudness` | number | 否 | `-23.0` | 参考目标响度（LUFS） |
| `include_timeline` | boolean | 否 | `false` | 是否包含逐窗口的 momentary/short-term/integrated 时间线 |

#### 输出示例

```json
{
  "integrated_loudness": -18.4,
  "loudness_range": 6.1,
  "loudness_range_low": -25.7,
  "loudness_range_high": -19.6,
  "sample_peak_dbfs": -1.2,
  "true_peak_dbtp": -0.8,
  "target_loudness": -23.0
}
```

---

### 2. 测量峰值

**ID**：`measure-peak`
**描述**：采样峰值和采样间真峰值（dBTP）

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `audio` | file | 是 | - | 待分析的音频文件 |
| `true_peak` | boolean | 否 | `true` | 是否计算采样间真峰值（dBTP） |

#### 输出示例

```json
{
  "sample_peak_dbfs": -0.9,
  "max_sample": 0.902,
  "min_sample": -0.898,
  "true_peak_dbtp": -0.4
}
```

---

### 3. 测量增益/余量

**ID**：`measure-gain`
**描述**：RMS、峰值、余量、DC 偏移、峰值/平坦因子——归一化/压缩决策的输入

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `audio` | file | 是 | - | 待分析的音频文件 |

#### 输出示例

```json
{
  "rms_dbfs": -18.7,
  "rms_peak_dbfs": -6.2,
  "rms_trough_dbfs": -42.1,
  "peak_dbfs": -0.9,
  "headroom_db": 0.9,
  "dc_offset": 0.00012,
  "crest_factor": 8.4,
  "flat_factor": 0.02
}
```

---

### 4. 检测削波

**ID**：`detect-clipping`
**描述**：基于 `astats` 的数字削波计数与比例。细粒度区域检测尚未实现（`regions` 返回空数组）

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `audio` | file | 是 | - | 待分析的音频文件 |
| `threshold` | number | 否 | `-0.1` | 视为削波的幅度阈值（dBFS） |
| `min_consecutive_length` | integer | 否 | `3` | 计入削波区域所需的最小连续超阈值样本数 |

#### 输出示例

```json
{
  "threshold_dbfs": -0.1,
  "min_consecutive_length": 3,
  "sample_count": 8820000,
  "clipped_sample_count": 342,
  "clipped_ratio": 0.0000387,
  "peak_dbfs": -0.02,
  "regions": []
}
```

---

### 5. 检测静音

**ID**：`detect-silence`
**描述**：通过 FFmpeg 的 `silencedetect` 滤镜检测静音区域

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `audio` | file | 是 | - | 待分析的音频文件 |
| `threshold` | number | 否 | `-60.0` | 视为静音的幅度阈值（dBFS） |
| `min_duration` | string | 否 | `500ms` | 认定为静音所需的最短低于阈值时长（例如 `500ms`、`1s`、`2.5s`） |

#### 输出示例

```json
{
  "threshold_dbfs": -60.0,
  "min_duration": 0.5,
  "duration": 180.5,
  "total_silent": 12.3,
  "silent_ratio": 0.068,
  "regions": [
    { "start": 0.0, "end": 3.4, "duration": 3.4 },
    { "start": 175.6, "end": 180.5, "duration": 4.9 }
  ]
}
```

---

### 6. 测量能量曲线

**ID**：`measure-energy`
**描述**：将 momentary 响度聚合为粗粒度能量曲线，并返回完整分析结果——活跃比例、首次活跃时间、峰值、平均响度、分桶曲线，以及（在指定 `segment_duration` 时）最佳片段

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `audio` | file | 是 | - | 待分析的音频文件 |
| `threshold` | number | 否 | `-40.0` | 视为活跃的 momentary 响度阈值（LUFS） |
| `segment_duration` | number | 否 | `30.0` | 待搜索片段的长度（秒）。省略则跳过片段搜索，仅返回曲线 |
| `resolution` | string | 否 | `1s` | 聚合 momentary 响度时使用的下采样间隔 |

#### 输出示例

```json
{
  "threshold": -40.0,
  "duration": 180.5,
  "resolution": 1.0,
  "active_duration": 142.0,
  "active_ratio": 0.787,
  "first_active_time": 12.0,
  "peak_time": 45.0,
  "peak_loudness": -8.3,
  "average_loudness": -22.5,
  "best_segment": {
    "start": 45.0,
    "duration": 30.0,
    "average_loudness": -18.7
  },
  "profile": [
    { "time": 0.0, "loudness": null,  "active": false },
    { "time": 1.0, "loudness": -55.2, "active": false },
    { "time": 2.0, "loudness": -38.1, "active": true }
  ]
}
```

---

### 7. 查找最佳 BGM 片段

**ID**：`find-best-bgm-segment`
**描述**：与 `measure-energy` 执行相同的能量分析，但工作流输出精简为仅挑选出的片段——下游音频裁剪器可以直接消费的字段

#### 输入参数

同 `measure-energy`

#### 输出示例

```json
{
  "start": 45.0,
  "duration": 30.0,
  "average_loudness": -18.7
}
```

## 自定义

### metric 选择指南

- **`loudness`** — 母带 QA、感知级别检查、广播交付目标
- **`peak`** — 编码前的削波安全性检查，尤其在采样间峰值敏感的有损格式中
- **`gain`** — 归一化前的检查：轨道平均响度以及剩余余量
- **`clipping`** — 检测源文件中已存在的数字过载
- **`silence`** — 修剪首尾死音，按结构性停顿分割较长录音
- **`energy`** — 从较长轨道中挑选有冲击力的片段（BGM 选择、缩略图、预览）

### 阈值与时长指南

- **Loudness `target_loudness`**：`-23.0` LUFS 为 EBU R128 广播标准；`-14.0` 常见于流媒体平台
- **Silence `threshold` / `min_duration`**：较低阈值配合较长时长可分离结构性静音（片段/曲目之间）；较高阈值配合较短时长可捕捉细粒度停顿
- **Energy `threshold`**：`-40.0` LUFS 是平衡的默认值；`-50` 可将安静的氛围段落也计入活跃，`-30` 则仅考虑明显有能量的段落
- **Energy `segment_duration`**：与音乐将要伴随的视频长度匹配。若只需能量曲线而不做片段评分，可省略

### metric 组合

将多个工作流串联可以构建更高阶的工具：
- 响度 + 峰值 → 母带预检
- 静音 + 能量 → 自动修剪安静的前奏/尾奏后，挑选最强片段
- 增益 + 削波 → 判断在进一步处理前是否需要（向下）归一化

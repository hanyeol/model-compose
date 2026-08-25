# 音频静音检测示例

此示例演示如何使用 model-compose 的 `audio-silence-detector` 组件，通过 FFmpeg 的 `silencedetect` 滤镜定位音频文件中的静音区域。

## 概述

此示例提供 2 种静音检测工作流：

1. **默认检测**：使用可配置的阈值和最小时长进行静音检测（适用于一般静音修剪或分段）
2. **严格检测**：仅检测更长、更安静的静音——适合修剪录音前后的死音（dead air）

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- 已安装 FFmpeg（`ffmpeg` 驱动必需）

### 设置

导航到此示例目录：
```bash
cd examples/media-processing/audio-silence-detector
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
   # 默认检测（自定义阈值和最小时长）
   model-compose run detect-silences --input '{
     "audio": "/path/to/audio.wav",
     "silence_threshold": -30.0,
     "min_silence_duration": "500ms"
   }'

   # 严格检测（固定 -40 dBFS / 2 秒）
   model-compose run detect-silences-strict --input '{"audio": "/path/to/audio.wav"}'
   ```

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=detect-silences" \
     -F "audio=@/path/to/audio.wav"
   ```

## 组件详情

### 音频静音检测组件

- **类型**：`audio-silence-detector`
- **用途**：定位音频轨道中的静音（安静）区域，并生成有声段与静音段交替的时间线
- **驱动**：
  - `ffmpeg` - FFmpeg `silencedetect` 音频滤镜（默认）

## 工作流详情

### 1. 静音检测（默认）

**ID**：`detect-silences`
**描述**：使用 FFmpeg 的 `silencedetect` 滤镜，通过可配置的阈值和最小时长检测静音

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `audio` | file | 是 | - | 要分析的音频文件 |
| `silence_threshold` | number | 否 | `-30.0` | 静音检测阈值（dBFS，值越低越安静） |
| `min_silence_duration` | string | 否 | `500ms` | 被识别为静音所需的最小持续时长（如 `500ms`、`1s`、`2.5s`） |

---

### 2. 静音检测（严格）

**ID**：`detect-silences-strict`
**描述**：仅检测长且深的静音（固定 `-40.0` dBFS 阈值和 `2s` 最小时长）。适合干净地修剪前后静音

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `audio` | file | 是 | - | 要分析的音频文件 |

---

### 输出格式

每个工作流返回覆盖整个音频时间线的段列表。段在 `audible`（有声）和 `silence`（低于阈值并持续至少 `min_silence_duration`）之间交替。

| 字段 | 类型 | 描述 |
|------|------|------|
| `start_time` | number | 段起始时间（秒） |
| `end_time` | number | 段结束时间（秒） |
| `type` | string | 段分类：`audible` 或 `silence` |

#### 输出示例

```json
[
  { "start_time": 0.0,   "end_time": 12.345, "type": "audible" },
  { "start_time": 12.345, "end_time": 15.678, "type": "silence" },
  { "start_time": 15.678, "end_time": 42.100, "type": "audible" },
  { "start_time": 42.100, "end_time": 45.000, "type": "silence" }
]
```

## 自定义

### 阈值与时长指南

- **`silence_threshold`**（dBFS）：多安静才算作静音
  - `-20.0` — 非常宽松，轻微的音量下降也算静音
  - `-30.0` — 适合一般语音/音乐的平衡默认值
  - `-40.0` — 严格，仅接近完全静音时才计入
- **`min_silence_duration`**：安静段持续多久才算数
  - `200ms` — 捕获词与词之间的短暂停顿
  - `500ms` — 句子之间的自然间隔（默认值）
  - `2s` 及以上 — 仅首尾死音

将较低的阈值与较长的时长组合可分离结构性静音（Take 之间、曲目之间、章节之间等）；将较高的阈值与较短的时长组合可检测细粒度的停顿。

# 音乐段落检测示例

此示例演示如何使用 model-compose 的 `music-segment-detector` 组件，通过节拍同步的色度特征与聚类查找音乐中的结构性段落边界（前奏、主歌、副歌等）。

## 概述

此示例提供 2 种音乐段落检测工作流：

1. **拉普拉斯（Laplacian）分段**（默认）：通过节拍同步的色度 + MFCC 谱（拉普拉斯）聚类检测段落边界。重复出现的段落（主歌、副歌等）倾向于获得相同的结构标签——适合具有清晰重复结构的音乐
2. **凝聚（Agglomerative）分段**：使用数据驱动的段落数量进行凝聚聚类以检测边界。当拉普拉斯输出在短片段或非常规素材上不稳定时使用

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- Python 依赖会在首次运行时自动安装：
  - `librosa`、`numpy`、`scipy`、`scikit-learn`（`native` 驱动使用）

### 设置

导航到此示例目录：
```bash
cd examples/media-processing/music-segment-detector
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
   # 拉普拉斯分段（默认）
   model-compose run detect-segments --input '{"audio": "/path/to/track.mp3"}'

   # 自定义采样率
   model-compose run detect-segments --input '{
     "audio": "/path/to/track.mp3",
     "sample_rate": 44100
   }'

   # 凝聚分段
   model-compose run detect-segments-agglomerative --input '{"audio": "/path/to/track.mp3"}'
   ```

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=detect-segments" \
     -F "audio=@/path/to/track.mp3"
   ```

## 组件详情

### 音乐段落检测组件

- **类型**：`music-segment-detector`
- **用途**：检测音乐中的结构性段落边界，并为每个段落分配结构标签，以便识别重复出现的段落
- **驱动**：
  - `native` - 基于 librosa 的分析，可配置分段策略（默认）

## 工作流详情

### 1. 音乐段落检测（拉普拉斯）

**ID**：`detect-segments`
**描述**：通过节拍同步的色度 + MFCC 谱聚类检测段落边界。重复出现的段落将获得相同的结构标签。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `audio` | file | 是 | - | 要分段的音频文件 |
| `sample_rate` | integer | 否 | `22050` | 分析所用的单声道 PCM 目标采样率 |

---

### 2. 音乐段落检测（凝聚）

**ID**：`detect-segments-agglomerative`
**描述**：使用数据驱动的段落数量进行凝聚聚类以检测边界。当拉普拉斯输出在短片段或非常规曲目上不稳定时更适合。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `audio` | file | 是 | - | 要分段的音频文件 |
| `sample_rate` | integer | 否 | `22050` | 分析所用的单声道 PCM 目标采样率 |

---

### 输出格式

每个工作流返回覆盖整个音频时间线的连续段落列表。共享同一标签的相邻段落将被自动合并。

| 字段 | 类型 | 描述 |
|------|------|------|
| `start_time` | number | 段落起始时间（秒） |
| `end_time` | number | 段落结束时间（秒） |
| `label` | string | 结构标签（`A`、`B`、`C`……）；相同标签重复出现表示结构相似的段落 |

#### 输出示例

```json
[
  { "start_time": 0.0,    "end_time": 12.345, "label": "A" },
  { "start_time": 12.345, "end_time": 45.678, "label": "B" },
  { "start_time": 45.678, "end_time": 78.900, "label": "C" },
  { "start_time": 78.900, "end_time": 112.234, "label": "B" }
]
```

在上例中，两个 `B` 段落被视为结构相似的段落（例如两次副歌）。

## 自定义

### 策略指南

- **`laplacian`** — 对于具有可识别重复结构（主歌/副歌/桥段）的典型歌曲，是最佳默认值。一次即可产生边界和结构标签，因此重复段落能自然对齐
- **`agglomerative`** — 无重复模型的数据驱动段落数量。适合极短片段、氛围/实验性素材，或 `laplacian` 返回不稳定边界时使用

### 采样率

默认值 `22050` Hz 在分析质量与速度之间取得平衡，是音乐信息检索（MIR）任务的标准值。当处理细微音色细节至关重要的素材时可提升到 `44100`；分析速度会变慢，而边界精度的提升较为有限。

### 最小段落时长

组件默认的 `min_segment_duration` 为 `2s`（短于此值的段落会被合并到相邻段落）。若要暴露更细致的过渡，或反之只保留更粗的结构，请在 action 中设置 `min_segment_duration`：

```yaml
actions:
  - id: laplacian
    audio: ${input.audio as file}
    strategy: laplacian
    min_segment_duration: 5s   # 更粗的结构视图
```

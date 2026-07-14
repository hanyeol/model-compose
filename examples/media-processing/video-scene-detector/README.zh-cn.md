# 视频场景检测示例

此示例演示如何使用 model-compose 的 `video-scene-detector` 组件，通过不同的检测后端来检测视频文件中的场景变化。

## 概述

此示例提供 4 种不同的场景检测工作流：

1. **自适应检测**：使用 PySceneDetect 的自适应检测器（推荐用于大多数视频）
2. **内容检测**：使用 PySceneDetect 的内容感知检测器
3. **时间范围检测**：在特定时间范围内使用可配置的检测器进行场景检测
4. **FFmpeg 检测**：使用 FFmpeg 内置的场景滤镜

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- 已安装 FFmpeg（`ffmpeg` 驱动必需）
- Python 依赖会在首次运行时自动安装：
  - `scenedetect[opencv]`（`pyscenedetect` 驱动用）

### 设置

导航到此示例目录：
```bash
cd examples/video-scene-detector
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
   - 上传视频文件
   - 点击"Run Workflow"按钮

   **使用 CLI：**
   ```bash
   # 自适应检测
   model-compose run detect-scenes --input '{"video": "/path/to/video.mp4"}'

   # 内容检测（自定义阈值）
   model-compose run detect-scenes-content --input '{"video": "/path/to/video.mp4", "threshold": 30.0}'

   # 时间范围检测
   model-compose run detect-scenes-range --input '{
     "video": "/path/to/video.mp4",
     "detector": "content",
     "start_time": "00:01:00",
     "end_time": "00:05:00"
   }'

   # FFmpeg 检测
   model-compose run detect-scenes-ffmpeg --input '{"video": "/path/to/video.mp4", "threshold": 0.4}'
   ```

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=detect-scenes" \
     -F "video=@/path/to/video.mp4"
   ```

## 组件详情

### 视频场景检测组件

- **类型**：`video-scene-detector`
- **用途**：检测视频文件中的场景变化和转场
- **驱动**：
  - `pyscenedetect` - 提供 5 种检测器的 PySceneDetect 库（默认）
  - `ffmpeg` - FFmpeg 场景滤镜
  - `transnetv2` - TransNetV2 深度学习模型

## 工作流详情

### 1. 场景检测（自适应）

**ID**：`detect-scenes`
**描述**：使用 PySceneDetect 的自适应检测器检测场景变化

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `video` | file | 是 | - | 要分析的视频文件 |
| `threshold` | number | 否 | `27.0` | 检测灵敏度阈值 |

---

### 2. 场景检测（内容）

**ID**：`detect-scenes-content`
**描述**：使用 PySceneDetect 的内容感知检测器检测场景变化

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `video` | file | 是 | - | 要分析的视频文件 |
| `threshold` | number | 否 | `27.0` | 检测灵敏度阈值 |

---

### 3. 场景检测（时间范围）

**ID**：`detect-scenes-range`
**描述**：在特定时间范围内检测场景变化

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `video` | file | 是 | - | 要分析的视频文件 |
| `detector` | select | 否 | `adaptive` | 检测器类型：adaptive、content、threshold、histogram、hash |
| `threshold` | number | 否 | - | 检测灵敏度阈值 |
| `start_time` | string | 否 | - | 开始时间（例如 `00:01:00`） |
| `end_time` | string | 否 | - | 结束时间（例如 `00:05:00`） |

---

### 4. 场景检测（FFmpeg）

**ID**：`detect-scenes-ffmpeg`
**描述**：使用 FFmpeg 的场景滤镜检测场景变化

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `video` | file | 是 | - | 要分析的视频文件 |
| `threshold` | number | 否 | `0.3` | 场景变化阈值（0.0 - 1.0） |

---

### 输出格式

所有工作流返回相同的输出结构：

| 字段 | 类型 | 描述 |
|------|------|------|
| `scenes` | array | 检测到的场景列表 |
| `scenes[].index` | integer | 场景索引（从 0 开始） |
| `scenes[].start` | string | 场景开始时间码（HH:MM:SS.mmm） |
| `scenes[].end` | string | 场景结束时间码（HH:MM:SS.mmm） |
| `scenes[].start_frame` | integer | 场景开始帧号 |
| `scenes[].end_frame` | integer | 场景结束帧号 |
| `scenes[].duration` | string | 场景持续时间码 |
| `total_scenes` | integer | 检测到的总场景数 |

#### 输出示例

```json
{
  "scenes": [
    {
      "index": 0,
      "start": "00:00:00.000",
      "end": "00:00:12.345",
      "start_frame": 0,
      "end_frame": 370,
      "duration": "00:00:12.345"
    },
    {
      "index": 1,
      "start": "00:00:12.345",
      "end": "00:00:28.678",
      "start_frame": 370,
      "end_frame": 860,
      "duration": "00:00:16.333"
    }
  ],
  "total_scenes": 2
}
```

## 自定义

### 切换驱动

更改 `driver` 字段以使用不同的检测后端：

```yaml
components:
  - id: scene-detector
    type: video-scene-detector
    driver: ffmpeg           # pyscenedetect, ffmpeg, transnetv2
```

### PySceneDetect 检测器类型

| 检测器 | 描述 | 默认阈值 |
|--------|------|----------|
| `adaptive` | 自适应内容检测（推荐） | 27.0 |
| `content` | 基于帧差异的内容感知检测 | 27.0 |
| `threshold` | 淡入/淡出检测 | 12.0 |
| `histogram` | 基于 HSV 直方图的检测 | 0.05 |
| `hash` | 基于感知哈希的检测 | 0.395 |

### FFmpeg 阈值指南

FFmpeg 场景滤镜阈值范围为 `0.0` 到 `1.0`：
- `0.1` - 非常灵敏（检测微小变化）
- `0.3` - 默认值（平衡检测）
- `0.5` - 较低灵敏度（仅检测主要场景变化）

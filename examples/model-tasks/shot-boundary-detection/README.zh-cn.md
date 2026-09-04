# 镜头边界检测示例 (TransNetV2)

此示例演示如何使用 model-compose 的 `shot-boundary-detection` 模型任务结合 **TransNetV2** 深度学习模型来检测视频文件中的镜头边界。

## 概述

TransNetV2 是基于 CNN 的镜头边界检测模型，在启发式方法（帧差、直方图）难以处理的场景（如溶解、淡入淡出、擦除、快速运动）中表现出色。

此示例提供 2 种工作流：

1. **默认检测**：检测整个视频中的镜头边界
2. **时间范围检测**：在特定时间范围内检测镜头边界

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- 已安装 FFmpeg（内部用于提取帧）
- Python 依赖会在首次运行时自动安装：
  - `transnetv2`（安装 TransNetV2 包）

### 下载模型权重

`transnetv2` pip 包**不**包含预训练权重。您必须从[官方 TransNetV2 仓库](https://github.com/soCzech/TransNetV2)下载 SavedModel 权重并放置在 `./models/transnetv2-weights/` 下。

```bash
# 在此示例目录中：
mkdir -p ./models

# 选项 1：克隆仓库（需要 git-lfs）
git lfs install
git clone https://github.com/soCzech/TransNetV2.git /tmp/TransNetV2
cp -r /tmp/TransNetV2/inference/transnetv2-weights ./models/

# 选项 2：如果您已有权重，创建软链接或复制
ln -s /path/to/transnetv2-weights ./models/transnetv2-weights
```

此步骤后目录结构应为：
```
./models/transnetv2-weights/
├── saved_model.pb
└── variables/
    ├── variables.data-00000-of-00001
    └── variables.index
```

> 注意：建议使用 GPU 以获得合理的吞吐量；CPU 推理可以运行但明显较慢。

### 设置

导航到此示例目录：
```bash
cd examples/model-tasks/shot-boundary-detection
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
   - 点击 "Run Workflow" 按钮

   **使用 CLI：**
   ```bash
   # 默认检测
   model-compose run detect-shots --input '{"video": "/path/to/video.mp4"}'

   # 自定义阈值
   model-compose run detect-shots --input '{"video": "/path/to/video.mp4", "threshold": 0.4}'

   # 时间范围检测
   model-compose run detect-shots-range --input '{
     "video": "/path/to/video.mp4",
     "start_time": "00:01:00",
     "end_time": "00:05:00"
   }'
   ```

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=detect-shots" \
     -F "video=@/path/to/video.mp4"
   ```

## 组件详情

### 镜头边界检测组件

- **类型**：`model`
- **任务**：`shot-boundary-detection`
- **驱动**：`custom`
- **系列**：`transnetv2`
- **用途**：使用深度学习模型检测视频文件中的镜头边界和转换

## 工作流详情

### 1. 检测镜头

**ID**：`detect-shots`
**描述**：检测整个视频中的镜头边界

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|-----|------|------|--------|------|
| `video` | file | 是 | - | 要分析的视频文件 |
| `threshold` | number | 否 | `0.5` | 检测置信度阈值 (0.0 - 1.0) |

---

### 2. 检测镜头 (时间范围)

**ID**：`detect-shots-range`
**描述**：在特定时间范围内检测镜头边界

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|-----|------|------|--------|------|
| `video` | file | 是 | - | 要分析的视频文件 |
| `threshold` | number | 否 | `0.5` | 检测置信度阈值 (0.0 - 1.0) |
| `start_time` | string | 否 | - | 开始时间（例如 `00:01:00`） |
| `end_time` | string | 否 | - | 结束时间（例如 `00:05:00`） |

---

### 输出格式

所有工作流都返回检测到的镜头的平面列表。

| 字段 | 类型 | 描述 |
|-----|------|------|
| `index` | integer | 镜头索引（从 0 开始） |
| `start_time` | string | 镜头开始时间码 (HH:MM:SS.mmm) |
| `end_time` | string | 镜头结束时间码 (HH:MM:SS.mmm) |
| `start_frame` | integer | 镜头开始帧号 |
| `end_frame` | integer | 镜头结束帧号 |
| `duration` | string | 镜头持续时间时间码 |

#### 输出示例

```json
[
  {
    "index": 0,
    "start_time": "00:00:00.000",
    "end_time": "00:00:12.345",
    "start_frame": 0,
    "end_frame": 370,
    "duration": "00:00:12.345"
  },
  {
    "index": 1,
    "start_time": "00:00:12.345",
    "end_time": "00:00:28.678",
    "start_frame": 370,
    "end_frame": 860,
    "duration": "00:00:16.333"
  }
]
```

## 阈值指南

TransNetV2 阈值范围为 `0.0` 到 `1.0`，控制模型将某一帧标记为镜头边界所需的置信度：

- `0.3` - 更灵敏（检测细微转换，可能过度分割）
- `0.5` - 默认（平衡）
- `0.7` - 较不灵敏（仅检测强转换）

## 何时使用 TransNetV2

TransNetV2 在含有多样化转场效果的内容中表现最佳。对于更简单的内容或没有 GPU 的环境，`video-scene-detector` 组件（使用 `pyscenedetect` 或 `ffmpeg` 驱动）可能是更好的选择。

| 内容类型 | 推荐 |
|---------|------|
| 含溶解和淡入淡出的电影、电视剧、纪录片 | `shot-boundary-detection`（本示例） |
| 含多样化转场效果的音乐视频、广告 | `shot-boundary-detection`（本示例） |
| 主要包含硬切的用户生成内容 | `video-scene-detector` + `pyscenedetect` 或 `ffmpeg` |
| 快速原型开发或仅 CPU 环境 | `video-scene-detector` + `ffmpeg` |

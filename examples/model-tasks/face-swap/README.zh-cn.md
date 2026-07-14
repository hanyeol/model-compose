# 人脸交换模型任务示例

本示例演示如何使用 model-compose 的内置 face-swap 任务，通过 InsightFace 的 inswapper 将源图像中的人脸身份转移到目标图像中每个检测到的人脸，提供离线人脸交换功能。

## 概述

此工作流提供本地人脸交换功能：

1. **本地人脸交换模型**：在本地运行 InsightFace 的 `inswapper_128` 模型，无需外部 API
2. **身份转移**：从源图像中提取主要人脸，并将其身份应用于目标图像中的人脸
3. **多人脸交换**：可选择替换目标中每个检测到的人脸，或按索引选择特定人脸
4. **自动对齐**：使用 `buffalo_l` 人脸分析包进行检测、关键点标注和对齐
5. **优雅降级**：目标中未检测到人脸时，原样返回原始目标图像
6. **自动模型管理**：首次使用时自动下载和缓存 swapper 和检测器包

## 准备工作

### 先决条件

- 已安装 model-compose 并在 PATH 中可用
- 运行 onnxruntime 所需的充足系统资源（推荐：4GB+ RAM）
- 带有 `insightface`、`opencv-python` 和 `onnxruntime` 的 Python 环境（首次运行时自动安装）

### 为什么选择本地人脸交换

与云端人脸交换服务不同，在本地运行 InsightFace 提供：

**本地处理的优势：**
- **隐私**：所有图像在本地处理，不会将人脸上传到外部服务
- **成本**：无按图像或 API 使用费用
- **离线**：初始模型下载后无需互联网连接
- **延迟**：每次推理无网络往返
- **管道友好**：与其他 model-compose 任务（姿态检测、图像超分等）无缝组合，适用于下游视频管道

**权衡：**
- **硬件要求**：需要足够的 CPU/GPU 资源；批处理或视频用途推荐使用 onnxruntime-gpu
- **模型限制**：`inswapper_128` 在粘贴回去之前生成 128×128 的人脸裁剪 — 非常高分辨率的目标可能从额外的人脸修复过程中受益（例如 GFPGAN、CodeFormer）
- **许可证**：`inswapper_128` 权重仅**用于非商业研究**

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/model-tasks/face-swap
   ```

2. 无需额外的环境配置 — swapper 模型和 `buffalo_l` 检测器包均在首次运行时自动下载并缓存。

## 如何运行

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **使用 API：**
   ```bash
   # 使用源的身份交换目标中的每个人脸
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "source=@/path/to/source_face.jpg" \
     -F "target=@/path/to/target_image.jpg" \
     -F 'input={"source_image": "@source", "target_image": "@target"}'

   # 仅交换目标中的特定人脸（index 0 = 检测分数最高）
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "source=@/path/to/source_face.jpg" \
     -F "target=@/path/to/group_photo.jpg" \
     -F 'input={"source_image": "@source", "target_image": "@target", "swap_all_faces": false, "face_index": 1}'

   # 针对困难情况（小人脸或部分遮挡的人脸）调整检测灵敏度
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "source=@/path/to/source_face.jpg" \
     -F "target=@/path/to/target_image.jpg" \
     -F 'input={"source_image": "@source", "target_image": "@target", "detection_threshold": 0.3}'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 上传 `source_image`（要转移的人脸）和 `target_image`（要修改的图像）
   - 可选切换 `swap_all_faces`、设置 `face_index`，或为较困难情况降低 `detection_threshold`
   - 点击"Run Workflow"按钮

## 配置参考

### 组件字段

| 字段            | 描述                                                                                     | 默认值        |
|------------------|-------------------------------------------------------------------------------------------|----------------|
| `task`           | 必须为 `face-swap`。                                                                      | —              |
| `driver`         | 必须为 `custom`。                                                                         | —              |
| `family`         | 人脸交换模型系列。目前仅 `insightface`。                                                  | —              |
| `model`          | Swapper 模型来源。指向 `inswapper_128.onnx` 权重（URL 或本地路径）。                      | —              |
| `detector_model` | 用于源和目标检测/关键点/对齐的 InsightFace 人脸分析包。                                   | `buffalo_l`    |

### 操作字段

| 字段                   | 描述                                                                                        | 默认值        |
|------------------------|--------------------------------------------------------------------------------------------|---------------|
| `source_image`         | 提供要转移人脸身份的图像。必须包含至少一张人脸。                                             | —             |
| `target_image`         | 将被替换人脸的图像（或批处理/流）。                                                          | —             |
| `swap_all_faces`       | 为 `true` 时，替换目标中每个检测到的人脸。为 `false` 时，仅使用 `face_index`。                | `true`        |
| `face_index`           | `swap_all_faces` 为 `false` 时要交换的目标人脸。人脸按检测分数排序（0 = 最高）。              | `0`           |
| `detection_threshold`  | 最小人脸检测置信度（0.0 – 1.0）。较低的值可捕获更难的人脸，但假阳性风险更高。                | `0.5`         |
| `detection_size`       | 检测输入大小 `[width, height]`。                                                             | `[640, 640]`  |
| `batch_size`           | `target_image` 为列表或流时，每批处理的目标图像数量。                                        | `1`           |

## 注意事项

- **源图像**：操作会选择检测分数最高的单张人脸。如果源中未检测到人脸，工作流将以明确的错误失败。
- **无人脸的目标图像**：原样返回原始目标 — 对逐帧处理视频时某些帧可能不含人物的情况很有用。
- **批处理 / 视频用途**：`target_image` 接受图像列表或流，因此该组件可无缝接入视频管道（例如在运动迁移生成之后）。
- **后处理**：为了在高分辨率下获得更高的保真度，可在此之后链接 `image-upscale`（或人脸修复）组件。

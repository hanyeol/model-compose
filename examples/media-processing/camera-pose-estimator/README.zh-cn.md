# Camera Pose Estimator 示例

此示例演示了使用 COLMAP 后端的 `camera-pose-estimator` 组件，展示 model-compose 如何从一组重叠照片中恢复相机内参和逐图像的位姿。

## 概述

此工作流提供了一个 Structure-from-Motion (SfM) 服务：

1. **特征提取与匹配**：在每张输入图像上检测 SIFT 关键点，并在图像对之间进行匹配。
2. **增量式重建**：对增量式稀疏重建进行光束法平差（bundle adjustment），生成逐图像的相机位姿以及稀疏 3D 点云。
3. **COLMAP 格式的工作空间**：以 COLMAP 二进制格式（`cameras.bin`、`images.bin`、`points3D.bin`）写入 `workspace_dir/sparse/0/`，下游任务（3D Gaussian Splatting 训练器、NeRF 管线、网格提取器）无需任何转换即可直接使用。

暴露了两个工作流，分别对应两种输入模式：

- `estimate-from-images`：直接提供图像（通常来自上游任务 —— 视频帧提取器、下载器、网页抓取器等）。工作空间会自动创建。
- `estimate-from-workspace`：指向一个已经包含 `images/` 子文件夹的工作空间 —— 标准 COLMAP 数据集所采用的布局。

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- 已安装 `pycolmap`（`pip install pycolmap`）

### 环境配置

1. 进入此示例目录：
   ```bash
   cd examples/media-processing/camera-pose-estimator
   ```

2. 验证 pycolmap 已安装：
   ```bash
   python -c "import pycolmap; print(pycolmap.__version__)"
   ```

3. 为 `estimate-from-workspace` 流程准备测试数据集。COLMAP 项目提供的小型、行为良好的数据集适合作为首次运行：
   ```bash
   mkdir -p ./data
   curl -L -o ./data/gerrard-hall.zip https://demuc.de/colmap/datasets/gerrard-hall.zip
   unzip -q ./data/gerrard-hall.zip -d ./data
   ```
   数据集解压到 `./data/gerrard-hall/`，包含一个 `images/` 子文件夹 —— 该文件夹就是可直接用于第二个工作流的工作空间。

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **从上传的图像集合进行估计（Web UI）：**
   - 打开 Web UI：http://localhost:8081
   - 选择 `estimate-from-images` 工作流
   - 上传覆盖场景的图像文件
   - 点击 "Run Workflow" 按钮

   **从上传的图像集合进行估计（API）：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/estimate-from-images/runs \
     -F "images=@scene/img_0001.jpg" \
     -F "images=@scene/img_0002.jpg" \
     -F "images=@scene/img_0003.jpg"
   ```

   **从已有工作空间进行估计（CLI）：**
   ```bash
   model-compose run estimate-from-workspace \
     --input '{"workspace_dir": "./data/gerrard-hall"}'
   ```

3. **检查结果：**

   工作流返回一个 `summary` JSON 以及 `points` GLB（稀疏点云 + 每张图像的相机 frustum）。当 Web UI 开启时，Gradio Model3D 查看器可直接内嵌渲染该 GLB：
   ```json
   {
     "summary": {
       "workspace_dir": "./data/gerrard-hall/sparse/0",
       "images_count": 100,
       "points_count": 15234,
       "cameras": [ { "id": 1, "model": "OPENCV", "width": 1920, "height": 1080, "params": [...] } ],
       "poses": [ { "image": "0001.jpg", "camera_id": 1, "quaternion": [qw, qx, qy, qz], "translation": [tx, ty, tz] } ]
     },
     "points": "<GLB 文件>"
   }
   ```

   完整重建结果以 COLMAP 二进制格式保存在磁盘的 `workspace_dir/sparse/0/`。如果生成了多个部分重建（partial reconstruction），额外的文件夹（`sparse/1/`、`sparse/2/`、……）会保留以供检查。

## 组件详情

### `estimator` — Camera Pose Estimator (COLMAP)

对一组图像运行 COLMAP 的特征提取、匹配和增量式建图管线。

主要选项：

- `camera_model`（默认 `opencv`）：假定的 COLMAP 相机模型。畸变可忽略的照片使用 `pinhole`，鱼眼镜头使用 `opencv-fisheye` 或 `radial-fisheye`，无标定信息时使用 `simple-pinhole`。
- `matcher`（默认 `exhaustive`）：图像对选择策略。`sequential` 对视频提取的帧要快得多（仅匹配相邻帧）；`spatial` 使用 GPS 元数据。
- `single_camera`（默认 `true`）：假设所有输入图像共享同一物理相机和同一组内参。对于混合来源的数据集请关闭。
- `use_gpu`（默认 `false`）：将 SIFT 提取和匹配路由到 GPU。需要 `pycolmap` 以 CUDA 支持构建（普通 `pycolmap` wheel 仅支持 CPU；Linux 上请使用 `pycolmap-cuda12`）。

### 动作输入

- `images`：构成一个场景（或场景批次/流）的图像。每个元素都是已渲染的图像 —— 通常从上游任务（`${jobs.frame-extractor.output}`）或上传的图像数组接入。
- `workspace_dir`：存放 COLMAP 工作空间（`images/`、`database.db`、`sparse/`）的目录。省略时使用 `.workspace/<component-id>/<run-id>/`。当 `images` 也被省略时，`workspace_dir/images/` 中已有的图像将被复用。
- `images` 或 `workspace_dir` 必须至少提供其中之一（或同时提供两者）。

### 动作输出

- `return_cameras`（默认 `true`）：将恢复的相机内参加入 JSON 结果。计算成本极低；仅在需要减小 HTTP 响应体积时关闭。
- `return_poses`（默认 `true`）：将逐图像的 world-from-camera 位姿加入 JSON 结果。计算成本极低；仅在需要减小 HTTP 响应体积时关闭。
- `return_points`（默认 `false`）：将稀疏点云 + 每张图像的相机 frustum 打包为 GLB 附加为 `result["points"]`。当输出送入 Gradio `Model3D` 查看器或其他 GLB 消费者时启用。若下游任务仅读取 `workspace_dir`（3DGS 训练器、网格提取器等），保持关闭。

### 批处理 / 流式

如果 `images` 是图像数组的列表或流，则每一项被视为独立场景并独立重建。当 `workspace_dir` 是标量（或省略）时，每个场景的工作空间会在 run-id 后追加 `-N` 后缀（`{run-id}-0/`、`{run-id}-1/`、……），以防场景之间互相覆盖。当 `workspace_dir` 本身为列表或流时，其各项按位置与 `images` 一一 zip 并按原样使用。

## 注意事项

- 重建质量在很大程度上取决于图像重叠度。相邻照片之间目标至少 60% 重叠，并从多个角度覆盖场景。
- 缺乏特征的表面（空白墙、水、玻璃、均匀草地）对 SIFT 而言难以处理，常导致部分或完全重建失败。
- 大约 100 张图像的 CPU 管线在现代笔记本电脑上通常需要几分钟。对于视频帧，请使用 `matcher: sequential` 使匹配时间与图像数量呈线性关系。
- 驱动会保留图像的原始字节以保存 EXIF（焦距、GPS），但只有当图像以未解码的流形式到达时才有效。如果上游步骤已经将其解码为 PIL，驱动接收到时 EXIF 已经丢失，`matcher: spatial` 也就没有 GPS 信息可用于排序。当需要基于 GPS 的匹配时，请将文件保留在磁盘上并使用 `estimate-from-workspace`。

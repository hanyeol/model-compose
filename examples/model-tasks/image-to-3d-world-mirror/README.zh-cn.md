# 图像转 3D 模型任务示例

本示例展示如何通过 model-compose 内置的 image-to-3d 任务，使用 HunyuanWorld-Mirror 2.0 从一组图像重建 3D 场景（Gaussian splats、基于深度的点云与相机参数）。

## 概述

Pixal3D 系列是根据图像的暗示*生成*形状，而 WorldMirror 则是*重建*图像本身已经包含的几何。给定一组同一场景的无姿态图像，管线只需一次 feed-forward 前向传播即可同时得到多种对齐好的产出。

该工作流提供本地多图像 3D 场景重建：

1. **WorldMirror 2.0 管线**：端到端运行统一的 WorldMirror 模型 —— 深度、法线、相机姿态、点云与 3D Gaussian Splatting 都从同一次前向输出中得到。
2. **一次调用，多种产出**：单次请求返回结果字典 —— Gaussian splats（`.ply`）、点云（`.ply`）、相机参数（JSON），以及可选的逐视角深度 / 法线图。通过 `return_*` 开关逐项启停。
3. **可选的相机 / 深度先验**：可注入已知的相机姿态（与 WorldMirror 自身 `camera_params.json` 相同模式的 JSON 文件）或逐视角深度图作为条件。先验是纯 conditioning 输入 —— 省略时模型仍可运行。
4. **鲁棒的过滤**：天空掩码（ONNX + 模型融合）、深度 / 法线不连续处的边缘过滤，以及基于置信度百分位的掩码，让点云与 Gaussian 保持整洁。
5. **点云与 Gaussian 压缩**：Voxel 合并加上可配置的下采样在不明显降低重建质量的前提下限制点数与 Gaussian 数量。
6. **自动模型管理**：WorldMirror 2.0 检查点会在首次运行时从 HuggingFace Hub 下载并缓存到本地。

## 准备

### 前置条件

- 已安装 model-compose 并可在 PATH 中调用。
- 支持 CUDA 的 GPU。峰值 VRAM 取决于目标分辨率与 `enable_bf16` 设置；在默认 952 像素目标下开启 bf16 时大约 **12-16 GB**，关闭时更多。目前不支持 Apple Silicon（MPS）与纯 CPU 推理 —— WorldMirror 的算子仅支持 CUDA。
- 装有 CUDA 工具链的 Linux 主机。首次运行会编译自定义 `gsplat` 变体和内置的 CUDA 扩展，仅有运行时并不足够。
- 一个能安装 `torch`、`gsplat`、`flash-attn` 以及 WorldMirror 附属包的 Python 环境 —— 首次运行会自动安装。
- 一个能访问 `tencent/HY-World-2.0` 仓库的 HuggingFace 访问令牌。启动 model-compose 前请通过 `HF_TOKEN` 环境变量设置。

### 本地 3D 重建的价值

与云端重建服务相比：

**本地处理的优点：**
- **隐私**：参考图像与重建后的几何不离开本机。
- **成本**：无按场景计费的 API 费用。
- **迭代性**：过滤阈值、压缩目标与产出选择可以每次调用自由调整。
- **易于组合**：可与其他 model-compose 任务组合（上游 image-background-removal、下游 file-store、用于 `.glb` 转换的 model-3d-converter 等），构建从拍摄到资产的完整管线。

**权衡：**
- **硬件门槛**：必须是 CUDA GPU，默认分辨率下大约需要 12 GB VRAM 作为舒适的基线。
- **首次运行成本**：管线会下载 WorldMirror 检查点并编译 CUDA 扩展 —— 第一次启动到控制器就绪需要数分钟。
- **许可**：WorldMirror 2.0 及其内部使用的各个模型都有各自的许可证。商业使用前请一并核对。

### 环境配置

1. 进入示例目录：
   ```bash
   cd examples/model-tasks/image-to-3d-world-mirror
   ```

2. 从模板复制 `.env` 并填入具有 `tencent/HY-World-2.0` 访问权限的 HuggingFace 令牌：
   ```bash
   cp .env.sample .env
   # 编辑 .env 并设置 HF_TOKEN=hf_xxx
   ```

3. 想以少量数值精度换取更低 VRAM，可在 `model-compose.yml` 中设置 `enable_bf16: true`。不需要的预测头可以通过 `disable_heads` 关闭（例如 `disable_heads: [normal]` 可释放约 200M 参数）。

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```
   > 首次启动会下载 WorldMirror 检查点并编译 CUDA 扩展。控制器就绪前可能需要数分钟。

2. **使用一组视角执行工作流：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "view0=@/path/to/view_00.png" \
     -F "view1=@/path/to/view_01.png" \
     -F "view2=@/path/to/view_02.png" \
     -F "view3=@/path/to/view_03.png" \
     -F 'input={"image": ["@view0", "@view1", "@view2", "@view3"]}'
   ```

   响应是包含所请求产出的 JSON 对象 —— Gaussian splats 与点云为 `.ply` 流，相机参数为内联 JSON 字典，若打开对应开关还会附带逐视角的深度 / 法线图像。

3. **复用上一次运行的相机**（与 WorldMirror 自身 `camera_params.json` 同模式，因此上一次调用返回的 JSON 可以直接送入下一次调用）：
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "view0=@/path/to/view_00.png" \
     -F "view1=@/path/to/view_01.png" \
     -F 'input={"image": ["@view0", "@view1"], "prior_cameras": "/path/to/camera_params.json"}'
   ```

4. **只需要几何时跳过大产出：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "view0=@/path/to/view_00.png" \
     -F "view1=@/path/to/view_01.png" \
     -F 'input={"image": ["@view0", "@view1"], "return_gaussians": false, "return_normal": false}'
   ```

## 配置参考

### 组件字段

| 字段            | 描述                                                                                                | 默认值               |
|-----------------|-----------------------------------------------------------------------------------------------------|----------------------|
| `task`          | 必须是 `image-to-3d`。                                                                              | —                    |
| `driver`        | 必须是 `custom`。                                                                                   | —                    |
| `family`        | 必须是 `world-mirror`。                                                                             | —                    |
| `model`         | WorldMirror 模型仓库（HuggingFace repo 或本地路径）。                                              | —                    |
| `subfolder`     | 仓库中放置 WorldMirror 检查点的子目录。                                                             | `HY-WorldMirror-2.0` |
| `device`        | 计算设备。需要解析为 `cuda` —— WorldMirror 不支持 CPU / MPS。                                       | `auto`               |
| `enable_bf16`   | 将模型转换为 bfloat16 以降低 VRAM（非关键层损失少量精度）。                                        | `false`              |
| `disable_heads` | 关闭并释放内存的预测头。可选值：`camera`、`depth`、`normal`、`points`、`gs`。                       | `[]`                 |

### 动作字段

| 字段                             | 描述                                                                                          | 默认值           |
|----------------------------------|-----------------------------------------------------------------------------------------------|------------------|
| `image`                          | 组成一个场景的图像路径 / URL 列表（或单个目录路径）。                                          | —                |
| `priors.cameras`                 | 可选相机先验 —— 匹配 WorldMirror `camera_params.json` 模式的 JSON 文件路径。                  | （无）           |
| `priors.depths`                  | 可选深度先验 —— 存放逐视角深度图（.npy / .exr / .png）的目录路径。                            | （无）           |
| `return_gaussians`               | 结果中包含 3D Gaussian Splatting `.ply`。                                                     | `true`           |
| `return_points`                  | 结果中包含基于深度的点云 `.ply`。                                                             | `true`           |
| `return_cameras`                 | 结果中以 JSON 字典的形式包含相机外参与内参。                                                   | `true`           |
| `return_depth`                   | 结果中包含逐视角深度图。                                                                       | `false`          |
| `return_normal`                  | 结果中包含逐视角表面法线图。                                                                   | `false`          |
| `params.target_size`             | 推理最大分辨率（长边）。图像会被缩放 + 中心裁剪对齐到 14 的倍数。                              | `952`            |
| `params.apply_sky_mask`          | 从点云与 Gaussian 中过滤天空区域。                                                             | `true`           |
| `params.apply_edge_mask`         | 过滤深度 / 法线不连续处附近的点。                                                              | `true`           |
| `params.apply_confidence_mask`   | 过滤置信度靠后的百分位点。                                                                     | `false`          |
| `params.sky_mask_source`         | 天空掩码来源：`auto`（ONNX + 模型融合）、`model`、`onnx`。                                     | `auto`           |
| `params.model_sky_threshold`     | 基于模型的天空检测阈值。                                                                       | `0.45`           |
| `params.confidence_percentile`   | 启用 `apply_confidence_mask` 时被剔除的靠后百分位。                                             | `10.0`           |
| `params.edge_normal_threshold`   | 法线边缘检测容差。                                                                             | `1.0`            |
| `params.edge_depth_threshold`    | 深度边缘检测相对容差。                                                                         | `0.03`           |
| `params.compress_pts`            | 通过 voxel 合并 + 下采样压缩基于深度的点云。                                                    | `true`           |
| `params.compress_pts_max_points` | 点云压缩后的最大点数。                                                                         | `2000000`        |
| `params.compress_pts_voxel_size` | 合并点使用的 voxel 大小。                                                                      | `0.002`          |
| `params.compress_gs_max_points`  | Voxel 剪枝后的最大 Gaussian 数。                                                               | `5000000`        |
| `params.max_resolution`          | 保存图像输出（深度 / 法线 PNG）的最大分辨率。                                                  | `1920`           |

## 注意事项

- **首次运行较慢**：首次启动会创建 `.venv/world-mirror` 隔离环境，安装 WorldMirror 的固定依赖，编译自定义 `gsplat` 变体，并下载 WorldMirror 检查点。控制器就绪前需要 10-20 分钟。后续运行会复用缓存的 venv 与产物。
- **隔离运行时**：模型 worker 运行在独立的 virtualenv（`runtime.type: virtualenv`，`path: .venv/world-mirror`）中，避免 WorldMirror 固定的 transformers / diffusers / cupy / open3d 版本与控制器的 site-packages 冲突。
- **必须使用 CUDA**：WorldMirror 硬编码了 CUDA 设备放置与 CUDA 专用算子；驱动在非 CUDA 主机上会拒绝加载。
- **不接受视频输入**：本示例只接受图像集合。若源为视频，请在上游用 `video-frame-extractor` 等组件先抽帧再喂入。
- **相机即数据**：`return_cameras: true` 会在响应中内联返回相机字典 —— 不会写任何文件。其模式与 WorldMirror 自身的 `camera_params.json` 相同，因此返回的字典可以用 `file-store` 组件保存，日后作为 `priors.cameras` 再次传入。
- **VRAM 规划**：`enable_bf16: true` 大约可将模型的激活内存减半；配合 `disable_heads` 是 12 GB 显卡上运行时的主要调整杠杆。24 GB 或更高显存下，默认配置即可从容运行。
- **输出使用**：`.ply` 文件可在 MeshLab、Blender（需插件）、CloudCompare 与大多数 Gaussian splatting 查看器中打开。深度 / 法线 PNG 是按输入顺序排列的逐视角图像。

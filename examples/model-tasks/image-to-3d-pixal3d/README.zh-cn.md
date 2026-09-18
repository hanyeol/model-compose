# 图像转 3D 模型任务示例

本示例展示如何通过 model-compose 内置的 image-to-3d 任务，使用 Pixal3D 从单张图像生成带纹理的 GLB 网格。

## 概述

该工作流提供本地单图 3D 资产生成：

1. **本地 Pixal3D 管线**：端到端运行 Pixal3D 的 sparse-structure / shape / texture flow-matching 各阶段，无需外部 API。
2. **自动相机估计**：MoGe-2 深度模型会自动估计输入图像的相机 FOV；若自动估计效果不理想，可以手动设置 `manual_fov`（弧度）。
3. **PBR 纹理**：生成的 GLB 携带烘焙好的 base colour / metallic / roughness 贴图 —— 可直接用于 glTF 查看器、Blender、Unreal 或任何支持 PBR 的渲染器。
4. **可调细节**：`resolution`（1024 或 1536）、`max_num_tokens` 与各阶段采样步数在网格细节、纹理保真度、VRAM / 时间之间进行权衡。
5. **自动模型管理**：Pixal3D 权重、MoGe-2 深度模型以及 DINOv3 条件权重都会在首次运行时从 HuggingFace Hub 下载并缓存到本地。

## 准备

### 前置条件

- 已安装 model-compose 并可在 PATH 中调用。
- 支持 CUDA 的 GPU。在 1536 分辨率下峰值 VRAM 约 **18 GB**，若使用 `low_vram: true` + 1024 分辨率则约 **10-12 GB**。Apple Silicon（MPS）和纯 CPU 推理不受支持 —— Pixal3D 的算子只支持 CUDA。
- 装有 CUDA 工具链的 Linux 主机。首次运行会用 nvcc 编译 neighborhood attention 算子（natten），仅有运行时并不足够。
- 一个能安装 `torch`、`natten` 以及 Pixal3D 附属包的 Python 环境 —— 首次运行会自动安装。

### 本地图像转 3D 的价值

与云端 3D 生成服务相比：

**本地处理的优点：**
- **隐私**：参考图像与生成资产不离开本机。
- **成本**：无每次生成的 API 费用。
- **迭代性**：采样步数、纹理尺寸和相机 FOV 可以每次调用自由调整。
- **易于组合**：可与其他 model-compose 任务组合（上游 image-background-removal、下游 file-store），构建端到端 3D 资产管线。

**权衡：**
- **硬件门槛**：必须是 CUDA GPU。`low_vram: true` 下至少 10 GB VRAM，完整模式需要 18 GB 以上。
- **首次运行成本**：管线会下载约 15 GB 权重并编译 CUDA 算子 —— 第一次启动到控制器就绪需要数分钟。
- **许可**：Pixal3D 及其内部使用的各个模型都有各自的许可证。商业使用前请一并核对。

### 环境配置

1. 进入示例目录：
   ```bash
   cd examples/model-tasks/image-to-3d-pixal3d
   ```

2. 无需额外环境配置 —— Pixal3D 检查点（`TencentARC/Pixal3D`）、MoGe-2 深度模型（`Ruicheng/moge-2-vitl`）以及 DINOv3 条件权重（`camenduru/dinov3-vitl16-pretrain-lvd1689m`）会在首次运行时从 HuggingFace Hub 下载并缓存到 `~/.cache/huggingface/`。

3. 想以推理速度换取更低 VRAM，可在 `model-compose.yml` 中设置 `low_vram: true`。想以纹理保真度换取速度，可设置 `resolution: 1024`。

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```
   > 首次启动会下载约 15 GB 权重并编译 CUDA 算子。控制器就绪前可能需要数分钟。

2. **执行工作流：**

   **使用 API：**
   ```bash
   # 最小调用 —— 用默认参数从图像生成 GLB
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.png" \
     -F 'input={"image": "@img"}' \
     -o output.glb

   # 固定种子实现可复现采样
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.png" \
     -F 'input={"image": "@img", "seed": 42}' \
     -o output.glb

   # 对 MoGe 判断有误的图像手动指定相机 FOV（0.2 弧度 ≈ 11.5°，窄镜头）
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.png" \
     -F 'input={"image": "@img", "manual_fov": 0.2}' \
     -o output.glb

   # 更高保真的纹理（8K 烘焙）+ 每阶段更多采样步数
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.png" \
     -F 'input={"image": "@img", "texture_size": 8192, "shape_slat_sampling_steps": 24, "tex_slat_sampling_steps": 24}' \
     -o output.glb
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 上传 `image`（干净背景的主体效果最好 —— Pixal3D 会自动去背景，但复杂背景仍可能影响姿态估计）
   - 可选地设置 `seed` 以保证可复现，或在自动相机估计不理想时设置 `manual_fov`
   - 点击 "Run Workflow" 获取 `.glb` 文件

## 配置参考

### 组件字段

| 字段         | 描述                                                                                                    | 默认值           |
|--------------|---------------------------------------------------------------------------------------------------------|------------------|
| `task`       | 必须是 `image-to-3d`。                                                                                  | —                |
| `driver`     | 必须是 `custom`。                                                                                       | —                |
| `family`     | 必须是 `pixal3d`。                                                                                      | —                |
| `model`      | Pixal3D 模型仓库（HuggingFace repo 或本地路径）。                                                       | —                |
| `device`     | 计算设备。需要解析为 `cuda` —— Pixal3D 不支持 CPU / MPS。                                               | `auto`           |
| `low_vram`   | 各阶段模型保留在 CPU，运行时按需迁到 GPU。将峰值 VRAM 降低到约 10-12 GB。                                | `false`          |
| `resolution` | 管线网格分辨率（`1024` 或 `1536`）。未设置时 low-VRAM 模式默认 `1024`，否则默认 `1536`。                 | （见描述）        |

### 动作字段

| 字段                                  | 描述                                                                          | 默认值           |
|---------------------------------------|-------------------------------------------------------------------------------|------------------|
| `image`                               | 输入图像（或图像列表 / 流）。                                                 | —                |
| `seed`                                | 可复现的随机种子。未设置时每次调用产生新样本。                                | （无）           |
| `batch_size`                          | 输入为列表 / 流时的批处理大小。                                               | `1`              |
| `params.manual_fov`                   | 相机 FOV（弧度）。未设置时由 MoGe-2 自动估计。                                | （自动估计）      |
| `params.mesh_scale`                   | 用于相机距离计算的目标网格尺度。                                              | `1.0`            |
| `params.image_resolution`             | 相机估计期间使用的工作分辨率。                                                | `512`            |
| `params.ss_sampling_steps`            | Sparse-structure 扩散采样步数（粗体素布局）。                                 | `12`             |
| `params.ss_guidance_strength`         | Sparse-structure classifier-free guidance 强度。                              | `7.5`            |
| `params.ss_guidance_rescale`          | Sparse-structure guidance rescale 系数。                                      | `0.7`            |
| `params.ss_rescale_t`                 | Sparse-structure 时间步 rescale 系数。                                        | `5.0`            |
| `params.shape_slat_sampling_steps`    | 形状 latent 采样步数（几何细化）。                                            | `12`             |
| `params.shape_slat_guidance_strength` | 形状 latent classifier-free guidance 强度。                                   | `7.5`            |
| `params.shape_slat_guidance_rescale`  | 形状 latent guidance rescale 系数。                                           | `0.5`            |
| `params.shape_slat_rescale_t`         | 形状 latent 时间步 rescale 系数。                                             | `3.0`            |
| `params.tex_slat_sampling_steps`      | 纹理 latent 采样步数（PBR colour / metallic / roughness）。                    | `12`             |
| `params.tex_slat_guidance_strength`   | 纹理 latent classifier-free guidance 强度。                                   | `1.0`            |
| `params.tex_slat_guidance_rescale`    | 纹理 latent guidance rescale 系数。                                           | `0.0`            |
| `params.tex_slat_rescale_t`           | 纹理 latent 时间步 rescale 系数。                                             | `3.0`            |
| `params.max_num_tokens`               | 每阶段最大 sparse token 数。数值越大几何越精细，VRAM 越高。                    | `49152`          |
| `params.texture_size`                 | 导出 GLB 时烘焙纹理分辨率（像素）。                                            | `4096`           |
| `params.decimation_target`            | 导出 GLB 前进行网格 decimation 的目标面数。                                    | `1000000`        |

## 注意事项

- **首次运行较慢**：首次启动会下载约 15 GB 权重并编译 neighborhood attention CUDA 算子（natten）。后续运行会复用缓存。
- **必须使用 CUDA**：Pixal3D 硬编码了 CUDA 设备放置与 CUDA 专用算子；驱动在非 CUDA 主机上会直接拒绝加载，而不是沉默地回退到损坏的路径。
- **VRAM 规划**：`low_vram: true` 用延迟（约 2-3 倍慢）换取更低峰值 VRAM（约 10-12 GB）。`resolution: 1536` 标准模式的峰值 VRAM 约为 18 GB，A100 40GB 或 RTX 6000 Ada 可轻松运行。
- **相机 FOV**：若自动估计的透视看起来失真（主体过度拉伸或压扁），设置 `manual_fov`。从 `0.2`（窄镜头，约 11.5°）开始，每次调整约 `0.05`。
- **背景鲁棒性**：Pixal3D 在预处理阶段会自动去背景，但如果主体贴到画框或严重遮挡，几何仍可能扭曲。若自动预处理不干净，可在上游加入 `image-background-removal`。
- **采样器调参**：默认每阶段 12 步在质量与速度间较为平衡。对最终交付资产建议将 shape / texture 阶段步数提高到 24；sparse-structure 阶段的增益相对较小。
- **输出**：每个输入返回一个 `.glb` 文件（批量输入返回列表）。可以直接被任何兼容 glTF 的查看器（`<model-viewer>`、Blender、three.js、Unity 的 glTFast 等）打开。

# 多视角图像转 3D 模型任务示例

本示例展示如何通过 model-compose 内置的 image-to-3d 任务，使用 Pixal3D 的 MV 分支从带姿态的多视角图像装配生成带纹理的 GLB 网格。

## 概述

单视角 Pixal3D 管线需要用 MoGe-2 猜测输入图像的相机，而多视角版本一次接受同一对象的多张带姿态视图。给定每个视角的 `transform_matrix` 与 `camera_angle_x`，管线会在其级联去噪器内融合各视角，输出一个高保真的 GLB。

该工作流提供本地多视角 3D 资产生成：

1. **Pixal3D MV 管线**：从与单视角 Pixal3D 相同的 HuggingFace 仓库中通过 `pipeline_mv.json` 加载 `ckpts/*_mv` 检查点。
2. **带姿态的视角**：每个输入视角都带有一张图像和一个 4x4 camera-to-world 矩阵（NeRF/Blender 惯例：Z-up 世界坐标，相机看 -Z 方向，其自身 +Y 为上方）。Frame 0 必须是 canonical front view（相机位于 `(0, -d, 0)`，看向原点，世界 +Z 为上）；否则生成的网格会以该视角的坐标系为准而旋转。
3. **自动抠图**：没有 alpha 通道的视角会使用与单视角路径相同的 `briaai/RMBG-2.0` 模型进行抠图。已有非全不透明 alpha 通道的视角则原样使用。
4. **PBR 纹理**：生成的 GLB 携带烘焙好的 base colour、metallic、roughness 贴图。
5. **可调细节**：`resolution`（1024 或 1536）、`max_num_tokens` 与各阶段采样步数在网格细节、纹理保真度、VRAM / 时间之间进行权衡。

## 准备

### 前置条件

- 已安装 model-compose 并可在 PATH 中调用。
- 支持 CUDA 的 GPU。VRAM 需求与单视角 Pixal3D 相同（1536 下约 18 GB，`low_vram: true` + 1024 下约 10-12 GB）。
- 装有 CUDA 工具链的 Linux 主机。
- 已接受受门控的 `briaai/RMBG-2.0` 模型条款的 HuggingFace 访问令牌（Pixal3D 的 rembg 步骤需要）。通过 `HF_TOKEN` 环境变量设置。

### 输入格式

动作需要两个平行数组加上一个共享 FOV：

- **`image`**：视角图像列表。第 `i` 个元素是第 `i` 个视角的图像。
- **`transform_matrix`**：与 `image` 平行的 4x4 camera-to-world 矩阵列表。
- **`camera_angle_x`**：水平 FOV（弧度）。所有视角共享的单个标量，或与 `image` 长度相同的每视角列表。
- **`mesh_scale`**：用于相机距离归一化的全局网格尺度。默认 `1.0`。

若视角按照 Pixal3D 附带的数据集惯例渲染（眼位环绕、方位角 0°/90°/180°/270°、仰角 0°、20° FOV），transform 如下：

```yaml
camera_angle_x: 0.349
transform_matrix:
  - [[ 1.0,  0.0,  0.0,  0.0],
     [ 0.0,  0.0, -1.0, -3.1192],
     [ 0.0,  1.0,  0.0,  0.0],
     [ 0.0,  0.0,  0.0,  1.0]]
  - [[ 0.0,  0.0,  1.0,  3.1192],
     [ 1.0,  0.0,  0.0,  0.0],
     [ 0.0,  1.0,  0.0,  0.0],
     [ 0.0,  0.0,  0.0,  1.0]]
  - [[-1.0,  0.0,  0.0,  0.0],
     [ 0.0,  0.0,  1.0,  3.1192],
     [ 0.0,  1.0,  0.0,  0.0],
     [ 0.0,  0.0,  0.0,  1.0]]
  - [[ 0.0,  0.0, -1.0, -3.1192],
     [-1.0,  0.0,  0.0,  0.0],
     [ 0.0,  1.0,  0.0,  0.0],
     [ 0.0,  0.0,  0.0,  1.0]]
```

### 环境配置

1. 进入示例目录：
   ```bash
   cd examples/model-tasks/image-to-3d-pixal3d-mv
   ```

2. 在 https://huggingface.co/briaai/RMBG-2.0 接受 `briaai/RMBG-2.0` 的许可，然后从模板复制 `.env` 并填入具有访问权限的 HuggingFace 令牌：
   ```bash
   cp .env.sample .env
   # 编辑 .env 并设置 HF_TOKEN=hf_xxx
   ```

3. 想以推理速度换取更低 VRAM，可在 `model-compose.yml` 中设置 `low_vram: true`。想以纹理保真度换取速度，可设置 `resolution: 1024`。

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```
   > 首次启动会下载 Pixal3D 检查点（包含 MV 分支）并编译 CUDA 算子。控制器就绪前可能需要数分钟。

2. **使用四个环绕视角执行工作流：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "front=@/path/to/front.png" \
     -F "right=@/path/to/right.png" \
     -F "back=@/path/to/back.png" \
     -F "left=@/path/to/left.png" \
     -F 'input={
       "image": ["@front", "@right", "@back", "@left"],
       "transform_matrix": [
         [[1,0,0,0],[0,0,-1,-3.1192],[0,1,0,0],[0,0,0,1]],
         [[0,0,1,3.1192],[1,0,0,0],[0,1,0,0],[0,0,0,1]],
         [[-1,0,0,0],[0,0,1,3.1192],[0,1,0,0],[0,0,0,1]],
         [[0,0,-1,-3.1192],[-1,0,0,0],[0,1,0,0],[0,0,0,1]]
       ],
       "camera_angle_x": 0.349
     }' \
     -o output.glb
   ```

## 配置参考

### 组件字段

| 字段         | 描述                                                                                                     | 默认值            |
|--------------|----------------------------------------------------------------------------------------------------------|-------------------|
| `task`       | 必须是 `image-to-3d`。                                                                                   | —                 |
| `driver`     | 必须是 `custom`。                                                                                        | —                 |
| `family`     | 必须是 `pixal3d-mv`。                                                                                    | —                 |
| `model`      | Pixal3D 模型仓库（HuggingFace repo 或本地路径）。                                                        | —                 |
| `device`     | 计算设备。需要解析为 `cuda` —— Pixal3D 不支持 CPU / MPS。                                                | `auto`            |
| `low_vram`   | 各阶段模型保留在 CPU，运行时按需迁到 GPU。                                                               | `false`           |
| `resolution` | 管线网格分辨率（`1024` 或 `1536`）。                                                                     | （见描述）        |

### 动作字段

| 字段                                  | 描述                                                                          | 默认值           |
|---------------------------------------|-------------------------------------------------------------------------------|------------------|
| `image`                               | 视角图像列表。第 0 个元素必须是 canonical front view。                        | —                |
| `transform_matrix`                    | 与 `image` 平行的 4x4 camera-to-world 矩阵列表。                              | —                |
| `camera_angle_x`                      | 水平 FOV（弧度）。标量（共享）或每视角列表。                                  | —                |
| `mesh_scale`                          | 用于相机距离归一化的全局网格尺度。                                            | `1.0`            |
| `seed`                                | 可复现的随机种子。未设置时每次调用产生新样本。                                | （无）           |
| `params.image_resolution`             | 预处理期间使用的工作分辨率。                                                  | `512`            |
| `params.ss_sampling_steps`            | Sparse-structure 扩散采样步数。                                               | `12`             |
| `params.ss_guidance_strength`         | Sparse-structure classifier-free guidance 强度。                              | `7.5`            |
| `params.ss_guidance_rescale`          | Sparse-structure guidance rescale 系数。                                      | `0.7`            |
| `params.ss_rescale_t`                 | Sparse-structure 时间步 rescale 系数。                                        | `5.0`            |
| `params.shape_slat_sampling_steps`    | 形状 latent 采样步数。                                                        | `12`             |
| `params.shape_slat_guidance_strength` | 形状 latent classifier-free guidance 强度。                                   | `7.5`            |
| `params.shape_slat_guidance_rescale`  | 形状 latent guidance rescale 系数。                                           | `0.5`            |
| `params.shape_slat_rescale_t`         | 形状 latent 时间步 rescale 系数。                                             | `3.0`            |
| `params.tex_slat_sampling_steps`      | 纹理 latent 采样步数。                                                        | `12`             |
| `params.tex_slat_guidance_strength`   | 纹理 latent classifier-free guidance 强度。                                   | `1.0`            |
| `params.tex_slat_guidance_rescale`    | 纹理 latent guidance rescale 系数。                                           | `0.0`            |
| `params.tex_slat_rescale_t`           | 纹理 latent 时间步 rescale 系数。                                             | `3.0`            |
| `params.max_num_tokens`               | 每阶段最大 sparse token 数。                                                  | `49152`          |
| `params.texture_size`                 | 烘焙纹理分辨率（像素）。                                                      | `4096`           |
| `params.decimation_target`            | 导出 GLB 前进行网格 decimation 的目标面数。                                    | `1000000`        |

## 注意事项

- **Frame 0 为主视角**：管线通过 `calc_mat_i = F @ inv(C_0) @ C_i` 将其他视角对齐到 canonical front pose。若 Frame 0 本身不是 canonical front view，整个装配相对于对象会发生旋转，生成的网格坐标系将与模型训练时不同。
- **`transform_matrix` 与 `image` 长度必须相同**：DSL validator 会强制这一点。`camera_angle_x` 也必须是标量或与之等长的列表。
- **距离从矩阵 translation 派生**：管线用 `‖transform_matrix[:, :3, 3]‖` 计算 `camera_distance`；不存在需要单独维护的 `distance` 字段。
- **坐标惯例**：NeRF/Blender —— Z-up 世界，每台相机沿自身 -Z 观察，其自身 +Y 为上。与训练渲染相同的惯例，因此数据集 `transforms.json` 可 1:1 映射到本动作。
- **Alpha 作为掩码**：已有非全不透明 alpha 通道的视角跳过 rembg 步骤。完全不透明或缺失 alpha 时会触发 `briaai/RMBG-2.0` 自动分割。
- **首次运行较慢**：与单视角 Pixal3D 相同的安装成本 —— 隔离 virtualenv 使用独立的 `.venv/pixal3d-mv` 目录，但仍安装相同的固定依赖与 CUDA 扩展。

# 图像转 3D 高斯泼溅示例

本示例展示如何通过 model-compose 内置的 `image-to-3d` 任务，使用 **TripoSplat**（由 TripoAI 开发）将单张图像转换为 3D 高斯泼溅（Gaussian Splat）。

## 概述

TripoSplat 从一张 2D 图像生成 3D 高斯泼溅资产（`.ply` 或 `.splat`）。与基于网格的 image-to-3D 模型不同，输出是一组有向高斯点云，在浏览器端查看器（SparkJS、SuperSplat、Three.js）中渲染干净，也便于组合进交互式场景。

该工作流提供：

1. **本地单图高斯泼溅生成**：flow-matching 管线 + VAE 解码器端到端运行，无需外部 API。
2. **可变高斯数量**：`num_gaussians` 可在 `[32768, 262144]` 范围（自动四舍五入到 32 的倍数）内任意选择，权衡视觉质量与渲染和存储开销。
3. **内置背景移除**：BiRefNet 作为管线的一部分加载，复杂背景在 flow 模型处理之前就被自动去除。
4. **双输出格式**：导出 `.ply`（通用高斯查看器输入）或 `.splat`（浏览器查看器偏好的紧凑二进制）。
5. **自动模型管理**：`VAST-AI/TripoSplat`（约 5 GB，分布在 `diffusion_models/`、`vae/`、`clip_vision/`、`background_removal/` 的 5 个 safetensors 文件）会在首次运行时下载并缓存到本地。

## 准备

### 前置条件

- 已安装 model-compose 并可在 PATH 中调用。
- 支持 CUDA 的 GPU。管线以 bfloat16 / float16 加载权重，不支持 CPU 和 MPS（Apple Silicon）。
- 一个能安装 `torch`、`torchvision`、`numpy`、`safetensors`、`pillow`、`tqdm` 的 Python 环境 —— 首次运行会自动安装到隔离的 `.venv/triposplat`。不需要 transformers、diffusers、flash-attn 或 spconv。
- 不需要 HuggingFace 令牌 —— `VAST-AI/TripoSplat` 是公开仓库。

### 许可

TripoSplat 代码与权重以 **MIT License** 发布，可直接用于商业用途而无需额外通知。完整条款请参见 [upstream LICENSE](https://github.com/VAST-AI-Research/TripoSplat/blob/main/LICENSE)。

### 为什么用高斯泼溅

与基于网格的 image-to-3D 输出相比：

- **浏览器端渲染快**：纯点云栅格化 —— 无三角形装配、无 UV 烘焙、无 PBR 着色管线。
- **视觉保真度高**：能很好地捕捉网格难以表达的柔和轮廓、头发、植物、半透明表面。
- **不是网格的替代品**：游戏引擎、DCC 工具、物理管线仍需要网格。对于 web 查看器、AR/VR、可视化，使用 TripoSplat；需要 GLB 时，使用 Pixal3D / AniGen / Hi3D。

### 环境配置

1. 进入示例目录：
   ```bash
   cd examples/model-tasks/image-to-3d-triposplat
   ```

2. （可选）若你的 HuggingFace 账号受频率限制，设置 `HF_TOKEN`：
   ```bash
   export HF_TOKEN=hf_xxx
   ```

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```
   > 首次启动会创建 `.venv/triposplat`，安装最小依赖集，克隆 TripoSplat 推理代码（约 2k LOC，两个 Python 文件），并下载约 5 GB 权重。控制器就绪前需要数分钟。后续运行会复用缓存的 venv 和产物。

2. **执行工作流：**

   **使用 API：**
   ```bash
   # 最小调用 —— 用默认设置生成 .ply 泼溅
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.webp" \
     -F 'input={"image": "@img"}' \
     -o output.ply

   # 固定种子，实现可复现采样
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.webp" \
     -F 'input={"image": "@img", "seed": 42}' \
     -o output.ply

   # 降低高斯数量以加快浏览器端渲染
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.webp" \
     -F 'input={"image": "@img", "num_gaussians": 65536}' \
     -o output.ply

   # 导出为 Three.js 友好的紧凑二进制 .splat
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.webp" \
     -F 'input={"image": "@img", "format": "splat"}' \
     -o output.splat
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 上传 `image`（背景不限 —— BiRefNet 会移除）
   - 可选设置 `seed`、`num_gaussians`（32768 / 65536 / 131072 / 262144）、`format`（`ply` / `splat`）
   - 点击 "Run Workflow"，即可取回泼溅文件

3. **查看结果**：将 `.ply` 或 `.splat` 文件拖入 [SparkJS](https://sparkjs.dev) 或 [SuperSplat](https://superspl.at/editor)，或在 Three.js 场景中用 `@mkkellogg/gaussian-splats-3d` 加载。

## 配置参考

### 组件字段

| 字段     | 说明                                                                        | 默认值  |
|----------|-----------------------------------------------------------------------------|---------|
| `task`   | 必须为 `image-to-3d`。                                                      | —       |
| `driver` | 必须为 `custom`。                                                           | —       |
| `family` | 必须为 `triposplat`。                                                       | —       |
| `model`  | TripoSplat 模型仓库（HuggingFace 仓库或本地路径）。                         | —       |
| `device` | 计算设备。必须解析为 `cuda` —— 仅支持 bfloat16 / fp16 权重。                | `auto`  |

### 动作字段

| 字段                   | 说明                                                                                        | 默认值     |
|------------------------|---------------------------------------------------------------------------------------------|------------|
| `image`                | 输入图像（单张、列表或流）。                                                                | —          |
| `seed`                 | 可复现采样所用的随机种子。                                                                  | `42`       |
| `batch_size`           | 当输入为列表或流时，每批处理的条目数。                                                      | `1`        |
| `format`               | 输出格式：`ply` 或 `splat`。                                                                | `ply`      |
| `params.steps`         | flow-matching 采样器步数。推荐 10-20。                                                      | `20`       |
| `params.guidance_scale`| 无分类器引导强度。`<= 1.0` 禁用 CFG。推荐 3.0。                                             | `3.0`      |
| `params.shift`         | flow-matching 时间步调度 shift。`1.0` 为均匀，更高则向前段加权。                            | `3.0`      |
| `params.num_gaussians` | 目标高斯数量。取值范围 `[32768, 262144]`，四舍五入到 32 的倍数。                            | `262144`   |
| `params.erode_radius`  | 背景移除后 alpha 蒙版的腐蚀半径。`0` 禁用，`1` 为 3x3 最小值滤波。                          | `1`        |

## 说明

- **最小依赖**：TripoSplat 刻意避开 `transformers`、`diffusers`、`flash-attn` 和 `spconv`。首次安装比其他 image-to-3d 管线（pixal3d、anigen、hi3d）明显更快。
- **非 pip 包**：upstream 以无 `setup.py` 或 `pyproject.toml` 的 top-level 文件 `triposplat.py` 和 `model.py` 发布。驱动将它们复制到 `mindor` 旁作为 `triposplat_pipeline/` 包，并把内部的 `from model import ...` 重写为 `from triposplat_pipeline.model import ...`。
- **隔离运行时**：模型工作进程运行在 `.venv/triposplat`，使 TripoSplat 的 torch 构建不会与控制器的 site-packages 冲突。
- **必须有 CUDA**：DINOv3·VAE 编码器以 bfloat16，BiRefNet·flow 模型·解码器以 float16 加载。无 CPU·MPS 路径。
- **高斯数量粒度**：`num_gaussians` 会被四舍五入到解码器 `gaussians_per_point`（通常为 32）的最近倍数。驱动按原样传递用户值，TripoSplat 会打印实际使用的数量。
- **结果查看**：`.ply` 是最通用的高斯泼溅格式，`.splat` 是 Three.js 偏好的紧凑二进制。两者都无法在 Blender 或 Unity glTFast 中打开 —— 它们期待网格而非高斯。
- **输出**：每个输入返回一个 `.ply` 或 `.splat` 文件（批量输入返回列表）。

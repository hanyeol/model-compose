# 图像转 3D 网格精修示例

本示例展示如何通过 model-compose 内置的 `image-to-3d` 任务，使用 **Hi3D v1.0**（基于 Sparc3D）将粗略的 3D 网格精修为高分辨率几何体。

## 概述

Hi3D v1.0 不是生成模型，而是**精修**（refinement）模型。每次请求都需要同时提供参考图像和上游生成的输入网格，Hi3D 会根据图像轮廓精修几何形状。输出只包含几何体的 GLB（无纹理、材质或顶点色）。

该工作流提供：

1. **参考图像条件精修**：flow-matching 栈将输入网格升级到 1024³（或 1536³）稀疏提取网格，通过 DINOv2 + CLIP 特征对齐到参考图像。
2. **输入网格来源自由**：任何 trimesh 可读的格式都可用（GLB、OBJ、PLY、STL）。由任意上游 image-to-3d 组件（`pixal3d`、`world-mirror`、Hunyuan3D-2 mini 等）生成的网格都可直接连接。
3. **自动模型管理**：Hi3D 检查点（`hi3d-official/Hi3Dv1.0`）会在首次运行时从 HuggingFace Hub 下载；DINOv2 与 CLIP 由管线在首次使用时一并获取。

## 准备

### 前置条件

- 已安装 model-compose 并可在 PATH 中调用。
- compute capability **8.0 以上**（Ampere 及以后）的 CUDA GPU。不支持 CPU、MPS（Apple Silicon）、AMD ROCm —— Hi3D 的 spconv / flash-attention 算子只支持 CUDA。
- 已安装 **CUDA 工具链 12.0–12.5** 的 Linux 主机。管线会用本地 nvcc 构建 spconv 和 flash-attn，CUDA 版本不匹配会在安装阶段失败。
- 能够安装 `torch==2.5.0`、`flash-attn==2.7.4.post1`、`spconv-cu120==2.3.6` 以及 Hi3D 的 `sparc3d` 包的 Python 环境 —— 首次运行时会自动安装到隔离的 `.venv/hi3d`。
- 上游组件提供输入网格。请参考下方的[生成输入网格](#生成输入网格)小节。

### 许可

Hi3D v1.0 并非在 Apache 或 MIT 协议下发布，而是 **Hi3D Open License Agreement v1.0**。商业使用允许，但若产品**月活跃用户超过 20 万**或**月营收超过 100 万美元**，需要申请单独许可。发布前请在 [Hi3D v1.0 仓库](https://github.com/hi3d-official/Hi3Dv1.0)核对条款。

### 生成输入网格

Hi3D 只精修、不生成。请将任意 image-to-3d 结果连接到 `mesh` 输入：

- **`image-to-3d-pixal3d`** —— 生成约 1k 面的 PBR GLB，直接传入其 `.glb` 输出即可。
- **`image-to-3d-world-mirror`** —— 适用于场景 / 环境；可直接使用其 `points.ply`，或通过转换器提取网格。
- **Hunyuan3D-2 mini** —— Hi3D 官方管线推荐的上游。可以作为独立 model-compose 组件移植，或手动运行 Hi3D 仓库中的 `demo/coarse_stage.py`。

输入网格无需干净或 watertight —— 只要轮廓大致匹配参考图像，Hi3D 的精修就能吸收相当多的拓扑瑕疵。

### 环境配置

1. 进入示例目录：
   ```bash
   cd examples/model-tasks/image-to-3d-hi3d
   ```

2. （可选）如果你的 HuggingFace 账号受频率限制，设置 `HF_TOKEN`：
   ```bash
   export HF_TOKEN=hf_xxx
   ```
   `hi3d-official/Hi3Dv1.0`、`facebook/dinov2-large`、`openai/clip-vit-large-patch14` 都是公开仓库，因此令牌并非必须。

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```
   > 首次启动会创建 `.venv/hi3d`，安装 Hi3D 的固定依赖，使用本地 CUDA 工具链构建 spconv / flash-attn，并下载 Hi3D 检查点加上 DINOv2 / CLIP（合计 ~10 GB）。控制器就绪前需要 10-20 分钟。

2. **执行工作流：**

   **使用 API：**
   ```bash
   # 最小调用 —— 用参考图像精修输入网格
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/reference.png" \
     -F "src=@/path/to/coarse.glb" \
     -F 'input={"image": "@img", "mesh": "@src"}' \
     -o refined.glb

   # 固定种子，实现可复现的精修
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/reference.png" \
     -F "src=@/path/to/coarse.glb" \
     -F 'input={"image": "@img", "mesh": "@src", "seed": 0}' \
     -o refined.glb

   # 高分辨率精修（1536 网格）—— 几何更锐利、VRAM 更多
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/reference.png" \
     -F "src=@/path/to/coarse.glb" \
     -F 'input={"image": "@img", "mesh": "@src", "resolution": 1536}' \
     -o refined.glb
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 上传参考 `image` 与 `mesh`（GLB / OBJ / PLY / STL）
   - 可选设置 `seed`、`resolution`（512 / 1024 / 1536）、`num_inference_steps`
   - 点击 "Run Workflow"，即可取回精修后的 `.glb` 文件

## 配置参考

### 组件字段

| 字段     | 说明                                                                | 默认值  |
|----------|---------------------------------------------------------------------|---------|
| `task`   | 必须为 `image-to-3d`。                                              | —       |
| `driver` | 必须为 `custom`。                                                   | —       |
| `family` | 必须为 `hi3d`。                                                     | —       |
| `model`  | Hi3D v1.0 模型仓库（HuggingFace 仓库或本地路径）。                  | —       |
| `device` | 计算设备。必须解析为 `cuda` —— Hi3D 不支持 CPU 或 MPS。             | `auto`  |

### 动作字段

| 字段                        | 说明                                                                                          | 默认值  |
|-----------------------------|-----------------------------------------------------------------------------------------------|---------|
| `image`                     | 参考图像（单张、列表或流）。                                                                  | —       |
| `mesh`                      | 待精修的输入网格（任意 trimesh 可读格式：GLB、OBJ、PLY、STL）。                               | —       |
| `seed`                      | 可复现精修所用的随机种子。                                                                    | `0`     |
| `batch_size`                | 当输入为列表或流时，每批处理的条目数。                                                        | `1`     |
| `params.resolution`         | 稀疏提取网格分辨率。取值之一：`512`、`1024`、`1536`。                                         | `1024`  |
| `params.num_inference_steps`| flow-matching 精修步数。                                                                      | `25`    |

## 说明

- **仅精修**：Hi3D 不接受仅图像输入。省略 `mesh` 会在请求时直接触发验证错误，而不是在生成过程中静默返回坏网格。
- **仅几何输出**：结果 GLB 只包含顶点位置与面；不生成纹理、法线、材质、顶点色。如有需要，请用上游纹理化管线补足。
- **首次运行较慢**：首次启动需 10-20 分钟来准备 venv、构建扩展（spconv、flash-attn）并下载权重。后续运行会复用缓存的 venv 和产物。
- **隔离运行时**：模型工作进程运行在 `.venv/hi3d`，使 Hi3D 的固定版本（`torch==2.5.0`、`flash-attn==2.7.4.post1`、`spconv-cu120==2.3.6`）不会与控制器的 site-packages 冲突。驱动在控制器环境中拒绝运行。
- **必须有 CUDA**：Hi3D 硬编码 CUDA 设备分配，并依赖针对 CUDA 12.0–12.5 编译的 spconv 算子。在非 CUDA 环境下，驱动会在加载时显式失败，而不是进入错误路径。
- **输入网格对齐**：Hi3D 精修的上限取决于输入网格与参考图像轮廓的匹配程度。如果输入错位（宽高比错误、朝向错误），结果也会保留该错位。精修前请先核对输入网格与参考图像的对齐。
- **VRAM**：`resolution: 1024` 的峰值 VRAM 约 20 GB，`1536` 接近 30 GB。24 GB 消费级显卡适合 1024 路径，1536 建议 A100 40GB 或 RTX 6000 Ada 级别。
- **输出**：每个输入返回一个 `.glb` 文件（批量输入返回列表）。可直接在 Blender、three.js、Unity glTFast 等任何 glTF 兼容查看器中加载。

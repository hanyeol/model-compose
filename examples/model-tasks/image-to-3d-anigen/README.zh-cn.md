# 图像转绑定 3D 模型任务示例

本示例演示如何通过 model-compose 内置的 image-to-3d 任务,使用 AniGen 从一张图像同时生成一个已绑定骨骼与蒙皮权重的 GLB 网格,以及一个仅可视化骨架的独立 GLB。

## 概述

此工作流提供本地单图像可动画 3D 资产生成:

1. **本地 AniGen 管线**: 端到端运行 AniGen 的 sparse-structure 与 structured-latent flow-matching 阶段 — 无外部 API。
2. **绑定网格**: 输出 GLB 内嵌骨骼、层级父级关系、逐顶点蒙皮权重,作为标准 glTF skinned-mesh — 直接放入 Blender、Unity、Unreal 或 three.js,使用任意动作片段驱动。
3. **骨架可视化**: 第二个 GLB 将预测的骨架渲染为可见骨骼 — 在确定绑定网格之前用于调试关节位置。
4. **可配置采样**: 逐阶段的 CFG 缩放、采样步数、关节密度、纹理尺寸,在绑定精度、网格细节、显存 / 时间之间灵活权衡。
5. **自动模型管理**: AniGen 权重(SS-Flow + SLAT-Flow + DAE + DINOv2 + DSINE + VGG)首次运行时从 HuggingFace Hub 下载并本地缓存。

## 准备

### 先决条件

- 已安装 model-compose 并在 PATH 中可用。
- 显存 **不低于 18 GB** 的 CUDA GPU (上游确认 A800、RTX 3090、RTX 4090、A100 可运行)。不支持 Apple Silicon(MPS) 与仅 CPU 推理 — AniGen 内核仅 CUDA。
- 已安装 CUDA 工具包 (11.8 或 12.x) 的 Linux 主机。首次运行会通过 nvcc 构建 pytorch3d 与 nvdiffrast,需要工具包而不仅是运行时。
- 可安装 `torch`、`spconv`、`pytorch3d`、`nvdiffrast` 与 AniGen 附属包的 Python 环境 — 首次运行自动完成安装。

### 为什么选择本地绑定 3D 生成

与云端绑定 3D 服务相比:

**本地处理的优势:**
- **隐私**: 参考图像与生成资产不会离开本机。
- **成本**: 无每次生成的 API 费用。
- **迭代**: 采样步数、CFG 缩放、关节密度、蒙皮平滑可按调用自由调节。
- **管线友好**: 可与其他 model-compose 任务(上游 image-background-removal、下游 file-store)组合形成端到端绑定资产管线。

**取舍:**
- **硬件要求**: 必须 18 GB 显存的 CUDA GPU。
- **首次运行成本**: 需下载 AniGen HuggingFace 快照(SS-Flow / SLAT-Flow / DAE / 辅助模型合计 10 GB+)并编译 CUDA 内核 — 首次控制器就绪预计 20-30 分钟。
- **许可**: AniGen 及其组件模型各自有独立许可。上游仓库将 `extensions/CUBVH/` 标注为非商业/研究用(仅与训练相关,不涉及推理)。商用前请审阅。

### 环境配置

1. 进入本示例目录:
   ```bash
   cd examples/model-tasks/image-to-3d-anigen
   ```

2. 默认无需 HuggingFace token — `VAST-AI/AniGen` 快照公开可下载。如果部署在需要认证的镜像后,按常规方式在 `.env` 中设置 `HF_TOKEN`。

3. 在 `model-compose.yml` 中选择 SS-Flow / SLAT-Flow 变体:
   - `ss_variant: solo` (默认) — 几何精准,适合大多数输入
   - `ss_variant: duet` — 更细节的骨架(手指等),几何略柔和
   - `ss_variant: epic` — 平衡
   - `slat_variant: auto` (默认) — 网络自选关节数
   - `slat_variant: control` — 关节数遵循 `params.joints_density` (0-4)

## 运行方式

1. **启动服务:**
   ```bash
   model-compose up
   ```
   > 首次启动需要下载 AniGen HF 快照并编译 CUDA 内核。预计控制器就绪需要 20-30 分钟。

2. **运行工作流:**

   **使用 API:**
   ```bash
   # 最小调用 — 从一张图像生成绑定网格与其骨架
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.png" \
     -F 'input={"image": "@img"}' \
     -o response.json

   # 用固定种子实现可复现采样
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.png" \
     -F 'input={"image": "@img", "seed": 42}' \
     -o response.json

   # 高质量采样:更多步数、更强的 SLAT 引导
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.png" \
     -F 'input={"image": "@img", "ss_steps": 50, "slat_steps": 50, "cfg_scale_slat": 4.0}' \
     -o response.json

   # 更密集的骨架(仅在 `slat_variant: control` 时有意义)
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.png" \
     -F 'input={"image": "@img", "joints_density": 3}' \
     -o response.json
   ```

   响应是一个 JSON 对象,引用两个 GLB 资源 — `mesh`(绑定网格)与 `skeleton`(骨架可视化)— 可通过返回的 URL 流式获取或下载。

   **使用 Web UI:**
   - 打开 Web UI: http://localhost:8081
   - 上传 `image`(干净背景的主体效果最好 — AniGen 会自动去除背景)
   - 需要可复现性时设置 `seed`
   - 点击 "Run Workflow" 同时获取 `mesh.glb` 与 `skeleton.glb`

## 配置参考

### 组件字段

| 字段           | 描述                                                                                                    | 默认值  |
|----------------|--------------------------------------------------------------------------------------------------------|---------|
| `task`         | 必须为 `image-to-3d`。                                                                                  | —       |
| `driver`       | 必须为 `custom`。                                                                                       | —       |
| `family`       | 必须为 `anigen`。                                                                                       | —       |
| `model`        | AniGen 模型仓库 (HuggingFace 仓库或本地路径)。                                                          | —       |
| `device`       | 计算设备。必须解析为 `cuda` — AniGen 不支持 CPU / MPS。                                                 | `auto`  |
| `ss_variant`   | SS-Flow 检查点变体 (`solo`, `epic`, `duet`)。                                                           | `solo`  |
| `slat_variant` | SLAT-Flow 检查点变体 (`auto`, `control`)。                                                              | `auto`  |

### 动作字段

| 字段                               | 描述                                                                                          | 默认值  |
|------------------------------------|-----------------------------------------------------------------------------------------------|---------|
| `image`                            | 输入图像 (或图像列表/流)。                                                                    | —       |
| `seed`                             | 用于可复现性的随机种子。未设置则每次调用产生新样本。                                          | (无)    |
| `batch_size`                       | 输入为列表/流时每批处理数量。                                                                 | `1`     |
| `return_mesh`                      | 结果中包含绑定网格 GLB。                                                                     | `true`  |
| `return_skeleton`                  | 结果中包含骨架可视化 GLB。                                                                    | `true`  |
| `return_image`                     | 结果中包含去除背景后的条件图像。                                                              | `false` |
| `params.cfg_scale_ss`              | Sparse-structure classifier-free guidance 缩放。                                             | `7.5`   |
| `params.cfg_scale_slat`            | Structured-latent classifier-free guidance 缩放。                                            | `3.0`   |
| `params.ss_steps`                  | Sparse-structure flow-matching 采样步数。                                                     | `25`    |
| `params.slat_steps`                | Structured-latent flow-matching 采样步数。                                                    | `25`    |
| `params.joints_density`            | 关节密度等级 (0-4) — 仅 `slat_variant: control` 使用。                                        | `1`     |
| `params.simplify_ratio`            | 后处理阶段的网格简化比例。                                                                    | `0.95`  |
| `params.fill_holes`                | 后处理时是否填充孔洞。                                                                        | `true`  |
| `params.no_smooth_skin_weights`    | 禁用蒙皮权重平滑。                                                                            | `false` |
| `params.smooth_skin_weights_iters` | 蒙皮权重平滑迭代次数。                                                                        | `100`   |
| `params.smooth_skin_weights_alpha` | 蒙皮权重平滑 alpha。                                                                          | `1.0`   |
| `params.no_filter_skin_weights`    | 禁用网格蒙皮权重的测地过滤。                                                                  | `false` |
| `params.texture_size`              | 烘焙纹理尺寸 (像素);`0` 禁用纹理烘焙。                                                       | `1024`  |

## 备注

- **首次运行较慢**: 首次启动会创建 `.venv/anigen` 隔离环境、安装 AniGen 固定依赖、编译 pytorch3d / nvdiffrast、下载 AniGen HF 快照。预计控制器就绪需要 20-30 分钟。后续运行复用缓存的 venv 与产物。
- **隔离运行时**: 模型工作进程运行在独立 virtualenv (`runtime.type: virtualenv`, `path: .venv/anigen`) 中,以避免 AniGen 的 torch 2.4/2.5 固定与 CUDA 扩展和控制器自身 site-packages 冲突。驱动会拒绝在控制器原生环境中运行。
- **必须 CUDA**: AniGen 硬编码 CUDA 设备放置与仅 CUDA 内核;驱动在非 CUDA 主机上拒绝加载,而非静默落到损坏路径。
- **两个 GLB 输出**: 工作流公开 `mesh`(已绑定、蒙皮、贴图)与 `skeleton`(仅骨骼可视化)。仅需绑定网格时设 `return_skeleton: false`;若还需去除背景后的条件图像,设 `return_image: true`。
- **变体取舍**: `ss_variant: solo` 优先精准几何(README 默认推荐)。当主体具有精细关节(带手指的手、复杂机械)时切换到 `duet`。仅在需要确定关节数时使用 `slat_variant: control` + `params.joints_density`;默认 `auto` 会依主体自选合理值。
- **背景稳健性**: AniGen 会在预处理阶段自动去除背景,但触及画面边缘或严重遮挡的主体仍可能产生变形几何。若自动预处理效果欠佳,考虑在上游接 `image-background-removal`。
- **采样调优**: 单阶段默认 25 步在质量与速度间较平衡。最终资产时将 `ss_steps` 与 `slat_steps` 双双提到 50;增加 `slat_steps` 的收益大于 `ss_steps`。
- **输出**: 每个结果依据 `return_*` 标志携带 `mesh`、`skeleton`、`image` 字段。任何 glTF 兼容查看器(`<model-viewer>`、Blender、three.js、Unity 的 glTFast)都能直接加载 GLB 文件,并使用现成动作片段驱动骨架。

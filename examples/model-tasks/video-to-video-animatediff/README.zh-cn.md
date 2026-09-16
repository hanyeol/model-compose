# Video-to-Video 模型任务示例

此示例演示如何在 Stable Diffusion 1.5 检查点之上叠加 AnimateDiff，通过文本提示词对现有视频进行风格化重绘，同时保留其运动。它通过 model-compose 内置的 video-to-video 任务公开。

## 概述

此工作流提供保留运动的本地视频风格化重绘：

1. **本地 AnimateDiff 流水线**: 通过 HuggingFace diffusers 端到端运行 Stable Diffusion 1.5 与 AnimateDiff 运动适配器 — 无需外部 API。
2. **源视频保留运动**: 输入视频同时提供构图和时间运动；提示词仅引导外观和风格。
3. **逐帧可调风格**: 单一 `denoise_strength` 参数在"更贴合提示词"与"更接近源视频"之间进行权衡。
4. **自动模型管理**: 基础检查点和运动适配器在首次运行时从 HuggingFace Hub 下载并在本地缓存。

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- 支持 CUDA 的 GPU，16 帧 512×512 `float16` 至少需要 **8 GB VRAM**。Apple Silicon (MPS) 未经测试且速度可能过慢。纯 CPU 推理不切实际。
- 可安装 `torch` 和 `diffusers` 的 Python 环境 — 首次运行会自动安装。

### 为何使用本地 Video-to-Video

与云端视频风格化重绘服务相比：

**本地处理的优势：**
- **隐私**: 源视频和提示词不会离开本机。
- **成本**: 无按秒或按渲染的 API 费用。
- **模型选择**: HuggingFace Hub 上任何 SD 1.5 微调模型均可作为外观骨干 — 更换 `model.repository` 即可改变整体美学。
- **易于组合**: 与其他 model-compose 任务（上游的 video-clipper、下游的 video-processor 等）组合，构建端到端的风格化重绘流水线。

**权衡：**
- **硬件要求**: 短片使用 8 GB VRAM 较为宽裕；随着片段变长或分辨率提高，VRAM 用量与帧数线性增长。
- **运动范围**: AnimateDiff 的运动适配器在短片上训练，~16 帧内可期待连贯运动，超过 ~32 帧后质量会下降。
- **许可证**: 商用前请检查基础模型和运动适配器各自的许可证。

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/model-tasks/video-to-video-animatediff
   ```

2. 无需额外的环境配置 — 基础检查点（`Realistic_Vision_V5.1_noVAE`）和运动适配器（`animatediff-motion-adapter-v1-5-3`）在首次运行时从 HuggingFace Hub 下载，并缓存到 `~/.cache/huggingface/` 下。

3. 若想更换美学风格，可编辑 `model-compose.yml` 中的 `model.repository`。只要运动适配器面向相同的基础架构，任何 SD 1.5 微调（例如动漫或插画模型）均可使用。

## 运行方法

1. **启动服务：**
   ```bash
   model-compose up
   ```
   > 首次启动会下载基础检查点（~2 GB）和运动适配器（~1.6 GB）。控制器报告就绪前预计需要几分钟。

2. **运行工作流：**

   **使用 API：**
   ```bash
   # 最简调用 — 用提示词对视频进行风格化重绘，其余参数使用默认值
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "clip=@/path/to/source.mp4" \
     -F 'input={"video": "@clip", "prompt": "cinematic shot, film grain, warm sunset lighting"}'

   # 更强的风格迁移（提高 strength）并指定种子
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "clip=@/path/to/source.mp4" \
     -F 'input={"video": "@clip", "prompt": "watercolor painting, soft brushstrokes", "denoise_strength": 0.7, "seed": 42}'

   # 更长的输出（32 帧），12 fps
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "clip=@/path/to/source.mp4" \
     -F 'input={"video": "@clip", "prompt": "neon cyberpunk city, rain, reflections", "num_frames": 32, "fps": 12}'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 上传 `video`（模型在 ~16 帧窗口上训练，短片效果最佳）并输入 `prompt`
   - 可选地调节 `denoise_strength`、`num_frames`、`fps`、`guidance_scale`，或设置 `seed`
   - 点击 "Run Workflow" 按钮即可获得 MP4 输出

## 配置参考

### 组件字段

| 字段             | 说明                                                                                                                          | 默认值                                                |
|------------------|-------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------|
| `task`           | 必须为 `video-to-video`。                                                                                                     | —                                                     |
| `driver`         | 必须为 `huggingface`。                                                                                                        | —                                                     |
| `architecture`   | Video-to-video 架构。目前仅支持 `animatediff`。                                                                               | —                                                     |
| `model`          | 基础 SD 1.5 风格检查点（HuggingFace 仓库或本地路径）。任何 SD 1.5 微调均可使用。                                              | —                                                     |
| `motion_adapter` | 与基础架构匹配的 AnimateDiff 运动适配器。                                                                                     | —                                                     |
| `device`         | 计算设备（`cuda`、`cuda:0` 等）。`auto` 会选择最优可用设备。                                                                  | `auto`                                                |

### 动作字段

| 字段                          | 说明                                                                                                                    | 默认值                                                   |
|-------------------------------|-------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------|
| `video`                       | 保留运动的源视频（或视频列表/流）。                                                                                     | —                                                        |
| `prompt`                      | 引导重绘外观的文本提示词。                                                                                              | （无）                                                   |
| `negative_prompt`             | 描述生成结果中应避免的内容的文本。                                                                                       | `"bad quality, worst quality, low resolution"`           |
| `seed`                        | 用于可复现性的随机种子。留空则每次调用都产生新的样本。                                                                  | （无）                                                   |
| `params.num_frames`           | 从输入视频中采样并输出的帧数。超过 ~32 帧后质量会下降。                                                                 | `16`                                                     |
| `params.fps`                  | 输出视频帧率。                                                                                                          | `8`                                                      |
| `params.height` / `.width`    | 输出视频分辨率。未设置时沿用输入视频的尺寸。                                                                            | (源尺寸)                                                 |
| `params.denoise_strength`     | 去噪强度。`0.4-0.5` 强力保留运动；`0.6-0.7` 更强地遵循提示词。                                                          | `0.5`                                                    |
| `params.guidance_scale`       | Classifier-free guidance 缩放。                                                                                         | `7.5`                                                    |
| `params.inference_steps`      | 每帧的 diffusion 推理步数。步数越多质量越好，但速度越慢。                                                               | `25`                                                     |
| `batch_size`                  | 当输入为列表或流时每批处理的 `(video, prompt)` 对数量。                                                                 | `1`                                                      |

## 注意事项

- **首次运行较慢**: 控制器需要下载基础检查点和运动适配器。后续运行会复用缓存文件。
- **帧数很重要**: AnimateDiff 在 ~16 帧窗口上训练。超过 ~32 帧后往往会出现明显的漂移和运动不一致。
- **强度甜蜜区**: `0.4` 以下几乎不改变输入；`0.7` 以上常常破坏运动连贯性。建议从 `0.5` 开始并进行调整。
- **美学切换**: 从写实切换到动漫风格时，将 `model.repository` 换成 SD 1.5 动漫微调（例如 `Meina/MeinaMix_V11` 等）。运动适配器保持不变。
- **提示词权重**: 描述性、以风格为主的提示词比以物体为主的提示词效果更好 — AnimateDiff 不能重构场景，只能重新上色和重新风格化。
- **VRAM 规划**: 16 帧 512×512 `float16` 大约需要 8-10 GB VRAM；24 帧约为 ~1.6 倍。遇到 OOM 时请减少 `num_frames` 或分辨率。
- **流水线搭配**: 上游搭配 `video-clipper` 在重绘前裁剪特定片段，或下游搭配 `video-processor` 将重绘后的片段合成回更长的剪辑中。

# 图像生成模型任务示例 (Qwen-Image 2.1)

本示例演示了如何通过 model-compose 内置的 image-generation 任务，使用阿里巴巴的 Qwen-Image-2.1 从文本提示生成高保真图像。

## 概述

此工作流程提供本地文生图生成能力：

1. **本地 Qwen-Image 2.1 管线**: 端到端运行 7B 扩散 transformer — 无需外部 API。
2. **Qwen3-VL 文本编码器**: 管线使用 Qwen3-VL 作为文本条件器，中文、韩文、英文提示词均可作为一等公民处理。
3. **True-CFG 引导**: 可选的 `true_cfg_scale > 1.0` 会启用带 `negative_prompt` 的 classifier-free guidance；保持 `1.0` 可跳过额外的前向计算，将推理时间减半。
4. **多种宽高比支持**: 1:1 (2048×2048)、4:3、3:2、16:9 及其竖版都原生支持。
5. **自动模型管理**: 权重在首次运行时从 HuggingFace Hub 下载并缓存到本地。

## 准备工作

### 前置条件

- 已安装 model-compose 且在 PATH 中可用。
- 支持 CUDA 的 GPU。Qwen-Image-2.1 使用 bfloat16 加载，2048×2048 分辨率下无 offload 大约需要 **24 GB** 显存；降低分辨率或使用 CPU offload 可以减少显存占用。
- 能够安装 `torch`、`diffusers` (main)、`transformers>=5.17` 的 Python 环境 — 首次运行时会自动安装到隔离的 virtualenv。
- 已接受 `Qwen/Qwen-Image-2.1` 许可的 HuggingFace 访问令牌。在启动 model-compose 前通过 `HF_TOKEN` 环境变量设置。

### 为什么使用隔离运行时

`QwenImage21Pipeline` 已合并到 `diffusers` main 分支，但**尚未包含在任何正式发布中**（截至 2026-09，最新版本为 v0.40.0）。image-generation 驱动会将 `diffusers @ git+https://github.com/huggingface/diffusers.git` 附加到此组件的 setup requirements，因此模型工作进程运行在专用的 `virtualenv` (`.venv/qwen-image`) 中，以避免该未发布构建覆盖控制器自身的 `diffusers` 安装，或与同一 compose 文件中其他扩散组件冲突。

### 环境配置

1. 进入示例目录：
   ```bash
   cd examples/model-tasks/image-generation-qwen-image
   ```

2. 在 https://huggingface.co/Qwen/Qwen-Image-2.1 接受 Qwen Research License，然后从示例复制 `.env` 并填入具有访问权限的 HuggingFace 访问令牌：
   ```bash
   cp .env.sample .env
   # 编辑 .env 并设置 HF_TOKEN=hf_xxx
   ```

3. 若要减少显存占用，降低 `width` / `height`（例如 1536×1536 或 1024×1024），或将默认为 40 的 `inference_steps` 调低。

## 运行方式

1. **启动服务:**
   ```bash
   model-compose up
   ```
   > 首次启动会创建 `.venv/qwen-image`、从 GitHub main 安装 `diffusers`、下载约 20 GB 权重并将管线加载到显存。控制器报告 ready 之前需要数分钟。

2. **执行工作流:**

   **使用 API:**
   ```bash
   # 最简调用 — 默认 2048×2048 文生图
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "A neon shop sign that reads \"QWEN IMAGE 2.1\", rainy night, reflections on wet pavement"}}' \
     -o output.png

   # 使用固定 seed 进行可复现采样
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "一只雪豹在长满青苔的岩石上休憩，电影感光线", "seed": 42}}' \
     -o output.png

   # 宽屏渲染 + negative prompt + true-CFG
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "日落时分辽阔的沙漠峡谷，超精细细节", "negative_prompt": "blurry, low quality, watermark", "true_cfg_scale": 4.0, "width": 2752, "height": 1536}}' \
     -o output.png
   ```

   **使用 Web UI:**
   - 打开 Web UI: http://localhost:8081
   - 输入描述目标图像的 `prompt`
   - 可选地设置 `seed` 以获得可复现性；如需引导采样，设置 `negative_prompt` + `true_cfg_scale > 1.0`；也可指定非正方形的 `width`/`height`
   - 点击 "Run Workflow" 即可获得 `.png` 文件

## 配置参考

### Component 字段

| 字段            | 说明                                                              | 默认值  |
|-----------------|-------------------------------------------------------------------|---------|
| `task`          | 必须为 `image-generation`。                                       | —       |
| `driver`        | 必须为 `huggingface`。                                            | —       |
| `architecture`  | 必须为 `qwen-image`。                                             | —       |
| `model`         | Qwen-Image 仓库（`Qwen/Qwen-Image-2.1` 或本地路径）。             | —       |
| `device`        | 计算设备。强烈建议 `cuda`。                                       | `auto`  |

### Action 字段

| 字段                     | 说明                                                                                       | 默认值  |
|--------------------------|--------------------------------------------------------------------------------------------|---------|
| `prompt`                 | 文本提示词（或列表/流）。                                                                   | —       |
| `negative_prompt`        | 描述需避免内容的文本。仅在 `true_cfg_scale > 1.0` 时生效。                                  | (无)    |
| `width`                  | 输出图像宽度（像素）。                                                                       | `1024`  |
| `height`                 | 输出图像高度（像素）。                                                                       | `1024`  |
| `num_return_images`      | 每个提示词返回的图像数量。                                                                    | `1`     |
| `seed`                   | 用于可复现性的随机种子。未设置则每次调用生成全新样本。                                        | (无)    |
| `batch_size`             | 输入为列表或流时每批处理的提示词数量。                                                        | `1`     |
| `params.inference_steps` | 去噪步数。                                                                                    | `40`    |
| `params.true_cfg_scale`  | True classifier-free guidance 系数。`1.0` 表示禁用 negative-prompt 引导。                    | `1.0`   |

## 注意事项

- **首次运行较慢**: 控制器会在首次启动时创建 `.venv/qwen-image` 环境、从 GitHub main 安装 `diffusers`、并下载约 20 GB 权重。控制器 ready 之前需要 10-15 分钟。后续运行会重用缓存的 venv 和权重。
- **Diffusers 锁定到 main**: Qwen-Image-2.1 依赖仅存在于 `diffusers` main 的类（`QwenImage21Pipeline`、`QwenImage21Transformer2DModel`、`AutoencoderKLQwenImage21`）。当下一个正式发布包含它们时，本示例的 setup 可以改为固定到 `diffusers>=<发布版本>` 而无需 git URL — 只要更新 model-compose，无需修改 compose。
- **Qwen Research License**: `Qwen/Qwen-Image-2.1` 以 Qwen Research License Agreement（非商业）发布。生产使用前请查看 https://huggingface.co/Qwen/Qwen-Image-2.1 的条款。
- **显存规划**: 7B transformer 加上 Qwen3-VL 文本编码器使 2048×2048 bfloat16 的峰值显存达到约 24 GB。可通过降低分辨率或为组件添加 `quantization` 配置以适配 16 GB 显卡；驱动将 `transformer` 和 `text_encoder` 标记为可量化，因此 4-bit 或 8-bit 权重节省最多。
- **`true_cfg_scale` 与速度**: 当 `true_cfg_scale > 1.0` 时，管线会在每一步为 negative prompt 运行一次额外的前向计算，推理时间大约翻倍。追求最快路径时保持 `1.0`，仅在确实需要 negative prompt 时调高。
- **多语言提示词**: Qwen-Image-2.1 的 Qwen3-VL 文本编码器原生支持中文、韩文、日文、英文提示词，混合语言提示也可以工作。
- **输出**: 结果是每个输入一个 `.png`（批量输入返回列表），由扩散 VAE 解码得到。

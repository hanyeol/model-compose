# 图像编辑模型任务示例 (Qwen-Image-Edit-2509)

本示例演示如何通过 model-compose 内置的 image-generation 任务，使用阿里巴巴的 Qwen-Image-Edit-2509 以自然语言指令编辑一张或多张参考图像。

## 概述

此工作流程提供本地指令式图像编辑能力：

1. **本地 Qwen-Image-Edit-2509 管线**: 端到端运行 20B 扩散 transformer — 无需外部 API。
2. **Qwen2.5-VL 文本编码器**: 管线使用 Qwen2.5-VL 作为视觉-语言条件器，支持直接引用图像内容的指令（"把夹克改成红色"、"将主体放到雪林里"）。
3. **多参考图像编辑**: 可传入单张参考图或最多三张图像的列表；模型会融合它们以实现身份保持编辑、商品合成或姿态迁移。
4. **True-CFG 引导**: `true_cfg_scale` 默认 `4.0`，使 `negative_prompt` 真正引导采样。若想跳过额外的前向计算、将推理时间减半，可将其降至 `1.0`（但失去负向提示引导）。
5. **自动模型管理**: 权重在首次运行时从 HuggingFace Hub 下载并缓存到本地。

## 准备工作

### 前置条件

- 已安装 model-compose 且在 PATH 中可用。
- 支持 CUDA 的 GPU。该示例通过 `cpu_offload: model` 将 Qwen-Image-Edit-2509 装入单张 **24 GB** GPU（1024×1024 bfloat16）。显存更小的显卡可切换到 `cpu_offload: sequential` 以进行层级卸载；48 GB 以上的显卡可移除该选项以获得最高速度。
- 能安装 `torch`、`diffusers>=0.41.0`、`transformers>=4.51.3` 的 Python 环境 — 首次运行会自动安装到隔离的 virtualenv。
- 已接受 `Qwen/Qwen-Image-Edit-2509` 许可的 HuggingFace 访问令牌。在启动 model-compose 前通过 `HF_TOKEN` 环境变量设置。

### 为什么使用隔离运行时

`QwenImageEditPlusPipeline` 从 `diffusers >= 0.41.0` 开始可用，但控制器的共享环境可能仍被其他组件固定在较旧版本。模型工作进程运行在专用 `virtualenv` (`.venv/qwen-image-edit`) 中，以避免该组件的 `diffusers` 升级覆盖控制器自身的安装，或与同一 compose 文件中的其他扩散组件冲突。

### 环境配置

1. 进入示例目录：
   ```bash
   cd examples/model-tasks/image-editing-qwen-image-edit-2509
   ```

2. 在 https://huggingface.co/Qwen/Qwen-Image-Edit-2509 接受 Qwen Research License，然后在 shell 或此 README 旁的 `.env` 文件中设置 `HF_TOKEN`：
   ```bash
   export HF_TOKEN=hf_xxx
   ```

3. 若需降低峰值显存，可调低 `width` / `height`（例如 768×768）或将 `inference_steps` 从默认 40 调低。

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```
   > 首次启动会创建 `.venv/qwen-image-edit` 环境、安装 `diffusers` 和 `transformers`、下载约 40 GB 权重并把管线加载到显存。预计需要 10-20 分钟才会报告 ready。

2. **运行工作流：**

   **使用 API：**
   ```bash
   # 单参考图编辑 — 附上一张图像并描述编辑
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "ref=@/path/to/subject.png" \
     -F 'input={"prompt": "把主体放到黄昏的雪松林中，电影级光线", "image": "@ref"}' \
     -o output.png

   # 固定种子 + 负向提示的可复现编辑
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "ref=@/path/to/subject.png" \
     -F 'input={"prompt": "将夹克改为红色皮质飞行员夹克", "negative_prompt": "模糊、多余肢体、水印", "image": "@ref", "seed": 42}' \
     -o output.png

   # 多参考图编辑 — 用一条指令合成两张图像
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "a=@/path/to/person.png" \
     -F "b=@/path/to/outfit.png" \
     -F 'input={"prompt": "让第一张图像中的人穿上第二张图像的服装", "image": ["@a", "@b"]}' \
     -o output.png
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 在 `image` 处上传一张或多张参考图像
   - 在 `prompt` 中输入编辑指令
   - 可选设置 `seed`、`negative_prompt`，或非正方形的 `width`/`height`
   - 点击 "Run Workflow" 以接收 `.png` 文件

## 配置参考

### 组件字段

| 字段            | 描述                                                              | 默认值 |
|-----------------|-------------------------------------------------------------------|--------|
| `task`          | 必须为 `image-generation`。                                        | —      |
| `driver`        | 必须为 `huggingface`。                                             | —      |
| `architecture`  | 必须为 `qwen-image-edit`。                                         | —      |
| `model`         | Qwen-Image-Edit 仓库 (`Qwen/Qwen-Image-Edit-2509` 或本地路径)。     | —      |
| `device`        | 计算设备。强烈建议使用 `cuda`。                                      | `auto` |
| `cpu_offload`   | 显存减少策略。`model` 可装入单张 24 GB GPU。                         | (无)   |

### 动作字段

| 字段                          | 描述                                                                                     | 默认值 |
|-------------------------------|-----------------------------------------------------------------------------------------|--------|
| `prompt`                      | 自然语言编辑指令（或指令的列表/流）。                                                      | —      |
| `negative_prompt`             | 描述需要避免内容的文本。仅在 `true_cfg_scale > 1.0` 时生效。                                 | (无)   |
| `image`                       | **必填。** 一张参考图像，或最多三张的列表。                                                   | —      |
| `width`                       | 输出图像宽度（像素）。                                                                      | `1024` |
| `height`                      | 输出图像高度（像素）。                                                                      | `1024` |
| `num_return_images`           | 每个 prompt 返回的图像数量。                                                                | `1`    |
| `seed`                        | 用于复现的随机种子。不设置则每次调用生成新样本。                                              | (无)   |
| `batch_size`                  | 输入为列表或流时每批处理的 prompt 数量。                                                     | `1`    |
| `params.inference_steps`      | 去噪步数。                                                                                | `40`   |
| `params.true_cfg_scale`       | True classifier-free guidance 比例。大于 1.0 时启用负向提示引导。                              | `4.0`  |
| `params.max_sequence_length`  | Qwen2.5-VL 文本编码器的最大 token 长度。                                                     | `512`  |

## 注意事项

- **首次运行较慢**：控制器会创建 `.venv/qwen-image-edit` 环境，安装 `diffusers` 和 `transformers`，并在首次启动时下载约 40 GB 权重。后续运行会复用缓存的 venv 和权重。
- **Qwen Research License**：`Qwen/Qwen-Image-Edit-2509` 以 Qwen Research License Agreement（非商用）发布。生产使用前请在 https://huggingface.co/Qwen/Qwen-Image-Edit-2509 查看条款。
- **显存规划**：20B 变换器加 Qwen2.5-VL 文本编码器（~7B）同时常驻会超过 24 GB。此示例使用 `cpu_offload: model`（整管线模块级卸载）将 1024×1024 的峰值显存控制在 24 GB 以下。若需更低峰值显存可切换到 `cpu_offload: sequential`（层级卸载，显存削减约 90%，但速度慢 2–5 倍）。添加 `quantization` 配置可进一步缩减权重 — 驱动将 `transformer` 和 `text_encoder` 标记为可量化，因此 4-bit/8-bit 收益最大。
- **`true_cfg_scale` 与速度**：当 `true_cfg_scale > 1.0` 时，管线会为负向提示每步多做一次前向，推理时间约加倍。Edit-2509 针对负向提示引导进行了调优，默认值为 `4.0`；仅在无需 `negative_prompt` 时将其降到 `1.0`。
- **多参考输入**：将 `image` 以 JSON 数组传入可用于身份保持合成、商品合成或服装迁移。Edit-2509 已在 1-3 张参考图上验证；更长的列表虽允许但质量会下降。
- **多语言指令**：Qwen2.5-VL 原生处理中文、韩语、日语和英语提示词；混合语言提示也可工作。
- **输出**：结果是每个输入对应一张 `.png`（批量输入返回列表），由扩散 VAE 解码得到。

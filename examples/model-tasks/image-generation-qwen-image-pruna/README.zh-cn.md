# 图像生成模型任务示例 (Qwen-Image 2.1 + Pruna LoRA)

本示例演示了如何用 [PrunaAI 的 distilled LoRA](https://huggingface.co/PrunaAI/P-Q-Image-2.1) 加速阿里巴巴的 Qwen-Image-2.1，将文生图去噪步数从基础管线的 40 步压缩到 5 步、6 步或 8 步。

## 概述

本工作流会将 PEFT LoRA 适配器挂载到基础 Qwen-Image-2.1 管线，并以更少的步数运行：

1. **基础 Qwen-Image 2.1 管线**: 与 [image-generation-qwen-image](../image-generation-qwen-image) 示例相同的本地管线 — 7B 扩散 transformer、Qwen3-VL 文本编码器、多语言提示词支持。
2. **Pruna Distilled LoRA**: Pruna 从基础模型中蒸馏得到的公开 LoRA 适配器，让管线在远少于原本步数的情况下收敛。
3. **声明式适配器组合**: 适配器通过模型组件的标准 `peft_adapter` 字段挂载 — 无需代码，只需 YAML。
4. **隔离的运行时**: 与基础 Qwen-Image 示例相同的 virtualenv 策略，将包含 `QwenImage21Pipeline` 的未发布 `diffusers` 构建隔离在控制器环境之外。

## 准备工作

### 前置条件

- 已安装 model-compose 且在 PATH 中可用。
- 支持 CUDA 的 GPU。本示例使用 `cpu_offload: model` 将管线装入单张 24 GB GPU；显存更充裕可移除或降级该选项。
- 能够安装 `torch`、`diffusers` (main)、`transformers>=5.17`、`peft` 的 Python 环境 — 首次运行时会自动安装到隔离的 virtualenv。
- 已接受 `Qwen/Qwen-Image-2.1` 许可的 HuggingFace 访问令牌。在启动 model-compose 前通过 `HF_TOKEN` 环境变量设置。

### 关于适配器

`PrunaAI/P-Q-Image-2.1` 在同一仓库中提供四个 `.safetensors` 变体：

| 变体                                                  | 去噪步数 | 说明                                                                 |
|-------------------------------------------------------|----------|----------------------------------------------------------------------|
| `p_q_image_2.1_8_steps_v0.1.safetensors`              | 8        | 本示例的默认值。v0.1 中质量与速度最佳平衡。                           |
| `p_q_image_2.1_5_steps_v0.1.safetensors`              | 5        | v0.1 中最快；质量下降更明显。                                         |
| `p_q_image_2.1_6_steps_v0.2.safetensors`              | 6        | 高级 v0.2 蒸馏。编辑时保留输入内容更重要时推荐使用。                  |
| `p_q_image_2.1_6_steps_upsampled_v0.2.safetensors`    | 6        | 内置 prompt 上采样的 v0.2 — 无需单独的 enhancer 调用。                |

切换变体时需同时编辑四个字段：

- `peft_adapter[0].model.filename`
- `action.params.inference_steps`
- `action.params.sigmas`（LoRA 针对每个变体特定的 sigma 调度训练）
- `scheduler.options`（v0.1 与 v0.2 需要不同的调度器行为 — 见下文）

**v0.1 (5 步 / 8 步)** 将 sigmas 原样使用，不做额外 shift：

```yaml
scheduler:
  options:
    use_dynamic_shifting: false
    shift: 1.0
    shift_terminal: null
```

Sigmas：
- 8 步: `[1.0, 0.933333333, 0.857142857, 0.769230769, 0.666666667, 0.545454545, 0.4, 0.222222222]`
- 5 步: `[1.0, 0.94, 0.857142857, 0.666666667, 0.4]`

**v0.2 (6 步 / 6 步 upsampled)** 保留依分辨率的 shift，仅禁用 terminal stretch：

```yaml
scheduler:
  options:
    use_dynamic_shifting: true
    shift_terminal: null
```

Sigmas（两个 v0.2 变体通用）: `[1.0, 0.925, 0.85, 0.625, 0.375, 0.125]`

如果不匹配 `scheduler.options`，管线默认的 `FlowMatchEulerDiscreteScheduler`（`use_dynamic_shifting: true`、`shift_terminal: 0.02`）会重新 shift 并 stretch 自定义 sigmas，得到 LoRA 从未训练过的调度。

### 环境配置

1. 进入示例目录：
   ```bash
   cd examples/model-tasks/image-generation-qwen-image-pruna
   ```

2. 在 https://huggingface.co/Qwen/Qwen-Image-2.1 接受 Qwen Research License，然后从示例复制 `.env` 并填入具有访问权限的访问令牌：
   ```bash
   cp .env.sample .env
   # 编辑 .env 并设置 HF_TOKEN=hf_xxx
   ```

## 运行方式

1. **启动服务:**
   ```bash
   model-compose up
   ```
   > 首次启动会创建 `.venv/qwen-image-pruna`、从 GitHub main 安装 `diffusers` 与 `peft`、下载约 20 GB 基础权重与 LoRA 文件，并将管线加载到显存。

2. **执行工作流:**

   **使用 API:**
   ```bash
   # 最简调用 — 默认 1024×1024 的 8 步文生图
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "A neon shop sign that reads \"QWEN IMAGE 2.1\", rainy night, reflections on wet pavement"}}' \
     -o output.png

   # 使用固定 seed 进行可复现采样
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "一只雪豹在长满青苔的岩石上休憩，电影感光线", "seed": 42}}' \
     -o output.png

   # 图像条件生成 — 传入一张或多张输入图像作为指令编辑的对象
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "ref=@/path/to/input.png" \
     -F 'input={"prompt": "同一主体置于黄昏雪林中，电影感光线", "image": "@ref"}' \
     -o output.png
   ```

   **使用 Web UI:**
   - 打开 Web UI: http://localhost:8081
   - 输入描述目标图像的 `prompt`
   - 可选地设置 `seed` 以获得可复现性；也可指定非正方形的 `width`/`height`
   - 点击 "Run Workflow" 即可获得 `.png` 文件

## 配置参考

### PEFT Adapter 字段

| 字段                        | 说明                                                                                    | 默认值  |
|-----------------------------|-----------------------------------------------------------------------------------------|---------|
| `type`                      | 适配器类型。扩散管线目前只支持 `lora`。                                                  | —       |
| `name`                      | 组合多个适配器时用于引用的标识符（`set_adapters([...])`）。                              | (无)    |
| `model.repository`          | 存放适配器权重的 HuggingFace 仓库。                                                      | —       |
| `model.filename`            | 仓库中要加载的文件。当仓库打包多个变体时必填。                                            | (无)    |
| `weight`                    | LoRA 生效时应用的适配器强度。                                                            | `1.0`   |

### Action 字段

与基础 [image-generation-qwen-image](../image-generation-qwen-image) 示例相同。此变体需要调整的两个旋钮：

| 字段                     | 说明                                                                                    | 默认值  |
|--------------------------|-----------------------------------------------------------------------------------------|---------|
| `params.inference_steps` | 需与 LoRA 变体一致：`8`、`5` 或 `6`（对应各文件）。                                     | `8`     |
| `params.true_cfg_scale`  | Pruna 的 distillation 目标 `1.0`。调高会抵消加速效果。                                  | `1.0`   |

## 注意事项

- **v0.2 vs v0.1**: v0.2 的 6 步适配器是 Pruna 的高级蒸馏，推荐作为基础模型的直接替换；v0.1（5/8 步）出于向后兼容仍保留。两代使用不同的 sigma 调度与不同的调度器设置 — 不要混用。
- **`true_cfg_scale` 已固定**: distilled 适配器是在无 classifier-free guidance 的条件下训练的。将 `true_cfg_scale` 提到 `1.0` 以上只会增加额外的前向计算开销而无相应的质量收益；`negative_prompt` 为与基础示例对称而接受，但在此 scale 下不产生效果。
- **显存规划**: 挂载 LoRA 与基础管线的显存占用基本相同。若需以速度换取更低峰值内存，请查阅基础示例的显存说明。
- **切换变体**: 仅编辑 `filename` 是不够的 — `filename`、`inference_steps`、`sigmas`、`scheduler.options` 必须保持一致。管线可以用 8 步 LoRA 跑 5 步而不报错，但输出会明显 under-denoise。
- **许可**: `Qwen/Qwen-Image-2.1` 和 Pruna LoRA 各自遵循其 HuggingFace 许可。生产使用前请查看各仓库的条款。

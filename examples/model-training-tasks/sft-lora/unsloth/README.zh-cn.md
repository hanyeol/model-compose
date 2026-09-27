# SFT + LoRA 模型训练器示例（Unsloth）

此示例演示如何使用 model-compose 的 `model-trainer` 组件（`sft` 任务 + **Unsloth** 驱动）对因果语言模型进行微调。它在 TinyLlama-1.1B 上附加 LoRA 适配器，使用 Alpaca 指令数据集进行监督微调（SFT），借助 Unsloth 的融合 CUDA 内核，相比原生 HuggingFace 后端可获得约 2 倍吞吐和约 30-70% 的 VRAM 节省。

## 概述

此工作流提供一个声明式的 SFT+LoRA 训练循环：

1. **Unsloth 快速内核**：通过 `FastLanguageModel.from_pretrained` 加载基础模型，该函数使用手工优化的 Triton 内核对注意力和 MLP 层进行 patch
2. **通过 `FastLanguageModel.get_peft_model` 的 LoRA 适配器**：PEFT 包装是 Unsloth 专用的 — 标准 `peft.get_peft_model` 会绕过快速内核
3. **自动模型配置**：首次运行时下载 TinyLlama 并缓存到 `~/.cache/huggingface/`
4. **指令数据集**：加载 `tatsu-lab/alpaca` 数据集并在其 `text` 列（预先展平的 instruction/response 提示）上训练
5. **检查点输出**：将训练后的 LoRA 适配器保存到 `output_dir` 并返回训练指标

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- **支持 CUDA 的 NVIDIA GPU** — Unsloth 只提供 CUDA 专用内核（Triton + bitsandbytes + xformers）。不支持 MPS 与 CPU。
- 建议 Compute Capability ≥ 7.0（Turing / RTX 20xx 及更高）。bfloat16 混合精度需要 Ampere+（RTX 30xx、A100、H100）。
- 包含 `torch`、`unsloth`、`trl`、`huggingface_hub` 的 Python 环境（由组件的 `_get_setup_requirements` 自动管理）
- rank 16 下的 TinyLlama 建议使用 **VRAM ≥ 6 GB** 的 GPU。得益于 Unsloth 的内存效率，4-6 GB 显存的卡也能装下此工作负载。
- **磁盘 ~5 GB** 用于 TinyLlama 权重与数据集缓存

### 为什么用 Unsloth

Unsloth 是一个 drop-in 的加速层，专为 decoder-only 语言模型的 LoRA/QLoRA 微调设计。与原生 HuggingFace 路径相比：

- 在 Ampere+ GPU 上通过融合的注意力/MLP 内核实现 **约 2 倍吞吐**
- 通过智能激活检查点和 4 位权重压缩实现 **约 30-70% VRAM 节省**
- 训练器使用 **相同的 TRL API** — `SFTTrainer` + `SFTConfig` 原样使用；加速位于模型包装而不是训练循环

权衡：

- **仅 CUDA**。不支持 MPS、CPU、ROCm（upstream 正在添加 ROCm 支持但尚未稳定）。
- **必须 LoRA/QLoRA**。Unsloth 后端不支持全量微调；组件 config 在加载时会拒绝。
- **Rope 缩放在加载时烘焙**到模型中 — 由 component-level 的 `max_seq_length` 决定。Action-level `max_seq_length` 仍然控制 per-batch truncation，但不能超过 component 值。
- **模型系列支持**仅限 decoder-only 架构（Llama、Mistral、Gemma、Qwen、Phi）。Encoder 模型（BERT、DeBERTa）通过 `FastModel` API 支持分类任务，但不在此 SFT 驱动的支持范围内。

### 环境配置

进入此示例目录：
```bash
cd examples/model-training-tasks/sft-lora/unsloth
```

无需额外的环境配置。模型和数据集会在首次工作流运行时自动下载。

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **触发训练：**

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "num_epochs": 1,
         "batch_size": 4,
         "learning_rate": 2e-4
       }
     }'
   ```

   **使用 Web UI：**
   - 打开 http://localhost:8081
   - 按需调整 `num_epochs`、`batch_size`、`learning_rate`
   - 点击 "Run Workflow"

   **使用 CLI：**
   ```bash
   model-compose run --input '{"num_epochs": 1}'
   ```

3. **查看训练后的适配器：**
   ```bash
   ls ./output/sft-lora-unsloth
   # adapter_config.json  adapter_model.safetensors  tokenizer.json  ...
   ```

## 组件详情

### Model-Trainer 组件（默认）

- **Type**：`model-trainer`
- **Task**：`sft`
- **Driver**：`unsloth`
- **基础模型**：`TinyLlama/TinyLlama-1.1B-Chat-v1.0`
- **max_seq_length**（component-level）：`2048` — 加载时通过 rope 缩放烘焙进模型
- **LoRA 配置**：
  - rank：16
  - alpha：32
  - dropout：0.05
  - target_modules：`q_proj`、`k_proj`、`v_proj`、`o_proj`

### 模型信息：TinyLlama-1.1B-Chat-v1.0

- **开发者**：TinyLlama 项目
- **参数量**：11 亿
- **类型**：因果 LM，chat 调优
- **许可证**：Apache 2.0
- **LoRA 后可训练参数**：约 4M（约 0.4%）

## 工作流详情

### "Fine-tune TinyLlama with SFT + LoRA (Unsloth)" 工作流（默认）

**描述**：使用 Unsloth 的快速内核和 LoRA 适配器在 Alpaca 指令数据集上对 TinyLlama-1.1B 进行监督微调，然后返回检查点目录和训练指标。

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `dataset_path` | string | 否 | `tatsu-lab/alpaca` | HuggingFace 数据集 repo id 或本地路径 |
| `dataset_split` | string | 否 | `train` | 要加载的数据集 split |
| `num_epochs` | int | 否 | `1` | 训练 epoch 数 |
| `batch_size` | int | 否 | `4` | 每设备训练批次大小 |
| `learning_rate` | float | 否 | `2e-4` | AdamW 初始学习率 |
| `output_dir` | string | 否 | `./output/sft-lora-unsloth` | 训练后适配器的保存位置 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `output_dir` | string | 保存的 LoRA 适配器 + tokenizer 所在目录 |
| `train_loss` | float | 最终训练损失 |
| `metrics` | object | 完整的 `Trainer.train()` 指标（train_runtime、samples_per_second 等） |

## `max_seq_length` 语义

Unsloth 的 `FastLanguageModel.from_pretrained` 在加载时应用 rope 缩放，将最大位置嵌入尺寸烘焙进 patch 后的模型。这与原生 HuggingFace 驱动不同 — 后者的 truncation 是 per-batch 的 tokenizer 设置。

- **`trainer.max_seq_length`（component-level）**：决定加载模型的位置容量。只需设置一次，覆盖任何下游 action 可能喂入的最长序列。
- **`action.max_seq_length`**：仍在 SFT config 级别控制 per-example truncation。若未设置，则使用 tokenizer 的 `model_max_length`。此值不能超过 component-level 值。

对大多数指令调优工作负载，component-level 值 `2048` 或 `4096` 是安全的默认。

## 系统要求

### 推荐配置

- **GPU**：VRAM ≥ 6 GB 的 NVIDIA GPU（RTX 3060 / T4 / A10 或更高）。Ampere+（RTX 30xx、A100、H100）可启用 bfloat16 并获得完整加速。
- **RAM**：16 GB
- **磁盘**：模型 + 数据集缓存 + 检查点共 10 GB
- **CUDA**：11.8+ 与匹配的 PyTorch

### 最低配置

- **GPU**：VRAM 4 GB 的 Turing（RTX 20xx / T4）。在有限硬件上跑更大模型时，使用 `quantization: nf4` 和 `batch_size: 1`。

## 定制

### 使用 QLoRA（4 位量化基础模型）

Unsloth 最大的收益体现在使用 QLoRA 的 7B+ 模型上。在组件中添加 `quantization`：

```yaml
component:
  type: model-trainer
  task: sft
  driver: unsloth
  model: mistralai/Mistral-7B-Instruct-v0.3
  max_seq_length: 2048
  lora:
    rank: 8
    alpha: 16
  quantization:
    type: nf4
    compute_dtype: bfloat16
  action:
    dataset: HuggingFaceH4/ultrachat_200k
    text_column: messages       # UltraChat 提供对话式数据
    output_dir: ./output/qlora
```

在 Unsloth 下，`quantization.type: int8` 映射到 `load_in_8bit=True`，`nf4`/`int4`/`fp4` 都映射到 `load_in_4bit=True`。Compute dtype 从 `precision` 和 GPU 的 bfloat16 支持情况推断。

注意：`messages` 路径要求 tokenizer 包含 `chat_template`。指令调优的检查点（`*-Instruct-*`、`*-chat`、`*-it`）自带；纯基础检查点没有，驱动会在训练开始时抛出 `ValueError` 拒绝。

### 使用 prompt/response 列

若数据集用 prompt 与 response 分列而不是预展平的文本字段：

```yaml
action:
  dataset: my-org/my-dataset
  prompt_column: instruction
  response_column: output
  system_column: system         # 可选
  output_dir: ./output/sft-lora-unsloth
```

驱动通过 `dataset.map` 构建规范的 `messages` 列，然后经由 tokenizer 的 chat template 路由。此路径同样需要 chat template。

### 与 datasets 组件串联

在一个 job 中预加载数据集并传给训练器：

```yaml
components:
  - id: alpaca
    type: datasets
    driver: huggingface
    action:
      method: load
      path: tatsu-lab/alpaca
      split: train

  - id: trainer
    type: model-trainer
    task: sft
    driver: unsloth
    model: TinyLlama/TinyLlama-1.1B-Chat-v1.0
    max_seq_length: 2048
    lora:
      rank: 16
    action:
      dataset: ${jobs.load-data.output}
      text_column: text
      output_dir: ./output/sft-lora-unsloth

workflow:
  jobs:
    - id: load-data
      component: alpaca
    - id: train
      component: trainer
      depends_on: [load-data]
```

## 故障排查

- **`Unsloth trainer requires 'lora' to be set`**：此后端不支持全量微调。请添加 `lora` 块或切换到 `driver: huggingface`。
- **`Unsloth trainer requires a CUDA device`**：`device` 必须为 `cuda`、`cuda:N` 或 `auto`。不支持 MPS 与 CPU。
- **显存不足（CUDA OOM）**：减小 `batch_size`（尝试 `1`），减小 component-level `max_seq_length`，或添加 `quantization: {type: nf4, compute_dtype: bfloat16}`。
- **首次运行时 Triton 编译错误**：Unsloth 针对您的 GPU JIT 编译 Triton 内核。编译输出缓存于 `~/.triton`，首次启动可能停顿 30-60 秒。
- **首次运行较慢**：TinyLlama（~2 GB）和 Alpaca（~50 MB）在首次启动时下载；后续运行复用缓存。
- **`chat_template is None` 错误**：切换到指令调优模型，或将 `text_column` 指向预展平的文本字段。

## 相关示例

- `examples/model-training-tasks/sft-lora/huggingface/` — 相同工作流的原生 HuggingFace 后端版本，用于在非 CUDA 硬件上做对比
- `examples/model-training-tasks/text-classification/huggingface/` — 使用 GLUE SST-2 的 BERT + LoRA 进行文本分类
- `examples/model-tasks/chat-completion/huggingface/` — 用预训练（或您微调后的）chat 模型进行推理

# SFT + LoRA 模型训练器示例

此示例演示如何使用 model-compose 的 `model-trainer` 组件（`sft` 任务 + HuggingFace 驱动）对因果语言模型进行微调。它在 TinyLlama-1.1B 上附加 LoRA 适配器，使用 Alpaca 指令数据集进行监督微调（SFT）。

## 概述

此工作流提供一个声明式的 SFT+LoRA 训练循环：

1. **HuggingFace Trainer**：以 `SFTConfig`（TRL 0.12+ API）封装 `trl.SFTTrainer`
2. **LoRA 适配器**：将 rank-16 LoRA 适配器附加到 `q_proj`/`k_proj`/`v_proj`/`o_proj`，仅训练约 1% 的参数
3. **自动模型配置**：首次运行时下载 TinyLlama 并缓存到 `~/.cache/huggingface/`
4. **指令数据集**：加载 `tatsu-lab/alpaca` 数据集并在其 `text` 列（预先展平的 instruction/response 提示）上训练
5. **检查点输出**：将训练后的 LoRA 适配器保存到 `output_dir` 并返回训练指标

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- 包含 `torch`、`transformers`、`datasets`、`peft`、`trl`、`accelerate` 的 Python 环境（由组件的 `_get_setup_requirements` 自动管理）
- 建议使用 **VRAM ≥ 8 GB** 的 GPU。仅 CPU 训练可运行，但在此数据集规模下每 epoch 需数小时
- **磁盘 ~5 GB** 用于 TinyLlama 权重与数据集缓存

### 为什么用 SFT + LoRA

- **SFT**（监督微调）是使用配对的 prompt/response 文本教基础 LM 遵循指令或适配领域的标准方法。
- **LoRA**（低秩自适应）针对每个注意力投影只训练一小对矩阵，而不是完整的权重矩阵。TinyLlama-1.1B 在 rank 16 下，可训练参数从 1.1B 降至约 4M，同时保留大部分微调收益。

### 环境配置

进入此示例目录：
```bash
cd examples/model-training-tasks/sft-lora/huggingface
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
   ls ./output/sft-lora
   # adapter_config.json  adapter_model.safetensors  tokenizer.json  ...
   ```

## 组件详情

### Model-Trainer 组件（默认）

- **Type**：`model-trainer`
- **Task**：`sft`
- **Driver**：`huggingface`
- **基础模型**：`TinyLlama/TinyLlama-1.1B-Chat-v1.0`
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

### "Fine-tune TinyLlama with SFT + LoRA" 工作流（默认）

**描述**：使用 LoRA 适配器在 Alpaca 指令数据集上对 TinyLlama-1.1B 进行监督微调，然后返回检查点目录和训练指标。

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `dataset` | string | 否 | `tatsu-lab/alpaca` | HuggingFace 数据集名称或本地路径 |
| `num_epochs` | int | 否 | `1` | 训练 epoch 数 |
| `batch_size` | int | 否 | `4` | 每设备训练批次大小 |
| `learning_rate` | float | 否 | `2e-4` | AdamW 初始学习率 |
| `output_dir` | string | 否 | `./output/sft-lora` | 训练后适配器的保存位置 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `output_dir` | string | 保存的 LoRA 适配器 + tokenizer 所在目录 |
| `train_loss` | float | 最终训练损失 |
| `metrics` | object | 完整的 `Trainer.train()` 指标（train_runtime、samples_per_second 等） |

## 系统要求

### 推荐配置

- **GPU**：VRAM ≥ 8 GB 的 NVIDIA GPU（RTX 3060 12GB、T4、A10 或更高）
- **RAM**：16 GB
- **磁盘**：模型 + 数据集缓存 + 检查点共 10 GB
- **CUDA**：11.8+ 与匹配的 PyTorch

### 仅 CPU

可运行但速度极慢（此数据集每 epoch 数小时）。仅建议以 `num_epochs: 1` 和小数据集切片对管线做冒烟测试。

## 定制

### 使用 QLoRA（4 位量化基础模型）

在有限 VRAM 上跑更大的模型时，在组件中添加 `quantization`。量化要求同时设置 `lora`（驱动会拒绝其他组合）。

```yaml
component:
  type: model-trainer
  task: sft
  driver: huggingface
  model: mistralai/Mistral-7B-Instruct-v0.3
  lora:
    rank: 8
    alpha: 16
  quantization:
    type: nf4
    compute_dtype: bfloat16
    double_quant: true
  action:
    dataset: HuggingFaceH4/ultrachat_200k
    text_column: messages       # UltraChat 提供对话式数据
    output_dir: ./output/qlora
```

注意：`messages` 路径要求 tokenizer 包含 `chat_template`。指令调优的检查点（`*-Instruct-*`、`*-chat`、`*-it`）自带；纯基础检查点没有，驱动会在训练开始时抛出 `ValueError` 拒绝。

### 使用 prompt/response 列

若数据集用 prompt 与 response 分列而不是预展平的文本字段：

```yaml
action:
  dataset: my-org/my-dataset
  prompt_column: instruction
  response_column: output
  system_column: system         # 可选
  output_dir: ./output/sft-lora
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
    driver: huggingface
    model: TinyLlama/TinyLlama-1.1B-Chat-v1.0
    lora:
      rank: 16
    action:
      dataset: ${jobs.load-data.output}
      text_column: text
      output_dir: ./output/sft-lora

workflow:
  jobs:
    - id: load-data
      component: alpaca
    - id: train
      component: trainer
      depends_on: [load-data]
```

## 故障排查

- **显存不足（CUDA OOM）**：减小 `batch_size`（尝试 `1`），启用 `gradient_checkpointing: true`（已启用），或切换到 QLoRA（`quantization.type: nf4`）。
- **`chat_template is None` 错误**：切换到指令调优模型，或将 `text_column` 指向预展平的文本字段。
- **首次运行较慢**：TinyLlama（~2 GB）和 Alpaca（~50 MB）在首次启动时下载；后续运行复用缓存。
- **`datasets` 版本不兼容**：驱动固定 `datasets>=2.14,<4.0` — 因为 TRL 0.13 的对话式自动检测在 datasets 4.0 上会失效。即使全局装了更新版本，model-compose 的隔离运行时也会安装固定版本。

## 相关示例

- `examples/model-training-tasks/text-classification/huggingface/` — 使用 GLUE SST-2 的 BERT + LoRA 进行文本分类
- `examples/model-training-tasks/sft-lora/unsloth/` — 相同工作流的 Unsloth fused CUDA 内核版（约 2 倍吞吐、约 30-70% VRAM 节省）
- `examples/model-tasks/chat-completion/huggingface/` — 用预训练（或您微调后的）chat 模型进行推理

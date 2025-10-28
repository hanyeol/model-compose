# 第9章：模型训练

> **⚠️ 开发状态**：此功能目前正在开发中。配置模式已定义，但训练执行服务尚未实现。未来版本将提供更新。

本章解释如何使用 model-compose 配置模型训练。

---

## 9.1 训练概述

### 9.1.1 支持的训练任务

model-compose 为以下训练任务提供配置：

- **SFT（监督微调）**：基于监督学习的微调
- **分类**：分类模型训练

### 9.1.2 训练组件结构

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft                      # 或 classification

    # LoRA 配置（可选）
    peft_adapter: lora
    lora_r: 8
    lora_alpha: 16

    # 训练参数
    learning_rate: 5e-5
    num_epochs: 3
    output_dir: ./trained-model
```

---

## 9.2 数据集准备

### 9.2.1 数据集组件概述

数据集组件提供准备训练数据的工具。

**支持的功能：**
- 从 HuggingFace Hub 加载数据集
- 从本地文件加载数据集
- 合并和转换数据集
- 行/列选择和过滤

### 9.2.2 加载 HuggingFace 数据集

**基本配置：**

```yaml
components:
  - id: dataset-loader
    type: datasets
    provider: huggingface
    path: tatsu-lab/alpaca          # HuggingFace Hub 路径
    split: train                    # train, test, validation 等
    fraction: 1.0                   # 数据比例 (0.0 ~ 1.0)
```

**高级配置：**

```yaml
components:
  - id: dataset-loader
    type: datasets
    provider: huggingface
    path: tatsu-lab/alpaca
    name: default                   # 数据集配置名称
    split: train
    fraction: 0.1                   # 仅使用 10%
    streaming: false                # 流式模式
    cache_dir: ./cache/datasets     # 缓存目录
    revision: main                  # 模型版本
    trust_remote_code: false        # 允许远程代码执行
    token: ${env.HF_TOKEN}          # HuggingFace 令牌
    shuffle: true                   # 打乱数据
```

**工作流示例：**

```yaml
workflows:
  - id: load-training-data
    jobs:
      - id: load
        component: dataset-loader
        input:
          path: ${input.dataset | tatsu-lab/alpaca}
          split: train
          fraction: 1.0
        output: ${output}
```

### 9.2.3 加载本地数据集

**JSON 文件：**

```yaml
components:
  - id: local-dataset
    type: datasets
    provider: local
    loader: json                    # json, csv, parquet, text
    data_files: ./data/train.json   # 文件路径
```

**CSV 文件：**

```yaml
components:
  - id: local-dataset
    type: datasets
    provider: local
    loader: csv
    data_files:
      - ./data/train.csv
      - ./data/validation.csv
```

**目录：**

```yaml
components:
  - id: local-dataset
    type: datasets
    provider: local
    loader: json
    data_dir: ./data/training       # 目录中的所有 JSON 文件
```

### 9.2.4 数据集操作

**合并数据集：**

```yaml
workflows:
  - id: merge-datasets
    jobs:
      - id: load-first
        component: dataset-loader
        input:
          path: tatsu-lab/alpaca
          split: train

      - id: load-second
        component: dataset-loader
        input:
          path: yahma/alpaca-cleaned
          split: train

      - id: concat
        component: dataset-ops
        method: concat
        input:
          datasets:
            - ${jobs.load-first.output}
            - ${jobs.load-second.output}
        depends_on: [ load-first, load-second ]
```

**列选择：**

```yaml
workflows:
  - id: select-columns
    jobs:
      - id: load
        component: dataset-loader
        input:
          path: tatsu-lab/alpaca
          split: train

      - id: select
        component: dataset-ops
        method: select
        input:
          dataset: ${jobs.load.output}
          axis: columns
          columns: [ instruction, input, output ]
        depends_on: [ load ]
```

**行选择：**

```yaml
workflows:
  - id: select-rows
    jobs:
      - id: load
        component: dataset-loader
        input:
          path: tatsu-lab/alpaca
          split: train

      - id: select
        component: dataset-ops
        method: select
        input:
          dataset: ${jobs.load.output}
          axis: rows
          indices: [ 0, 1, 2, 3, 4 ]    # 前 5 行
        depends_on: [ load ]
```

**数据过滤：**

```yaml
components:
  - id: dataset-ops
    type: datasets
    method: filter
    dataset: ${input.dataset}
    condition: ${input.condition}    # 过滤条件
```

**数据映射：**

```yaml
components:
  - id: dataset-ops
    type: datasets
    method: map
    dataset: ${input.dataset}
    template: ${input.template}      # 数据转换模板
```

### 9.2.5 数据集格式

**SFT 训练的数据格式：**

1. **单文本列：**
```json
{
  "text": "完整的训练文本在这里..."
}
```

2. **提示-响应格式：**
```json
{
  "prompt": "用户问题或指令",
  "response": "模型的预期响应"
}
```

3. **指令格式（Alpaca 风格）：**
```json
{
  "instruction": "任务指令",
  "input": "可选上下文",
  "output": "预期输出"
}
```

4. **对话格式：**
```json
{
  "system": "你是一个有帮助的助手",
  "prompt": "用户消息",
  "response": "助手响应"
}
```

---

## 9.3 训练配置

### 9.3.1 基本训练配置

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    # 数据集
    dataset: ${input.dataset}

    # 学习率和批量大小
    learning_rate: 5e-5
    per_device_train_batch_size: 8
    per_device_eval_batch_size: 8
    num_epochs: 3

    # 输出目录
    output_dir: ./output/model
```

### 9.3.2 优化器配置

**支持的优化器：**

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft
    optimizer: adamw_torch          # 默认
```

**优化器类型：**

**AdamW 变体：**
- `adamw_torch`：PyTorch 默认 AdamW
- `adamw_torch_fused`：融合 AdamW（更快）
- `adamw_8bit`：8位 AdamW（内存高效）
- `adamw_bnb_8bit`：BitsAndBytes 8位 AdamW

**内存高效优化器：**
- `adafactor`：Adafactor（内存高效）
- `lomo`：LOMO（低内存优化）
- `galore_adamw`：GaLore AdamW
- `galore_adamw_8bit`：GaLore AdamW 8位

**高级优化器：**
- `grokadamw`：Grok AdamW
- `stableadamw`：稳定 AdamW
- `schedule_free_radamw`：无调度 RAdamW

**传统优化器：**
- `sgd`：随机梯度下降
- `adagrad`：Adagrad
- `rmsprop`：RMSprop

### 9.3.3 学习率调度器

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft
    lr_scheduler_type: linear       # 默认
    warmup_steps: 100
```

**调度器类型：**

- `linear`：线性衰减
- `cosine`：余弦衰减
- `cosine_with_restarts`：带重启的余弦
- `polynomial`：多项式衰减
- `constant`：恒定学习率
- `constant_with_warmup`：带预热的恒定
- `inverse_sqrt`：逆平方根衰减
- `reduce_lr_on_plateau`：平台期降低
- `cosine_with_min_lr`：带最小学习率的余弦
- `warmup_stable_decay`：预热-稳定-衰减

### 9.3.4 优化设置

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    # 权重衰减（正则化）
    weight_decay: 0.01

    # 梯度裁剪
    max_grad_norm: 1.0

    # 梯度累积
    gradient_accumulation_steps: 4
```

**梯度累积：**
- 有效批量大小 = `per_device_train_batch_size × gradient_accumulation_steps × num_gpus`
- 当内存不足时，减少批量大小并增加累积步数

### 9.3.5 评估和保存

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    # 评估
    eval_steps: 500                 # 每 500 步评估一次
    eval_dataset: ${input.eval_dataset}

    # 检查点保存
    save_steps: 500                 # 每 500 步保存一次

    # 日志记录
    logging_steps: 10               # 每 10 步记录一次
```

### 9.3.6 内存优化

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    # 梯度检查点
    gradient_checkpointing: true    # 节省内存，降低速度

    # 混合精度
    fp16: true                      # FP16 (V100, RTX 系列)
    # 或
    bf16: true                      # BF16（推荐用于 A100、H100）
```

**内存优化选项：**
- `gradient_checkpointing`：节省约 30-40% 内存，降低约 20% 速度
- `fp16`：FP16 混合精度，节省内存并提高速度
- `bf16`：BF16 混合精度，更好的数值稳定性（Ampere+ GPU）

### 9.3.7 可重现性设置

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft
    seed: 42                        # 随机种子
```

---

## 9.4 微调

### 9.4.1 SFT（监督微调）

**基本配置：**

```yaml
components:
  - id: sft-trainer
    type: model-trainer
    task: sft

    # 数据集
    dataset: ${input.dataset}
    eval_dataset: ${input.eval_dataset}

    # 数据格式
    text_column: text               # 单文本列
    max_seq_length: 512

    # 训练设置
    learning_rate: 5e-5
    num_epochs: 3
    per_device_train_batch_size: 4
    output_dir: ./output/sft-model
```

**提示-响应格式：**

```yaml
components:
  - id: sft-trainer
    type: model-trainer
    task: sft

    dataset: ${input.dataset}

    # 对话格式
    prompt_column: prompt
    response_column: response
    system_column: system           # 可选

    max_seq_length: 1024
```

**数据验证：**
- 需要 `text_column` 或 `prompt_column` + `response_column`
- 如果两者都指定则报错

### 9.4.2 序列打包

```yaml
components:
  - id: sft-trainer
    type: model-trainer
    task: sft

    dataset: ${input.dataset}
    text_column: text

    # 序列打包
    packing: true                   # 将短样本组合成一个序列
    max_seq_length: 512
```

**打包优势：**
- 提高许多短样本的训练效率
- 增加 GPU 利用率
- 减少训练时间

**打包劣势：**
- 样本边界可能不清楚
- 可能降低某些任务的性能

---

## 9.5 LoRA 训练

### 9.5.1 LoRA 概述

LoRA（低秩适应）是一种高效微调大型模型的技术。

**优势：**
- 大幅减少可训练参数（<1%）
- 减少内存使用
- 更快的训练
- 可以将多个 LoRA 适配器应用于一个基础模型

### 9.5.2 基本 LoRA 配置

```yaml
components:
  - id: lora-trainer
    type: model-trainer
    task: sft

    # 启用 LoRA
    peft_adapter: lora

    # LoRA 超参数
    lora_r: 8                       # LoRA 秩（越低越节省内存）
    lora_alpha: 16                  # LoRA 缩放（通常是 r 的 2 倍）
    lora_dropout: 0.05              # Dropout 率

    # 数据集和训练设置
    dataset: ${input.dataset}
    learning_rate: 1e-4             # LoRA 通常使用更高的学习率
    num_epochs: 3
    output_dir: ./output/lora-adapter
```

### 9.5.3 目标模块配置

```yaml
components:
  - id: lora-trainer
    type: model-trainer
    task: sft
    peft_adapter: lora

    # 指定目标模块
    lora_target_modules:
      - q_proj                      # 查询投影
      - v_proj                      # 值投影
      - k_proj                      # 键投影
      - o_proj                      # 输出投影

    lora_r: 16
    lora_alpha: 32
```

**常见目标模块：**
- **Transformer 注意力**：`q_proj`、`k_proj`、`v_proj`、`o_proj`
- **MLP**：`gate_proj`、`up_proj`、`down_proj`
- **嵌入**：`embed_tokens`、`lm_head`

**目标模块选择指南：**
- 更多模块：更好的性能，更多内存
- 仅注意力：内存高效，大多数情况下足够
- 注意力 + MLP：更好的性能，更多内存

### 9.5.4 LoRA 偏置配置

```yaml
components:
  - id: lora-trainer
    type: model-trainer
    task: sft
    peft_adapter: lora

    lora_bias: none                 # none, all, lora_only
```

**偏置选项：**
- `none`：不训练偏置（默认，内存高效）
- `all`：训练所有偏置
- `lora_only`：仅训练 LoRA 层偏置

### 9.5.5 QLoRA（量化 LoRA）

QLoRA 将 LoRA 应用于量化的基础模型，以实现更多内存节省。

```yaml
components:
  - id: qlora-trainer
    type: model-trainer
    task: sft

    # LoRA 设置
    peft_adapter: lora
    lora_r: 64
    lora_alpha: 16

    # 4 位量化
    quantization: nf4               # int4 或 nf4
    bnb_4bit_compute_dtype: bfloat16
    bnb_4bit_use_double_quant: true

    # 数据集和训练
    dataset: ${input.dataset}
    learning_rate: 2e-4
    num_epochs: 1
    per_device_train_batch_size: 4
    gradient_accumulation_steps: 4

    # 内存优化
    gradient_checkpointing: true
    bf16: true
```

**量化选项：**
- `nf4`：NormalFloat 4 位（推荐）
- `int4`：4 位整数量化
- `int8`：8 位整数量化

**QLoRA 推荐设置：**
- 更高的 `lora_r`（64+）
- 更高的学习率（2e-4）
- BF16 混合精度
- 梯度检查点

### 9.5.6 LoRA 超参数指南

| 参数 | 低值 | 高值 | 推荐用途 |
|---------|---------|---------|-----------|
| `lora_r` | 4-8 | 64-128 | 标准：8-16，QLoRA：64 |
| `lora_alpha` | 8-16 | 32-64 | 通常是 r 的 2 倍 |
| `lora_dropout` | 0.0 | 0.1 | 小数据集：0.05-0.1 |
| `learning_rate` | 1e-5 | 5e-4 | 完整 FT：5e-5，LoRA：1e-4 |

---

## 9.6 训练监控

### 9.6.1 日志配置

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    # 日志记录
    logging_steps: 10               # 日志输出间隔
    eval_steps: 100                 # 评估间隔
```

**预期日志输出：**
- 训练损失
- 学习率
- 梯度范数
- 训练速度（样本/秒）

### 9.6.2 评估指标

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    eval_dataset: ${input.eval_dataset}
    eval_steps: 500
```

**预期评估指标：**
- 评估损失
- 困惑度
- 特定任务指标（分类准确率等）

### 9.6.3 TensorBoard 集成（即将推出）

TensorBoard 集成将在未来版本中添加：

```bash
# 预期用法
tensorboard --logdir ./output/runs
```

---

## 9.7 检查点管理

### 9.7.1 检查点保存

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    output_dir: ./output/checkpoints
    save_steps: 500                 # 每 500 步保存一次
```

**预期目录结构：**
```
output/checkpoints/
  ├── checkpoint-500/
  │   ├── model.safetensors
  │   ├── config.json
  │   ├── training_args.bin
  │   └── optimizer.pt
  ├── checkpoint-1000/
  └── checkpoint-1500/
```

### 9.7.2 从检查点恢复

将在未来版本中支持：

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    resume_from_checkpoint: ./output/checkpoints/checkpoint-1000
```

### 9.7.3 保存最终模型

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    output_dir: ./output/final-model
```

**预期最终模型结构：**
```
output/final-model/
  ├── model.safetensors
  ├── config.json
  ├── tokenizer.json
  ├── tokenizer_config.json
  └── special_tokens_map.json
```

---

## 9.8 实际示例

### 9.8.1 Alpaca 风格微调

```yaml
components:
  - id: alpaca-loader
    type: datasets
    provider: huggingface
    path: tatsu-lab/alpaca
    split: train

  - id: alpaca-trainer
    type: model-trainer
    task: sft

    # LoRA 设置
    peft_adapter: lora
    lora_r: 16
    lora_alpha: 32
    lora_dropout: 0.05
    lora_target_modules: [q_proj, v_proj]

    # 数据设置
    dataset: ${input.dataset}
    prompt_column: instruction
    response_column: output
    max_seq_length: 512

    # 训练设置
    learning_rate: 1e-4
    num_epochs: 3
    per_device_train_batch_size: 4
    gradient_accumulation_steps: 4

    # 优化
    gradient_checkpointing: true
    fp16: true

    output_dir: ./output/alpaca-lora

workflows:
  - id: train-alpaca
    jobs:
      - id: load-data
        component: alpaca-loader

      - id: train
        component: alpaca-trainer
        input:
          dataset: ${jobs.load-data.output}
        depends_on: [load-data]
```

### 9.8.2 使用 QLoRA 训练大型模型

```yaml
components:
  - id: qlora-trainer
    type: model-trainer
    task: sft

    # QLoRA 设置
    peft_adapter: lora
    lora_r: 64
    lora_alpha: 16
    quantization: nf4
    bnb_4bit_compute_dtype: bfloat16

    # 数据
    dataset: ${input.dataset}
    text_column: text
    max_seq_length: 2048
    packing: true

    # 训练
    learning_rate: 2e-4
    num_epochs: 1
    per_device_train_batch_size: 1
    gradient_accumulation_steps: 16

    # 优化
    optimizer: adamw_8bit
    gradient_checkpointing: true
    bf16: true

    output_dir: ./output/qlora-model
```

### 9.8.3 自定义数据集准备和训练

```yaml
components:
  - id: local-data
    type: datasets
    provider: local
    loader: json
    data_files: ./data/custom_train.json

  - id: data-processor
    type: datasets
    method: map

  - id: custom-trainer
    type: model-trainer
    task: sft

    peft_adapter: lora
    lora_r: 8
    lora_alpha: 16

    dataset: ${input.dataset}
    prompt_column: user_input
    response_column: assistant_response

    learning_rate: 5e-5
    num_epochs: 5
    per_device_train_batch_size: 8

    output_dir: ./output/custom-model

workflows:
  - id: train-custom
    jobs:
      - id: load
        component: local-data

      - id: process
        component: data-processor
        input:
          dataset: ${jobs.load.output}
          template: ${input.template}
        depends_on: [load]

      - id: train
        component: custom-trainer
        input:
          dataset: ${jobs.process.output}
        depends_on: [process]
```

---

## 下一步

学习数据集准备后：

- **第 10 章**：外部服务集成 - 利用 API 服务
- **第 8 章**：使用本地 AI 模型 - 加载 LoRA 适配器和推理

当前可用功能：
- 数据集加载和操作（HuggingFace、本地文件）
- 数据集合并、过滤、选择
- 使用 LoRA 适配器进行推理（参见第 8 章）

待添加功能：
- 模型训练执行
- 检查点管理
- 训练监控和可视化

---

**下一章**：[10. 外部服务集成](./10-external-service-integration.md)

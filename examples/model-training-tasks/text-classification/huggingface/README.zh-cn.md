# 文本分类 + LoRA 模型训练器示例

此示例演示如何使用 model-compose 的 `model-trainer` 组件（`text-classification` 任务 + HuggingFace 驱动）微调一个序列分类器。它在 GLUE SST-2 上对 BERT-base 附加 LoRA 适配器，进行二分类情感分类（positive/negative）训练。

## 概述

此工作流提供一个声明式的 Classification+LoRA 训练循环：

1. **HuggingFace Trainer**：以 `TrainingArguments` 与 `AutoModelForSequenceClassification` 封装 `transformers.Trainer`
2. **LoRA 适配器**：将 rank-8 LoRA 适配器附加到 BERT 的 `query`/`value` 投影
3. **自动模型配置**：首次运行时下载 `bert-base-uncased`
4. **GLUE SST-2 数据集**：从 GLUE 加载 SST-2 情感数据集，在 `sentence` 列上训练
5. **安全的 Split 选择**：自动挑选 `validation` split 作为评估集（SST-2 的 `test` split 标签被 mask — 驱动会拒绝并 fallthrough）
6. **检查点输出**：将训练后的适配器保存到 `output_dir` 并返回训练指标

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- 包含 `torch`、`transformers`、`datasets`、`peft`、`accelerate` 的 Python 环境（由组件的 `_get_setup_requirements` 自动管理）
- 建议使用 **VRAM ≥ 4 GB** 的 GPU，但此示例足够小，可在 **CPU 上约 30 分钟** 完成 3 个 epoch。
- **磁盘 ~1 GB** 用于 BERT 权重与 SST-2 数据集缓存

### 为什么用 Classification + LoRA

- **序列分类** 是情感、主题或意图标注的标准任务。`AutoModelForSequenceClassification` 在基础 transformer 之上加一个线性分类头。
- rank 8 的 **LoRA** 只让 BERT 约 0.3% 的参数可训练，同时在 GLUE 规模的任务上通常能匹配全量微调的准确度。
- **SST-2** 是标准的二分类情感基准（67k 训练样本）。在 batch size 32 下 1-3 个 epoch 即可收敛。

### 环境配置

进入此示例目录：
```bash
cd examples/model-training-tasks/text-classification/huggingface
```

无需额外的环境配置。

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
         "num_epochs": 3,
         "batch_size": 32,
         "learning_rate": 5e-5
       }
     }'
   ```

   **使用 Web UI：**
   - 打开 http://localhost:8081
   - 按需调整 `num_epochs`、`batch_size`、`learning_rate`
   - 点击 "Run Workflow"

   **使用 CLI：**
   ```bash
   model-compose run --input '{"num_epochs": 3}'
   ```

3. **查看训练后的适配器：**
   ```bash
   ls ./output/classification
   # adapter_config.json  adapter_model.safetensors  tokenizer_config.json  ...
   ```

## 组件详情

### Model-Trainer 组件（默认）

- **Type**：`model-trainer`
- **Task**：`text-classification`
- **Driver**：`huggingface`
- **基础模型**：`bert-base-uncased`
- **LoRA 配置**：
  - rank：8
  - alpha：16
  - dropout：0.05
  - target_modules：`query`、`value`（BERT self-attention 命名）
- **Label Names**：`[negative, positive]`（`id2label` / `label2id` 会一起保存到检查点）

### 模型信息：bert-base-uncased

- **开发者**：Google Research
- **参数量**：1.1 亿
- **类型**：encoder-only 双向 transformer
- **许可证**：Apache 2.0
- **LoRA 后可训练参数**：约 300K（约 0.3%）

## 工作流详情

### "Fine-tune BERT for SST-2 Sentiment Classification" 工作流（默认）

**描述**：使用 LoRA 适配器在 GLUE SST-2 上对 BERT-base 进行二分类情感分类微调，然后返回检查点目录和训练指标。

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `dataset_path` | string | 否 | `stanfordnlp/sst2` | HuggingFace 数据集 repo id。对多 config 的 repo（例如 `nyu-mll/glue`）还需设置 `dataset_name` |
| `dataset_name` | string | 否 | *(未设置)* | 多 config repo 的 config 名（例如 `nyu-mll/glue` 下的 `sst2`、`mrpc`、`cola`） |
| `text_column` | string | 否 | `sentence` | 输入文本所在列 |
| `label_column` | string | 否 | `label` | 整数类别标签所在列 |
| `label_names` | list | 否 | `["negative", "positive"]` | 按 id 顺序的人类可读类别名。长度必须与数据集中的类别数一致 |
| `num_epochs` | int | 否 | `3` | 训练 epoch 数 |
| `batch_size` | int | 否 | `32` | 每设备训练批次大小 |
| `learning_rate` | float | 否 | `5e-5` | AdamW 初始学习率 |
| `output_dir` | string | 否 | `./output/classification` | 训练后适配器的保存位置 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `output_dir` | string | 保存的 LoRA 适配器 + tokenizer 所在目录 |
| `train_loss` | float | 最终训练损失 |
| `metrics` | object | 完整的 `Trainer.train()` 指标（train_runtime、samples_per_second 等） |

## 标签处理

驱动按以下优先级解析标签列表：

1. **action config 中显式的 `label_names`**（本例使用 `[negative, positive]`）
2. **数据集标签 feature 的 `ClassLabel.names`**（SST-2 也带有）
3. **对该 split 中不同值的扫描**

解析出的 `num_labels` 与 `id2label` / `label2id` 映射会传给 `AutoModelForSequenceClassification.from_pretrained`，使分类头具有正确的输出尺寸，并让保存的检查点能把预测解码回可读标签。

若数据集的原始标签值不连续（例如 `{1, 2}` 而不是 `{0, 1}`），驱动会自动构建 `label_remap` 并在训练前重写标签。非整数标签（float、string、None）不会被静默强制转换，而是在训练开始时被显式拒绝。

## Split 处理

`_load_datasets` 按 `validation` → `eval` → `test` 顺序挑选评估 split。GLUE SST-2 的 `test` split 所有标签被 mask 为 `-1`，驱动会检测到并 fallthrough 到 `validation`。这意味着：

- 使用 `path: nyu-mll/glue, name: sst2`，训练自动用 `train`，评估自动用 `validation`。
- 若所有候选都没有可用标签，会跳过评估，而不是 fallback 到任意 split。

## 系统要求

### 最低配置

- **CPU**：任何现代多核 CPU
- **RAM**：4 GB
- **磁盘**：2 GB
- **训练时间**：CPU 上 3 epoch 约 30 分钟（Apple Silicon：约 15 分钟）

### 推荐配置

- **GPU**：任何 VRAM ≥ 4 GB 的 CUDA GPU（此为极小工作负载）
- **训练时间**：RTX 3060 上 3 epoch 约 5 分钟

## 定制

### 使用不同的分类数据集

所有数据集形态的输入都可在运行时覆写 — 无需编辑 YAML。

CoLA（语法可接受性，2 类，位于 `nyu-mll/glue` 多 config repo 下）：

```bash
model-compose run --input '{
  "dataset_path": "nyu-mll/glue",
  "dataset_name": "cola",
  "text_column": "sentence",
  "label_names": ["unacceptable", "acceptable"]
}'
```

AG News（4 类新闻主题，单 config repo）：

```bash
model-compose run --input '{
  "dataset_path": "ag_news",
  "text_column": "text",
  "label_names": ["world", "sports", "business", "sci-tech"]
}'
```

### 使用 QLoRA（4 位量化基础模型）

对于更大的 encoder，如 `deberta-v3-large`：

```yaml
component:
  type: model-trainer
  task: text-classification
  driver: huggingface
  model: microsoft/deberta-v3-large
  lora:
    rank: 8
    alpha: 16
    target_modules: [query_proj, value_proj]
  quantization:
    type: nf4
    compute_dtype: bfloat16
  action:
    dataset: ${jobs.load-dataset.output}
    text_column: sentence
    label_names: [negative, positive]
```

注意：量化要求同时设置 `lora`（驱动会拒绝其他组合）。

### 与 datasets 组件串联

在一个 job 中预加载并预打乱数据集，再传给训练器：

```yaml
components:
  - id: sst2
    type: datasets
    driver: huggingface
    action:
      method: load
      path: glue
      name: sst2
      shuffle: true

  - id: trainer
    type: model-trainer
    task: text-classification
    driver: huggingface
    model: bert-base-uncased
    lora:
      rank: 8
      target_modules: [query, value]
    action:
      dataset: ${jobs.load-data.output}
      text_column: sentence
      label_names: [negative, positive]
      output_dir: ./output/classification

workflow:
  jobs:
    - id: load-data
      component: sst2
    - id: train
      component: trainer
      depends_on: [load-data]
```

## 故障排查

- **`num_labels` 不匹配错误**：数据集中不同标签数与声明的不同。移除 `label_names` 让驱动自动检测，或修正列表。
- **非整数标签被拒**：驱动拒绝 float/bool/string 标签 — 因为 `int(0.8)` 会静默塌陷为 0。请在训练前对标签做分桶或类型转换。
- **CPU 上训练缓慢**：预期行为 — BERT 的 CPU 推理尚可，但 batch 32 的训练很重。减小 `batch_size` 或使用 GPU。
- **`datasets` 版本不兼容**：驱动固定 `datasets>=2.14,<4.0`。即使全局装了更新版本，model-compose 的隔离运行时也会安装固定版本。

## 使用训练后的分类器

训练后，用一个 `text-classification` 任务的 `model` 组件加载适配器：

```yaml
component:
  type: model
  task: text-classification
  model: bert-base-uncased
  peft_adapters:
    - type: lora
      model: ./output/classification
  action:
    text: ${input.text}
```

由于适配器检查点保存了 `id2label`，输出会直接是 `"positive"` / `"negative"` 而不是 `0` / `1`。

## 相关示例

- `examples/model-training-tasks/sft-lora/huggingface/` — 在 Alpaca 指令数据集上的 TinyLlama SFT+LoRA
- `examples/model-tasks/text-classification/` — 用预训练（或您微调后的）分类器进行推理

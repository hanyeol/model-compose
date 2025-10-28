# 第8章：使用本地 AI 模型

本章介绍如何在 model-compose 中使用本地 AI 模型。

---

## 8.1 本地模型概述

### 什么是本地模型？

本地模型是直接在您的系统上运行的 AI 模型，无需外部 API。model-compose 支持各种驱动程序和模型格式，提供灵活的模型执行环境。

### 支持的模型驱动

model-compose 支持以下模型驱动：

| 驱动 | 描述 | 主要用例 |
|--------|-------------|-------------------|
| `huggingface` | HuggingFace transformers | 通用推理，最广泛的模型支持 |
| `unsloth` | Unsloth 优化模型 | 快速微调，内存高效训练 |
| `vllm` | vLLM 推理引擎 | 高性能 LLM 服务，生产部署 |
| `llamacpp` | llama.cpp 引擎 | CPU 推理，GGUF 格式，低资源环境 |
| `custom` | 自定义实现 | 特殊模型，自定义逻辑 |

### 支持的模型格式

支持各种模型格式：

| 格式 | 描述 | 兼容驱动 |
|--------|-------------|-------------------|
| `pytorch` | PyTorch 默认格式 (.bin, .pt) | huggingface, unsloth |
| `safetensors` | 安全张量存储格式 | huggingface, unsloth |
| `onnx` | 优化的跨平台格式 | custom |
| `gguf` | llama.cpp 量化格式 | llamacpp |
| `tensorrt` | NVIDIA TensorRT 优化 | custom |

### 本地模型的优缺点

**优点：**
- **节省成本**：无 API 调用费用
- **隐私**：数据不会离开您的系统
- **离线执行**：无需互联网连接
- **定制**：应用微调、LoRA 适配器
- **低延迟**：无网络延迟（取决于本地硬件）

**缺点：**
- **硬件要求**：需要 GPU 内存和计算能力
- **模型大小**：需要下载和存储大型模型文件
- **配置复杂性**：环境设置、依赖管理
- **性能限制**：大型模型需要高端 GPU

### 基本用法

**简单模型加载（HuggingFace）**
```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-7b-hf
  # 默认驱动是 huggingface
```

**指定驱动**
```yaml
component:
  type: model
  task: text-generation
  driver: unsloth  # 使用 Unsloth 驱动
  model: unsloth/llama-2-7b-bnb-4bit
```

**加载本地文件**
```yaml
component:
  type: model
  task: text-generation
  model:
    provider: local
    path: /path/to/model
    format: pytorch
```

**GGUF 格式**
```yaml
component:
  type: model
  task: text-generation
  driver: llamacpp
  model:
    provider: local
    path: /models/llama-2-7b-chat.Q4_K_M.gguf
    format: gguf
```

---

## 8.2 模型安装和设置

### 指定模型源

model-compose 可以通过两个提供者加载模型：

#### 1. HuggingFace Hub (provider: huggingface)

**简单方法（字符串）**
```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-7b-hf
  # 自动从 HuggingFace Hub 加载
```

**详细配置**
```yaml
component:
  type: model
  task: text-generation
  model:
    provider: huggingface
    repository: meta-llama/Llama-2-7b-hf
    revision: main                  # 分支或提交哈希
    filename: pytorch_model.bin     # 特定文件
    cache_dir: /custom/cache        # 缓存目录
    local_files_only: false         # 仅使用本地缓存
    token: ${env.HUGGINGFACE_TOKEN} # 私有模型令牌
```

**HuggingFace 配置字段：**
- `repository`：HuggingFace 模型仓库（必需）
- `revision`：模型版本或分支（默认：`main`）
- `filename`：仓库中的特定文件（可选）
- `cache_dir`：模型文件缓存目录（默认：`~/.cache/huggingface/`）
- `local_files_only`：仅使用本地缓存（默认：`false`）
- `token`：私有模型访问令牌（可选）

#### 2. 本地文件 (provider: local)

**简单方法（路径字符串）**
```yaml
component:
  type: model
  task: text-generation
  model: /path/to/model
  # 自动识别为本地路径
```

**详细配置**
```yaml
component:
  type: model
  task: text-generation
  model:
    provider: local
    path: /path/to/model
    format: pytorch  # pytorch, safetensors, onnx, gguf, tensorrt
```

**本地配置字段：**
- `path`：模型文件或目录路径（必需）
- `format`：模型文件格式（默认：`pytorch`）

**本地路径识别规则：**

以这些模式开头的字符串会自动识别为本地路径：
- 绝对路径：`/path/to/model`
- 相对路径：`./model`、`../model`
- 主目录：`~/models/model`
- Windows 驱动器：`C:\models\model`

其他的识别为 HuggingFace Hub 仓库：
- `meta-llama/Llama-2-7b-hf`
- `gpt2`
- `username/custom-model`

### HuggingFace 模型下载

模型在首次运行时自动下载，所需包会自动安装：

```yaml
component:
  type: model
  task: chat-completion
  model: meta-llama/Llama-2-7b-chat-hf
  # 首次运行时下载到 ~/.cache/huggingface/
```

手动下载：
```bash
# 使用 HuggingFace CLI 预下载
pip install huggingface-hub
huggingface-cli download meta-llama/Llama-2-7b-chat-hf
```

### 访问私有模型

```yaml
component:
  type: model
  task: text-generation
  model:
    provider: huggingface
    repository: meta-llama/Llama-2-7b-hf
    token: ${env.HUGGINGFACE_TOKEN}
```

环境变量设置：
```bash
export HUGGINGFACE_TOKEN=hf_your_token_here
model-compose up
```

### 使用特定模型版本

```yaml
component:
  type: model
  task: text-generation
  model:
    provider: huggingface
    repository: meta-llama/Llama-2-7b-hf
    revision: v1.0  # 特定标签
    # 或提交哈希：revision: a1b2c3d4
```

### 离线模式

```yaml
component:
  type: model
  task: text-generation
  model:
    provider: huggingface
    repository: gpt2
    local_files_only: true  # 仅从本地缓存加载
```

---

## 8.3 支持的任务类型

model-compose 支持以下任务类型：

| 任务 | 描述 | 主要用例 |
|------|-------------|-------------------|
| `text-generation` | 文本生成 | 故事写作、代码生成 |
| `chat-completion` | 对话补全 | 聊天机器人、助手 |
| `text-classification` | 文本分类 | 情感分析、主题分类 |
| `text-embedding` | 文本嵌入 | 语义搜索、RAG |
| `image-to-text` | 图像描述 | 图像描述、VQA |
| `image-generation` | 图像生成 | 文本到图像转换 |
| `image-upscale` | 图像放大 | 分辨率增强 |
| `face-embedding` | 人脸嵌入 | 人脸识别、比较 |

### 8.3.1 text-generation

基于提示生成文本。

```yaml
component:
  type: model
  task: text-generation
  model: HuggingFaceTB/SmolLM3-3B
  text: ${input.prompt as text}
  params:
    max_output_length: 32768
    temperature: 0.7
    top_p: 0.9
```

**关键参数：**
- `max_output_length`：生成的最大令牌数
- `temperature`：生成随机性（0.0~2.0，越低越确定）
- `top_p`：核采样阈值
- `top_k`：Top-K 采样
- `repetition_penalty`：重复惩罚（1.0~2.0）

### 8.3.2 chat-completion

处理对话消息。

```yaml
component:
  type: model
  task: chat-completion
  model: HuggingFaceTB/SmolLM3-3B
  messages:
    - role: system
      content: ${input.system_prompt}
    - role: user
      content: ${input.user_prompt}
  params:
    max_output_length: 2048
    temperature: 0.7
```

**消息格式：**
- `role`：`system`、`user`、`assistant`
- `content`：消息内容

### 8.3.3 text-classification

将文本分类到类别中。

```yaml
component:
  type: model
  task: text-classification
  model: distilbert-base-uncased-finetuned-sst-2-english
  text: ${input.text as text}
  output:
    label: ${result.label}
    score: ${result.score}
```

### 8.3.4 text-embedding

将文本转换为高维向量。

```yaml
component:
  type: model
  task: text-embedding
  model: sentence-transformers/all-MiniLM-L6-v2
  text: ${input.text as text}
  output:
    embedding: ${result.embedding}
```

使用示例（RAG 系统）：
```yaml
workflow:
  title: Document Search
  jobs:
    - id: embed-query
      component: embedder
      input:
        text: ${input.query}
      output:
        query_vector: ${result.embedding}

    - id: search
      component: vector-store
      action: search
      input:
        vector: ${jobs.embed-query.output.query_vector}
        top_k: 5
```

### 8.3.5 image-to-text

分析图像并生成文本。

```yaml
component:
  type: model
  task: image-to-text
  model: Salesforce/blip-image-captioning-large
  architecture: blip
  image: ${input.image as image}
  prompt: ${input.prompt as text}
```

**支持的架构：**
- `blip`：图像描述
- `git`：生成式图像到文本
- `vit-gpt2`：视觉转换器 + GPT-2

### 8.3.6 image-generation

从文本提示生成图像。

```yaml
component:
  type: model
  task: image-generation
  architecture: flux
  model: black-forest-labs/FLUX.1-dev
  prompt: ${input.prompt as text}
  params:
    width: 1024
    height: 1024
    num_inference_steps: 50
```

**支持的架构：**
- `flux`：FLUX 模型
- `sdxl`：Stable Diffusion XL
- `hunyuan`：HunyuanDiT

### 8.3.7 image-upscale

增强图像分辨率。

```yaml
component:
  type: model
  task: image-upscale
  architecture: real-esrgan
  model: RealESRGAN_x4plus
  image: ${input.image as image}
  params:
    scale: 4
```

**支持的架构：**
- `real-esrgan`：Real-ESRGAN
- `esrgan`：ESRGAN
- `swinir`：SwinIR
- `ldsr`：潜在扩散超分辨率

### 8.3.8 face-embedding

从人脸图像中提取特征向量。

```yaml
component:
  type: model
  task: face-embedding
  model: buffalo_l
  image: ${input.image as image}
```

---

## 8.4 模型配置（设备、精度、批量大小）

### 设备配置

```yaml
component:
  type: model
  task: text-generation
  model: gpt2
  device: cuda         # 'cuda', 'cpu', 'mps' (Apple Silicon)
  device_mode: single  # 'single', 'auto' (multi-GPU)
```

**设备选项：**
- `cuda`：NVIDIA GPU
- `cpu`：仅 CPU
- `mps`：Apple Silicon GPU (M1/M2/M3)

**设备模式：**
- `single`：单 GPU
- `auto`：跨多个 GPU 自动分布

多 GPU 示例：
```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-70b-hf
  device: cuda
  device_mode: auto  # 自动分布到多个 GPU
```

### 精度配置

```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-7b-hf
  precision: float16  # 'auto', 'float32', 'float16', 'bfloat16'
```

**精度选项：**
- `auto`：自动选择（GPU 使用 float16，CPU 使用 float32）
- `float32`：最高精度，最多内存使用
- `float16`：一半内存，更快推理（CUDA）
- `bfloat16`：float16 的替代方案，更稳定（现代 GPU）

精度比较：

| 精度 | 内存 | 速度 | 精度 | 推荐用途 |
|-----------|--------|-------|----------|-----------------|
| float32 | 100% | 基准 | 最高 | CPU，需要高精度 |
| float16 | 50% | 2倍快 | 略有降低 | CUDA GPU |
| bfloat16 | 50% | 2倍快 | 比 float16 更稳定 | 现代 GPU (A100, H100) |

### 量化

量化以减少内存并提高速度：

```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-7b-hf
  quantization: int8  # 'none', 'int8', 'int4', 'nf4'
```

**量化选项：**
- `none`：无量化（默认）
- `int8`：8位整数（需要 bitsandbytes）
- `int4`：4位整数（需要 bitsandbytes）
- `nf4`：4位 NormalFloat（用于 QLoRA）

### 批量大小

```yaml
component:
  type: model
  task: text-classification
  model: distilbert-base-uncased
  batch_size: 32  # 一次处理的输入数量
```

批量大小选择指南：
- **小批量（1-8）**：低延迟，实时推理
- **中批量（16-32）**：平衡吞吐量/延迟
- **大批量（64+）**：最大吞吐量，批量处理

### 低内存加载

```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-70b-hf
  low_cpu_mem_usage: true  # 最小化 CPU RAM 使用
  device: cuda
```

---

## 8.5 使用 LoRA/PEFT 适配器

LoRA（低秩适应）是一种通过添加小型适配器模块来将模型适应特定任务的技术，无需微调整个模型。

### 应用 LoRA 适配器

```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-7b-hf
  peft_adapters:
    - type: lora
      name: alpaca
      model: tloen/alpaca-lora-7b
      weight: 1.0
  text: ${input.prompt as text}
```

### 多个 LoRA 适配器

可以同时应用多个 LoRA 适配器：

```yaml
component:
  type: model
  task: text-generation
  model:
    provider: huggingface
    repository: meta-llama/Llama-2-7b-hf
    token: ${env.HUGGINGFACE_TOKEN}
  peft_adapters:
    - type: lora
      name: alpaca
      model: tloen/alpaca-lora-7b
      weight: 0.7
    - type: lora
      name: assistant
      model: plncmm/guanaco-lora-7b
      weight: 0.8
  text: ${input.prompt as text}
```

### 适配器权重

使用 `weight` 参数控制适配器影响：

```yaml
peft_adapters:
  - type: lora
    name: style-adapter
    model: user/style-lora
    weight: 0.5  # 50% 影响
```

- `weight: 0.0`：禁用适配器
- `weight: 0.5`：应用 50%
- `weight: 1.0`：应用 100%（默认）

### 本地 LoRA 适配器

使用本地文件系统中的适配器：

```yaml
peft_adapters:
  - type: lora
    name: custom-lora
    model:
      provider: local
      path: /path/to/lora/adapter
    weight: 1.0
```

### LoRA 用例

**1. 领域适应**
```yaml
# 医疗领域专用模型
peft_adapters:
  - type: lora
    name: medical
    model: medalpaca/medalpaca-lora-7b
    weight: 1.0
```

**2. 风格控制**
```yaml
# 结合多种写作风格
peft_adapters:
  - type: lora
    name: formal
    model: user/formal-writing-lora
    weight: 0.6
  - type: lora
    name: technical
    model: user/technical-lora
    weight: 0.4
```

**3. 多语言支持**
```yaml
# 增强韩语支持
peft_adapters:
  - type: lora
    name: korean
    model: beomi/llama-2-ko-7b-lora
    weight: 1.0
```

---

## 8.6 模型服务框架

对于大规模生产环境或高性能推理，可以使用专用的模型服务框架。

> **重要**：vLLM 和 Ollama 等模型服务框架使用本地模型，但通过 HTTP API 通过 `http-server` 或 `http-client` 组件访问，而不是 `model` 组件。这是因为单独的服务器进程加载和服务模型。

### vLLM

vLLM 是用于大型语言模型的高性能推理引擎。

#### vLLM 特性

- **PagedAttention**：内存高效的注意力机制
- **连续批处理**：高吞吐量
- **快速推理**：优化的 CUDA 内核
- **OpenAI 兼容 API**：轻松集成现有代码

#### vLLM 配置示例

```yaml
component:
  type: http-server
  manage:
    install:
      - bash
      - -c
      - |
        eval "$(pyenv init -)" &&
        (pyenv activate vllm 2>/dev/null || pyenv virtualenv $(python --version | cut -d' ' -f2) vllm) &&
        pyenv activate vllm &&
        pip install vllm
    start:
      - bash
      - -c
      - |
        eval "$(pyenv init -)" &&
        pyenv activate vllm &&
        python -m vllm.entrypoints.openai.api_server
          --model Qwen/Qwen2-7B-Instruct
          --port 8000
          --served-model-name qwen2-7b-instruct
          --max-model-len 2048
  port: 8000
  method: POST
  path: /v1/chat/completions
  headers:
    Content-Type: application/json
  body:
    model: qwen2-7b-instruct
    messages:
      - role: user
        content: ${input.prompt as text}
    max_tokens: 512
    temperature: ${input.temperature as number | 0.7}
    streaming: true
  stream_format: json
  output: ${response[].choices[0].delta.content}
```

#### vLLM 参数

**服务器参数：**
- `--model`：模型名称或路径
- `--port`：服务器端口
- `--host`：绑定主机
- `--served-model-name`：API 的模型名称
- `--max-model-len`：最大序列长度
- `--tensor-parallel-size`：张量并行（多 GPU）
- `--dtype`：数据类型（auto、float16、bfloat16）

**推理参数：**
- `max_tokens`：生成的最大令牌数
- `temperature`：生成随机性
- `top_p`：核采样
- `streaming`：启用流式响应

### Ollama

Ollama 是在本地运行大型语言模型的简单工具。

#### Ollama 特性

- **简易安装**：一键安装
- **模型库**：预优化模型
- **低门槛**：无需复杂配置
- **REST API**：简单的 HTTP 接口

#### Ollama 自动管理（http-server 组件）

当 model-compose 自动安装和运行 Ollama 时：

```yaml
component:
  type: http-server
  manage:
    install:
      - bash
      - -c
      - |
        # macOS/Linux
        curl -fsSL https://ollama.ai/install.sh | sh
        # 下载模型
        ollama pull llama2
    start: [ ollama, serve ]
  port: 11434
  method: POST
  path: /api/generate
  headers:
    Content-Type: application/json
  body:
    model: llama2
    prompt: ${input.prompt as text}
    stream: false
  output:
    response: ${response.response}
```

**流式示例：**

```yaml
component:
  type: http-server
  manage:
    start: [ ollama, serve ]
  port: 11434
  method: POST
  path: /api/generate
  body:
    model: llama2
    prompt: ${input.prompt as text}
    stream: true
  stream_format: json
  output: ${response[].response}
```

**聊天 API：**

```yaml
component:
  type: http-server
  manage:
    start: [ ollama, serve ]
  port: 11434
  method: POST
  path: /api/chat
  body:
    model: llama2
    messages: ${input.messages}
  output:
    message: ${response.message.content}
```

#### 使用现有 Ollama 服务器（http-client）

当 Ollama 服务器已经在运行时：

```yaml
component:
  type: http-client
  endpoint: http://localhost:11434/api/generate
  method: POST
  body:
    model: llama2
    prompt: ${input.prompt as text}
  output:
    response: ${response.response}
```

### TGI (Text Generation Inference)

HuggingFace 的生产级推理服务器。

```yaml
component:
  type: http-client
  endpoint: http://localhost:8080/generate
  method: POST
  headers:
    Content-Type: application/json
  body:
    inputs: ${input.prompt as text}
    parameters:
      max_new_tokens: 512
      temperature: 0.7
      top_p: 0.9
  output:
    generated_text: ${response.generated_text}
```

### 框架比较

| 框架 | 优点 | 缺点 | 推荐用途 |
|-----------|------|------|-----------------|
| **vLLM** | 最佳性能，高吞吐量 | 复杂设置，仅 CUDA | 生产，大规模服务 |
| **Ollama** | 易于安装，低门槛 | 有限的模型，有限的控制 | 开发，原型设计，个人使用 |
| **TGI** | HuggingFace 集成，稳定性 | 比 vLLM 慢 | 使用 HuggingFace 生态系统时 |
| **transformers** | 最大兼容性，定制 | 性能较低 | 研究，实验，自定义模型 |

---

## 8.7 性能优化技巧

### 1. 选择适当的精度

```yaml
# 使用 GPU
component:
  type: model
  model: large-model
  precision: float16  # 或 bfloat16（现代 GPU）
  device: cuda

# 仅 CPU
component:
  type: model
  model: small-model
  precision: float32  # float32 在 CPU 上更稳定
  device: cpu
```

### 2. 使用量化

```yaml
# 当内存有限时
component:
  type: model
  model: meta-llama/Llama-2-13b-hf
  quantization: int8  # ~50% 内存减少
  device: cuda
```

### 3. 适当的批量大小

```yaml
# 优化吞吐量
component:
  type: model
  task: text-classification
  model: bert-base
  batch_size: 32  # 根据 GPU 内存调整
```

### 4. 模型缓存

```yaml
# 缓存以重用模型
component:
  type: model
  model:
    provider: huggingface
    repository: gpt2
    cache_dir: /data/model-cache  # 使用快速 SSD
```

### 5. 使用多个 GPU

```yaml
# 模型并行
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-70b-hf
  device: cuda
  device_mode: auto  # 自动分布到多个 GPU
```

### 常见性能问题和解决方案

| 问题 | 原因 | 解决方案 |
|-------|-------|----------|
| 首次运行慢 | 模型下载、编译 | 预下载模型，预热 |
| OOM（内存不足） | 模型大于 GPU 内存 | 量化，降低精度，较小批量 |
| 低吞吐量 | 批量大小小 | 增加批量大小 |
| 高延迟 | 批量大小大 | 减小批量大小，实时处理 |
| 不稳定输出 | float16 精度问题 | 使用 bfloat16 或 float32 |

---

## 下一步

试试看：
- 测试来自 HuggingFace Hub 的各种模型
- 实验量化和精度设置
- 加载和合并 LoRA 适配器
- 使用批处理优化吞吐量

---

**下一章**：[9. 模型训练](./09-model-training.md)

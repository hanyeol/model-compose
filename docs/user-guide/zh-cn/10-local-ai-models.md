# 第10章：使用本地 AI 模型

本章介绍如何在 model-compose 中使用本地 AI 模型。

---

## 10.1 本地模型概述

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

## 10.2 模型安装和设置

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

## 10.3 支持的任务类型

model-compose 支持以下任务类型：

| 任务 | 描述 | 主要用例 |
|------|-------------|-------------------|
| `text-generation` | 文本生成 | 故事写作、代码生成 |
| `chat-completion` | 对话补全 | 聊天机器人、助手 |
| `text-to-text` | seq2seq 文本变换 | 翻译、摘要、改写 |
| `text-classification` | 文本分类 | 情感分析、主题分类 |
| `text-embedding` | 文本嵌入 | 语义搜索、RAG |
| `text-reranking` | 查询-文档评分 | 在 RAG 流水线中对检索结果重排序 |
| `typed-decision` | 带逐候选项概率的类型化分类 | 路由、策略校验、结构化分诊 |
| `image-to-text` | 图像描述 | 图像描述、VQA |
| `image-text-to-text` | 多模态图像 + 文本生成 | 视觉推理、多模态对话 |
| `image-embedding` | 图像嵌入 | 视觉检索、图像去重、聚类 |
| `video-embedding` | 视频嵌入 | 语义视频检索、去重、聚类 |
| `image-generation` | 图像生成 | 文本到图像转换 |
| `image-upscale` | 图像放大 | 分辨率增强 |
| `text-to-speech` | 文本转语音合成 | 语音生成、克隆、设计 |
| `speech-to-text` | 语音识别 | 转录、字幕 |
| `speaker-diarization` | 谁在什么时候说话 | 会议、访谈的逐说话人分段 |
| `voice-activity-detection` | 检测音频中的语音片段 | ASR 前的静音过滤、字幕分割 |
| `face-detection` | 人脸检测 | 在图像中定位人脸 |
| `pose-detection` | 姿态检测 | 关键点估计 |
| `object-detection` | 目标检测 | 使用类别标签和边界框检测目标 |
| `image-segmentation` | 图像分割 | 生成分区二值掩码（自动模式或框提示模式） |
| `text-to-video` | 从文本生成视频 | 由提示词驱动的短视频片段 |
| `image-to-video` | 从图像生成视频 | 让静态图像动起来，可选由提示词引导 |
| `video-to-video` | 从源片段变换视频 | 用提示词重新风格化片段（AnimateDiff），或用输入的姿态/表情驱动参考角色（Wan-Animate） |
| `image-to-3d` | 单图 3D 网格生成 | 从参考图像生成带纹理的 GLB 资产 |
| `face-embedding` | 人脸嵌入 | 人脸识别、比较 |
| `face-tracking` | 人脸追踪 | 在视频帧中追踪身份并归纳为时间码片段 |
| `pose-tracking` | 姿态追踪 | 在视频帧中按轨迹追踪人物（姿态），并归纳为时间码片段 |
| `object-tracking` | 目标追踪 | 在视频帧中按轨迹追踪目标，并归纳为时间码片段 |
| `shot-boundary-detection` | 镜头边界检测 | 检测视频中的硬切换，返回每个镜头的起止时间码 |
| `music-generation` | 音乐生成 | 音频/音乐合成 |
| `music-source-separation` | 音乐源分离 | 将混音拆分为人声 / 鼓 / 贝斯 / 其他音轨 |
| `music-transcription` | 音乐转录 | 将音频录音转换为 MIDI 和音符事件 |
| `music-beat-tracking` | 音乐节拍跟踪 | 检测音乐录音中的节拍和强拍位置 |
| `talking-head` | 肖像到视频的对口型 | 用驱动音频让静态肖像动起来（身份合成） |
| `lip-sync` | 视频到视频的对口型 | 将人脸视频的嘴部运动重新同步到新的音轨 |

### 10.3.1 text-generation

基于提示生成文本。

```yaml
component:
  type: model
  task: text-generation
  model: HuggingFaceTB/SmolLM3-3B
  action:
    prompt: ${input.prompt as text}
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

### 10.3.2 chat-completion

处理对话消息。

```yaml
component:
  type: model
  task: chat-completion
  model: HuggingFaceTB/SmolLM3-3B
  action:
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

**覆盖 chat 模板：**

在组件上设置 `chat_template` 可覆盖分词器默认的 Jinja 模板（适用于 `huggingface`、`vllm` 和 `llamacpp` 驱动）：

```yaml
component:
  type: model
  task: chat-completion
  model: HuggingFaceTB/SmolLM3-3B
  chat_template: |
    {%- for message in messages %}
    <|{{ message.role }}|>
    {{ message.content }}</s>
    {%- endfor %}
```

### 10.3.3 text-to-text

运行 seq2seq（encoder-decoder）变换，如翻译、摘要和改写。

```yaml
# 翻译（Helsinki-NLP）
component:
  type: model
  task: text-to-text
  driver: huggingface
  model: Helsinki-NLP/opus-mt-en-fr
  action:
    text: ${input.text as text}
```

```yaml
# 摘要（BART）
component:
  type: model
  task: text-to-text
  driver: huggingface
  architecture: bart
  model: facebook/bart-large-cnn
  action:
    text: ${input.document as text}
    params:
      max_output_length: 150
```

```yaml
# T5 系列（需要在输入文本中包含任务前缀）
component:
  type: model
  task: text-to-text
  driver: huggingface
  architecture: t5
  model: t5-base
  action:
    text: "summarize: ${input.document}"
```

**支持的架构：**
- `auto`（默认）：从模型自动推断
- `bart`：BART 系列 encoder-decoder 模型
- `t5`：T5 系列模型（需要在输入文本中携带任务前缀）

### 10.3.4 text-classification

将文本分类到类别中。

```yaml
component:
  type: model
  task: text-classification
  model: distilbert-base-uncased-finetuned-sst-2-english
  action:
    text: ${input.text as text}
    output:
      label: ${result.label}
      score: ${result.score}
```

### 10.3.5 text-embedding

将文本转换为高维向量。

```yaml
component:
  type: model
  task: text-embedding
  model: sentence-transformers/all-MiniLM-L6-v2
  action:
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

### 10.3.6 text-reranking

使用 cross-encoder 对每个 (query, document) 对进行评分，并按相关性排序返回文档。这是典型检索流水线的第二阶段：先由向量库拉取宽粒度候选集，再由 reranker 精修最优结果。

```yaml
component:
  type: model
  task: text-reranking
  model: BAAI/bge-reranker-v2-m3
  action:
    query: ${input.query}
    documents: ${input.candidates}
    top_k: 5
```

**关键参数：**
- `query`：查询字符串。传入列表可一次运行多个独立的重排任务。
- `documents`：候选文档。可为字符串，或与 `document_field: <field>` 搭配使用的对象。
- `top_k`：每个查询仅保留前 K 个结果。
- `score_threshold`：丢弃分数低于此值的结果。
- `return_documents`：为 `false` 时结果仅包含 `index` 和 `score`。

使用示例（RAG 重排阶段）：
```yaml
workflow:
  title: Reranked Document Search
  jobs:
    - id: embed-query
      component: embedder
      input:
        text: ${input.query}

    - id: retrieve
      component: vector-store
      action: search
      input:
        vector: ${jobs.embed-query.output}
        top_k: 50

    - id: rerank
      component: reranker
      input:
        query: ${input.query}
        candidates: ${jobs.retrieve.output}
        document_field: text
        top_k: 5
```

### 10.3.7 typed-decision

根据调用方提供的模式，为每个问题返回类型化答案，并附带逐候选项的概率。评分器直接读取答案 token 的 logits，因此输出保证是允许值之一 —— 没有自由格式生成、没有 JSON 解析。

**问题类型**（`schema` 中的每一项）：
- `noul` — 是/否。可选 `criteria: {true?: ..., false?: ...}` 用于细化两个选项的文本描述。
- `choice` — 从 N 个命名选项中选一个。`criteria` 是 `{name: description}` 映射。
- `score` — 按有序刻度打分。`criteria` 是级别描述的列表，索引 0 在前。结果是**期望级别**（浮点数），由跨级别的 softmax 平均得到。

支持三种系列（均使用 `driver: custom`）。每个组件挑选其中一个；如需组合，请运行多个组件。

```yaml
component:
  type: model
  task: typed-decision
  driver: custom
  family: laya                          # 'laya' | 'kev' | 'nimble'
  preset: multilingual                  # 仅 laya：'english' | 'multilingual'（默认）| 'typed-decisions'
  action:
    text: ${input.text}
    schema: ${input.schema}
    return_probabilities: true
```

**关键参数：**
- `text`：评分器判断的非结构化文本。传入列表可一次评分多个输入。
- `schema`：问题 ID 到问题规范的映射。每个规范包含 `type: noul | choice | score`、`instructions`，以及（`noul` 除外的）`criteria`。
- `return_probabilities`：在 `fields[qid].scores` 中为每个问题返回逐候选项分数。
- `return_logits`：返回每个问题 softmax 前的原始 logits（`nimble` 仅在 API 层暴露 logits）。

**结果结构**：`{ decision: { qid: value }, fields?: { qid: { scores: {...} } } }`。`noul` 解析为布尔值，`choice` 解析为获胜选项名，`score` 解析为期望级别。

**系列：**

- `laya`（Convai Innovations，[示例](../../examples/model-tasks/typed-decision-laya)）— 基于 ModernBERT/mmBERT 的非自回归评分器，带 RLCD 训练的决策头。捆绑三个检查点，通过 `preset` 选择：`english`（ModernBERT-large，512-token 上下文）、`multilingual`（mmBERT-base，100+ 语言，最多 1024 token —— 通过 `max_seq_length` 可扩展至 8192）以及 `typed-decisions`（在四个 typed-decisions 工作流上微调）。可在 CUDA、MPS（Apple Silicon）或 CPU 上运行。在 Linux+x86_64 上启用 `fast: true` 可使用 TileLang 融合 CUDA 内核。
- `kev`（Jared Palmer，[示例](../../examples/model-tasks/typed-decision-kev)）— LoRA 适配器、指针评分头与元数据的捆绑，架设在冻结的 Qwen3.5 基础模型之上（基础模型 ID 从检查点的 `head.pt` 读取，无需手动覆盖）。规格：0.8B / 4B / 9B。后端在 Apple Silicon 上自动选择 MLX，在 CUDA/CPU 上选择 Torch；`max_state_length` 与 `max_branch_length` 分别限制共享状态和每个问题分支的长度。
- `nimble`（Bespoke Labs，[示例](../../examples/model-tasks/typed-decision-nimble)）— 首次启动时将 LoRA 适配器合并到基础模型（默认 Qwen/Qwen3.5-9B），合并后的快照会被缓存。在 Apple Silicon 上需要 MLX，在 Linux 上需要支持 BF16 的 NVIDIA GPU；驱动会自动选择后端。

### 10.3.8 image-to-text

分析图像并生成文本。

```yaml
component:
  type: model
  task: image-to-text
  model: Salesforce/blip-image-captioning-large
  architecture: blip
  action:
    image: ${input.image as image}
    prompt: ${input.prompt as text}
```

**支持的架构：**
- `blip`：图像描述
- `git`：生成式图像到文本
- `vit-gpt2`：视觉转换器 + GPT-2

### 10.3.9 image-embedding

将图像编码为固定大小的向量，用于视觉相似度、图像去重和检索索引。

```yaml
component:
  type: model
  task: image-embedding
  driver: huggingface
  architecture: clip
  model: openai/clip-vit-base-patch32
  action:
    image: ${input.image as image}
    batch_size: 16
    params:
      normalize: true
```

**支持的架构：**
- `clip`：OpenAI CLIP — 通过 `get_image_features` 编码图像
- `siglip`：Google SigLIP — 通过 `get_image_features` 编码图像
- `dinov2`：Meta DINOv2 — 自监督编码器，使用 `params.pooling` 聚合
- `auto`：`AutoModel` 自动回退 — 若加载的模型公开 `get_image_features` 则走该路径，否则对 `last_hidden_state` 进行池化

CLIP 和 SigLIP 具有内置池化，因此 `params.pooling` 被忽略。DINOv2（以及 `auto` 加载了无投影头的模型时）通过 `params.pooling` 选择 `cls`（默认）、`mean` 或 `max`。

结果：每张图像返回一个向量（`List[float]`）。列表输入返回向量列表；异步流输入返回按序产出向量的异步迭代器。

### 10.3.10 video-embedding

将视频帧序列编码为单个固定大小的向量，适用于语义视频检索、去重或聚类。通常与 `video-frame-extractor` 搭配，先从源视频中采样帧。

```yaml
component:
  id: video-embed
  type: model
  task: video-embedding
  driver: huggingface
  architecture: xclip
  model: microsoft/xclip-base-patch32
  action:
    frames: ${input.frames}
    params:
      normalize: true
    output: ${result}
```

| 字段 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `frames` | image / list | **必需** | 一个视频的帧、帧列表、逐视频帧批次的列表，或帧批次的流 |
| `batch_size` | int | `1` | 每批处理的视频数量 |
| `params.normalize` | bool | `true` | 对输出向量做 L2 归一化 |

**支持的架构：**
- `xclip`：Microsoft X-CLIP（视频-文本对比；如 `microsoft/xclip-base-patch32`）。
- `videomae`：VideoMAE 掩码自编码器（如 `MCG-NJU/videomae-base`）。
- `auto`：从加载的模型配置自动推断。

结果形态：

```json
[0.021, -0.114, 0.087, ...]
```

典型流水线：`video-frame-extractor` → `video-embedding` → `vector-store` 进行检索。

### 10.3.11 image-generation

从文本提示生成图像。

```yaml
component:
  type: model
  task: image-generation
  architecture: flux
  model: black-forest-labs/FLUX.1-dev
  action:
    prompt: ${input.prompt as text}
    width: 1024
    height: 1024
    params:
      inference_steps: 50
```

**支持的架构：**
- `flux`：FLUX 模型
- `sdxl`：Stable Diffusion XL
- `hunyuan`：HunyuanDiT

### 10.3.12 image-upscale

增强图像分辨率。

```yaml
component:
  type: model
  task: image-upscale
  architecture: real-esrgan
  model: RealESRGAN_x4plus
  action:
    image: ${input.image as image}
    params:
      scale: 4
```

**支持的架构：**
- `real-esrgan`：Real-ESRGAN
- `esrgan`：ESRGAN
- `swinir`：SwinIR
- `ldsr`：潜在扩散超分辨率

### 10.3.13 text-to-speech

从文本合成语音音频。此任务使用 `driver: custom`，通过 `family` 字段选择模型系列，通过动作的 `method` 字段选择生成方式。支持七个系列：`qwen`、`kokoro`、`chatterbox`、`luxtts`、`tada`、`cosyvoice`、`fireredtts3`。

**可用方法：**

| 方法 | 描述 |
|------|------|
| `generate` | 使用预设语音合成，可选带风格控制 |
| `clone` | 从参考音频片段克隆语音 |
| `design` | 从自然语言描述创建新语音 |
| `edit` | 编辑现有音频（内容、语速、音调、音量） |

并非每个系列都实现所有方法 —— 请参见下方系列小节和[参考对照表](../reference/compose/components/model.md#text-to-speech)。

**公共 action 字段（所有系列）：**

| 字段 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `method` | string | **必需** | 生成方式：`generate`、`clone`、`design`、`edit` |
| `text` | string/array | **必需** | 要合成的文本（或文本列表）；`edit` 会忽略 |
| `language` | string | `null` | 文本语言；用于按语言条件化的系列 |
| `batch_size` | int | `1` | 每批处理的输入文本数量 |

#### 系列：`qwen`

阿里 Qwen3-TTS。三种方法均可用；选择匹配方法的检查点。

推荐检查点：

| 模型 | 方法 | 描述 |
|------|------|------|
| `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` | `generate` | 带风格控制的内置语音 |
| `Qwen/Qwen3-TTS-12Hz-1.7B-Base` | `clone` | 从参考音频克隆语音 |
| `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign` | `design` | 从描述设计语音 |

`generate` — 选择一个内置语音并可选添加风格指令：

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: qwen
  model: Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
  device: cuda:0
  action:
    method: generate
    text: ${input.text as text}
    voice: ${input.voice | vivian}
    instructions: ${input.instructions | ""}
```

`clone` — 从一段简短参考片段复现目标语音：

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: qwen
  model: Qwen/Qwen3-TTS-12Hz-1.7B-Base
  device: cuda:0
  action:
    method: clone
    text: ${input.text as text}
    reference_audio: ${input.reference_audio as audio}
    reference_text: ${input.reference_text as text}
```

`design` — 用自然语言描述所需语音：

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: qwen
  model: Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign
  device: cuda:0
  action:
    method: design
    text: ${input.text as text}
    instructions: ${input.instructions as text}
```

支持语言：英语、中文、日语、韩语、德语、法语、俄语、葡萄牙语、西班牙语、意大利语 —— 根据 `language` 的 ISO 639-1 前缀解析（例如 `ko`、`zh-CN`）。

#### 系列：`kokoro`

Kokoro TTS。轻量级、预设语音合成；仅支持 `generate`。

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: kokoro
  model: hexgrad/Kokoro-82M
  device: cuda:0
  action:
    method: generate
    text: ${input.text as text}
    voice: ${input.voice | af_heart}
    speed: ${input.speed | 1.0}
```

语音 ID 遵循 Kokoro 的 `<language><gender>_<name>` 约定（例如 `af_heart`、`af_bella`、`am_michael`、`bf_emma`）。支持语言：美式英语、英式英语、日语、普通话、西班牙语、法语、印地语、意大利语、巴西葡萄牙语。输出采样率：24 kHz。

#### 系列：`chatterbox`

Resemble AI Chatterbox。带表现力控制（`exaggeration`、`cfg_weight`、`temperature`）的预设合成和零样本克隆。

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: chatterbox
  model: ResembleAI/chatterbox
  device: cuda:0
  action:
    method: clone
    text: ${input.text as text}
    reference_audio: ${input.reference_audio as audio}
    exaggeration: 0.6
    cfg_weight: 0.5
    temperature: 0.8
```

如要使用预设合成，将 `method` 切换为 `generate` 并去掉 `reference_audio`。建议参考音频长度：5 秒或以上。

#### 系列：`luxtts`

LuxTTS。带精细流匹配控制的零样本克隆；仅支持 `clone`。

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: luxtts
  model: BeaverAI/luxtts-v1
  device: cuda:0
  action:
    method: clone
    text: ${input.text as text}
    reference_audio: ${input.reference_audio as audio}
    num_steps: 4
    guidance_scale: 3.0
    speed: 1.0
```

通过 `num_steps`（默认 `4`）和 `guidance_scale`（默认 `3.0`）在质量和速度之间权衡。输出采样率：48 kHz。在 CPU 上，线程数会自动限制。

#### 系列：`tada`

Hume TADA。零样本克隆；仅支持 `clone`。若省略 `reference_text`，TADA 会使用内置 ASR 转录参考片段 —— 仅支持英语。

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: tada
  model:
    repository: HumeAI/tada-v0.1
    allow_patterns: ["*.safetensors", "*.json", "*.txt", "*.bin", "*.model"]
  device: cuda:0
  action:
    method: clone
    text: ${input.text as text}
    reference_audio: ${input.reference_audio as audio}
    reference_text: ${input.reference_text | ""}
```

分词器默认使用无门控的 `unsloth/Llama-3.2-1B` 镜像；如需覆盖，请在组件级设置 `tokenizer` 字段。输出采样率：24 kHz。由于 Apple Silicon 上流匹配不稳定，MPS 会回退到 CPU。

#### 系列：`cosyvoice`

FunAudioLLM CosyVoice / CosyVoice2 / CosyVoice3。AutoModel 工厂会检查模型目录内的 `cosyvoice{,2,3}.yaml` 来选择正确版本。

首次启动时运行时会从 GitHub 下载并安装上游的 `cosyvoice` 与 `matcha` 包（锁定 commit）。不需要 `git` CLI，但首次运行可能耗时较长。

`generate` — 在 `CosyVoice-300M-SFT` 上使用内置说话人，或在 v2/v3 上使用预注册的零样本说话人：

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: cosyvoice
  model: FunAudioLLM/CosyVoice-300M-SFT
  device: cuda:0
  action:
    method: generate
    text: ${input.text as text}
    voice: ${input.voice}
```

`clone` — 带转录时走零样本，无转录时走跨语种（任意语言的参考）：

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: cosyvoice
  model: FunAudioLLM/CosyVoice2-0.5B
  device: cuda:0
  action:
    method: clone
    text: ${input.text as text}
    reference_audio: ${input.reference_audio as audio}
    reference_text: ${input.reference_text | ""}
```

`design` — 指令引导的语音设计（仅 CosyVoice2/3）：

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: cosyvoice
  model: FunAudioLLM/CosyVoice2-0.5B
  device: cuda:0
  action:
    method: design
    text: ${input.text as text}
    instructions: ${input.instructions as text}
    reference_audio: ${input.reference_audio as audio}
```

仅 CUDA 生效的加速开关：`load_jit`、`load_trt`、`load_vllm`、`fp16`。在 CPU 上会被静默忽略。

#### 系列：`fireredtts3`

FireRedTeam FireRedTTS3。两个预设共享同一系列：

- `preset: base` — 仅克隆，带语言条件化。
- `preset: instruct` — 克隆，加语音设计与音频编辑。

首次启动时运行时会从 GitHub 下载并安装上游的 `fireredtts3` 包（锁定 commit）。

在 `base` 预设上进行 `clone`：

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: fireredtts3
  preset: base
  model: FireRedTeam/FireRedTTS3
  device: cuda:0
  action:
    method: clone
    text: ${input.text as text}
    reference_audio: ${input.reference_audio as audio}
    reference_text: ${input.reference_text | ""}
    language: ${input.language | en}
```

在 `instruct` 预设上进行 `design` —— 描述目标语音：

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: fireredtts3
  preset: instruct
  model: FireRedTeam/FireRedTTS3-Instruct
  device: cuda:0
  action:
    method: design
    text: ${input.text as text}
    instructions: ${input.instructions as text}
```

在 `instruct` 预设上进行 `edit` —— `text` 字段会被忽略；仅由指令改写音频：

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: fireredtts3
  preset: instruct
  model: FireRedTeam/FireRedTTS3-Instruct
  device: cuda:0
  action:
    method: edit
    reference_audio: ${input.reference_audio as audio}
    instructions: ${input.instructions as text}
    mode: ${input.mode | semantic}
```

编辑模式：`semantic` 用于自由格式的内容编辑，`acoustic` 用于诸如 `adjust the speed to 1.2` 之类的模板指令。两个预设的输出采样率均为 24 kHz。在 `base` 预设上调用 `design`/`edit` 会抛出运行时错误。

### 10.3.14 speech-to-text

将音频转录为文本，可选带逐段或逐词时间戳。支持 HuggingFace transformers 后端（Whisper 系列）以及若干 `custom` 系列（faster-whisper、crisper-whisper、fun-asr、vibevoice）。

```yaml
component:
  id: transcriber
  type: model
  task: speech-to-text
  driver: custom
  family: faster-whisper
  model:
    provider: huggingface
    repository: Systran/faster-whisper-large-v3
  compute_type: float16
  action:
    audio: ${input.audio as audio}
    language: en
    return_timestamps: true
    timestamp_level: word
    output: ${result as json}
```

**公共 action 字段：**

| 字段 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `audio` | audio | **必需** | 输入音频文件、音频列表或 async 流 |
| `language` | string | `null` | 语言代码（`en`、`ko` ...）；未设置时在支持处触发自动检测 |
| `return_timestamps` | bool | `false` | 在结果中包含逐段时间戳 |
| `timestamp_level` | string | `segment` | `segment` 或 `word`；`word` 级需要后端支持 |
| `time_offset` | time / list | `null` | 加到每段时间戳上的偏移；标量广播，列表按音频配对 |
| `batch_size` | int | `1` | 每批处理的音频数量 |
| `streaming` | bool | `false` | 增量发出转录 chunk |

各系列的专属 action 字段包括：`faster-whisper` 与 HuggingFace `whisper` 驱动的 Whisper 风格解码参数（`num_beams`、`temperature`、`no_speech_threshold`, ...）；`crisper-whisper` 的风格/热词控制（`mode`、`hotwords`、`longform_strategy`, ...）；`vibevoice` 的采样 / beam / 上下文旋钮（`temperature`、`top_p`、`num_beams`、`context_info`）。Fun-ASR 在组件上配置 VAD 与标点（`voice_activity_detection`、`punctuation`）。

纯文本模式（默认）为每个输入返回一个字符串；带时间戳模式返回 `{ text, start_time, end_time }` 分段列表，当 `timestamp_level: word` 时还会附加 `words` 数组。

```json
[
  {
    "text": "Hello world",
    "start_time": 0.12,
    "end_time": 1.03,
    "words": [
      { "text": "Hello", "start_time": 0.12, "end_time": 0.44 },
      { "text": "world", "start_time": 0.46, "end_time": 1.03 }
    ]
  }
]
```

当 `streaming: true` 时，Whisper 系列后端会随解码进度以 token 级别流式输出 chunk —— `return_timestamps: false` 时是纯文本 chunk，开启时间戳时是带 `"type": "segment"` 的分段字典。VibeVoice 的流式检查点按 chunk 输出转录文本；离线检查点则将收集到的分段逐个重发（每个带 `"type": "segment"`），或在关闭时间戳时将整段转录作为单一字符串 chunk 输出。

#### 支持的系列

| 系列 | 后端 | 说明 |
|------|------|------|
| `faster-whisper` | [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) | CTranslate2 Whisper 运行时；支持 beam search、VAD、分块长音频 |
| `crisper-whisper` | [nyralabs/crisperwhisper](https://pypi.org/project/crisperwhisper/) | 逐词精准的 Whisper 变体。优先选择 `ct2` fork，否则回退到 `transformers`。尺寸简称（`large`、`turbo`、`medium`、`small` 及 `*_pro`）会解析到 `nyralabs/CrisperWhisper2.0_<size>` |
| `fun-asr` | [FunAudioLLM/FunASR](https://github.com/modelscope/FunASR) | 以中文为主的多语言 ASR，可选 VAD 与标点阶段。默认模型：`FunAudioLLM/Fun-ASR-MLT-Nano-2512` |
| `vibevoice` | [microsoft/VibeVoice](https://github.com/microsoft/VibeVoice) | 流式和离线 ASR 检查点。默认：`microsoft/VibeVoice-ASR-Streaming-1.5B`。在 10 种语言中自动检测语言 |

HuggingFace 的 `whisper` 驱动通过 `transformers` 运行原版 Whisper 检查点；当你需要 transformers 生态（LoRA 适配器、量化）而非 CT2 加速的 `faster-whisper` 时选它。

### 10.3.15 speaker-diarization

按说话人对音频文件分段，返回带起止时间和说话人标签的逐说话人语段。运行 `pyannote.audio` 说话人分割流水线。

```yaml
component:
  id: diarizer
  type: model
  task: speaker-diarization
  driver: custom
  family: pyannote
  model:
    provider: huggingface
    repository: pyannote/speaker-diarization-3.1
    token: ${env.HUGGINGFACE_TOKEN}
  action:
    audio: ${input.audio as audio}
    min_speaker_count: 2
    max_speaker_count: 4
    params:
      min_segment_duration: 250ms
      merge_gap: 500ms
    output: ${result as json}
```

| 字段 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `audio` | audio | **必需** | 输入音频文件、音频列表或 async 流 |
| `speaker_count` | int | `null` | 已知的精确说话人数量 |
| `min_speaker_count` | int | `null` | 考虑的说话人数量下限 |
| `max_speaker_count` | int | `null` | 考虑的说话人数量上限 |
| `batch_size` | int | `1` | 每批处理的音频数量 |
| `streaming` | bool | `false` | 以 async iterator 输出语段（伪流式：流水线需要先接收整段音频） |
| `params.min_segment_duration` | duration | `"0s"` | 丢弃短于此值的语段 |
| `params.merge_gap` | duration | `"0s"` | 在此间隔内合并同一说话人的相邻语段 |

Duration 字段接受 `"250ms"`、`"0.5s"` 或纯数字（秒）格式。

结果形态（按 `start_time` 排序、包含 `segments` 数组的逐音频 dict）：

```json
{
  "segments": [
    { "speaker": "SPEAKER_00", "start_time": 0.48,  "end_time": 3.72,  "confidence": 1.0 },
    { "speaker": "SPEAKER_01", "start_time": 3.90,  "end_time": 7.16,  "confidence": 1.0 },
    { "speaker": "SPEAKER_00", "start_time": 7.44,  "end_time": 12.02, "confidence": 1.0 }
  ]
}
```

`confidence` 固定为 `1.0` —— pyannote 不暴露逐语段置信度。pyannote 的说话人分割并非真正可流式：`streaming: true` 时会将相同的语段逐个重发以维持 `AsyncIterator` 契约，每个 chunk 在语段字段之外还带有 `"type": "segment"`。

默认的 `pyannote/speaker-diarization-3.1` 检查点在 HuggingFace 上受门控。请接受许可，并通过 `model.token`（或 `${env.HUGGINGFACE_TOKEN}`）传入访问令牌。

#### 支持的系列

| 系列 | 后端 | 说明 |
|------|------|------|
| `pyannote` | [pyannote/pyannote-audio](https://github.com/pyannote/pyannote-audio) | 运行任意 `pyannote.audio` 分割流水线；需要接受 HuggingFace 许可 |

### 10.3.16 voice-activity-detection

检测音频文件中的语音片段，返回每个片段的起止时间和置信度。静音区域从结果中省略。通常用作 speech-to-text 前的预处理步骤，以跳过静音并减少幻觉。

```yaml
component:
  type: model
  task: voice-activity-detection
  driver: custom
  family: silero
  device: cpu
  action:
    audio: ${input.audio as audio}
    sample_rate: 16000
    params:
      threshold: 0.5
      min_speech_duration: 250ms
      min_silence_duration: 500ms
      speech_padding_time: 100ms
```

| 字段 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `sample_rate` | int | `16000` | 目标采样率（16000 或 8000）；根据需要重采样 |
| `threshold` | float | `0.5` | 语音概率阈值（0.0 - 1.0）；越高越严格 |
| `min_speech_duration` | duration | `250ms` | 丢弃短于此值的语音块 |
| `min_silence_duration` | duration | `500ms` | 分割相邻块所需的静音时长 |
| `speech_padding_time` | duration | `100ms` | 为每个检测到的块两侧添加的填充 |

Duration 字段接受 `"250ms"`、`"0.5s"` 或纯数字（秒）格式。

结果形态（包含 `segments` 数组的逐音频 dict；省略静音区域）：

```json
{
  "segments": [
    { "start_time": 0.124, "end_time": 44.58,  "confidence": 0.916 },
    { "start_time": 47.07, "end_time": 150.02, "confidence": 0.937 }
  ]
}
```

当 `streaming: true` 时，每个输入的结果是一个 async iterator，每当一个语音片段被确认时便发出一个 chunk。每个 chunk 在 segment 字段之外还带有 `"type": "segment"`。

#### 支持的系列

| 系列 | 后端 | 说明 |
|------|------|------|
| `silero` | [snakers4/silero-vad](https://github.com/snakers4/silero-vad) (pip) | 轻量级 CNN (~1MB)；模型捆绑在 pip 包中 |

### 10.3.17 face-embedding

从人脸图像中提取特征向量。

```yaml
component:
  type: model
  task: face-embedding
  model: buffalo_l
  action:
    image: ${input.image as image}
```

### 10.3.18 face-tracking

在视频帧序列中追踪人脸。逐帧检测结果按人脸嵌入的余弦相似度归入身份轨迹，同一身份的连续命中合并为时间码片段。使用 InsightFace。

```yaml
component:
  type: model
  task: face-tracking
  driver: custom
  family: insightface
  model:
    provider: local
    path: ./.models/antelopev2
  action:
    frames: ${input.frames}
    frame_rate: ${input.frame_rate}
    return_track_image: true
    params:
      similarity_threshold: 0.4
      min_frame_count: 2
      merge_gap: 1.0
```

接受单个帧序列、序列列表或帧批次的 async 流；对流式输入延迟运行，不缓存整个视频。完整选项和结果结构请参见 [Model Component 参考](../reference/compose/components/model.md#face-tracking)。

### 10.3.19 pose-tracking

在视频帧序列中追踪人物（姿态）。逐帧姿态检测按底层追踪器的持久 `track_id` 分组，同一轨迹的连续命中合并为时间码片段。使用 Ultralytics YOLO-pose。

```yaml
component:
  type: model
  task: pose-tracking
  driver: custom
  family: yolo
  action:
    frames: ${input.frames}
    frame_rate: ${input.frame_rate}
    skeleton_format: openpose
    return_track_image: true
    params:
      min_confidence: 0.5
      min_frame_count: 3
      merge_gap: 0.5
```

接受与 face-tracking 相同的输入形态。完整选项、流式 chunk 结构与结果结构请参见 [Model Component 参考](../reference/compose/components/model.md#pose-tracking)。

### 10.3.20 object-tracking

在视频帧序列中追踪目标。逐帧检测按追踪器的持久 `track_id` 分组，同一轨迹的连续命中合并为时间码片段，可选对小间隔进行插值。使用 Ultralytics YOLO。

```yaml
component:
  type: model
  task: object-tracking
  driver: custom
  family: yolo
  action:
    frames: ${input.frames}
    frame_rate: ${input.frame_rate}
    labels: [ person, car ]
    return_track_image: true
    params:
      min_confidence: 0.3
      min_frame_count: 3
      merge_gap: 0.5
      tracker: bytetrack
```

接受与 face-tracking 相同的输入形态。完整选项、流式 chunk 结构与结果结构请参见 [Model Component 参考](../reference/compose/components/model.md#object-tracking)。

### 10.3.21 object-detection

在图像中检测目标，返回每个目标的边界框、类别标签和置信度分数。使用 Ultralytics YOLO。

```yaml
component:
  type: model
  task: object-detection
  driver: custom
  family: yolo
  action:
    image: ${input.image as image}
    labels: [ person, dog ]      # 可选：类别过滤
    bounding_box_padding: 0.05   # 为下游裁剪或 SAM 提示扩展每个框 5%
    params:
      min_confidence: 0.4
```

支持任意 Ultralytics YOLO 检测（或分割）`.pt` 检查点。完整选项和结果结构请参见 [Model Component 参考](../reference/compose/components/model.md#object-detection)。

### 10.3.22 image-segmentation

从图像中生成分区二值分割掩码。支持**自动模式**（对每个不同区域生成掩码）和**框提示模式**（在用户提供的边界框周围优化掩码，例如来自 `object-detection` 的输出）。通过 Ultralytics 使用 Meta 的 Segment Anything Model (SAM)。

```yaml
component:
  type: model
  task: image-segmentation
  driver: custom
  family: sam
  action:
    image: ${input.image as image}
    box_prompt: ${input.box_prompt as json}   # 可选：省略则为自动模式
    max_segment_count: 20
    params:
      min_confidence: 0.6
```

支持任意 Ultralytics SAM 检查点（`sam_b.pt`、`sam2_b.pt`、`mobile_sam.pt` 等）。完整选项和结果结构请参见 [Model Component 参考](../reference/compose/components/model.md#image-segmentation)。

### 10.3.23 text-to-video

从文本提示生成短视频片段。使用 `driver: custom`，通过 `family` 字段选择模型系列，并通过 `preset` 字段选择检查点变体。

```yaml
component:
  type: model
  task: text-to-video
  driver: custom
  family: wan
  preset: t2v-a14b
  model: Wan-AI/Wan2.2-T2V-A14B
  device: cuda:0
  action:
    prompt: ${input.prompt as text}
    negative_prompt: ${input.negative_prompt | ""}
    params:
      num_frames: 81
      fps: 24
      width: 1280
      height: 720
      inference_steps: 50
      guidance_scale: 5.0
```

**支持的系列与预设：**
- `wan`
  - `t2v-a14b` — Wan2.2 T2V 27B（14B 激活）；需要 ~80GB+ VRAM。
  - `ti2v-5b` — Wan2.2 混合文本+图像到视频 5B；可在单个 24GB GPU（RTX 4090）上运行。

结果是每个提示对应一个 mp4 流（批量提示则为 mp4 流列表）。完整选项请参见 [Model Component 参考](../reference/compose/components/model.md#text-to-video)。

### 10.3.24 image-to-video

生成让输入图像动起来的短视频片段，可选由文本提示引导。

```yaml
component:
  type: model
  task: image-to-video
  driver: custom
  family: wan
  preset: i2v-a14b
  model: Wan-AI/Wan2.2-I2V-A14B
  device: cuda:0
  action:
    image: ${input.image as image}
    prompt: ${input.prompt | ""}
    params:
      num_frames: 81
      fps: 24
      inference_steps: 40
      guidance_scale: 5.0
```

**支持的系列与预设：**
- `wan`
  - `i2v-a14b` — Wan2.2 I2V 27B（14B 激活）；需要 ~80GB+ VRAM。
  - `ti2v-5b` — Wan2.2 混合文本+图像到视频 5B；可在单个 24GB GPU 上运行。

`width`/`height` 可选；省略时使用输入图像的尺寸。结果形态与 `text-to-video` 相同（每个输入一个 mp4 流）。

### 10.3.25 video-to-video

变换现有视频片段。支持两个驱动系列：

- **`huggingface`（AnimateDiff）** — 用文本提示重新风格化片段，同时保留其运动。由 HuggingFace diffusers 的 AnimateDiff 流水线叠加在 Stable Diffusion 1.5 检查点之上驱动。
- **`custom`（Wan-Animate）** — 用输入片段的姿态和表情驱动参考角色。

```yaml
# AnimateDiff — 用提示词重新风格化，同时保留运动
component:
  type: model
  task: video-to-video
  driver: huggingface
  architecture: animatediff
  model:
    provider: huggingface
    repository: SG161222/Realistic_Vision_V5.1_noVAE
  motion_adapter:
    provider: huggingface
    repository: guoyww/animatediff-motion-adapter-v1-5-3
  # 可选的 IP-Adapter — 提供 action 级别的 `reference_image` 以引导外观。
  ip_adapter:
    provider: huggingface
    repository: h94/IP-Adapter
    filename: models/ip-adapter_sd15.bin
  device: cuda
  action:
    video: ${input.video as video}
    prompt: ${input.prompt}
    negative_prompt: ${input.negative_prompt | "bad quality, worst quality, low resolution"}
    reference_image: ${input.reference_image as image?}
    seed: ${input.seed as integer}
    params:
      num_frames: ${input.num_frames as integer}
      fps: ${input.fps as integer}
      inference_steps: ${input.inference_steps as integer | 25}
      guidance_scale: ${input.guidance_scale as number | 7.5}
      denoise_strength: ${input.denoise_strength as number | 0.5}
      ip_adapter_scale: ${input.ip_adapter_scale as number | 0.6}
```

```yaml
# Wan-Animate — 用输入片段的运动驱动参考角色
component:
  type: model
  task: video-to-video
  driver: custom
  family: wan
  preset: animate-14b
  model: Wan-AI/Wan2.2-Animate-14B
  # 预处理检查点 —— 姿态提取和人体检测始终必需。
  pose2d_model: Wan-AI/Wan2.2-Animate-14B/process_checkpoint/pose2d/vitpose_h_wholebody.onnx
  det_model: Wan-AI/Wan2.2-Animate-14B/process_checkpoint/det/yolov10m.onnx
  # 可选 —— 仅在替换模式和带图像编辑的姿态重定向时需要。
  sam2_model: Wan-AI/Wan2.2-Animate-14B/process_checkpoint/sam2/sam2_hiera_large.pt
  flux_kontext_model: black-forest-labs/FLUX.1-Kontext-dev
  cpu_offload: false
  device: cuda:0
  action:
    video: ${input.driving_video as video}
    reference_image: ${input.reference_image as image}
    prompt: ${input.prompt | ""}
    params:
      clip_len: 77
      inference_steps: 20
      guidance_scale: 1.0
      resolution_width: 1280
      resolution_height: 720
      preprocess_fps: 30
```

**支持的系列 / 架构：**

- `huggingface` → `animatediff` — Stable Diffusion 1.5 检查点 + AnimateDiff 运动适配器。任意 SD 1.5 微调都能作为外观骨干。
- `custom` → `wan`（`animate-14b`）— Wan2.2 Animate 14B。需要 CUDA。

**AnimateDiff 备注：** `num_frames`/`fps` 可选；省略时会消费全部输入帧，输出继承源片段的原生 fps，从而保留输入的播放时长。AnimateDiff 在约 16 帧窗口上训练，因此在很长的片段上质量会退化 —— 请在上游将长输入拆成短段（例如使用 `video-clipper`），并在下游拼接结果。当提供 `reference_image` 时，IP-Adapter 会转移色彩/纹理/主体线索；将 `ip_adapter_scale` 保持在 `0.5-0.7` 附近。

**Wan-Animate 备注：** `reference_image` 是必需的 —— 它是被驱动片段动画化的目标角色。驱动会先运行 Wan 预处理流水线（姿态提取、人体检测，以及可选的用于角色替换的 SAM2 与用于姿态重定向的 FLUX.1-Kontext），随后再进入主生成步骤，因此对应的检查点必须在组件上声明。设置 `params.replace_flag: true` 进行角色替换（需要 `sam2_model`），或 `params.use_flux: true`（配合 `params.retarget_flag: true`）进行基于编辑的重定向（需要 `flux_kontext_model`）。`cpu_offload: true` 以吞吐量为代价降低峰值 VRAM。

结果是每个输入对应一个 mp4 流（批量输入则为列表）。完整选项请参见 [Model Component 参考](../reference/compose/components/model.md#video-to-video)。

### 10.3.26 image-to-3d

从单张图像生成 3D GLB 资产。`family: pixal3d` 将 sparse-structure / shape / texture flow-matching 各阶段串联起来生成带烘焙 PBR 贴图的网格；`family: anigen` 生成绑定网格（骨骼 + 蒙皮权重烘焙进标准 glTF skinned-mesh）以及独立的骨架可视化。

```yaml
component:
  type: model
  task: image-to-3d
  driver: custom
  family: pixal3d
  device: cuda
  model:
    provider: huggingface
    repository: TencentARC/Pixal3D
  low_vram: false
  action:
    image: ${input.image as image}
    seed: ${input.seed as integer}
    params:
      texture_size: 4096
      shape_slat_sampling_steps: 12
      tex_slat_sampling_steps: 12
```

对于 AniGen，在组件上选择 SS-Flow 和 SLAT-Flow 变体，并在动作中切换要返回的输出：

```yaml
component:
  type: model
  task: image-to-3d
  driver: custom
  family: anigen
  device: cuda
  model:
    provider: huggingface
    repository: VAST-AI/AniGen
  ss_variant: solo      # solo（默认，精准几何）、epic、duet
  slat_variant: auto    # auto（默认，网络自选关节数）、control
  action:
    image: ${input.image as image}
    seed: ${input.seed as integer}
    return_mesh: true
    return_skeleton: true
    params:
      ss_steps: 25
      slat_steps: 25
      texture_size: 1024
```

**支持的系列与预设：**
- `pixal3d` — Pixal3D 单图→带纹理的 GLB。需要 CUDA GPU。1536 分辨率（默认）下峰值 VRAM 约 18 GB；`low_vram: true` + 1024 分辨率下约 10-12 GB。
- `anigen` — AniGen 单图→绑定 GLB 加骨架可视化。需要显存不低于 18 GB 的 CUDA GPU（仅 Linux；CUDA 11.8 或 12.x）。

对 Pixal3D，`low_vram: true` 会将各阶段模型保留在 CPU、按需迁到 GPU，用推理延迟换取更低峰值 VRAM；`manual_fov`（弧度）用于替代基于 MoGe 的自动 FOV 估计。对 AniGen，`slat_variant: control` 遵循 `params.joints_density`（0-4），默认 `auto` 会自选关节数。输出形态取决于系列 —— `pixal3d` 每个输入返回一个 `.glb` 流（`model/gltf-binary`）；`anigen` 每个输入返回一个包含 `mesh` 与 `skeleton` GLB 流的 dict（若 `return_image: true` 还包含 `image`）。完整选项请参见 [Model Component 参考](../reference/compose/components/model.md#image-to-3d)。

### 10.3.27 shot-boundary-detection

检测视频中的镜头边界（硬切换和转场），返回每个镜头的起止时间码和帧号。使用深度学习模型逐帧识别精确的切换点。使用 `driver: custom`，通过 `family` 字段选择模型系列。

```yaml
component:
  id: shot-detector
  type: model
  task: shot-boundary-detection
  driver: custom
  family: transnetv2
  model:
    provider: local
    path: ./models/transnetv2-weights
  max_concurrent_count: 1
  action:
    video: ${input.video as file}
    params:
      threshold: 0.5
    output: ${result as json}
```

| 字段 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `video` | video | **必需** | 输入视频文件、视频列表或 async 流 |
| `start_time` | time | `null` | 源视频中开始检测的时间点（如 `00:01:00`、`60s`） |
| `end_time` | time | `null` | 源视频中停止检测的时间点 |
| `batch_size` | int | `1` | 每批处理的视频数量 |
| `streaming` | bool | `false` | 每检测到一个镜头就发出一个 chunk（逐输入流） |
| `params.threshold` | float | `0.5` | 帧被判定为镜头边界的置信度阈值（0.0 - 1.0）；越高边界越少 |

结果形态（包含 `shots` 数组的逐视频 dict）：

```json
{
  "shots": [
    {
      "index": 0,
      "start_time": "00:00:00.000",
      "end_time": "00:00:12.345",
      "start_frame": 0,
      "end_frame": 370,
      "duration": "00:00:12.345"
    },
    {
      "index": 1,
      "start_time": "00:00:12.345",
      "end_time": "00:00:28.678",
      "start_frame": 370,
      "end_frame": 860,
      "duration": "00:00:16.333"
    }
  ]
}
```

当 `streaming: true` 时，每个输入的结果是一个 async iterator，每检测到一个镜头边界便发出一个 chunk。每个 chunk 在镜头字段之外还带有 `"type": "shot"`。

#### 支持的系列

| 系列 | 后端 | 说明 |
|------|------|------|
| `transnetv2` | [soCzech/TransNetV2](https://github.com/soCzech/TransNetV2) | 深度学习镜头检测器；GPU 加速（TensorFlow）。将 `model.path` 指向包含 `saved_model.pb` 与 `variables/` 的 SavedModel 文件夹 |

与 `video-scene-detector` 组件（通过 PySceneDetect/FFmpeg 使用经典 CV 启发式规则聚合语义相似帧）相比，`shot-boundary-detection` 运行专门训练用于定位切换点的神经网络，在现代剪辑内容上通常更准确。

### 10.3.28 music-generation

生成或编辑音乐音频。动作的 `method` 字段用于选择操作 —— 从提示词从头生成（同时也用于 MIDI 合成）、以新风格翻唱现有曲目、重写指定区间、在结尾之后延续、在源音频上叠加新乐器层、为纯人声源生成伴奏、规划可编辑的 ABC 乐谱。使用 `driver: custom`，通过 `family` 字段选择模型系列；ACE-Step 需要 `preset` 字段选择检查点变体，YuE2 使用 `vae`、`backend`、`quantization`、`memory_budget_gib` 和 `cpu_offload`。

```yaml
component:
  type: model
  task: music-generation
  driver: custom
  family: ace-step
  preset: acestep-v15-turbo
  model: /path/to/ace-step-checkpoints
  device: cuda:0
  action:
    method: generate
    prompt: ${input.prompt as text}
    lyrics: ${input.lyrics | ""}
    params:
      duration: 30
      bpm: 120
      key_scale: C
      time_signature: 4/4
      inference_steps: 8
      guidance_scale: 5.0
```

**支持的 method：**

| Method | 用途 | 必填字段（除公共字段外） |
|--------|------|--------------------------|
| `generate` | 从头生成音乐 | `prompt`（可选：`lyrics`、`reference_audio`） |
| `cover` | 以新风格翻唱现有曲目 | `source`、`prompt`（可选：`lyrics`） |
| `rewrite` | 重新生成指定 `[start_time, end_time]` 区间 | `source`、`start_time`、`end_time`、`prompt`（可选：`lyrics`） |
| `extend` | 将源音频延续到自然结尾之后 | `source`、`prompt`（可选：`lyrics`） |
| `layer` | 在源音频上叠加新乐器或声部 | `source`、`track_class`（可选：`prompt`、`lyrics`） |
| `accompany` | 为纯人声源生成伴奏（仅 `ace-step`） | `vocal`、`track_classes`（可选：`prompt`） |
| `score` | 规划可编辑的 ABC 乐谱（仅 `yue2`；不渲染音频） | `style`、`lyrics` |

**支持的 family 和 preset：**
- `ace-step`
  - `acestep-v15-turbo` — 快速 turbo 变体（默认 `inference_steps: 8`）。
  - `acestep-v15-base` — base 变体（推荐 `inference_steps: 32`）。
  - `acestep-v15-sft` — SFT 变体（推荐 `inference_steps: 50`）。
- `midi-ddsp`
  - 使用特定 URMP 乐器音色（violin、viola、cello、double-bass、flute、oboe、clarinet、saxophone、bassoon、trumpet、horn、trombone、tuba）合成单声部 MIDI 文件。`method: generate` 搭配 `midi` 和 `instrument` 字段使用。多声部 MIDI 会被拒绝。
- `yue2`
  - 具备可编辑 ABC 乐谱规划的完整歌曲生成。`generate` 从 `style` + `lyrics` 创作，`cover` 重新演绎提供的 ABC 乐谱，`score` 仅返回规划后的 ABC。`params.cot_mode` 选择思维链风格（`full` 含和弦符号、`melody` 用于翻唱、`off` 直接生成）。渲染 48 kHz 立体声音频。

`ace-step` 和 `midi-ddsp` 均不支持 HuggingFace Hub 标识符，`model` 必须是本地检查点目录。`yue2` 同时接受 HuggingFace 仓库 ID（例如 `m-a-p/YuE2-3B`）和本地路径。

MIDI-DDSP 固定依赖 TensorFlow 2.11 且无法与宿主 mindor 栈共存，因此组件必须在隔离运行时（`virtualenv`、`docker` 或 `apple-container`）下运行；`native` / `embedded` / `process` 运行时会在加载时被拒绝。

YuE2 的非量化预设需要支持 BF16 的 CUDA GPU 和 ≥24 GB VRAM。请通过 `quantization.type: fp8`、`cpu_offload: ar` 以及较小的 `vae.tile_size` 适配更小的预算。在 macOS 15.1 以下版本，MPS 后端无法执行 VAE 的超大 Conv1d 层，请设置 `cpu_offload: vae`（或 `cpu_offload: [ar, vae]`）让解码器在 CPU 上运行。选择 `backend: vllm` 时会自动安装模型的 `[fast]` 附加依赖（vLLM + Triton）。

```yaml
component:
  type: model
  task: music-generation
  driver: custom
  family: midi-ddsp
  runtime:
    type: virtualenv
    driver: pyenv
    python: "3.10.14"
  model: /path/to/midi_ddsp_model_weights_urmp_9_10
  action:
    method: generate
    midi: ${input.midi}
    instrument: violin
```

```yaml
component:
  type: model
  task: music-generation
  driver: custom
  family: yue2
  model: m-a-p/YuE2-3B
  device: cuda
  action:
    method: generate
    style: ${input.style as text}
    lyrics: ${input.lyrics as text}
    params:
      cot_mode: full
```

生成音频的方法返回每个输入的 PCM 音频流（批处理输入则返回流列表）；YuE2 的 `score` 则返回 `{ abc, truncated }`。每个 method 的完整字段列表请参见 [Model Component 参考](../reference/compose/components/model.md#music-generation)。

### 10.3.29 music-source-separation

将混合录音分离为独立的乐器音轨（人声、鼓、贝斯、其他）。使用 `driver: custom`，并通过 `family` 字段选择模型后端。

```yaml
component:
  type: model
  task: music-source-separation
  driver: custom
  family: demucs
  model: htdemucs_ft
  device: cpu   # htdemucs_ft 不支持 MPS，请使用 cpu 或 cuda
  action:
    audio: ${input.audio as audio}
    params:
      stems: [ vocals ]   # 省略时会返回模型可产出的所有音轨
      overlap: 0.25
      shifts: 1
```

**支持的 family：**

| Family | 适用范围 | 说明 |
|--------|----------|------|
| `demucs` | 四音轨（或六音轨）分离 | Meta AI 的 Hybrid Transformer Demucs。`htdemucs_ft` 是微调后的集成模型；`htdemucs_6s` 额外提供 `guitar` 和 `piano` 音轨 |
| `mdx-net` | 人声分离 | 基于 ONNX Runtime 的 UVR MDX-Net。伴奏音轨通过从混音中减去人声得到 |
| `bs-roformer` | 可配置的音轨分离 | lucidrains 的 Band-Split RoFormer。该包仅包含架构本身——请将 `model` 指向预训练的 `.ckpt`/`.safetensors`，并将 `params` 与该 checkpoint 匹配 |
| `mel-band-roformer` | 可配置的音轨分离 | BS-RoFormer 的 mel-band 变体。mel 滤波器组在模型构建时确定，因此 `params.sample_rate` 必须与 checkpoint 保持一致 |

当仅请求一个音轨时，该动作返回单个音频流。当请求多个音轨时（例如 `stems: [vocals, drums, bass, other]`），或当省略 `stems` 从而返回模型可产出的所有音轨时，返回 `{ "<stem_name>": <stream>, ... }` 形式的映射。提高 `shifts` 和 `overlap` 会以更长的运行时间换取更干净的分离效果。

与 `music-transcription` 组合使用可将每个音轨转录为独立的 MIDI，或对人声音轨使用 `speech-to-text` 以获得更清晰的歌词转录。完整的 family 字段列表请参见 [Model Component 参考](../reference/compose/components/model.md#music-source-separation)。

### 10.3.30 music-transcription

将录制的音频转录为 MIDI 文件和音符事件（起始时间、结束时间、音高、力度）的 JSON 列表。使用 `driver: custom`，并通过 `family` 字段选择模型后端。

```yaml
component:
  type: model
  task: music-transcription
  driver: custom
  family: basic-pitch
  device: auto
  action:
    audio: ${input.audio as audio}
    return_pitch_bends: false
    params:
      onset_threshold: 0.5
      frame_threshold: 0.3
      minimum_note_length: 58.0
```

**支持的 family：**

| Family | 适用范围 | 说明 |
|--------|----------|------|
| `basic-pitch` | 复音、乐器无关 | Spotify Basic Pitch (ICASSP-2022)；通过 ONNX 在 CPU 上运行；检查点随 wheel 一同分发 |
| `piano-transcription` | 仅限 88 键钢琴 | ByteDance Piano Transcription；可检测延音踏板事件；首次使用时自动下载约 180 MB 检查点 |

该动作为每个输入返回包含两个字段的字典：`midi`（MIDI 文件）和 `notes`（`{start_time, end_time, pitch, velocity}` 对象的 JSON 列表，时间以秒为单位，音高为 MIDI 音符编号）。启用 `return_pitch_bends` 时，Basic Pitch 会为每个音符添加 `pitch_bends` 数组。Piano Transcription 会直接将踏板事件写入 MIDI。

与 `music-source-separation` 组合使用，可对混音中的每个音轨独立转录（例如将人声与伴奏作为不同声部分别转录）。完整的 family 字段列表请参见 [Model Component 参考](../reference/compose/components/model.md#music-transcription)。

### 10.3.31 music-beat-tracking

检测音乐录音中的节拍和强拍位置。每个检测到的节拍都会记录其在小节中的位置——可用于节拍同步剪辑、速度/拍号分析、DJ 风格的时间伸缩以及结构分段。使用 `driver: custom`，并通过 `family` 字段选择模型后端。

```yaml
component:
  type: model
  task: music-beat-tracking
  driver: custom
  family: beat-this
  device: auto
  model: final0
  dbn: false
  action:
    audio: ${input.audio as audio}
    return_metadata: true
```

**支持的 family：**

| Family | 后端 | 说明 |
|--------|------|------|
| `beat-this` | CPJKU Beat This! (ISMIR 2024) | 基于 Transformer 的节拍/强拍联合估计器；检查点在首次使用时自动从 HuggingFace 下载；通过 `dbn: true` 可启用 madmom DBN 后处理 |

该动作为每个输入返回包含 `beats` 列表的字典。每个事件包含 `time`（秒）、`is_downbeat`（小节起点时为 `true`）以及 `beat_number`（在小节中的位置——强拍上为 `1`，随后为 `2, 3, ...`；第一个强拍之前的弱起拍为 `null`）。当 `return_metadata: true` 时，还会包含 `duration`。

完整的 family 字段列表请参见 [Model Component 参考](../reference/compose/components/model.md#music-beat-tracking)。

### 10.3.32 talking-head

让静态肖像跟随驱动音频片段进行对口型（并带头部运动）。与编辑现有视频嘴部的 `lip-sync` 不同，`talking-head` 从单张图像合成头部运动和表情。使用 `driver: custom`，通过 `family` 字段选择模型后端。

```yaml
component:
  type: model
  task: talking-head
  driver: custom
  family: sadtalker
  preset: v0.0.2-256
  preprocessor: full
  model: vinthony/SadTalker
  device: cuda:0
  action:
    image: ${input.image as image}
    audio: ${input.audio as audio}
    params:
      still: true
      expression_scale: 1.0
      pose_style: 0
```

**支持的 family：**

| Family | 预设 | 说明 |
|--------|------|------|
| `sadtalker` | `v0.0.2-256`、`v0.0.2-512` | 经典 Audio2Coeff + 人脸渲染器；256 预设约需 6 GB VRAM，512 约需 12 GB。暴露参考视频运动迁移和手动 yaw/pitch/roll 关键帧。 |
| `hallo2` | （单一构建） | 基于扩散的肖像动画器，带长视频分块拼接模式。暴露逐信号权重（pose/face/lip）以及可选的内置超分辨率。 |
| `hallo3` | （单一构建） | 更新的基于 DiT 的肖像视频生成器；接受可选的文本提示。质量更高，但推理时间更长。 |
| `sonic` | （单一构建） | LeonJoe13/Sonic，基于 SVD-XT 骨干与 whisper-tiny 音频嵌入；产生富有表现力的头部运动。 |
| `echomimic` | `v1`、`v2` | AntGroup EchoMimic：v1 用于肖像取景，v2 用于半身，可选运动同步参考视频。 |
| `float` | （单一构建） | 流匹配肖像动画器，带按情感条件化；扩散系选项中最快的一个。 |

**关键 action 字段**（因系列而异 —— 完整列表请参见参考）：

- `image`、`audio` — 必需输入；均可为单值、列表或流。
- `params.fps` — 输出帧率（默认 25）。
- `params.inference_steps` — 去噪 / 流匹配步数（支持的系列）。
- `params.cfg_scale`、`params.guidance_scale` — classifier-free guidance 控制。
- `params.still`（SadTalker）、`params.crop`（Float）— 保持头/身体静止，仅让嘴部动。
- `params.enhancer` — 可选的逐帧人脸增强器（`gfpgan`、`RestoreFormer`）（SadTalker）。
- `params.long_video` — 为长于模型上下文窗口的音频启用分窗口拼接（Hallo2、Hallo3）。

结果是一个 mp4 流（批量输入则为流列表），每个都带 `format: "mp4"` 与匹配所请求帧率的 `fps` 属性。完整的 family 字段列表请参见 [Model Component 参考](../reference/compose/components/model.md#talking-head)。

### 10.3.33 lip-sync

将人脸视频的嘴部运动重新同步到驱动音频片段。仅重新生成嘴部区域；身份、表情、头部姿态和背景直接来自源视频。使用 `driver: custom`，通过 `family` 字段选择模型后端。

```yaml
component:
  type: model
  task: lip-sync
  driver: custom
  family: wav2lip
  preset: wav2lip-gan
  device: cuda:0
  action:
    video: ${input.video as video}
    audio: ${input.audio as audio}
    params:
      face_bounding_box_padding: [0, 0, 0, 10]
      resize_factor: 1
      face_smoothing: true
```

**支持的 family：**

| Family | 预设 | 说明 |
|--------|------|------|
| `wav2lip` | `wav2lip`、`wav2lip-gan` | 经典 GAN 对口型；VRAM 占用最小、推理最快。自动从 Easy-Wav2Lip 发布镜像拉取预设检查点。 |
| `musetalk` | `v1`、`v15` | 扩散潜空间的 VAE+UNet，带 InsightFace + Whisper 前端。质量高于 Wav2Lip；v1.5 使用基于 parsing 的融合。自动拉取 `TMElyralab/MuseTalk`。 |
| `latentsync` | `1.5`、`1.6` | 字节跳动基于扩散的对口型；在 512×512 (v1.6) 下输出最锐利。v1.6 约需 12GB VRAM，v1.5 约需 6GB。自动拉取 `ByteDance/LatentSync-<preset>`。 |

**关键 action 字段**（因系列而异 —— 完整列表请参见参考表）：

- `video`、`audio` — 必需输入；均可为单值、列表或流。
- `params.fps` — 输出帧率；未设置时默认为源视频的帧率。
- `params.face_bounding_box` — 绕过人脸检测的 LTRB 像素元组（Wav2Lip）。当源视频的自动检测失败时提供。
- `params.face_bounding_box_padding` — 围绕检测到的人脸添加的 LTRB 像素填充（Wav2Lip）。加大 `bottom` 可在特写镜头中避免下巴被裁掉。
- `params.parsing_mode` — 用于融合的人脸 parsing 区域：`jaw`、`neck` 或 `raw`（MuseTalk v1.5）。
- `params.inference_steps`、`params.guidance_scale` — 扩散采样控制（LatentSync）。
- `params.generator_batch_size` — UNet 推理批大小（Wav2Lip、MuseTalk）。
- `params.use_float16` — fp16 推理，节省内存和降低延迟（MuseTalk、LatentSync）。

若音频长于视频，Wav2Lip 和 MuseTalk 会循环源帧（MuseTalk 使用 ping-pong，Wav2Lip 使用正向重复）以填满时间线。LatentSync 精确生成与音频等长的时长，并裁剪源视频以匹配。

结果是一个 mp4 流（批量输入则为流列表），每个都带 `format: "mp4"` 与匹配输出帧率的 `fps` 属性。完整的 family 字段列表请参见 [Model Component 参考](../reference/compose/components/model.md#lip-sync)。

---

## 10.4 模型配置（设备、精度、批量大小）

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
  quantization: int8  # 'int8', 'int4', 'fp4', 'nf4'（省略则不量化）
```

**量化选项：**
- （省略 `quantization:`）：不量化（默认）
- `int8`：8 位整数（需要 bitsandbytes）
- `int4`：4 位整数（需要 bitsandbytes）
- `fp4`：4 位浮点（需要 bitsandbytes）
- `nf4`：4 位 NormalFloat（用于 QLoRA）

也可以将 `quantization` 展开为完整配置：

```yaml
quantization:
  type: nf4
  compute_dtype: bfloat16
  double_quant: true
```

### 批量大小

```yaml
component:
  type: model
  task: text-classification
  model: distilbert-base-uncased
  action:
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

## 10.5 使用 LoRA/PEFT 适配器

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
  action:
    prompt: ${input.prompt as text}
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
  action:
    prompt: ${input.prompt as text}
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

## 10.6 模型服务框架

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
  action:
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
      stream: true
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

## 10.7 性能优化技巧

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
  action:
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

**下一章**：[第11章：模型训练](./11-model-training.md)

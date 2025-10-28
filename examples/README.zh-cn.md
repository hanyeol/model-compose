# Model-Compose 示例

本目录包含演示 model-compose 各种功能和用例的实用示例。每个示例都包含一个可直接运行的 `model-compose.yml` 配置文件。

## 📋 快速开始

运行任何示例：

```bash
cd examples/<example-name>
model-compose up
```

或直接运行工作流：

```bash
cd examples/<example-name>
model-compose run <workflow-name> --input '{"key": "value"}'
```

---

## 📂 示例结构

每个示例目录通常包含：

```
example-name/
├── model-compose.yml   # 主配置文件
├── README.md           # 示例特定文档（可选）
└── .env.example        # 环境变量模板（可选）
```

---

## 🔑 环境变量

许多示例需要 API 密钥。在示例目录中创建 `.env` 文件：

```bash
# OpenAI 示例
OPENAI_API_KEY=your-api-key

# ElevenLabs 示例
ELEVENLABS_API_KEY=your-api-key

# HuggingFace 示例
HUGGINGFACE_TOKEN=your-token-here
```

---

## 🎯 按类别分类的示例

### 外部 API 集成

#### OpenAI API
- **[openai-chat-completions](./openai-chat-completions/)** - 与 GPT 模型聊天
- **[openai-chat-completions-stream](./openai-chat-completions-stream/)** - 流式聊天响应
- **[openai-audio-speech](./openai-audio-speech/)** - 使用 OpenAI TTS 的文本转语音
- **[openai-audio-transciptions](./openai-audio-transciptions/)** - 音频转录 (Whisper)
- **[openai-image-generations](./openai-image-generations/)** - 使用 DALL-E 生成图像
- **[openai-image-edits](./openai-image-edits/)** - 使用 DALL-E 编辑图像
- **[openai-image-variations](./openai-image-variations/)** - 创建图像变体

#### 其他服务
- **[elevenlabs-text-to-speech](./elevenlabs-text-to-speech/)** - 使用 ElevenLabs 的高质量 TTS

### 多步骤工作流

- **[make-inspiring-quote-voice](./make-inspiring-quote-voice/)** - 生成励志名言文本 → 转换为语音
- **[analyze-disk-usage](./analyze-disk-usage/)** - 分析磁盘使用情况 → 生成报告

### 本地 AI 模型

- **[model-tasks](./model-tasks/)** - 各种本地模型任务
  - [chat-completion](./model-tasks/chat-completion/) - 与本地 LLM 聊天
  - [text-generation](./model-tasks/text-generation/) - 生成文本
  - [text-generation-lora](./model-tasks/text-generation-lora/) - 使用 LoRA 适配器生成文本
  - [summarization](./model-tasks/summarization/) - 文本摘要
  - [summarization-stream](./model-tasks/summarization-stream/) - 流式摘要
  - [translation](./model-tasks/translation/) - 文本翻译
  - [translation-stream](./model-tasks/translation-stream/) - 流式翻译
  - [text-classification](./model-tasks/text-classification/) - 文本分类
  - [text-embedding](./model-tasks/text-embedding/) - 生成文本嵌入
  - [image-to-text](./model-tasks/image-to-text/) - 图像描述
  - [image-upscale](./model-tasks/image-upscale/) - 图像放大
  - [face-embedding](./model-tasks/face-embedding/) - 生成面部嵌入
- **[vllm-chat-completion-stream](./vllm-chat-completion-stream/)** - 使用 vLLM 的流式聊天（本地模型服务）

### 数据处理

- **[split-text](./split-text/)** - 文本分割和处理
- **[image-processor](./image-processor/)** - 图像处理工作流

### 向量数据库

- **[vector-store](./vector-store/)** - 向量数据库集成示例
  - [chroma](./vector-store/chroma/) - ChromaDB 集成
  - [milvus](./vector-store/milvus/) - Milvus 向量数据库

### 数据管理

- **[datasets](./datasets/)** - 数据集加载和操作
  - [huggingface](./datasets/huggingface/) - HuggingFace 数据集集成

### 服务器与集成

- **[echo-server](./echo-server/)** - 简单的 HTTP 服务器示例
- **[mcp-servers](./mcp-servers/)** - Model Context Protocol 服务器示例

---

## 🧩 按组件分类的示例

按组件类型浏览示例：

### HTTP Client 组件
- [openai-chat-completions](./openai-chat-completions/)
- [openai-chat-completions-stream](./openai-chat-completions-stream/)
- [openai-audio-speech](./openai-audio-speech/)
- [openai-audio-transciptions](./openai-audio-transciptions/)
- [openai-image-generations](./openai-image-generations/)
- [openai-image-edits](./openai-image-edits/)
- [openai-image-variations](./openai-image-variations/)
- [elevenlabs-text-to-speech](./elevenlabs-text-to-speech/)
- [make-inspiring-quote-voice](./make-inspiring-quote-voice/)

### Model 组件（本地 AI）

#### 聊天与文本生成
- [model-tasks/chat-completion](./model-tasks/chat-completion/)
- [model-tasks/text-generation](./model-tasks/text-generation/)
- [model-tasks/text-generation-lora](./model-tasks/text-generation-lora/)
- [vllm-chat-completion-stream](./vllm-chat-completion-stream/)

#### 文本处理
- [model-tasks/summarization](./model-tasks/summarization/)
- [model-tasks/summarization-stream](./model-tasks/summarization-stream/)
- [model-tasks/translation](./model-tasks/translation/)
- [model-tasks/translation-stream](./model-tasks/translation-stream/)
- [model-tasks/text-classification](./model-tasks/text-classification/)

#### 嵌入
- [model-tasks/text-embedding](./model-tasks/text-embedding/)
- [model-tasks/face-embedding](./model-tasks/face-embedding/)

#### 图像处理
- [model-tasks/image-to-text](./model-tasks/image-to-text/)
- [model-tasks/image-upscale](./model-tasks/image-upscale/)

### Vector Store 组件
- [vector-store/chroma](./vector-store/chroma/)
- [vector-store/milvus](./vector-store/milvus/)

### Datasets 组件
- [datasets/huggingface](./datasets/huggingface/)

### Text Splitter 组件
- [split-text](./split-text/)

### Image Processor 组件
- [image-processor](./image-processor/)

### Shell 组件
- [analyze-disk-usage](./analyze-disk-usage/)

### HTTP Server 组件
- [echo-server](./echo-server/)

---

## 🚀 下一步

1. 浏览符合您用例的示例
2. 复制一个示例作为项目的起点
3. 修改 `model-compose.yml` 以满足您的需求
4. 参阅[用户指南](../docs/user-guide/)获取详细文档

---

## 🤝 贡献示例

有有用的示例想要分享？

1. 在 `examples/` 下创建一个新目录
2. 添加 `model-compose.yml` 文件
3. 可选择性添加包含具体说明的 `README.md`
4. 提交 pull request

---

## 📚 其他资源

- [用户指南](../docs/user-guide/zh-cn/) - 综合文档
- [GitHub Repository](https://github.com/hanyeol/model-compose) - 源代码和问题

---

**编排愉快！🎉**

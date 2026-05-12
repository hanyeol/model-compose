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

# Anthropic 示例
ANTHROPIC_API_KEY=your-api-key

# ElevenLabs 示例
ELEVENLABS_API_KEY=your-api-key

# HuggingFace 示例
HUGGINGFACE_TOKEN=your-token-here
```

---

## 🎯 按类别分类的示例

### 外部 API 集成

#### OpenAI API
- **[openai-chat-completions](./model-providers/openai/openai-chat-completions/)** - 与 GPT 模型聊天
- **[openai-chat-completions-stream](./model-providers/openai/openai-chat-completions-stream/)** - 流式聊天响应
- **[openai-audio-speech](./model-providers/openai/openai-audio-speech/)** - 使用 OpenAI TTS 的文本转语音
- **[openai-audio-transciptions](./model-providers/openai/openai-audio-transciptions/)** - 音频转录 (Whisper)
- **[openai-image-generations](./model-providers/openai/openai-image-generations/)** - 使用 DALL-E 生成图像
- **[openai-image-edits](./model-providers/openai/openai-image-edits/)** - 使用 DALL-E 编辑图像
- **[openai-image-variations](./model-providers/openai/openai-image-variations/)** - 创建图像变体

#### Anthropic API
- **[anthropic-chat-completions](./model-providers/anthropic/anthropic-chat-completions/)** - 与 Claude 模型聊天
- **[anthropic-chat-completions-stream](./model-providers/anthropic/anthropic-chat-completions-stream/)** - Claude 流式聊天

#### xAI API
- **[xai-chat-completion](./model-providers/xai/xai-chat-completion/)** - 与 xAI 的 Grok 模型聊天

#### Google Cloud API
- **[google-cloud-vision](./model-providers/google/google-cloud-vision/)** - 使用 Google Cloud Vision API 进行图像分析

#### 其他服务
- **[elevenlabs-text-to-speech](./model-providers/elevenlabs/elevenlabs-text-to-speech/)** - 使用 ElevenLabs 的高质量 TTS

### AI 代理

- **[agents](./agents/)** - 使用 ReAct 循环和工具的自主 AI 代理示例
  - [code-reviewer](./agents/code-reviewer/) - 自动代码审查代理
  - [design-md-generator](./agents/design-md-generator/) - 通过网站分析生成 DESIGN.md
  - [disk-analyzer](./agents/disk-analyzer/) - 磁盘使用分析代理
  - [human-in-the-loop](./agents/human-in-the-loop/) - 带危险操作审批门控的代理
  - [multi-tool](./agents/multi-tool/) - 多工具代理演示
  - [rag-assistant](./agents/rag-assistant/) - 基于 RAG 的知识库问答代理
  - [web-page-analyzer](./agents/web-page-analyzer/) - 网页内容分析代理
  - [web-researcher](./agents/web-researcher/) - 自主网络研究代理
  - [web3-airdrop-hunter](./agents/web3-airdrop-hunter/) - Web3 空投发现代理

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
- **[vllm-chat-completion-stream](./vllm-chat-completion-stream/)** - 使用 vLLM 的流式聊天
- **[vllm-text-to-speech](./vllm-text-to-speech/)** - 通过 vLLM-Omni 使用 Qwen3-TTS 文本转语音
- **[vibevoice-realtime-tts](./vibevoice-realtime-tts/)** - 使用 VibeVoice 的实时 WebSocket TTS

### 音视频处理

- **[audio-extractor](./audio-extractor/)** - 从视频中提取音频并转换格式
- **[video-converter](./video-converter/)** - 视频格式转换和编码配置
- **[video-scene-detector](./video-scene-detector/)** - 视频场景切换检测

### 数据处理

- **[split-text](./split-text/)** - 文本分割和处理
- **[image-processor](./image-processor/)** - 图像处理工作流

### 网络自动化

- **[web-browser](./web-browser/)** - 支持 CAPTCHA 处理的无头浏览器自动化
- **[web-scraper](./web-scraper/)** - 使用 CSS/XPath 选择器的多功能网页抓取

### 数据存储

- **[vector-store](./vector-store/)** - 向量数据库集成
  - [chroma](./vector-store/chroma/) - ChromaDB 集成
  - [milvus](./vector-store/milvus/) - Milvus 向量数据库
- **[graph-store](./graph-store/)** - 图数据库集成
  - [neo4j](./graph-store/neo4j/) - Neo4j 图数据库
  - [arangodb](./graph-store/arangodb/) - ArangoDB 图存储
- **[key-value-store](./key-value-store/)** - 键值存储集成
  - [redis](./key-value-store/redis/) - Redis KV 存储操作

### 数据管理

- **[datasets](./datasets/)** - 数据集加载和操作
  - [huggingface](./datasets/huggingface/) - HuggingFace 数据集集成

### 分布式工作流

- **[workflow-queue](./workflow-queue/)** - 通过 Redis 队列的分布式工作流执行
- **[workflow-queue-stream](./workflow-queue-stream/)** - 通过 Redis Streams 和 SSE 的分布式流式输出

### 集成渠道

- **[channels](./channels/)** - 外部消息平台集成
  - [telegram](./channels/telegram/) - 使用 Webhook 的 Telegram 机器人

### 工作流控制

- **[interrupt](./interrupt/)** - 带审批门控的人机协作工作流控制

### 基础设施

- **[docker](./docker/)** - Docker 容器运行时示例
- **[gateway](./gateway/)** - 隧道和端口转发
  - [ngrok](./gateway/http-tunnel/ngrok/) - ngrok HTTP 隧道
  - [cloudflare](./gateway/http-tunnel/cloudflare/) - Cloudflare 隧道
  - [cloudflare-named](./gateway/http-tunnel/cloudflare-named/) - Cloudflare 命名隧道
  - [ssh-tunnel](./gateway/ssh-tunnel/) - SSH 远程端口转发

### 服务器与集成

- **[echo-server](./echo-server/)** - 简单的 HTTP 服务器示例
- **[mcp-servers](./mcp-servers/)** - Model Context Protocol 服务器示例

---

## 🧩 按组件分类的示例

按组件类型浏览示例：

### HTTP Client 组件
- [openai-chat-completions](./model-providers/openai/openai-chat-completions/)
- [openai-chat-completions-stream](./model-providers/openai/openai-chat-completions-stream/)
- [openai-audio-speech](./model-providers/openai/openai-audio-speech/)
- [openai-audio-transciptions](./model-providers/openai/openai-audio-transciptions/)
- [openai-image-generations](./model-providers/openai/openai-image-generations/)
- [openai-image-edits](./model-providers/openai/openai-image-edits/)
- [openai-image-variations](./model-providers/openai/openai-image-variations/)
- [anthropic-chat-completions](./model-providers/anthropic/anthropic-chat-completions/)
- [anthropic-chat-completions-stream](./model-providers/anthropic/anthropic-chat-completions-stream/)
- [xai-chat-completion](./model-providers/xai/xai-chat-completion/)
- [google-cloud-vision](./model-providers/google/google-cloud-vision/)
- [elevenlabs-text-to-speech](./model-providers/elevenlabs/elevenlabs-text-to-speech/)
- [make-inspiring-quote-voice](./make-inspiring-quote-voice/)

### Agent 组件
- [agents/code-reviewer](./agents/code-reviewer/)
- [agents/design-md-generator](./agents/design-md-generator/)
- [agents/disk-analyzer](./agents/disk-analyzer/)
- [agents/human-in-the-loop](./agents/human-in-the-loop/)
- [agents/multi-tool](./agents/multi-tool/)
- [agents/rag-assistant](./agents/rag-assistant/)
- [agents/web-page-analyzer](./agents/web-page-analyzer/)
- [agents/web-researcher](./agents/web-researcher/)
- [agents/web3-airdrop-hunter](./agents/web3-airdrop-hunter/)

### Model 组件（本地 AI）

#### 聊天与文本生成
- [model-tasks/chat-completion](./model-tasks/chat-completion/)
- [model-tasks/text-generation](./model-tasks/text-generation/)
- [model-tasks/text-generation-lora](./model-tasks/text-generation-lora/)
- [vllm-chat-completion-stream](./vllm-chat-completion-stream/)
- [vllm-text-to-speech](./vllm-text-to-speech/)

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

### 音视频组件
- [audio-extractor](./audio-extractor/)
- [video-converter](./video-converter/)
- [video-scene-detector](./video-scene-detector/)
- [vibevoice-realtime-tts](./vibevoice-realtime-tts/)

### Web Browser 组件
- [web-browser](./web-browser/)

### Web Scraper 组件
- [web-scraper](./web-scraper/)

### Vector Store 组件
- [vector-store/chroma](./vector-store/chroma/)
- [vector-store/milvus](./vector-store/milvus/)

### Graph Store 组件
- [graph-store/neo4j](./graph-store/neo4j/)
- [graph-store/arangodb](./graph-store/arangodb/)

### Key-Value Store 组件
- [key-value-store/redis](./key-value-store/redis/)

### Datasets 组件
- [datasets/huggingface](./datasets/huggingface/)

### Text Splitter 组件
- [split-text](./split-text/)

### Image Processor 组件
- [image-processor](./image-processor/)

### Shell 组件
- [analyze-disk-usage](./analyze-disk-usage/)

### Workflow 组件
- [workflow-queue](./workflow-queue/)
- [workflow-queue-stream](./workflow-queue-stream/)

### HTTP Server 组件
- [echo-server](./echo-server/)
- [docker](./docker/)

### Gateway 组件
- [gateway/http-tunnel/ngrok](./gateway/http-tunnel/ngrok/)
- [gateway/http-tunnel/cloudflare](./gateway/http-tunnel/cloudflare/)
- [gateway/http-tunnel/cloudflare-named](./gateway/http-tunnel/cloudflare-named/)
- [gateway/ssh-tunnel](./gateway/ssh-tunnel/)

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

## 📖 其他语言

- **🌍 English**: [English Documentation](README.md)
- **🇰🇷 한국어**: [한국어 문서](README.ko.md)

---

**编排愉快！🎉**

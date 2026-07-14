# Model-Compose 示例

本目录包含演示 model-compose 各种功能和用例的实用示例。每个示例都包含一个可直接运行的 `model-compose.yml` 配置文件以及各语言版本的 README。

## 📋 快速开始

运行任意示例：

```bash
cd examples/<category>/<example-name>
model-compose up
```

或直接运行特定工作流：

```bash
cd examples/<category>/<example-name>
model-compose run <workflow-name> --input '{"key": "value"}'
```

---

## 📂 示例结构

每个示例目录通常包含：

```
example-name/
├── model-compose.yml       # 主配置文件
├── README.md               # 英文文档
├── README.ko.md            # 韩文文档
├── README.zh-cn.md         # 简体中文文档
└── .env.sample             # 环境变量模板（可选）
```

---

## 🔑 环境变量

许多示例需要 API 密钥。请在示例目录中创建 `.env` 文件：

```bash
# OpenAI 示例
OPENAI_API_KEY=your-api-key

# Anthropic 示例
ANTHROPIC_API_KEY=your-api-key

# xAI 示例
XAI_API_KEY=your-api-key

# ElevenLabs 示例
ELEVENLABS_API_KEY=your-api-key

# HuggingFace 示例
HUGGINGFACE_TOKEN=your-token-here
```

---

## 🗂️ 分类

示例按照以下顶层分类组织：

| 分类 | 涵盖内容 |
|---|---|
| [`model-providers/`](./model-providers/) | 外部模型 API（OpenAI, Anthropic, xAI, Google, ElevenLabs, vLLM） |
| [`model-tasks/`](./model-tasks/) | 本地模型任务（chat, embedding, TTS, vision 等）—— HuggingFace / llama.cpp / vLLM |
| [`agents/`](./agents/) | 使用 ReAct 循环和工具调用的自主智能体 |
| [`showcase/`](./showcase/) | 组合多个组件的端到端管道 |
| [`media-processing/`](./media-processing/) | 音频、视频、图像处理组件 |
| [`web-automation/`](./web-automation/) | 网页抓取和浏览器自动化 |
| [`text-processing/`](./text-processing/) | 文本分割和预处理 |
| [`data-streaming/`](./data-streaming/) | 流式输入/输出（帧、实时聊天） |
| [`job-flow/`](./job-flow/) | 工作流控制：条件路由、hook、interrupt |
| [`workflow-queue/`](./workflow-queue/) | 基于队列的分布式工作流执行 |
| [`mcp-servers/`](./mcp-servers/) | 构建 MCP（Model Context Protocol）服务器 |
| [`integrations/`](./integrations/) | 外部基础设施（channels, stores, search, datasets, gateway） |
| [`runtime/`](./runtime/) | 组件执行运行时（Docker, Apple Container, virtualenv 等） |

---

## 🎯 按分类浏览示例

### Model Providers

通过 HTTP 客户端访问的外部模型 API。

#### OpenAI
- [openai-chat-completions](./model-providers/openai/openai-chat-completions/) — 与 GPT 模型对话
- [openai-chat-completions-stream](./model-providers/openai/openai-chat-completions-stream/) — 流式对话响应
- [openai-audio-speech](./model-providers/openai/openai-audio-speech/) — 使用 OpenAI TTS 的文本转语音
- [openai-audio-transciptions](./model-providers/openai/openai-audio-transciptions/) — 音频转录（Whisper）
- [openai-image-generations](./model-providers/openai/openai-image-generations/) — 使用 DALL-E 生成图像
- [openai-image-generations-multi](./model-providers/openai/openai-image-generations-multi/) — 多图像生成
- [openai-image-edits](./model-providers/openai/openai-image-edits/) — 使用 DALL-E 编辑图像
- [openai-image-variations](./model-providers/openai/openai-image-variations/) — 创建图像变体

#### Anthropic
- [anthropic-chat-completions](./model-providers/anthropic/anthropic-chat-completions/) — 与 Claude 模型对话
- [anthropic-chat-completions-stream](./model-providers/anthropic/anthropic-chat-completions-stream/) — 使用 Claude 的流式对话

#### xAI
- [xai-chat-completion](./model-providers/xai/xai-chat-completion/) — 与 Grok 模型对话

#### Google Cloud
- [google-cloud-vision](./model-providers/google/google-cloud-vision/) — 使用 Google Cloud Vision API 分析图像

#### ElevenLabs
- [elevenlabs-text-to-speech](./model-providers/elevenlabs/elevenlabs-text-to-speech/) — 高质量 TTS

#### vLLM
- [vllm-chat-completion-stream](./model-providers/vllm/vllm-chat-completion-stream/) — 通过 vLLM 服务器的流式对话
- [vllm-text-to-speech](./model-providers/vllm/vllm-text-to-speech/) — 通过 vLLM-Omni 的 Qwen3-TTS 语音合成

### 本地模型任务

通过 HuggingFace、llama.cpp 或 vLLM 执行本地模型。

#### 对话与文本生成
- [chat-completion/huggingface](./model-tasks/chat-completion/huggingface/) — 使用 HuggingFace LLM 对话
- [chat-completion/llamacpp](./model-tasks/chat-completion/llamacpp/) — 通过 llama.cpp 使用 GGUF 模型对话
- [text-generation](./model-tasks/text-generation/) — 文本生成
- [text-generation-lora](./model-tasks/text-generation-lora/) — 基于 LoRA 适配器的文本生成
- [text-generation-llamacpp](./model-tasks/text-generation-llamacpp/) — 通过 llama.cpp 生成文本

#### 文本处理
- [summarization](./model-tasks/summarization/) — 文本摘要
- [summarization-stream](./model-tasks/summarization-stream/) — 流式摘要
- [translation](./model-tasks/translation/) — 文本翻译
- [translation-stream](./model-tasks/translation-stream/) — 流式翻译
- [text-classification](./model-tasks/text-classification/) — 文本分类
- [text-reranking](./model-tasks/text-reranking/) — 针对查询对文档进行重排序

#### 嵌入
- [text-embedding](./model-tasks/text-embedding/) — 文本嵌入
- [text-embedding-llamacpp](./model-tasks/text-embedding-llamacpp/) — 通过 llama.cpp 生成嵌入
- [face-embedding](./model-tasks/face-embedding/) — 基于 InsightFace 的人脸嵌入

#### 视觉
- [image-to-text](./model-tasks/image-to-text/) — 图像描述
- [image-text-to-text/huggingface](./model-tasks/image-text-to-text/huggingface/) — HuggingFace VLM (Qwen2.5-VL)
- [image-text-to-text/vllm](./model-tasks/image-text-to-text/vllm/) — 基于 vLLM 的 VLM OCR (olmOCR)
- [image-upscale](./model-tasks/image-upscale/) — 图像放大
- [image-background-removal](./model-tasks/image-background-removal/) — 去除图像背景
- [face-swap](./model-tasks/face-swap/) — 人脸替换
- [pose-detection](./model-tasks/pose-detection/) — 人体姿态检测

#### 语音 / 音频
- [speech-to-text](./model-tasks/speech-to-text/) — 语音识别
- [text-to-speech-generate](./model-tasks/text-to-speech-generate/) — 基础 TTS
- [text-to-speech-design](./model-tasks/text-to-speech-design/) — 基于语音设计的 TTS
- [text-to-speech-clone](./model-tasks/text-to-speech-clone/) — 语音克隆 TTS
- [text-to-speech-to-text](./model-tasks/text-to-speech-to-text/) — TTS → STT 往返
- [music-generation](./model-tasks/music-generation/) — 音乐生成

### Agents

使用 ReAct 循环和工具调用的自主智能体。

- [code-reviewer](./agents/code-reviewer/) — 自动代码审查智能体
- [design-md-generator](./agents/design-md-generator/) — 基于网站分析生成 DESIGN.md
- [disk-analyzer](./agents/disk-analyzer/) — 磁盘使用分析智能体
- [human-in-the-loop](./agents/human-in-the-loop/) — 对危险操作的审批门
- [kpop-fancam-collector](./agents/kpop-fancam-collector/) — K-pop 粉丝拍摄发现/收集智能体
- [multi-tool](./agents/multi-tool/) — 多工具智能体演示
- [rag-assistant](./agents/rag-assistant/) — 基于 RAG 的知识库问答
- [web-page-analyzer](./agents/web-page-analyzer/) — 网页内容分析
- [web-researcher](./agents/web-researcher/) — 自主网络研究智能体
- [web3-airdrop-hunter](./agents/web3-airdrop-hunter/) — Web3 空投发现智能体

### Showcase

组合多个组件的端到端管道。

- [analyze-disk-usage](./showcase/analyze-disk-usage/) — 收集磁盘使用数据 → GPT-4o 分析
- [make-inspiring-quote-voice](./showcase/make-inspiring-quote-voice/) — 生成名言 → 转换为语音
- [find-person-scenes](./showcase/find-person-scenes/) — 通过人脸嵌入定位视频中目标人物出现的场景
- [vibevoice-realtime-tts](./showcase/vibevoice-realtime-tts/) — 基于 Microsoft VibeVoice 的实时 WebSocket TTS
- [echo-server](./showcase/echo-server/) — 最小 HTTP 回显服务器

### Media Processing

音频、视频、图像处理组件。

- [audio-extractor](./media-processing/audio-extractor/) — 从视频中提取音频
- [audio-feature-extractor](./media-processing/audio-feature-extractor/) — 提取频谱/波形特征
- [video-converter](./media-processing/video-converter/) — 视频格式/编解码器转换
- [video-scene-detector](./media-processing/video-scene-detector/) — 检测视频场景变化
- [image-processor](./media-processing/image-processor/) — 缩放、裁剪、旋转、滤镜、调整
- [image-processor-dual-input](./media-processing/image-processor-dual-input/) — URL + 上传双输入图像处理

### Web Automation

- [web-scraper](./web-automation/web-scraper/) — 基于 CSS/XPath 选择器的网页抓取
- [web-browser](./web-automation/web-browser/) — 无头浏览器自动化（支持 CAPTCHA 处理）
- [capture-youtube-video](./web-automation/capture-youtube-video/) — 通过浏览器录制 YouTube 播放

### Text Processing

- [split-text](./text-processing/split-text/) — 支持重叠配置的文本分块

### Data Streaming

流式输入/输出。

- [video-to-frames](./data-streaming/video-to-frames/) — 视频帧流式传输
- [dir-videos-to-frames](./data-streaming/dir-videos-to-frames/) — 目录内所有视频的帧流式传输
- [youtube-live-chat](./data-streaming/youtube-live-chat/) — YouTube 实时聊天消息流式传输

### Job Flow

工作流控制模式。

#### Conditional Routing
- [conditional-routing/if](./job-flow/conditional-routing/if/) — `if` 条件路由
- [conditional-routing/switch](./job-flow/conditional-routing/switch/) — `switch` 路由
- [conditional-routing/random](./job-flow/conditional-routing/random/) — 随机路由

#### Job 生命周期
- [hook](./job-flow/hook/) — before/after Python hook
- [interrupt](./job-flow/interrupt/) — 人工审批门

### Workflow Queue

通过 Redis 队列进行分布式工作流执行。

- [non-stream](./workflow-queue/non-stream/) — 基础 dispatcher/subscriber 模式
- [stream](./workflow-queue/stream/) — 基于 Redis Streams 和 SSE 的流式输出

### MCP Servers

使用 model-compose 构建 MCP（Model Context Protocol）服务器。

- [korea-dart-mcp](./mcp-servers/korea-dart-mcp/) — 暴露 Korea DART 披露信息的 MCP 服务器
- [slack-bot](./mcp-servers/slack-bot/) — 支持 Slack 机器人的 MCP 服务器

### Integrations

外部基础设施集成。

#### Channels
- [channels/telegram](./integrations/channels/telegram/) — 基于 webhook 的 Telegram 机器人

#### Vector Stores
- [vector-store/chroma](./integrations/vector-store/chroma/) — ChromaDB
- [vector-store/milvus](./integrations/vector-store/milvus/) — Milvus

#### Graph Stores
- [graph-store/neo4j](./integrations/graph-store/neo4j/) — Neo4j
- [graph-store/arangodb](./integrations/graph-store/arangodb/) — ArangoDB

#### Key-Value Stores
- [key-value-store/redis](./integrations/key-value-store/redis/) — Redis

#### Search Engines
- [search-engine/sqlite](./integrations/search-engine/sqlite/) — SQLite FTS

#### Datasets
- [datasets/huggingface](./integrations/datasets/huggingface/) — HuggingFace datasets

#### Gateway（隧道）
- [gateway/http-tunnel/ngrok](./integrations/gateway/http-tunnel/ngrok/) — ngrok HTTP 隧道
- [gateway/http-tunnel/cloudflare](./integrations/gateway/http-tunnel/cloudflare/) — Cloudflare 隧道
- [gateway/http-tunnel/cloudflare-named](./integrations/gateway/http-tunnel/cloudflare-named/) — Cloudflare 命名隧道
- [gateway/ssh-tunnel](./integrations/gateway/ssh-tunnel/) — SSH 远程端口转发

### Runtime

组件执行运行时。

- [process](./runtime/process/) — 原生进程
- [embedded](./runtime/embedded/) — 嵌入控制器进程内运行
- [virtualenv-python](./runtime/virtualenv-python/) — Python virtualenv
- [virtualenv-pyenv](./runtime/virtualenv-pyenv/) — pyenv 管理的 virtualenv
- [docker-shell](./runtime/docker-shell/) — Docker 容器内的 shell 命令
- [docker-model](./runtime/docker-model/) — Docker 容器内的本地模型
- [docker-custom-image](./runtime/docker-custom-image/) — 自定义 Docker 镜像构建
- [docker-nginx](./runtime/docker-nginx/) — Nginx 容器提供静态文件服务
- [apple-container](./runtime/apple-container/) — Apple Container 运行时

---

## 🚀 下一步

1. 浏览与您用例匹配的分类
2. 复制示例作为项目起点
3. 根据需要修改 `model-compose.yml`
4. 详细文档请参考 [User Guide](../docs/user-guide/)

---

## 🤝 贡献示例

有实用的示例想要分享？

1. 在 `examples/` 下对应分类中创建新目录
2. 添加 `model-compose.yml` 文件
3. 参考相邻示例的样式编写 `README.md`、`README.ko.md` 和 `README.zh-cn.md`
4. 更新本索引
5. 提交 Pull Request

---

## 📚 更多资源

- [User Guide](../docs/user-guide/) — 综合文档
- [GitHub Repository](https://github.com/hanyeol/model-compose) — 源代码与 issues

---

## 📖 其他语言

- **🇬🇧 English**: [English User Guide](README.md)
- **🇰🇷 한국어**: [한국어 사용자 가이드](README.ko.md)

---

**Happy Composing! 🎉**

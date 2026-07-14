# Model-Compose Examples

This directory contains practical examples demonstrating the features and use cases of model-compose. Each example includes a ready-to-run `model-compose.yml` configuration file along with locale-specific READMEs.

## 📋 Quick Start

To run any example:

```bash
cd examples/<category>/<example-name>
model-compose up
```

Or run a workflow directly:

```bash
cd examples/<category>/<example-name>
model-compose run <workflow-name> --input '{"key": "value"}'
```

---

## 📂 Example Structure

Each example directory typically contains:

```
example-name/
├── model-compose.yml       # Main configuration file
├── README.md               # Example-specific documentation (English)
├── README.ko.md            # Korean documentation
├── README.zh-cn.md         # Simplified Chinese documentation
└── .env.sample             # Environment variable template (optional)
```

---

## 🔑 Environment Variables

Many examples require API keys. Create a `.env` file in the example directory:

```bash
# OpenAI examples
OPENAI_API_KEY=your-api-key

# Anthropic examples
ANTHROPIC_API_KEY=your-api-key

# xAI examples
XAI_API_KEY=your-api-key

# ElevenLabs examples
ELEVENLABS_API_KEY=your-api-key

# HuggingFace examples
HUGGINGFACE_TOKEN=your-token-here
```

---

## 🗂️ Categories

The examples are organized into the following top-level categories:

| Category | What it covers |
|---|---|
| [`model-providers/`](./model-providers/) | External model APIs (OpenAI, Anthropic, xAI, Google, ElevenLabs, vLLM) |
| [`model-tasks/`](./model-tasks/) | Local model tasks (chat, embedding, TTS, vision, etc.) via HuggingFace / llama.cpp / vLLM |
| [`agents/`](./agents/) | Autonomous agents with ReAct loops and tool use |
| [`showcase/`](./showcase/) | End-to-end pipelines combining multiple components |
| [`media-processing/`](./media-processing/) | Audio, video, and image processing components |
| [`web-automation/`](./web-automation/) | Web scraping and browser automation |
| [`text-processing/`](./text-processing/) | Text splitting and preprocessing |
| [`data-streaming/`](./data-streaming/) | Streaming inputs/outputs (frames, live chat) |
| [`job-flow/`](./job-flow/) | Workflow control: conditional routing, hooks, interrupts |
| [`workflow-queue/`](./workflow-queue/) | Distributed workflow execution via a queue |
| [`mcp-servers/`](./mcp-servers/) | Building MCP (Model Context Protocol) servers |
| [`integrations/`](./integrations/) | External infrastructure (channels, stores, search, datasets, gateway) |
| [`runtime/`](./runtime/) | Component execution runtimes (Docker, Apple Container, virtualenv, etc.) |

---

## 🎯 Examples by Category

### Model Providers

External model APIs accessed through HTTP clients.

#### OpenAI
- [openai-chat-completions](./model-providers/openai/openai-chat-completions/) — Chat with GPT models
- [openai-chat-completions-stream](./model-providers/openai/openai-chat-completions-stream/) — Streaming chat responses
- [openai-audio-speech](./model-providers/openai/openai-audio-speech/) — Text-to-speech using OpenAI TTS
- [openai-audio-transciptions](./model-providers/openai/openai-audio-transciptions/) — Audio transcription (Whisper)
- [openai-image-generations](./model-providers/openai/openai-image-generations/) — Image generation with DALL-E
- [openai-image-generations-multi](./model-providers/openai/openai-image-generations-multi/) — Multi-image generation
- [openai-image-edits](./model-providers/openai/openai-image-edits/) — Image editing with DALL-E
- [openai-image-variations](./model-providers/openai/openai-image-variations/) — Create image variations

#### Anthropic
- [anthropic-chat-completions](./model-providers/anthropic/anthropic-chat-completions/) — Chat with Claude models
- [anthropic-chat-completions-stream](./model-providers/anthropic/anthropic-chat-completions-stream/) — Streaming chat with Claude

#### xAI
- [xai-chat-completion](./model-providers/xai/xai-chat-completion/) — Chat with Grok models

#### Google Cloud
- [google-cloud-vision](./model-providers/google/google-cloud-vision/) — Image analysis with Google Cloud Vision API

#### ElevenLabs
- [elevenlabs-text-to-speech](./model-providers/elevenlabs/elevenlabs-text-to-speech/) — High-quality TTS

#### vLLM
- [vllm-chat-completion-stream](./model-providers/vllm/vllm-chat-completion-stream/) — Streaming chat via vLLM server
- [vllm-text-to-speech](./model-providers/vllm/vllm-text-to-speech/) — Text-to-speech with Qwen3-TTS via vLLM-Omni

### Local Model Tasks

Local model execution via HuggingFace, llama.cpp, or vLLM.

#### Chat & Text Generation
- [chat-completion/huggingface](./model-tasks/chat-completion/huggingface/) — Chat with a HuggingFace LLM
- [chat-completion/llamacpp](./model-tasks/chat-completion/llamacpp/) — Chat with a GGUF model via llama.cpp
- [text-generation](./model-tasks/text-generation/) — Text generation
- [text-generation-lora](./model-tasks/text-generation-lora/) — Text generation with LoRA adapters
- [text-generation-llamacpp](./model-tasks/text-generation-llamacpp/) — Text generation via llama.cpp

#### Text Processing
- [summarization](./model-tasks/summarization/) — Summarize text
- [summarization-stream](./model-tasks/summarization-stream/) — Streaming summarization
- [translation](./model-tasks/translation/) — Translate text
- [translation-stream](./model-tasks/translation-stream/) — Streaming translation
- [text-classification](./model-tasks/text-classification/) — Classify text
- [text-reranking](./model-tasks/text-reranking/) — Rerank documents against a query

#### Embeddings
- [text-embedding](./model-tasks/text-embedding/) — Text embeddings
- [text-embedding-llamacpp](./model-tasks/text-embedding-llamacpp/) — Embeddings via llama.cpp
- [face-embedding](./model-tasks/face-embedding/) — Face embeddings (InsightFace)

#### Vision
- [image-to-text](./model-tasks/image-to-text/) — Image captioning
- [image-text-to-text/huggingface](./model-tasks/image-text-to-text/huggingface/) — VLM (Qwen2.5-VL) via HuggingFace
- [image-text-to-text/vllm](./model-tasks/image-text-to-text/vllm/) — VLM OCR (olmOCR) via vLLM
- [image-upscale](./model-tasks/image-upscale/) — Upscale images
- [image-background-removal](./model-tasks/image-background-removal/) — Remove image backgrounds
- [face-swap](./model-tasks/face-swap/) — Face swapping
- [pose-detection](./model-tasks/pose-detection/) — Human pose detection

#### Speech / Audio
- [speech-to-text](./model-tasks/speech-to-text/) — Speech recognition
- [text-to-speech-generate](./model-tasks/text-to-speech-generate/) — Basic TTS
- [text-to-speech-design](./model-tasks/text-to-speech-design/) — TTS with voice design
- [text-to-speech-clone](./model-tasks/text-to-speech-clone/) — Voice cloning TTS
- [text-to-speech-to-text](./model-tasks/text-to-speech-to-text/) — TTS → STT round-trip
- [music-generation](./model-tasks/music-generation/) — Music generation

### Agents

Autonomous agents with ReAct loops and tool use.

- [code-reviewer](./agents/code-reviewer/) — Automated code review agent
- [design-md-generator](./agents/design-md-generator/) — Generate DESIGN.md from website analysis
- [disk-analyzer](./agents/disk-analyzer/) — Disk usage analysis agent
- [human-in-the-loop](./agents/human-in-the-loop/) — Approval gates for dangerous operations
- [kpop-fancam-collector](./agents/kpop-fancam-collector/) — K-pop fancam discovery/collection agent
- [multi-tool](./agents/multi-tool/) — Multi-tool agent demonstration
- [rag-assistant](./agents/rag-assistant/) — RAG-based knowledge base Q&A
- [web-page-analyzer](./agents/web-page-analyzer/) — Web page content analysis
- [web-researcher](./agents/web-researcher/) — Autonomous web research agent
- [web3-airdrop-hunter](./agents/web3-airdrop-hunter/) — Web3 airdrop discovery agent

### Showcase

End-to-end pipelines combining multiple components.

- [analyze-disk-usage](./showcase/analyze-disk-usage/) — Collect disk usage → GPT-4o analysis
- [make-inspiring-quote-voice](./showcase/make-inspiring-quote-voice/) — Generate a quote → convert to speech
- [find-person-scenes](./showcase/find-person-scenes/) — Locate a target person's scenes in a video via face embedding
- [vibevoice-realtime-tts](./showcase/vibevoice-realtime-tts/) — Real-time WebSocket TTS with Microsoft VibeVoice
- [echo-server](./showcase/echo-server/) — Minimal HTTP echo server

### Media Processing

Audio, video, and image processing components.

- [audio-extractor](./media-processing/audio-extractor/) — Extract audio from video files
- [audio-feature-extractor](./media-processing/audio-feature-extractor/) — Extract spectrum/waveform features
- [video-converter](./media-processing/video-converter/) — Video format/codec conversion
- [video-scene-detector](./media-processing/video-scene-detector/) — Detect scene changes in videos
- [image-processor](./media-processing/image-processor/) — Resize, crop, rotate, filter, adjust
- [image-processor-dual-input](./media-processing/image-processor-dual-input/) — Image processing from URL + upload

### Web Automation

- [web-scraper](./web-automation/web-scraper/) — Web scraping with CSS/XPath selectors
- [web-browser](./web-automation/web-browser/) — Headless browser automation with CAPTCHA handling
- [capture-youtube-video](./web-automation/capture-youtube-video/) — Record YouTube playback via browser

### Text Processing

- [split-text](./text-processing/split-text/) — Text chunking with configurable overlap

### Data Streaming

Streaming inputs/outputs.

- [video-to-frames](./data-streaming/video-to-frames/) — Stream video frames
- [dir-videos-to-frames](./data-streaming/dir-videos-to-frames/) — Stream frames across all videos in a directory
- [youtube-live-chat](./data-streaming/youtube-live-chat/) — Stream YouTube live chat messages

### Job Flow

Workflow control patterns.

#### Conditional Routing
- [conditional-routing/if](./job-flow/conditional-routing/if/) — `if` condition routing
- [conditional-routing/switch](./job-flow/conditional-routing/switch/) — `switch` routing
- [conditional-routing/random](./job-flow/conditional-routing/random/) — Random routing

#### Job Lifecycle
- [hook](./job-flow/hook/) — Before/after Python hooks
- [interrupt](./job-flow/interrupt/) — Human-in-the-loop approval gate

### Workflow Queue

Distributed workflow execution via a Redis queue.

- [non-stream](./workflow-queue/non-stream/) — Basic dispatcher/subscriber pattern
- [stream](./workflow-queue/stream/) — Streaming output via Redis Streams and SSE

### MCP Servers

Building MCP (Model Context Protocol) servers with model-compose.

- [korea-dart-mcp](./mcp-servers/korea-dart-mcp/) — MCP server exposing Korea DART filings
- [slack-bot](./mcp-servers/slack-bot/) — MCP server backing a Slack bot

### Integrations

External infrastructure integrations.

#### Channels
- [channels/telegram](./integrations/channels/telegram/) — Telegram bot with webhook

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

#### Gateway (Tunnels)
- [gateway/http-tunnel/ngrok](./integrations/gateway/http-tunnel/ngrok/) — ngrok HTTP tunnel
- [gateway/http-tunnel/cloudflare](./integrations/gateway/http-tunnel/cloudflare/) — Cloudflare tunnel
- [gateway/http-tunnel/cloudflare-named](./integrations/gateway/http-tunnel/cloudflare-named/) — Cloudflare named tunnel
- [gateway/ssh-tunnel](./integrations/gateway/ssh-tunnel/) — SSH remote port forwarding

### Runtime

Component execution runtimes.

- [process](./runtime/process/) — Native process
- [embedded](./runtime/embedded/) — Embedded in the controller process
- [virtualenv-python](./runtime/virtualenv-python/) — Python virtualenv
- [virtualenv-pyenv](./runtime/virtualenv-pyenv/) — pyenv-managed virtualenv
- [docker-shell](./runtime/docker-shell/) — Shell command in a Docker container
- [docker-model](./runtime/docker-model/) — Local model in a Docker container
- [docker-custom-image](./runtime/docker-custom-image/) — Custom Docker image build
- [docker-nginx](./runtime/docker-nginx/) — Static file server via Nginx container
- [apple-container](./runtime/apple-container/) — Apple Container runtime

---

## 🚀 Next Steps

1. Browse the categories that match your use case
2. Copy an example as a starting point for your project
3. Modify `model-compose.yml` to fit your needs
4. Refer to the [User Guide](../docs/user-guide/) for detailed documentation

---

## 🤝 Contributing Examples

Have a useful example to share?

1. Create a new directory under the matching category in `examples/`
2. Add a `model-compose.yml` file
3. Add `README.md`, `README.ko.md`, and `README.zh-cn.md` following the style of neighboring examples
4. Update this index
5. Submit a pull request

---

## 📚 Additional Resources

- [User Guide](../docs/user-guide/) — Comprehensive documentation
- [GitHub Repository](https://github.com/hanyeol/model-compose) — Source code and issues

---

## 📖 Other Languages

- **🇰🇷 한국어**: [한국어 사용자 가이드](README.ko.md)
- **🇨🇳 简体中文**: [简体中文用户指南](README.zh-cn.md)

---

**Happy Composing! 🎉**

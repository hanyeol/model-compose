# Model-Compose Examples

This directory contains practical examples demonstrating various features and use cases of model-compose. Each example includes a ready-to-run `model-compose.yml` configuration file.

## 📋 Quick Start

To run any example:

```bash
cd examples/<example-name>
model-compose up
```

Or run a workflow directly:

```bash
cd examples/<example-name>
model-compose run <workflow-name> --input '{"key": "value"}'
```

---

## 📂 Example Structure

Each example directory typically contains:

```
example-name/
├── model-compose.yml   # Main configuration file
├── README.md           # Example-specific documentation (optional)
└── .env.example        # Environment variable template (optional)
```

---

## 🔑 Environment Variables

Many examples require API keys. Create a `.env` file in the example directory:

```bash
# For OpenAI examples
OPENAI_API_KEY=your-api-key

# For Anthropic examples
ANTHROPIC_API_KEY=your-api-key

# For ElevenLabs examples
ELEVENLABS_API_KEY=your-api-key

# For HuggingFace examples
HUGGINGFACE_TOKEN=your-token-here
```

---

## 🎯 Examples by Category

### External API Integration

#### OpenAI API
- **[openai-chat-completions](./model-providers/openai/openai-chat-completions/)** - Chat with GPT models
- **[openai-chat-completions-stream](./model-providers/openai/openai-chat-completions-stream/)** - Streaming chat responses
- **[openai-audio-speech](./model-providers/openai/openai-audio-speech/)** - Text-to-speech using OpenAI TTS
- **[openai-audio-transciptions](./model-providers/openai/openai-audio-transciptions/)** - Audio transcription (Whisper)
- **[openai-image-generations](./model-providers/openai/openai-image-generations/)** - Image generation with DALL-E
- **[openai-image-edits](./model-providers/openai/openai-image-edits/)** - Image editing with DALL-E
- **[openai-image-variations](./model-providers/openai/openai-image-variations/)** - Create image variations

#### Anthropic API
- **[anthropic-chat-completions](./model-providers/anthropic/anthropic-chat-completions/)** - Chat with Claude models
- **[anthropic-chat-completions-stream](./model-providers/anthropic/anthropic-chat-completions-stream/)** - Streaming chat with Claude

#### xAI API
- **[xai-chat-completion](./model-providers/xai/xai-chat-completion/)** - Chat with xAI's Grok models

#### Google Cloud API
- **[google-cloud-vision](./model-providers/google/google-cloud-vision/)** - Image analysis with Google Cloud Vision API

#### Other Services
- **[elevenlabs-text-to-speech](./model-providers/elevenlabs/elevenlabs-text-to-speech/)** - High-quality TTS with ElevenLabs

### AI Agents

- **[agents](./agents/)** - Autonomous AI agent examples with ReAct loops and tool usage
  - [code-reviewer](./agents/code-reviewer/) - Automated code review agent
  - [design-md-generator](./agents/design-md-generator/) - Generate DESIGN.md from website analysis
  - [disk-analyzer](./agents/disk-analyzer/) - Disk usage analysis agent
  - [human-in-the-loop](./agents/human-in-the-loop/) - Agent with approval gates for dangerous operations
  - [multi-tool](./agents/multi-tool/) - Multi-tool agent demonstration
  - [rag-assistant](./agents/rag-assistant/) - RAG-based knowledge base Q&A agent
  - [web-page-analyzer](./agents/web-page-analyzer/) - Web page content analysis agent
  - [web-researcher](./agents/web-researcher/) - Autonomous web research agent
  - [web3-airdrop-hunter](./agents/web3-airdrop-hunter/) - Web3 airdrop discovery agent

### Multi-Step Workflows

- **[make-inspiring-quote-voice](./make-inspiring-quote-voice/)** - Generate quote text → convert to speech
- **[analyze-disk-usage](./analyze-disk-usage/)** - Analyze disk usage → generate report

### Local AI Models

- **[model-tasks](./model-tasks/)** - Various local model tasks
  - [chat-completion](./model-tasks/chat-completion/) - Chat with local LLMs
  - [text-generation](./model-tasks/text-generation/) - Generate text
  - [text-generation-lora](./model-tasks/text-generation-lora/) - Text generation with LoRA adapters
  - [summarization](./model-tasks/summarization/) - Summarize text
  - [summarization-stream](./model-tasks/summarization-stream/) - Streaming summarization
  - [translation](./model-tasks/translation/) - Translate text
  - [translation-stream](./model-tasks/translation-stream/) - Streaming translation
  - [text-classification](./model-tasks/text-classification/) - Classify text
  - [text-embedding](./model-tasks/text-embedding/) - Generate text embeddings
  - [image-to-text](./model-tasks/image-to-text/) - Image captioning
  - [image-upscale](./model-tasks/image-upscale/) - Upscale images
  - [face-embedding](./model-tasks/face-embedding/) - Generate face embeddings
- **[vllm-chat-completion-stream](./vllm-chat-completion-stream/)** - Streaming chat with vLLM
- **[vllm-text-to-speech](./vllm-text-to-speech/)** - Text-to-speech with Qwen3-TTS via vLLM-Omni
- **[vibevoice-realtime-tts](./vibevoice-realtime-tts/)** - Real-time TTS via WebSocket with VibeVoice

### Audio & Video Processing

- **[audio-extractor](./audio-extractor/)** - Extract audio from video files with format conversion
- **[video-converter](./video-converter/)** - Video format conversion with configurable encoding
- **[video-scene-detector](./video-scene-detector/)** - Scene change detection in video files

### Data Processing

- **[split-text](./split-text/)** - Text splitting and processing
- **[image-processor](./image-processor/)** - Image processing workflows

### Web Automation

- **[web-browser](./web-browser/)** - Headless browser automation with CAPTCHA handling
- **[web-scraper](./web-scraper/)** - Multi-purpose web scraping with CSS/XPath selectors

### Data Stores

- **[vector-store](./vector-store/)** - Vector database integration
  - [chroma](./vector-store/chroma/) - ChromaDB integration
  - [milvus](./vector-store/milvus/) - Milvus vector database
- **[graph-store](./graph-store/)** - Graph database integration
  - [neo4j](./graph-store/neo4j/) - Neo4j graph database
  - [arangodb](./graph-store/arangodb/) - ArangoDB graph store
- **[key-value-store](./key-value-store/)** - Key-value store integration
  - [redis](./key-value-store/redis/) - Redis KV store operations

### Data Management

- **[datasets](./datasets/)** - Dataset loading and manipulation
  - [huggingface](./datasets/huggingface/) - HuggingFace datasets integration

### Distributed Workflows

- **[workflow-queue](./workflow-queue/)** - Distributed workflow execution via Redis queue
- **[workflow-queue-stream](./workflow-queue-stream/)** - Distributed streaming output via Redis Streams and SSE

### Integration Channels

- **[channels](./channels/)** - External messaging platform integrations
  - [telegram](./channels/telegram/) - Telegram bot with webhook

### Workflow Control

- **[interrupt](./interrupt/)** - Human-in-the-loop workflow control with approval gates

### Infrastructure

- **[docker](./docker/)** - Docker container runtime example
- **[gateway](./gateway/)** - Tunneling and port forwarding
  - [ngrok](./gateway/http-tunnel/ngrok/) - ngrok HTTP tunnel
  - [cloudflare](./gateway/http-tunnel/cloudflare/) - Cloudflare tunnel
  - [cloudflare-named](./gateway/http-tunnel/cloudflare-named/) - Cloudflare named tunnel
  - [ssh-tunnel](./gateway/ssh-tunnel/) - SSH remote port forwarding

### Server & Integration

- **[echo-server](./echo-server/)** - Simple HTTP server example
- **[mcp-servers](./mcp-servers/)** - Model Context Protocol server examples

---

## 🧩 Examples by Component

Browse examples organized by the component types they demonstrate:

### HTTP Client Component
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

### Agent Component
- [agents/code-reviewer](./agents/code-reviewer/)
- [agents/design-md-generator](./agents/design-md-generator/)
- [agents/disk-analyzer](./agents/disk-analyzer/)
- [agents/human-in-the-loop](./agents/human-in-the-loop/)
- [agents/multi-tool](./agents/multi-tool/)
- [agents/rag-assistant](./agents/rag-assistant/)
- [agents/web-page-analyzer](./agents/web-page-analyzer/)
- [agents/web-researcher](./agents/web-researcher/)
- [agents/web3-airdrop-hunter](./agents/web3-airdrop-hunter/)

### Model Component (Local AI)

#### Chat & Text Generation
- [model-tasks/chat-completion](./model-tasks/chat-completion/)
- [model-tasks/text-generation](./model-tasks/text-generation/)
- [model-tasks/text-generation-lora](./model-tasks/text-generation-lora/)
- [vllm-chat-completion-stream](./vllm-chat-completion-stream/)
- [vllm-text-to-speech](./vllm-text-to-speech/)

#### Text Processing
- [model-tasks/summarization](./model-tasks/summarization/)
- [model-tasks/summarization-stream](./model-tasks/summarization-stream/)
- [model-tasks/translation](./model-tasks/translation/)
- [model-tasks/translation-stream](./model-tasks/translation-stream/)
- [model-tasks/text-classification](./model-tasks/text-classification/)

#### Embeddings
- [model-tasks/text-embedding](./model-tasks/text-embedding/)
- [model-tasks/face-embedding](./model-tasks/face-embedding/)

#### Image Processing
- [model-tasks/image-to-text](./model-tasks/image-to-text/)
- [model-tasks/image-upscale](./model-tasks/image-upscale/)

### Audio & Video Components
- [audio-extractor](./audio-extractor/)
- [video-converter](./video-converter/)
- [video-scene-detector](./video-scene-detector/)
- [vibevoice-realtime-tts](./vibevoice-realtime-tts/)

### Web Browser Component
- [web-browser](./web-browser/)

### Web Scraper Component
- [web-scraper](./web-scraper/)

### Vector Store Component
- [vector-store/chroma](./vector-store/chroma/)
- [vector-store/milvus](./vector-store/milvus/)

### Graph Store Component
- [graph-store/neo4j](./graph-store/neo4j/)
- [graph-store/arangodb](./graph-store/arangodb/)

### Key-Value Store Component
- [key-value-store/redis](./key-value-store/redis/)

### Datasets Component
- [datasets/huggingface](./datasets/huggingface/)

### Text Splitter Component
- [split-text](./split-text/)

### Image Processor Component
- [image-processor](./image-processor/)

### Shell Component
- [analyze-disk-usage](./analyze-disk-usage/)

### Workflow Component
- [workflow-queue](./workflow-queue/)
- [workflow-queue-stream](./workflow-queue-stream/)

### HTTP Server Component
- [echo-server](./echo-server/)
- [docker](./docker/)

### Gateway Component
- [gateway/http-tunnel/ngrok](./gateway/http-tunnel/ngrok/)
- [gateway/http-tunnel/cloudflare](./gateway/http-tunnel/cloudflare/)
- [gateway/http-tunnel/cloudflare-named](./gateway/http-tunnel/cloudflare-named/)
- [gateway/ssh-tunnel](./gateway/ssh-tunnel/)

---

## 🚀 Next Steps

1. Browse the examples that match your use case
2. Copy an example as a starting point for your project
3. Modify the `model-compose.yml` to fit your needs
4. Refer to the [User Guide](../docs/user-guide/) for detailed documentation

---

## 🤝 Contributing Examples

Have a useful example to share?

1. Create a new directory under `examples/`
2. Add a `model-compose.yml` file
3. Optionally add a `README.md` with specific instructions
4. Submit a pull request

---

## 📚 Additional Resources

- [User Guide](../docs/user-guide/) - Comprehensive documentation
- [GitHub Repository](https://github.com/hanyeol/model-compose) - Source code and issues

---

## 📖 Other Languages

- **🇰🇷 한국어**: [한국어 사용자 가이드](README.ko.md)
- **🇨🇳 简体中文**: [简体中文用户指南](README.zh-cn.md)

---

**Happy Composing! 🎉**

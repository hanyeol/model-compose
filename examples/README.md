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

# For ElevenLabs examples
ELEVENLABS_API_KEY=your-api-key

# For HuggingFace examples
HUGGINGFACE_TOKEN=your-token-here
```

---

## 🎯 Examples by Category

### External API Integration

#### OpenAI API
- **[openai-chat-completions](./openai-chat-completions/)** - Chat with GPT models
- **[openai-chat-completions-stream](./openai-chat-completions-stream/)** - Streaming chat responses
- **[openai-audio-speech](./openai-audio-speech/)** - Text-to-speech using OpenAI TTS
- **[openai-audio-transciptions](./openai-audio-transciptions/)** - Audio transcription (Whisper)
- **[openai-image-generations](./openai-image-generations/)** - Image generation with DALL-E
- **[openai-image-edits](./openai-image-edits/)** - Image editing with DALL-E
- **[openai-image-variations](./openai-image-variations/)** - Create image variations

#### Other Services
- **[elevenlabs-text-to-speech](./elevenlabs-text-to-speech/)** - High-quality TTS with ElevenLabs

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
- **[vllm-chat-completion-stream](./vllm-chat-completion-stream/)** - Streaming chat with vLLM (local model serving)

### Data Processing

- **[split-text](./split-text/)** - Text splitting and processing
- **[image-processor](./image-processor/)** - Image processing workflows

### Vector Databases

- **[vector-store](./vector-store/)** - Vector database integration examples
  - [chroma](./vector-store/chroma/) - ChromaDB integration
  - [milvus](./vector-store/milvus/) - Milvus vector database

### Data Management

- **[datasets](./datasets/)** - Dataset loading and manipulation
  - [huggingface](./datasets/huggingface/) - HuggingFace datasets integration

### Server & Integration

- **[echo-server](./echo-server/)** - Simple HTTP server example
- **[mcp-servers](./mcp-servers/)** - Model Context Protocol server examples

---

## 🧩 Examples by Component

Browse examples organized by the component types they demonstrate:

### HTTP Client Component
- [openai-chat-completions](./openai-chat-completions/)
- [openai-chat-completions-stream](./openai-chat-completions-stream/)
- [openai-audio-speech](./openai-audio-speech/)
- [openai-audio-transciptions](./openai-audio-transciptions/)
- [openai-image-generations](./openai-image-generations/)
- [openai-image-edits](./openai-image-edits/)
- [openai-image-variations](./openai-image-variations/)
- [elevenlabs-text-to-speech](./elevenlabs-text-to-speech/)
- [make-inspiring-quote-voice](./make-inspiring-quote-voice/)

### Model Component (Local AI)

#### Chat & Text Generation
- [model-tasks/chat-completion](./model-tasks/chat-completion/)
- [model-tasks/text-generation](./model-tasks/text-generation/)
- [model-tasks/text-generation-lora](./model-tasks/text-generation-lora/)
- [vllm-chat-completion-stream](./vllm-chat-completion-stream/)

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

### Vector Store Component
- [vector-store/chroma](./vector-store/chroma/)
- [vector-store/milvus](./vector-store/milvus/)

### Datasets Component
- [datasets/huggingface](./datasets/huggingface/)

### Text Splitter Component
- [split-text](./split-text/)

### Image Processor Component
- [image-processor](./image-processor/)

### Shell Component
- [analyze-disk-usage](./analyze-disk-usage/)

### HTTP Server Component
- [echo-server](./echo-server/)

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

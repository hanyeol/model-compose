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
| [`media-broadcast/`](./media-broadcast/) | Live broadcasting pipelines (RTMP, YouTube Live) |
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
- [typed-decision-nimble](./model-tasks/typed-decision-nimble/) — Typed decisions with per-candidate probabilities (Bespoke Nimble-9B)
- [typed-decision-kev](./model-tasks/typed-decision-kev/) — One-shot typed decisions with per-candidate probabilities (Kev-4B)

#### Embeddings
- [text-embedding](./model-tasks/text-embedding/) — Text embeddings
- [text-embedding-llamacpp](./model-tasks/text-embedding-llamacpp/) — Embeddings via llama.cpp
- [text-embedding-lfm2](./model-tasks/text-embedding-lfm2/) — Multilingual embeddings via LFM2.5-Encoder-350M
- [face-embedding](./model-tasks/face-embedding/) — Face embeddings (InsightFace)
- [voice-embedding](./model-tasks/voice-embedding/) — Speaker embeddings (pyannote.audio)
- [music-embedding-sampleid](./model-tasks/music-embedding-sampleid/) — Music embeddings (Sony Sample ID)
- [video-embedding](./model-tasks/video-embedding/) — Video-level embeddings (X-CLIP)

#### Vision
- [image-to-text](./model-tasks/image-to-text/) — Image captioning
- [image-text-to-text/huggingface](./model-tasks/image-text-to-text/huggingface/) — VLM (Qwen2.5-VL) via HuggingFace
- [image-text-to-text/vllm](./model-tasks/image-text-to-text/vllm/) — VLM OCR (olmOCR) via vLLM
- [image-generation-qwen-image](./model-tasks/image-generation-qwen-image/) — Image generation with Qwen-Image 2.1
- [image-upscale](./model-tasks/image-upscale/) — Upscale images
- [image-background-removal](./model-tasks/image-background-removal/) — Remove image backgrounds
- [image-segmentation](./model-tasks/image-segmentation/) — Segmentation masks with SAM
- [face-swap](./model-tasks/face-swap/) — Face swapping
- [pose-detection](./model-tasks/pose-detection/) — Human pose detection
- [object-detection](./model-tasks/object-detection/) — Object detection with YOLO

#### 3D Reconstruction
- [image-to-3d-anigen](./model-tasks/image-to-3d-anigen/) — Rigged 3D mesh from a single image (AniGen)
- [image-to-3d-pixal3d](./model-tasks/image-to-3d-pixal3d/) — Textured 3D mesh from a single image (Pixal3D)
- [image-to-3d-pixal3d-mv](./model-tasks/image-to-3d-pixal3d-mv/) — Textured 3D mesh from multi-view images (Pixal3D MV)
- [image-to-3d-world-mirror](./model-tasks/image-to-3d-world-mirror/) — 3D scene reconstruction with HunyuanWorld-Mirror 2.0

#### Video
- [video-to-video-animatediff](./model-tasks/video-to-video-animatediff/) — Restyle a video with a prompt via AnimateDiff (SD 1.5)
- [shot-boundary-detection](./model-tasks/shot-boundary-detection/) — Detect shot boundaries with TransNetV2
- [object-tracking](./model-tasks/object-tracking/) — Track objects across video frames (YOLO + ByteTrack/BoT-SORT)
- [face-tracking](./model-tasks/face-tracking/) — Track faces across video frames (InsightFace)
- [pose-tracking](./model-tasks/pose-tracking/) — Track human poses across video frames (YOLOv8-pose)

#### Talking Head / Lip Sync
- [talking-head-sadtalker](./model-tasks/talking-head-sadtalker/) — Portrait talking-head with SadTalker
- [talking-head-echomimic](./model-tasks/talking-head-echomimic/) — Portrait/half-body talking-head with EchoMimic
- [talking-head-float](./model-tasks/talking-head-float/) — Emotion-conditioned talking-head with Float
- [talking-head-hallo2](./model-tasks/talking-head-hallo2/) — High-resolution long-form talking-head with Hallo2
- [talking-head-hallo3](./model-tasks/talking-head-hallo3/) — DiT-based talking-head with Hallo3 (CogVideoX-5B)
- [talking-head-sonic](./model-tasks/talking-head-sonic/) — Portrait talking-head with Sonic
- [lip-sync-wav2lip](./model-tasks/lip-sync-wav2lip/) — Lip sync with Wav2Lip
- [lip-sync-latentsync](./model-tasks/lip-sync-latentsync/) — Lip sync with LatentSync
- [lip-sync-musetalk](./model-tasks/lip-sync-musetalk/) — Lip sync with MuseTalk

#### Speech / Audio
- [speech-to-text](./model-tasks/speech-to-text/) — Speech recognition
- [speech-to-text-crisper-whisper](./model-tasks/speech-to-text-crisper-whisper/) — Verbatim transcription with CrisperWhisper 2.0
- [speech-to-text-vibevoice](./model-tasks/speech-to-text-vibevoice/) — Long-form transcription with VibeVoice-ASR
- [speech-to-text-vibevoice-streaming](./model-tasks/speech-to-text-vibevoice-streaming/) — Streaming transcription with VibeVoice-ASR-Streaming
- [text-to-speech-generate](./model-tasks/text-to-speech-generate/) — Basic TTS
- [text-to-speech-design](./model-tasks/text-to-speech-design/) — TTS with voice design
- [text-to-speech-design-fireredtts3](./model-tasks/text-to-speech-design-fireredtts3/) — Voice design with FireRedTTS3-Instruct
- [text-to-speech-edit-fireredtts3](./model-tasks/text-to-speech-edit-fireredtts3/) — Speech editing with FireRedTTS3-Instruct
- [text-to-speech-clone](./model-tasks/text-to-speech-clone/) — Voice cloning TTS
- [text-to-speech-clone-cosyvoice](./model-tasks/text-to-speech-clone-cosyvoice/) — Zero-shot voice cloning with CosyVoice2
- [text-to-speech-clone-fireredtts3](./model-tasks/text-to-speech-clone-fireredtts3/) — Zero-shot voice cloning with FireRedTTS3-Base
- [text-to-speech-clone-luxtts](./model-tasks/text-to-speech-clone-luxtts/) — Zero-shot voice cloning with LuxTTS (ZipVoice)
- [text-to-speech-clone-tada](./model-tasks/text-to-speech-clone-tada/) — Voice cloning with HumeAI TADA
- [text-to-speech-to-text](./model-tasks/text-to-speech-to-text/) — TTS → STT round-trip
- [audio-text-alignment](./model-tasks/audio-text-alignment/) — Word-level forced alignment (Wav2Vec2 CTC)
- [voice-activity-detection](./model-tasks/voice-activity-detection/) — Detect speech segments with Silero VAD
- [speaker-diarization](./model-tasks/speaker-diarization/) — "Who spoke when" with pyannote.audio

#### Music
- [music-generation](./model-tasks/music-generation/) — Music generation
- [music-generation-yue2](./model-tasks/music-generation-yue2/) — Full-song generation with YuE2 (score + acoustic synthesis)
- [music-source-separation](./model-tasks/music-source-separation/) — Vocal stem separation with Demucs v4
- [music-source-separation-mdx23c-drumsep](./model-tasks/music-source-separation-mdx23c-drumsep/) — Per-piece drum stem separation with MDX23C DrumSep
- [music-transcription](./model-tasks/music-transcription/) — Notes/MIDI transcription with Spotify Basic Pitch
- [music-beat-tracking-beat-this](./model-tasks/music-beat-tracking-beat-this/) — Detect beats and downbeats with Beat This!

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
- [upscale-video](./showcase/upscale-video/) — Frame-by-frame super-resolution upscaling of a video (preserves audio)
- [echo-server](./showcase/echo-server/) — Minimal HTTP echo server

### Media Processing

Audio, video, and image processing components.

#### Audio
- [audio-extractor](./media-processing/audio-extractor/) — Extract audio from video files
- [audio-feature-extractor](./media-processing/audio-feature-extractor/) — Extract spectrum/waveform features
- [audio-analyzer](./media-processing/audio-analyzer/) — Inspect loudness, peak, gain, silence, energy
- [audio-capture](./media-processing/audio-capture/) — Capture microphone or system loopback as an AAC stream
- [audio-clipper](./media-processing/audio-clipper/) — Lossless time-range cutting via ffmpeg
- [audio-mixer](./media-processing/audio-mixer/) — Mix multiple audio sources with ffmpeg
- [audio-normalizer](./media-processing/audio-normalizer/) — LUFS loudness normalization with true-peak ceiling
- [audio-processor](./media-processing/audio-processor/) — DSP chain (EQ, dynamics, spatial, effects)
- [audio-refiner](./media-processing/audio-refiner/) — Drop silence/noise via Silero VAD + clipper
- [audio-silence-detector](./media-processing/audio-silence-detector/) — Locate silent regions with ffmpeg `silencedetect`
- [audio-spectrum-to-video](./media-processing/audio-spectrum-to-video/) — Render audio as an equalizer-style MP4
- [audio-synchronizer](./media-processing/audio-synchronizer/) — Compute time offsets between multi-source recordings
- [music-analyzer](./media-processing/music-analyzer/) — Extract rhythm/tonality/spectral properties
- [music-segment-detector](./media-processing/music-segment-detector/) — Find intro/verse/chorus segment boundaries
- [speech-to-text-with-correction](./media-processing/speech-to-text-with-correction/) — Whisper STT aligned to a reference transcript
- [speech-to-text-with-vad](./media-processing/speech-to-text-with-vad/) — Whisper STT with Silero VAD pre-segmentation

#### Video
- [video-converter](./media-processing/video-converter/) — Video format/codec conversion
- [video-scene-detector](./media-processing/video-scene-detector/) — Detect scene changes in videos
- [video-scene-splitter](./media-processing/video-scene-splitter/) — Detect and save each scene as its own file
- [video-capture](./media-processing/video-capture/) — Capture the local camera as a fragmented MP4 stream
- [video-clipper](./media-processing/video-clipper/) — Lossless time-range cutting via ffmpeg
- [video-mixer](./media-processing/video-mixer/) — Composite multiple videos with ffmpeg
- [video-playback](./media-processing/video-playback/) — Play a video in an OS-native window via ffplay
- [video-processor](./media-processing/video-processor/) — Per-frame resize/crop/pad/flip/rotate
- [video-refiner](./media-processing/video-refiner/) — VAD-driven speech-only video assembly
- [video-dubbing](./media-processing/video-dubbing/) — End-to-end dubbing (Whisper → translate → TTS → Wav2Lip)
- [video-to-gif](./media-processing/video-to-gif/) — Convert a video (or a clip) to an animated GIF
- [screen-capture](./media-processing/screen-capture/) — Capture the display/region/mic as continuous streams
- [youtube-downloader](./media-processing/youtube-downloader/) — Download YouTube videos with cookie-based auth
- [face-mosaic](./media-processing/face-mosaic/) — Pixelate/blur faces in a video (streaming, preserves audio)
- [pose-skeleton-overlay](./media-processing/pose-skeleton-overlay/) — Overlay YOLOv8-pose skeletons on every video frame
- [nsfw-mosaic](./media-processing/nsfw-mosaic/) — Pixelate/blur NSFW regions in a video (streaming, preserves audio)

#### Image
- [image-processor](./media-processing/image-processor/) — Resize, crop, rotate, filter, adjust
- [image-processor-dual-input](./media-processing/image-processor-dual-input/) — Image processing from URL + upload
- [face-gender-annotate](./media-processing/face-gender-annotate/) — Draw male/female-colored face bounding boxes
- [nsfw-annotate](./media-processing/nsfw-annotate/) — Draw labelled bounding boxes over NSFW detections
- [pose-brightness-sweep](./media-processing/pose-brightness-sweep/) — Compare YOLO-pose across brightness variants
- [html-animation-to-video](./media-processing/html-animation-to-video/) — Render an HTML animation to MP4

#### Metadata / 3D
- [media-inspector](./media-processing/media-inspector/) — Read metadata via ffprobe + exiftool
- [model-3d-converter](./media-processing/model-3d-converter/) — Convert between 3D asset formats

### Media Broadcast

Live broadcasting pipelines.

- [youtube-live](./media-broadcast/youtube-live/) — Continuous YouTube Live RTMP broadcasting driven by a shared data queue

### Web Automation

- [web-scraper](./web-automation/web-scraper/) — Web scraping with CSS/XPath selectors
- [web-browser](./web-automation/web-browser/) — Headless browser automation with CAPTCHA handling
- [capture-youtube-video](./web-automation/capture-youtube-video/) — Record YouTube playback via browser

### Text Processing

- [split-text](./text-processing/split-text/) — Text chunking with configurable overlap
- [load-document](./text-processing/load-document/) — Load and chunk PDF/DOCX/HTML documents (Docling, pypdf)

### Data Streaming

Streaming inputs/outputs.

- [video-to-frames](./data-streaming/video-to-frames/) — Stream video frames
- [video-to-frames-bulk](./data-streaming/video-to-frames-bulk/) — Stream frames across all videos in a directory
- [youtube-live-chat](./data-streaming/youtube-live-chat/) — Stream YouTube live chat messages
- [data-queue-basic](./data-streaming/data-queue-basic/) — Producer/consumer via a shared `data-queue`
- [data-queue-audio-playback](./data-streaming/data-queue-audio-playback/) — Cross-workflow queued audio playback
- [sentence-splitter](./data-streaming/sentence-splitter/) — Pipe an OpenAI stream through a sentence splitter
- [llm-streaming-voice](./data-streaming/llm-streaming-voice/) — End-to-end LLM → sentence-splitter → TTS → queued playback

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
- [audio-processor-mcp](./mcp-servers/audio-processor-mcp/) — MCP server exposing DSP audio effects over stdio

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
- [key-value-store/memory](./integrations/key-value-store/memory/) — In-memory key-value store
- [key-value-store/sqlite](./integrations/key-value-store/sqlite/) — SQLite key-value store

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

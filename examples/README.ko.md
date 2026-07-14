# Model-Compose 예제

이 디렉터리에는 model-compose의 기능과 사용 사례를 시연하는 실용 예제들이 담겨 있습니다. 각 예제는 바로 실행 가능한 `model-compose.yml` 설정 파일과 언어별 README를 포함합니다.

## 📋 빠른 시작

예제 실행:

```bash
cd examples/<category>/<example-name>
model-compose up
```

특정 워크플로만 실행:

```bash
cd examples/<category>/<example-name>
model-compose run <workflow-name> --input '{"key": "value"}'
```

---

## 📂 예제 구조

각 예제 디렉터리에는 일반적으로 다음이 포함됩니다:

```
example-name/
├── model-compose.yml       # 메인 설정 파일
├── README.md               # 영어 문서
├── README.ko.md            # 한국어 문서
├── README.zh-cn.md         # 중국어 간체 문서
└── .env.sample             # 환경 변수 템플릿 (선택)
```

---

## 🔑 환경 변수

많은 예제가 API 키를 필요로 합니다. 예제 디렉터리에 `.env` 파일을 만들어 주세요:

```bash
# OpenAI 예제
OPENAI_API_KEY=your-api-key

# Anthropic 예제
ANTHROPIC_API_KEY=your-api-key

# xAI 예제
XAI_API_KEY=your-api-key

# ElevenLabs 예제
ELEVENLABS_API_KEY=your-api-key

# HuggingFace 예제
HUGGINGFACE_TOKEN=your-token-here
```

---

## 🗂️ 카테고리

예제는 다음과 같이 최상위 카테고리로 정리되어 있습니다:

| 카테고리 | 다루는 내용 |
|---|---|
| [`model-providers/`](./model-providers/) | 외부 모델 API (OpenAI, Anthropic, xAI, Google, ElevenLabs, vLLM) |
| [`model-tasks/`](./model-tasks/) | 로컬 모델 태스크 (chat, embedding, TTS, vision 등) — HuggingFace / llama.cpp / vLLM |
| [`agents/`](./agents/) | ReAct 루프와 도구 사용을 활용한 자율 에이전트 |
| [`showcase/`](./showcase/) | 여러 컴포넌트를 조합한 end-to-end 파이프라인 |
| [`media-processing/`](./media-processing/) | 오디오, 비디오, 이미지 처리 컴포넌트 |
| [`web-automation/`](./web-automation/) | 웹 스크래핑과 브라우저 자동화 |
| [`text-processing/`](./text-processing/) | 텍스트 분할과 전처리 |
| [`data-streaming/`](./data-streaming/) | 스트리밍 입출력 (프레임, 라이브 채팅) |
| [`job-flow/`](./job-flow/) | 워크플로 제어: 조건 분기, hook, interrupt |
| [`workflow-queue/`](./workflow-queue/) | 큐 기반 분산 워크플로 실행 |
| [`mcp-servers/`](./mcp-servers/) | MCP (Model Context Protocol) 서버 구축 |
| [`integrations/`](./integrations/) | 외부 인프라 (channels, stores, search, datasets, gateway) |
| [`runtime/`](./runtime/) | 컴포넌트 실행 런타임 (Docker, Apple Container, virtualenv 등) |

---

## 🎯 카테고리별 예제

### Model Providers

HTTP 클라이언트를 통해 접근하는 외부 모델 API.

#### OpenAI
- [openai-chat-completions](./model-providers/openai/openai-chat-completions/) — GPT 모델과 채팅
- [openai-chat-completions-stream](./model-providers/openai/openai-chat-completions-stream/) — 스트리밍 채팅
- [openai-audio-speech](./model-providers/openai/openai-audio-speech/) — OpenAI TTS로 음성 합성
- [openai-audio-transciptions](./model-providers/openai/openai-audio-transciptions/) — Whisper 음성 인식
- [openai-image-generations](./model-providers/openai/openai-image-generations/) — DALL-E 이미지 생성
- [openai-image-generations-multi](./model-providers/openai/openai-image-generations-multi/) — 다중 이미지 생성
- [openai-image-edits](./model-providers/openai/openai-image-edits/) — DALL-E 이미지 편집
- [openai-image-variations](./model-providers/openai/openai-image-variations/) — 이미지 변형 생성

#### Anthropic
- [anthropic-chat-completions](./model-providers/anthropic/anthropic-chat-completions/) — Claude 모델과 채팅
- [anthropic-chat-completions-stream](./model-providers/anthropic/anthropic-chat-completions-stream/) — Claude 스트리밍 채팅

#### xAI
- [xai-chat-completion](./model-providers/xai/xai-chat-completion/) — Grok 모델과 채팅

#### Google Cloud
- [google-cloud-vision](./model-providers/google/google-cloud-vision/) — Google Cloud Vision API로 이미지 분석

#### ElevenLabs
- [elevenlabs-text-to-speech](./model-providers/elevenlabs/elevenlabs-text-to-speech/) — 고품질 TTS

#### vLLM
- [vllm-chat-completion-stream](./model-providers/vllm/vllm-chat-completion-stream/) — vLLM 서버를 통한 스트리밍 채팅
- [vllm-text-to-speech](./model-providers/vllm/vllm-text-to-speech/) — vLLM-Omni + Qwen3-TTS 음성 합성

### 로컬 모델 태스크

HuggingFace, llama.cpp, vLLM을 통한 로컬 모델 실행.

#### 채팅 및 텍스트 생성
- [chat-completion/huggingface](./model-tasks/chat-completion/huggingface/) — HuggingFace LLM 채팅
- [chat-completion/llamacpp](./model-tasks/chat-completion/llamacpp/) — llama.cpp로 GGUF 모델 채팅
- [text-generation](./model-tasks/text-generation/) — 텍스트 생성
- [text-generation-lora](./model-tasks/text-generation-lora/) — LoRA 어댑터 기반 텍스트 생성
- [text-generation-llamacpp](./model-tasks/text-generation-llamacpp/) — llama.cpp로 텍스트 생성

#### 텍스트 처리
- [summarization](./model-tasks/summarization/) — 텍스트 요약
- [summarization-stream](./model-tasks/summarization-stream/) — 스트리밍 요약
- [translation](./model-tasks/translation/) — 텍스트 번역
- [translation-stream](./model-tasks/translation-stream/) — 스트리밍 번역
- [text-classification](./model-tasks/text-classification/) — 텍스트 분류
- [text-reranking](./model-tasks/text-reranking/) — 쿼리 대비 문서 재랭킹

#### 임베딩
- [text-embedding](./model-tasks/text-embedding/) — 텍스트 임베딩
- [text-embedding-llamacpp](./model-tasks/text-embedding-llamacpp/) — llama.cpp 임베딩
- [face-embedding](./model-tasks/face-embedding/) — InsightFace 얼굴 임베딩

#### 비전
- [image-to-text](./model-tasks/image-to-text/) — 이미지 캡셔닝
- [image-text-to-text/huggingface](./model-tasks/image-text-to-text/huggingface/) — HuggingFace VLM (Qwen2.5-VL)
- [image-text-to-text/vllm](./model-tasks/image-text-to-text/vllm/) — vLLM 기반 VLM OCR (olmOCR)
- [image-upscale](./model-tasks/image-upscale/) — 이미지 업스케일
- [image-background-removal](./model-tasks/image-background-removal/) — 배경 제거
- [face-swap](./model-tasks/face-swap/) — 얼굴 스왑
- [pose-detection](./model-tasks/pose-detection/) — 인체 포즈 감지

#### 음성 / 오디오
- [speech-to-text](./model-tasks/speech-to-text/) — 음성 인식
- [text-to-speech-generate](./model-tasks/text-to-speech-generate/) — 기본 TTS
- [text-to-speech-design](./model-tasks/text-to-speech-design/) — 음성 디자인 기반 TTS
- [text-to-speech-clone](./model-tasks/text-to-speech-clone/) — 음성 클로닝 TTS
- [text-to-speech-to-text](./model-tasks/text-to-speech-to-text/) — TTS → STT 왕복
- [music-generation](./model-tasks/music-generation/) — 음악 생성

### Agents

ReAct 루프와 도구 사용을 활용한 자율 에이전트.

- [code-reviewer](./agents/code-reviewer/) — 자동 코드 리뷰 에이전트
- [design-md-generator](./agents/design-md-generator/) — 웹사이트 분석 기반 DESIGN.md 생성
- [disk-analyzer](./agents/disk-analyzer/) — 디스크 사용량 분석 에이전트
- [human-in-the-loop](./agents/human-in-the-loop/) — 위험한 작업에 대한 승인 게이트
- [kpop-fancam-collector](./agents/kpop-fancam-collector/) — K-pop 팬캠 탐색/수집 에이전트
- [multi-tool](./agents/multi-tool/) — 다중 도구 에이전트 시연
- [rag-assistant](./agents/rag-assistant/) — RAG 기반 지식 Q&A
- [web-page-analyzer](./agents/web-page-analyzer/) — 웹 페이지 콘텐츠 분석
- [web-researcher](./agents/web-researcher/) — 자율 웹 리서치 에이전트
- [web3-airdrop-hunter](./agents/web3-airdrop-hunter/) — Web3 에어드랍 탐색 에이전트

### Showcase

여러 컴포넌트를 조합한 end-to-end 파이프라인.

- [analyze-disk-usage](./showcase/analyze-disk-usage/) — 디스크 사용량 수집 → GPT-4o 분석
- [make-inspiring-quote-voice](./showcase/make-inspiring-quote-voice/) — 명언 생성 → 음성 변환
- [find-person-scenes](./showcase/find-person-scenes/) — 얼굴 임베딩으로 비디오 내 인물 등장 장면 검색
- [vibevoice-realtime-tts](./showcase/vibevoice-realtime-tts/) — Microsoft VibeVoice 기반 실시간 WebSocket TTS
- [echo-server](./showcase/echo-server/) — 최소 HTTP 에코 서버

### Media Processing

오디오, 비디오, 이미지 처리 컴포넌트.

- [audio-extractor](./media-processing/audio-extractor/) — 비디오에서 오디오 추출
- [audio-feature-extractor](./media-processing/audio-feature-extractor/) — 스펙트럼/파형 특성 추출
- [video-converter](./media-processing/video-converter/) — 비디오 포맷/코덱 변환
- [video-scene-detector](./media-processing/video-scene-detector/) — 비디오 장면 변화 감지
- [image-processor](./media-processing/image-processor/) — 리사이즈, 크롭, 회전, 필터, 조정
- [image-processor-dual-input](./media-processing/image-processor-dual-input/) — URL + 업로드 이미지 처리

### Web Automation

- [web-scraper](./web-automation/web-scraper/) — CSS/XPath 셀렉터 기반 웹 스크래핑
- [web-browser](./web-automation/web-browser/) — 헤드리스 브라우저 자동화 (CAPTCHA 대응)
- [capture-youtube-video](./web-automation/capture-youtube-video/) — 브라우저 기반 YouTube 재생 캡처

### Text Processing

- [split-text](./text-processing/split-text/) — 오버랩 설정 가능한 텍스트 청킹

### Data Streaming

스트리밍 입출력.

- [video-to-frames](./data-streaming/video-to-frames/) — 비디오 프레임 스트리밍
- [dir-videos-to-frames](./data-streaming/dir-videos-to-frames/) — 디렉터리 내 모든 비디오 프레임 스트리밍
- [youtube-live-chat](./data-streaming/youtube-live-chat/) — YouTube 라이브 채팅 스트리밍

### Job Flow

워크플로 제어 패턴.

#### Conditional Routing
- [conditional-routing/if](./job-flow/conditional-routing/if/) — `if` 조건 분기
- [conditional-routing/switch](./job-flow/conditional-routing/switch/) — `switch` 분기
- [conditional-routing/random](./job-flow/conditional-routing/random/) — 랜덤 분기

#### Job 생명주기
- [hook](./job-flow/hook/) — before/after Python hook
- [interrupt](./job-flow/interrupt/) — 인간 승인 게이트

### Workflow Queue

Redis 큐를 통한 분산 워크플로 실행.

- [non-stream](./workflow-queue/non-stream/) — 기본 dispatcher/subscriber 패턴
- [stream](./workflow-queue/stream/) — Redis Streams와 SSE 기반 스트리밍 출력

### MCP Servers

model-compose로 MCP (Model Context Protocol) 서버 구축.

- [korea-dart-mcp](./mcp-servers/korea-dart-mcp/) — Korea DART 공시 정보를 노출하는 MCP 서버
- [slack-bot](./mcp-servers/slack-bot/) — Slack 봇을 위한 MCP 서버

### Integrations

외부 인프라 통합.

#### Channels
- [channels/telegram](./integrations/channels/telegram/) — 웹훅 기반 Telegram 봇

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

#### Gateway (터널)
- [gateway/http-tunnel/ngrok](./integrations/gateway/http-tunnel/ngrok/) — ngrok HTTP 터널
- [gateway/http-tunnel/cloudflare](./integrations/gateway/http-tunnel/cloudflare/) — Cloudflare 터널
- [gateway/http-tunnel/cloudflare-named](./integrations/gateway/http-tunnel/cloudflare-named/) — Cloudflare Named 터널
- [gateway/ssh-tunnel](./integrations/gateway/ssh-tunnel/) — SSH 원격 포트 포워딩

### Runtime

컴포넌트 실행 런타임.

- [process](./runtime/process/) — 네이티브 프로세스
- [embedded](./runtime/embedded/) — 컨트롤러 프로세스 내 임베디드 실행
- [virtualenv-python](./runtime/virtualenv-python/) — Python virtualenv
- [virtualenv-pyenv](./runtime/virtualenv-pyenv/) — pyenv 관리 virtualenv
- [docker-shell](./runtime/docker-shell/) — Docker 컨테이너 내 셸 명령
- [docker-model](./runtime/docker-model/) — Docker 컨테이너 내 로컬 모델
- [docker-custom-image](./runtime/docker-custom-image/) — 커스텀 Docker 이미지 빌드
- [docker-nginx](./runtime/docker-nginx/) — Nginx 컨테이너 정적 파일 서버
- [apple-container](./runtime/apple-container/) — Apple Container 런타임

---

## 🚀 다음 단계

1. 사용 사례에 맞는 카테고리를 둘러보세요
2. 예제를 프로젝트 시작점으로 복사하세요
3. 필요에 맞게 `model-compose.yml`을 수정하세요
4. 자세한 설명은 [User Guide](../docs/user-guide/)를 참고하세요

---

## 🤝 예제 기여하기

공유할 유용한 예제가 있으신가요?

1. `examples/` 아래 적절한 카테고리에 새 디렉터리를 만드세요
2. `model-compose.yml` 파일을 추가하세요
3. 주변 예제의 스타일을 따라 `README.md`, `README.ko.md`, `README.zh-cn.md`를 작성하세요
4. 이 인덱스를 업데이트하세요
5. Pull Request를 보내주세요

---

## 📚 추가 리소스

- [User Guide](../docs/user-guide/) — 종합 문서
- [GitHub Repository](https://github.com/hanyeol/model-compose) — 소스 코드와 이슈

---

## 📖 다른 언어

- **🇬🇧 English**: [English User Guide](README.md)
- **🇨🇳 简体中文**: [简体中文用户指南](README.zh-cn.md)

---

**즐거운 컴포징 되세요! 🎉**

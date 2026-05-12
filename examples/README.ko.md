# Model-Compose 예제

이 디렉토리에는 model-compose의 다양한 기능과 사용 사례를 보여주는 실용적인 예제가 포함되어 있습니다. 각 예제에는 바로 실행 가능한 `model-compose.yml` 설정 파일이 포함되어 있습니다.

## 📋 빠른 시작

예제를 실행하려면:

```bash
cd examples/<example-name>
model-compose up
```

또는 워크플로우를 직접 실행:

```bash
cd examples/<example-name>
model-compose run <workflow-name> --input '{"key": "value"}'
```

---

## 📂 예제 구조

각 예제 디렉토리는 일반적으로 다음을 포함합니다:

```
example-name/
├── model-compose.yml   # 메인 설정 파일
├── README.md           # 예제별 문서 (선택 사항)
└── .env.example        # 환경 변수 템플릿 (선택 사항)
```

---

## 🔑 환경 변수

많은 예제에서 API 키가 필요합니다. 예제 디렉토리에 `.env` 파일을 생성하세요:

```bash
# OpenAI 예제용
OPENAI_API_KEY=your-api-key

# Anthropic 예제용
ANTHROPIC_API_KEY=your-api-key

# ElevenLabs 예제용
ELEVENLABS_API_KEY=your-api-key

# HuggingFace 예제용
HUGGINGFACE_TOKEN=your-token-here
```

---

## 🎯 카테고리별 예제

### 외부 API 통합

#### OpenAI API
- **[openai-chat-completions](./model-providers/openai/openai-chat-completions/)** - GPT 모델과 대화
- **[openai-chat-completions-stream](./model-providers/openai/openai-chat-completions-stream/)** - 스트리밍 채팅 응답
- **[openai-audio-speech](./model-providers/openai/openai-audio-speech/)** - OpenAI TTS를 사용한 텍스트 음성 변환
- **[openai-audio-transciptions](./model-providers/openai/openai-audio-transciptions/)** - 오디오 전사 (Whisper)
- **[openai-image-generations](./model-providers/openai/openai-image-generations/)** - DALL-E로 이미지 생성
- **[openai-image-edits](./model-providers/openai/openai-image-edits/)** - DALL-E로 이미지 편집
- **[openai-image-variations](./model-providers/openai/openai-image-variations/)** - 이미지 변형 생성

#### Anthropic API
- **[anthropic-chat-completions](./model-providers/anthropic/anthropic-chat-completions/)** - Claude 모델과 대화
- **[anthropic-chat-completions-stream](./model-providers/anthropic/anthropic-chat-completions-stream/)** - Claude 스트리밍 채팅

#### xAI API
- **[xai-chat-completion](./model-providers/xai/xai-chat-completion/)** - xAI의 Grok 모델과 대화

#### Google Cloud API
- **[google-cloud-vision](./model-providers/google/google-cloud-vision/)** - Google Cloud Vision API를 사용한 이미지 분석

#### 기타 서비스
- **[elevenlabs-text-to-speech](./model-providers/elevenlabs/elevenlabs-text-to-speech/)** - ElevenLabs를 사용한 고품질 TTS

### AI 에이전트

- **[agents](./agents/)** - ReAct 루프와 도구를 활용한 자율 AI 에이전트 예제
  - [code-reviewer](./agents/code-reviewer/) - 자동 코드 리뷰 에이전트
  - [design-md-generator](./agents/design-md-generator/) - 웹사이트 분석을 통한 DESIGN.md 생성
  - [disk-analyzer](./agents/disk-analyzer/) - 디스크 사용량 분석 에이전트
  - [human-in-the-loop](./agents/human-in-the-loop/) - 위험 작업에 대한 승인 게이트가 있는 에이전트
  - [multi-tool](./agents/multi-tool/) - 멀티 도구 에이전트 데모
  - [rag-assistant](./agents/rag-assistant/) - RAG 기반 지식베이스 Q&A 에이전트
  - [web-page-analyzer](./agents/web-page-analyzer/) - 웹 페이지 콘텐츠 분석 에이전트
  - [web-researcher](./agents/web-researcher/) - 자율 웹 리서치 에이전트
  - [web3-airdrop-hunter](./agents/web3-airdrop-hunter/) - Web3 에어드롭 탐색 에이전트

### 여러 단계 워크플로우

- **[make-inspiring-quote-voice](./make-inspiring-quote-voice/)** - 명언 텍스트 생성 → 음성으로 변환
- **[analyze-disk-usage](./analyze-disk-usage/)** - 디스크 사용량 분석 → 보고서 생성

### 로컬 AI 모델

- **[model-tasks](./model-tasks/)** - 다양한 로컬 모델 작업
  - [chat-completion](./model-tasks/chat-completion/) - 로컬 LLM과 채팅
  - [text-generation](./model-tasks/text-generation/) - 텍스트 생성
  - [text-generation-lora](./model-tasks/text-generation-lora/) - LoRA 어댑터를 사용한 텍스트 생성
  - [summarization](./model-tasks/summarization/) - 텍스트 요약
  - [summarization-stream](./model-tasks/summarization-stream/) - 스트리밍 요약
  - [translation](./model-tasks/translation/) - 텍스트 번역
  - [translation-stream](./model-tasks/translation-stream/) - 스트리밍 번역
  - [text-classification](./model-tasks/text-classification/) - 텍스트 분류
  - [text-embedding](./model-tasks/text-embedding/) - 텍스트 임베딩 생성
  - [image-to-text](./model-tasks/image-to-text/) - 이미지 캡셔닝
  - [image-upscale](./model-tasks/image-upscale/) - 이미지 업스케일
  - [face-embedding](./model-tasks/face-embedding/) - 얼굴 임베딩 생성
- **[vllm-chat-completion-stream](./vllm-chat-completion-stream/)** - vLLM을 사용한 스트리밍 채팅
- **[vllm-text-to-speech](./vllm-text-to-speech/)** - vLLM-Omni를 통한 Qwen3-TTS 텍스트 음성 변환
- **[vibevoice-realtime-tts](./vibevoice-realtime-tts/)** - VibeVoice를 사용한 실시간 WebSocket TTS

### 오디오 및 비디오 처리

- **[audio-extractor](./audio-extractor/)** - 비디오에서 오디오 추출 및 포맷 변환
- **[video-converter](./video-converter/)** - 비디오 포맷 변환 및 인코딩 설정
- **[video-scene-detector](./video-scene-detector/)** - 비디오 장면 전환 감지

### 데이터 처리

- **[split-text](./split-text/)** - 텍스트 분할 및 처리
- **[image-processor](./image-processor/)** - 이미지 처리 워크플로우

### 웹 자동화

- **[web-browser](./web-browser/)** - CAPTCHA 처리를 포함한 헤드리스 브라우저 자동화
- **[web-scraper](./web-scraper/)** - CSS/XPath 셀렉터를 사용한 다목적 웹 스크래핑

### 데이터 스토어

- **[vector-store](./vector-store/)** - 벡터 데이터베이스 통합
  - [chroma](./vector-store/chroma/) - ChromaDB 통합
  - [milvus](./vector-store/milvus/) - Milvus 벡터 데이터베이스
- **[graph-store](./graph-store/)** - 그래프 데이터베이스 통합
  - [neo4j](./graph-store/neo4j/) - Neo4j 그래프 데이터베이스
  - [arangodb](./graph-store/arangodb/) - ArangoDB 그래프 스토어
- **[key-value-store](./key-value-store/)** - 키-값 스토어 통합
  - [redis](./key-value-store/redis/) - Redis KV 스토어 작업

### 데이터 관리

- **[datasets](./datasets/)** - 데이터셋 로드 및 조작
  - [huggingface](./datasets/huggingface/) - HuggingFace 데이터셋 통합

### 분산 워크플로우

- **[workflow-queue](./workflow-queue/)** - Redis 큐를 통한 분산 워크플로우 실행
- **[workflow-queue-stream](./workflow-queue-stream/)** - Redis Streams 및 SSE를 통한 분산 스트리밍 출력

### 통합 채널

- **[channels](./channels/)** - 외부 메시징 플랫폼 통합
  - [telegram](./channels/telegram/) - 웹훅을 사용한 텔레그램 봇

### 워크플로우 제어

- **[interrupt](./interrupt/)** - 승인 게이트를 사용한 휴먼 인 더 루프 워크플로우 제어

### 인프라

- **[docker](./docker/)** - Docker 컨테이너 런타임 예제
- **[gateway](./gateway/)** - 터널링 및 포트 포워딩
  - [ngrok](./gateway/http-tunnel/ngrok/) - ngrok HTTP 터널
  - [cloudflare](./gateway/http-tunnel/cloudflare/) - Cloudflare 터널
  - [cloudflare-named](./gateway/http-tunnel/cloudflare-named/) - Cloudflare 네임드 터널
  - [ssh-tunnel](./gateway/ssh-tunnel/) - SSH 원격 포트 포워딩

### 서버 및 통합

- **[echo-server](./echo-server/)** - 간단한 HTTP 서버 예제
- **[mcp-servers](./mcp-servers/)** - Model Context Protocol 서버 예제

---

## 🧩 컴포넌트별 예제

시연하는 컴포넌트 유형별로 정리된 예제를 둘러보세요:

### HTTP 클라이언트 컴포넌트
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

### 에이전트 컴포넌트
- [agents/code-reviewer](./agents/code-reviewer/)
- [agents/design-md-generator](./agents/design-md-generator/)
- [agents/disk-analyzer](./agents/disk-analyzer/)
- [agents/human-in-the-loop](./agents/human-in-the-loop/)
- [agents/multi-tool](./agents/multi-tool/)
- [agents/rag-assistant](./agents/rag-assistant/)
- [agents/web-page-analyzer](./agents/web-page-analyzer/)
- [agents/web-researcher](./agents/web-researcher/)
- [agents/web3-airdrop-hunter](./agents/web3-airdrop-hunter/)

### 모델 컴포넌트 (로컬 AI)

#### 채팅 및 텍스트 생성
- [model-tasks/chat-completion](./model-tasks/chat-completion/)
- [model-tasks/text-generation](./model-tasks/text-generation/)
- [model-tasks/text-generation-lora](./model-tasks/text-generation-lora/)
- [vllm-chat-completion-stream](./vllm-chat-completion-stream/)
- [vllm-text-to-speech](./vllm-text-to-speech/)

#### 텍스트 처리
- [model-tasks/summarization](./model-tasks/summarization/)
- [model-tasks/summarization-stream](./model-tasks/summarization-stream/)
- [model-tasks/translation](./model-tasks/translation/)
- [model-tasks/translation-stream](./model-tasks/translation-stream/)
- [model-tasks/text-classification](./model-tasks/text-classification/)

#### 임베딩
- [model-tasks/text-embedding](./model-tasks/text-embedding/)
- [model-tasks/face-embedding](./model-tasks/face-embedding/)

#### 이미지 처리
- [model-tasks/image-to-text](./model-tasks/image-to-text/)
- [model-tasks/image-upscale](./model-tasks/image-upscale/)

### 오디오 및 비디오 컴포넌트
- [audio-extractor](./audio-extractor/)
- [video-converter](./video-converter/)
- [video-scene-detector](./video-scene-detector/)
- [vibevoice-realtime-tts](./vibevoice-realtime-tts/)

### 웹 브라우저 컴포넌트
- [web-browser](./web-browser/)

### 웹 스크래퍼 컴포넌트
- [web-scraper](./web-scraper/)

### 벡터 스토어 컴포넌트
- [vector-store/chroma](./vector-store/chroma/)
- [vector-store/milvus](./vector-store/milvus/)

### 그래프 스토어 컴포넌트
- [graph-store/neo4j](./graph-store/neo4j/)
- [graph-store/arangodb](./graph-store/arangodb/)

### 키-값 스토어 컴포넌트
- [key-value-store/redis](./key-value-store/redis/)

### 데이터셋 컴포넌트
- [datasets/huggingface](./datasets/huggingface/)

### 텍스트 분할기 컴포넌트
- [split-text](./split-text/)

### 이미지 프로세서 컴포넌트
- [image-processor](./image-processor/)

### 쉘 컴포넌트
- [analyze-disk-usage](./analyze-disk-usage/)

### 워크플로우 컴포넌트
- [workflow-queue](./workflow-queue/)
- [workflow-queue-stream](./workflow-queue-stream/)

### HTTP 서버 컴포넌트
- [echo-server](./echo-server/)
- [docker](./docker/)

### 게이트웨이 컴포넌트
- [gateway/http-tunnel/ngrok](./gateway/http-tunnel/ngrok/)
- [gateway/http-tunnel/cloudflare](./gateway/http-tunnel/cloudflare/)
- [gateway/http-tunnel/cloudflare-named](./gateway/http-tunnel/cloudflare-named/)
- [gateway/ssh-tunnel](./gateway/ssh-tunnel/)

---

## 🚀 다음 단계

1. 사용 사례와 일치하는 예제를 찾아보세요
2. 프로젝트의 시작점으로 예제를 복사하세요
3. 필요에 맞게 `model-compose.yml`을 수정하세요
4. 자세한 문서는 [사용자 가이드](../docs/user-guide/ko/README.md)를 참조하세요

---

## 🤝 예제 기여하기

유용한 예제를 공유하고 싶으신가요?

1. `examples/` 아래에 새 디렉토리를 생성하세요
2. `model-compose.yml` 파일을 추가하세요
3. 선택적으로 구체적인 지침이 포함된 `README.md`를 추가하세요
4. 풀 리퀘스트를 제출하세요

---

## 📚 추가 자료

- [사용자 가이드](../docs/user-guide/ko/README.md) - 포괄적인 문서
- [GitHub 저장소](https://github.com/hanyeol/model-compose) - 소스 코드 및 이슈

---

## 📖 다른 언어로 보기

- **🌍 English**: [English User Guide](README.md)
- **🇨🇳 简体中文**: [简体中文用户指南](README.zh-cn.md)

---

**즐거운 작성 되세요! 🎉**

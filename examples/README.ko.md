# model-compose 예제

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

# ElevenLabs 예제용
ELEVENLABS_API_KEY=your-api-key

# HuggingFace 예제용
HUGGINGFACE_TOKEN=your-token-here
```

---

## 🎯 카테고리별 예제

### 외부 API 통합

#### OpenAI API
- **[openai-chat-completions](./openai-chat-completions/README.ko.md)** - GPT 모델과 대화
- **[openai-chat-completions-stream](./openai-chat-completions-stream/README.ko.md)** - 스트리밍 채팅 응답
- **[openai-audio-speech](./openai-audio-speech/README.ko.md)** - OpenAI TTS를 사용한 텍스트 음성 변환
- **[openai-audio-transciptions](./openai-audio-transciptions/README.ko.md)** - 오디오 전사 (Whisper)
- **[openai-image-generations](./openai-image-generations/README.ko.md)** - DALL-E로 이미지 생성
- **[openai-image-edits](./openai-image-edits/README.ko.md)** - DALL-E로 이미지 편집
- **[openai-image-variations](./openai-image-variations/README.ko.md)** - 이미지 변형 생성

#### 기타 서비스
- **[elevenlabs-text-to-speech](./elevenlabs-text-to-speech/README.ko.md)** - ElevenLabs를 사용한 고품질 TTS

### 다중 단계 워크플로우

- **[make-inspiring-quote-voice](./make-inspiring-quote-voice/README.ko.md)** - 명언 텍스트 생성 → 음성으로 변환
- **[analyze-disk-usage](./analyze-disk-usage/README.ko.md)** - 디스크 사용량 분석 → 보고서 생성

### 로컬 AI 모델

- **[model-tasks](./model-tasks/README.ko.md)** - 다양한 로컬 모델 작업
  - [chat-completion](./model-tasks/chat-completion/README.ko.md) - 로컬 LLM과 채팅
  - [text-generation](./model-tasks/text-generation/README.ko.md) - 텍스트 생성
  - [text-generation-lora](./model-tasks/text-generation-lora/README.ko.md) - LoRA 어댑터를 사용한 텍스트 생성
  - [summarization](./model-tasks/summarization/README.ko.md) - 텍스트 요약
  - [summarization-stream](./model-tasks/summarization-stream/README.ko.md) - 스트리밍 요약
  - [translation](./model-tasks/translation/README.ko.md) - 텍스트 번역
  - [translation-stream](./model-tasks/translation-stream/README.ko.md) - 스트리밍 번역
  - [text-classification](./model-tasks/text-classification/README.ko.md) - 텍스트 분류
  - [text-embedding](./model-tasks/text-embedding/README.ko.md) - 텍스트 임베딩 생성
  - [image-to-text](./model-tasks/image-to-text/README.ko.md) - 이미지 캡셔닝
  - [image-upscale](./model-tasks/image-upscale/README.ko.md) - 이미지 업스케일
  - [face-embedding](./model-tasks/face-embedding/README.ko.md) - 얼굴 임베딩 생성
- **[vllm-chat-completion-stream](./vllm-chat-completion-stream/README.ko.md)** - vLLM을 사용한 스트리밍 채팅 (로컬 모델 서빙)

### 데이터 처리

- **[split-text](./split-text/README.ko.md)** - 텍스트 분할 및 처리
- **[image-processor](./image-processor/README.ko.md)** - 이미지 처리 워크플로우

### 벡터 데이터베이스

- **[vector-store](./vector-store/README.ko.md)** - 벡터 데이터베이스 통합 예제
  - [chroma](./vector-store/chroma/README.ko.md) - ChromaDB 통합
  - [milvus](./vector-store/milvus/README.ko.md) - Milvus 벡터 데이터베이스

### 데이터 관리

- **[datasets](./datasets/README.ko.md)** - 데이터셋 로드 및 조작
  - [huggingface](./datasets/huggingface/README.ko.md) - HuggingFace 데이터셋 통합

### 서버 및 통합

- **[echo-server](./echo-server/README.ko.md)** - 간단한 HTTP 서버 예제
- **[mcp-servers](./mcp-servers/README.ko.md)** - Model Context Protocol 서버 예제

---

## 🧩 컴포넌트별 예제

시연하는 컴포넌트 유형별로 정리된 예제를 둘러보세요:

### HTTP 클라이언트 컴포넌트
- [openai-chat-completions](./openai-chat-completions/README.ko.md)
- [openai-chat-completions-stream](./openai-chat-completions-stream/README.ko.md)
- [openai-audio-speech](./openai-audio-speech/README.ko.md)
- [openai-audio-transciptions](./openai-audio-transciptions/README.ko.md)
- [openai-image-generations](./openai-image-generations/README.ko.md)
- [openai-image-edits](./openai-image-edits/README.ko.md)
- [openai-image-variations](./openai-image-variations/README.ko.md)
- [elevenlabs-text-to-speech](./elevenlabs-text-to-speech/README.ko.md)
- [make-inspiring-quote-voice](./make-inspiring-quote-voice/README.ko.md)

### 모델 컴포넌트 (로컬 AI)

#### 채팅 및 텍스트 생성
- [model-tasks/chat-completion](./model-tasks/chat-completion/README.ko.md)
- [model-tasks/text-generation](./model-tasks/text-generation/README.ko.md)
- [model-tasks/text-generation-lora](./model-tasks/text-generation-lora/README.ko.md)
- [vllm-chat-completion-stream](./vllm-chat-completion-stream/README.ko.md)

#### 텍스트 처리
- [model-tasks/summarization](./model-tasks/summarization/README.ko.md)
- [model-tasks/summarization-stream](./model-tasks/summarization-stream/README.ko.md)
- [model-tasks/translation](./model-tasks/translation/README.ko.md)
- [model-tasks/translation-stream](./model-tasks/translation-stream/README.ko.md)
- [model-tasks/text-classification](./model-tasks/text-classification/README.ko.md)

#### 임베딩
- [model-tasks/text-embedding](./model-tasks/text-embedding/README.ko.md)
- [model-tasks/face-embedding](./model-tasks/face-embedding/README.ko.md)

#### 이미지 처리
- [model-tasks/image-to-text](./model-tasks/image-to-text/README.ko.md)
- [model-tasks/image-upscale](./model-tasks/image-upscale/README.ko.md)

### 벡터 스토어 컴포넌트
- [vector-store/chroma](./vector-store/chroma/README.ko.md)
- [vector-store/milvus](./vector-store/milvus/README.ko.md)

### 데이터셋 컴포넌트
- [datasets/huggingface](./datasets/huggingface/README.ko.md)

### 텍스트 분할기 컴포넌트
- [split-text](./split-text/README.ko.md)

### 이미지 프로세서 컴포넌트
- [image-processor](./image-processor/README.ko.md)

### 쉘 컴포넌트
- [analyze-disk-usage](./analyze-disk-usage/README.ko.md)

### HTTP 서버 컴포넌트
- [echo-server](./echo-server/README.ko.md)

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

- [사용자 가이드](../docs/user-guide/ko/README.ko.md) - 포괄적인 문서
- [영문 사용자 가이드](../docs/user-guide/README.md) - English documentation
- [GitHub 저장소](https://github.com/hanyeol/model-compose) - 소스 코드 및 이슈

---

**즐거운 작성 되세요! 🎉**

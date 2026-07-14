<div align="center">

![model-compose - Compose Any AI, Deploy Anywhere](docs/images/main-banner.png)

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![PyPI version](https://img.shields.io/pypi/v/model-compose.svg)](https://pypi.org/project/model-compose/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://pepy.tech/badge/model-compose)](https://pepy.tech/project/model-compose)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)

[English](README.md) | [中文](README.zh-cn.md)

</div>

---

# model-compose

**프로덕션급 AI 서비스를 몇 분 안에 배포하세요.**

YAML 파일 하나. 어떤 모델이든, 어떤 프로토콜이든, 어떤 런타임이든. 챗 API, RAG 파이프라인, 자율 에이전트, MCP 서버를 애플리케이션 코드 없이 만들고 — `docker-compose`처럼 같은 파일을 어디에나 배포하세요.

AI 시스템은 단일 프로바이더, 런타임, 클라우드에 종속되어서는 안 됩니다. model-compose는 네 가지 원칙 위에 세워져 있습니다:

- **Composable** — 모델, 에이전트, 워크플로우, 도구, 메모리, 프로토콜이 교체 가능한 구성 요소입니다.
- **Portable** — AI 시스템을 한 번 정의하고, 재설계 없이 어디에나 배포합니다.
- **Hybrid-First** — 클라우드 API와 로컬 모델을 자신의 조건에 맞게 연결합니다.
- **Stream-Native** — 데이터가 도착하는 즉시 워크플로우를 따라 흐릅니다 — 토큰, 오디오, 프레임, 이벤트가 1급 값.

<div align="center">

[Quick Start](#quick-start) · [What You Can Build](#what-you-can-build) · [Documentation](docs/user-guide/README.md) · [Examples](examples/README.md)

</div>

---

## Quick Start

pip로 설치:

```bash
pip install model-compose
```

또는 [uv](https://docs.astral.sh/uv/)로 설치:

```bash
uv pip install model-compose
```

`model-compose.yml` 작성:

```yaml
controller:
  adapter:
    type: http-server
    port: 8080
  webui:
    port: 8081

workflow:
  job:
    component: chatgpt
    input:
      prompt: ${input.prompt}

component:
  id: chatgpt
  type: http-client
  base_url: https://api.openai.com/v1
  action:
    path: /chat/completions
    method: POST
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
    body:
      model: gpt-4o
      messages:
        - role: user
          content: ${input.prompt}
```

실행:

```bash
export OPENAI_API_KEY=your-key
model-compose up
```

**끝입니다.** `http://localhost:8080`에서 GPT-4o를 서비스하고 `http://localhost:8081`에서 웹 UI가 실행됩니다. 애플리케이션 코드 없음. 프레임워크 보일러플레이트 없음. 같은 파일이 로컬, Docker, 프로덕션에서 그대로 돌아갑니다.

---

## What You Can Build

YAML 파일 하나로 오늘 바로 서비스할 수 있는 것들 — 몇 가지 예시일 뿐입니다.

### 🤖 자율 에이전트

계획하고, 도구를 사용하고, 다단계 작업을 수행하는 ReAct 에이전트를 선언적으로 구축하세요.

```yaml
component:
  id: research-agent
  type: agent
  tools: [search-web, fetch-page]
  max_iteration_count: 10
  action:
    model:
      component: chatgpt
    system_prompt: You are a web research assistant.
    user_prompt: ${input.question}
```

[agents/](examples/agents/) 아래에 코드 리뷰어, RAG 어시스턴트, Web3 에어드랍 헌터를 포함한 10개의 실전 에이전트가 있습니다.

### 🔍 RAG 파이프라인

임베딩, 벡터 검색, 생성을 하나의 워크플로우로 조합하세요 — 접착 코드 없이.

```yaml
workflow:
  jobs:
    - id: embed
      component: embedder
      input: { text: ${input.query} }

    - id: retrieve
      component: knowledge
      action: search
      input: { vector: ${jobs.embed.output} }

    - id: answer
      component: chatgpt
      input:
        context: ${jobs.retrieve.output}
        question: ${input.query}
```

Chroma, Milvus, Qdrant, FAISS, Neo4j, ArangoDB, Redis 네이티브 드라이버가 기본 제공됩니다.

### 🌐 MCP 서버

어떤 워크플로우든 Claude, ChatGPT, Cursor가 사용할 수 있는 MCP 서버로 만드세요 — 한 줄 변경으로.

```yaml
controller:
  adapter:
    type: mcp-server   # ← 이전: http-server
    port: 8080
```

Korea DART MCP와 Slack 봇 MCP 등 전체 예제는 [mcp-servers/](examples/mcp-servers/)에서 확인할 수 있습니다.

### ⚡ 스트리밍 멀티모달 워크플로우

토큰, 오디오 청크, 비디오 프레임을 end-to-end로 스트리밍하세요 — 모든 단계에서 1급 지원.

```yaml
workflow:
  job:
    component: chatgpt
    output: ${output as sse-text}

component:
  id: chatgpt
  type: http-client
  action:
    body: { stream: true, ... }
    stream_format: json
    output: ${response[].choices[0].delta.content}
```

실시간 TTS, video-to-frames, 라이브 채팅 예제는 [data-streaming/](examples/data-streaming/)과 [showcase/](examples/showcase/)에 있습니다.

---

## Why model-compose?

| | **model-compose** | Managed APIs (OpenAI 등) | Code Frameworks (LangChain 등) |
|---|---|---|---|
| **첫 API까지의 시간** | **몇 분** (YAML 하나) | 몇 시간 (SDK + 서버 코드) | 며칠 (프레임워크 + 통합) |
| **Provider Coupling** | **설정만으로 멀티 프로바이더** | SDK당 단일 프로바이더 | 추상화를 통한 멀티 프로바이더 |
| **Code Coupling** | **선언적 YAML — 애플리케이션 코드 불필요** | 애플리케이션 코드 필요 | 프레임워크 전용 코드 필요 |
| **Infrastructure Control** | **완전한 주권** | 프로바이더 관리 | 높은 추상화 |
| **Runtime Flexibility** | **Hybrid-First (로컬 + 클라우드)** | 클라우드 전용 | 커스터마이즈 복잡 |
| **Protocol Support** | **HTTP / WebSocket / MCP** | 프로바이더 한정 | 제한적 |
| **Data Streaming** | **모든 단계에서 1급 지원** | 응답 전용 (SSE 토큰) | 프레임워크가 감싼 제너레이터 |
| **Deployment** | **Docker / Native / Process** | 프로바이더 관리 | 수동 통합 |

---

## 개발에서 프로덕션까지

노트북에서 돌아가던 같은 YAML이 재작성 없이 확장됩니다.

### 1. 로컬에서 개발

```bash
model-compose up
```

Gradio 웹 UI가 `:8081`에 함께 실행되어 반복 개발에 최적.

### 2. 컨테이너로 배포

`runtime:` 블록만 추가. 같은 파일, 같은 동작:

```yaml
controller:
  runtime:
    type: docker
    image: my-ai-service:latest
    ports: [ "8080:8080" ]
```

### 3. 수평 확장

큐를 추가하세요. 디스패처가 작업을 받고, N대의 머신에서 서브스크라이버가 처리:

```yaml
controller:
  adapter: { type: http-server, port: 8080 }
  queue:
    driver: redis
    host: redis.internal
    name: my-queue
```

공유 파일시스템 없음. 코드 변경 없음. 서브스크라이버만 더 붙이면 확장.

---

## Highlights

- **어떤 모델이든, 어디서든** — 로컬은 HuggingFace, vLLM, llama.cpp, 클라우드는 OpenAI/Anthropic/Google/xAI를 HTTP로
- **YAML로 만드는 에이전트** — ReAct 루프, 도구 사용, 다단계 추론 — 코드 없이
- **Human-in-the-loop** — 승인을 위해 워크플로우 일시 정지, CLI/UI/API로 재개
- **20+ 컴포넌트** — 모델, 에이전트, HTTP/WebSocket 클라이언트, 벡터/그래프 스토어, 셸, 브라우저 등
- **어떤 프로토콜이든** — HTTP REST, WebSocket, MCP를 한 줄로
- **어떤 런타임이든** — Docker, 네이티브, 프로세스, 임베디드 — 한 줄로 전환
- **분산 실행** — Redis 큐 디스패치로 수평 확장
- **즉시 웹 UI** — Gradio UI를 YAML 2줄로
- **모든 곳에서 스트리밍** — SSE, WebSocket, 잡 간 스트림이 1급 값

---

## Real-World Examples

100개 이상의 실행 가능한 예제가 카테고리별로 정리되어 있습니다:

| 카테고리 | 담긴 내용 |
|---|---|
| [`agents/`](examples/agents/) | 코드 리뷰어, RAG 어시스턴트, 웹 리서처, Web3 에어드랍 헌터, ... |
| [`showcase/`](examples/showcase/) | end-to-end 파이프라인: 디스크 분석, 얼굴 기반 장면 검색, 실시간 TTS |
| [`model-providers/`](examples/model-providers/) | OpenAI, Anthropic, xAI, Google, ElevenLabs, vLLM |
| [`model-tasks/`](examples/model-tasks/) | 로컬 챗, 임베딩, TTS, VLM, 얼굴 임베딩, ... |
| [`mcp-servers/`](examples/mcp-servers/) | Claude, Cursor, ChatGPT에 노출할 MCP 서버 구축 |
| [`workflow-queue/`](examples/workflow-queue/) | Redis 기반 분산 디스패치 (스트리밍 + 논-스트리밍) |
| [`data-streaming/`](examples/data-streaming/) | video-to-frames, YouTube 라이브 채팅, 스트리밍 입력 |
| [`integrations/`](examples/integrations/) | 벡터/그래프/KV 스토어, 검색 엔진, 채널, 터널 |

전체 목록은 [examples/README.md](examples/README.ko.md)에서 확인할 수 있습니다.

---

## Architecture

Protocol adapters → Composition engine → Runtime executors

![Architecture Diagram](docs/images/architecture-diagram.png)

---

## Contributing

모든 기여를 환영합니다 — 버그 수정, 문서 개선, 새 예제.

```bash
git clone https://github.com/hanyeol/model-compose.git
cd model-compose
pip install -e .
```

CONTRIBUTING 가이드가 있다면 참고하시거나, 바로 PR을 열어주세요.

---

## License

MIT License © 2025-2026 Hanyeol Cho.

---

## Contact

질문, 아이디어, 피드백이 있으신가요? [이슈를 열거나](https://github.com/hanyeol/model-compose/issues) [GitHub Discussions](https://github.com/hanyeol/model-compose/discussions)에서 대화를 시작해주세요.

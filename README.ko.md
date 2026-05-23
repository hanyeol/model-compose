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

**AI 시스템을 조합하고, 어디서나 배포하세요.**

YAML로 워크플로우, 에이전트, 모델, 그리고 종합적인 AI 서비스를 정의하세요. 로컬에서 실행하고, 프로덕션에서 확장하고, 스택을 다시 작성하지 않고도 어떤 환경에나 배포할 수 있습니다.

`docker-compose`에서 영감을 받았습니다 — 하나의 YAML 파일로 전체 AI 시스템을 정의합니다.

<div align="center">

[사용자 가이드](docs/user-guide/ko/README.md) · [빠른 시작](#빠른-시작) · [예제](examples/README.ko.md) · [기여하기](#기여하기)

</div>

---

## Philosophy

AI 시스템은 단일 제공자, 런타임, 또는 클라우드에 종속되어서는 안 됩니다. AI 시스템은 이식 가능하고, 검토 가능하며, 어디서나 실행될 수 있어야 합니다.

오늘날 많은 AI 애플리케이션은 제공자별 API, 관리형 런타임, 닫힌 생태계에 강하게 결합되어 있습니다. 처음에는 편리할 수 있지만, 이런 결합은 벤더 종속을 만듭니다 — 컴포넌트를 다시 작성하지 않고는 교체할 수 없고, 시스템을 다른 환경으로 옮길 수 없으며, 팀은 클라우드의 편리함과 로컬 제어 사이에서 양자택일을 강요받습니다.

**model-compose**는 세 가지 핵심 원칙을 바탕으로 근본적으로 다른 접근 방식을 취합니다:

* **Composable** — 모델, 에이전트, 워크플로우, 도구, 메모리, 프로토콜을 모듈식의 교체 가능한 구성 요소로 다룹니다.

* **Portable** — AI 시스템을 한 번 정의한 뒤, 핵심 아키텍처를 재설계하지 않고 로컬, 컨테이너, 또는 분산 프로덕션 환경에 배포할 수 있습니다.

* **Hybrid-First** — 클라우드 API와 로컬 모델을 자신의 조건에 맞게 연결합니다. 시스템의 동작을 변경하지 않고 인프라 레이어를 자유롭게 교체하여 프라이버시, 지연 시간, 비용을 최적화합니다.

model-compose의 목표는 또 다른 폐쇄형 플랫폼을 만드는 것이 아니라, 개발자에게 아키텍처의 자율성을 돌려주는 것입니다.

---

## Why model-compose?

| Feature | Managed APIs (OpenAI 등) | Code Frameworks (LangChain 등) | **model-compose** |
|---|---|---|---|
| **Provider Coupling** | SDK당 단일 프로바이더 | 추상화를 통한 멀티 프로바이더 | **설정만으로 멀티 프로바이더** |
| **Code Coupling** | 애플리케이션 코드 필요 | 프레임워크 전용 코드 필요 | **선언적 YAML — 애플리케이션 코드 불필요** |
| **Infrastructure Control** | 프로바이더 관리 | 높은 추상화 | **완전한 주권** |
| **Runtime Flexibility** | 클라우드 전용 | 커스터마이즈 복잡 | **Hybrid-First (로컬 + 클라우드)** |
| **Protocol Support** | 프로바이더 한정 | 제한적 | **HTTP / WebSocket / MCP** |
| **Deployment** | 프로바이더 관리 | 수동 통합 | **Docker / Native / Process** |

---

## Highlights

- **Any model, anywhere** — HuggingFace, vLLM, llama.cpp로 프라이버시, 오프라인, API 비용 제로를 위해 모델을 로컬 실행하거나, OpenAI, Anthropic, Google 등에 연결
- **AI agents in YAML** — 도구 사용, 계획, 다단계 추론이 가능한 자율 에이전트를 선언적으로 구축
- **Human-in-the-loop** — 워크플로우가 승인 게이트, 사용자 입력, 수동 검토를 위해 일시 중지한 뒤 재개 가능
- **Real-time streaming** — 모든 프로바이더 및 로컬 모델에서 실시간 AI 응답을 위한 내장 SSE 스트리밍
- **20+ components ready** — 모델, 에이전트, HTTP/WebSocket 클라이언트, 벡터/그래프 스토어, 쉘 명령 등
- **Deploy as container** — 동일한 YAML이 Docker 컨테이너, 네이티브 프로세스, 또는 단독 서비스로 실행 — 한 줄로 런타임 전환
- **Serve any protocol** — HTTP REST, WebSocket, 또는 MCP를 한 줄 변경으로
- **Distributed execution** — Redis 큐를 통해 워크플로우를 원격 워커에 디스패치 — 서버 추가로 수평 확장
- **Instant Web UI** — 2줄의 YAML로 Gradio 기반 인터페이스 추가

---

## 설치

```
pip install model-compose
```

또는 소스에서 설치:

```
git clone https://github.com/hanyeol/model-compose.git
cd model-compose
pip install -e .
```

> 요구사항: Python 3.10 이상

---

## 빠른 시작

`model-compose.yml` 파일로 AI 런타임을 정의하세요:

```yaml
controller:
  adapter:
    type: http-server
    port: 8080
  webui:
    port: 8081

workflows:
  - id: chat
    default: true
    jobs:
      - component: chatgpt

components:
  - id: chatgpt
    type: http-client
    base_url: https://api.openai.com/v1
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

`.env` 파일 생성:

```bash
OPENAI_API_KEY=your-key
```

실행:

```bash
model-compose up
```

AI 런타임이 `http://localhost:8080`에서, Web UI가 `http://localhost:8081`에서 서비스됩니다.

> 더 많은 워크플로우는 [예제](examples/README.ko.md)를, 자세한 내용은 [사용자 가이드](docs/user-guide/ko/README.md)를 참조하세요.

---

## Core Capabilities

### 선언적 YAML 설정
단일 YAML 파일로 전체 AI 시스템을 정의합니다. 워크플로우, 에이전트, 모델, API, 벡터/그래프 스토어, 런타임을 커스텀 코드 없이 함께 조합하고 배포합니다.

```yaml
controller:
  adapter:
    type: http-server
    port: 8080

workflows:
  - id: chat
    default: true
    jobs:
      - component: chatgpt

components:
  - id: chatgpt
    type: http-client
    base_url: https://api.openai.com/v1
    action:
      path: /chat/completions
      method: POST
```

### 유연한 컴포넌트 시스템
20개 이상의 재사용 가능한 컴포넌트 타입. HTTP 클라이언트, 로컬 모델, 벡터 스토어, 쉘 명령, 워크플로우를 자유롭게 조합합니다. 한 번 정의하면 어디서나 사용.

```yaml
components:
  - id: chatgpt
    type: http-client

  - id: local-llm
    type: model

  - id: assistant
    type: agent

  - id: knowledge
    type: vector-store

  - id: cache
    type: key-value-store

  - id: runner
    type: shell
```

### 고급 워크플로우 구성
조건부 로직, 병렬 실행, 데이터 변환으로 작업을 연결합니다. 변수 바인딩 — `${input}`, `${response}`, `${env}` — 으로 작업 간 데이터를 전달하며, 타입 변환과 기본값을 지원합니다.

```yaml
workflows:
  - id: rag-pipeline
    jobs:
      - id: embed
        component: embedder
        input:
          text: ${input.query}

      - id: search
        component: vector-store
        action: search
        input:
          vector: ${jobs.embed.output}
        depends_on: [embed]

      - id: answer
        component: chatgpt
        input:
          context: ${jobs.search.output}
          question: ${input.query}
        depends_on: [search]
```

### AI 에이전트 컴포넌트
워크플로우를 도구로 활용하는 자율 AI 에이전트를 구축합니다. 에이전트가 추론, 계획하고, 다른 워크플로우를 동적으로 호출하여 다단계 작업을 수행합니다 — 모두 YAML로 선언적 정의.

```yaml
components:
  - id: research-agent
    type: agent
    tools:
      - search-web
      - fetch-page
    max_iteration_count: 10
    action:
      model:
        component: chatgpt
        input:
          messages: ${messages}
          tools: ${tools}
      system_prompt: You are a web research assistant.
      user_prompt: ${input.question}
```

### Human-in-the-Loop
모든 워크플로우에 승인 게이트와 사용자 입력 단계를 추가합니다. 워크플로우가 일시 중지되고, CLI, Web UI, API를 통해 사용자 입력을 요청한 후 원활하게 재개됩니다.

```yaml
workflows:
  - id: write-with-approval
    jobs:
      - id: write-file
        component: file-writer
        input:
          path: ${input.path}
          content: ${input.content}
        interrupt:
          before:
            message: "Approve file write to ${job.input.path}?"
```

### 로컬 모델 실행
HuggingFace 등에서 제공하는 모델을 로컬에서 실행하며 transformers, vLLM, PyTorch를 네이티브 지원합니다. LoRA/PEFT를 통한 파인튜닝도 YAML 설정으로.

```yaml
components:
  - id: local-llm
    type: model
    task: chat-completion
    model: HuggingFaceTB/SmolLM3-3B
    action:
      messages:
        - role: user
          content: ${input.prompt}
```

### 범용 AI 서비스 통합
OpenAI, Anthropic, Google, xAI, ElevenLabs, 그리고 모든 커스텀 HTTP API에 연결합니다. 단일 워크플로우에서 서비스를 자유롭게 조합.

```yaml
components:
  - id: claude
    type: http-client
    base_url: https://api.anthropic.com/v1
    action:
      path: /messages
      method: POST
      headers:
        x-api-key: ${env.ANTHROPIC_API_KEY}
        anthropic-version: "2023-06-01"
      body:
        model: claude-opus-4-20250514
        max_tokens: 1024
        messages:
          - role: user
            content: ${input.prompt}
```

### 실시간 스트리밍
실시간 AI 응답을 위한 내장 SSE(Server-Sent Events) 스트리밍. 모든 프로바이더 또는 로컬 모델에서 자동 청킹 및 연결 관리.

```yaml
workflows:
  - id: chat
    jobs:
      - component: chatgpt
        output: ${output as sse-text}

components:
  - id: chatgpt
    type: http-client
    base_url: https://api.openai.com/v1
    action:
      path: /chat/completions
      method: POST
      body:
        model: gpt-4o
        messages: ${input.messages}
        stream: true
      stream_format: json
      output: ${response[].choices[0].delta.content}
```

### 내장 데이터 스토어 통합
벡터 검색을 위한 Chroma, FAISS, Milvus, Qdrant 네이티브 통합. 그래프 스토어를 위한 Neo4j, ArangoDB. 키-값 저장을 위한 Redis. 임베딩 검색과 시맨틱 검색으로 RAG 시스템 구축.

```yaml
components:
  - id: knowledge
    type: vector-store
    driver: chroma
    actions:
      - id: insert
        collection: docs
        method: insert
        vector: ${input.vector}
        metadata:
          text: ${input.text}

      - id: search
        collection: docs
        method: search
        query: ${input.vector}
```

### Deploy in Any Runtime
네이티브, 프로세스, Docker, 또는 네이티브 컨테이너 모드로 실행합니다. 동일한 설정이 모든 런타임에서 동작합니다 — 한 줄만 변경.

```yaml
controller:
  runtime:
    type: docker
    image: my-ai-service:latest
    ports:
      - "8080:8080"
  adapter:
    type: http-server
    port: 8080
```

### 프로토콜 어댑터
HTTP REST, WebSocket, 또는 MCP(Model Context Protocol)로 한 줄만 변경하면 서빙합니다. 동시성 제어, 헬스 체크, 자동 API 문서화 포함.

```yaml
# HTTP REST
controller:
  adapter:
    type: http-server
    port: 8080

# MCP (Model Context Protocol)
controller:
  adapter:
    type: mcp-server
    port: 8080
```

### 분산 워크플로우 실행
Redis 기반 큐 디스패치로 AI 워크로드를 여러 머신에 분산합니다. 공유 파일시스템이나 코드 변경 없이 워커를 추가하여 수평 확장.

```yaml
controller:
  adapter:
    type: http-server
    port: 8080
  queue:
    driver: redis
    host: localhost
    port: 6379
    name: my-queue
```

### Webhook 및 Callback 리스너
비동기 워크플로우를 위한 HTTP Callback 리스너와 웹훅을 위한 HTTP Trigger 리스너. 실세계 이벤트에 반응하는 AI 시스템 구축.

```yaml
listener:
  type: http-trigger
  port: 8091
  triggers:
    - path: /webhook
      method: POST
      workflow: handle-message
      input:
        text: ${body.message.text}
```

### 게이트웨이 및 터널 지원
ngrok, Cloudflare, SSH 터널로 로컬 서비스를 인터넷에 노출합니다. 복잡한 네트워킹 없이 웹훅 통합과 퍼블릭 API 배포.

```yaml
gateway:
  type: http-tunnel
  driver: ngrok
  port:
    - 8090
```

### Instant Web UI
2줄의 YAML로 비주얼 인터페이스를 추가합니다. Gradio 기반 채팅 UI 또는 커스텀 정적 프론트엔드로 테스트와 디버깅.

```yaml
controller:
  webui:
    driver: gradio
    port: 8081
```

---

## 아키텍처

프로토콜 어댑터 → 컴포지션 엔진 → 런타임 실행기

![아키텍처 다이어그램](docs/images/architecture-diagram.png)

---

## 기여하기

모든 기여를 환영합니다!
버그 수정, 문서 개선, 예제 추가 등 — 모든 도움이 소중합니다.

```
# 개발 환경 설정
git clone https://github.com/hanyeol/model-compose.git
cd model-compose
pip install -e .[dev]
```

---

## 라이선스

MIT License © 2025-2026 Hanyeol Cho.

---

## 문의

질문, 아이디어, 피드백이 있으신가요? [이슈를 열거나](https://github.com/hanyeol/model-compose/issues) [GitHub Discussions](https://github.com/hanyeol/model-compose/discussions)에서 토론을 시작하세요.

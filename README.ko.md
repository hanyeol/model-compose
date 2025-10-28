<div align="center">

![model-compose - 선언적 AI 워크플로우 오케스트레이터](docs/images/main-banner.png)

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![PyPI version](https://img.shields.io/pypi/v/model-compose.svg)](https://pypi.org/project/model-compose/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://pepy.tech/badge/model-compose)](https://pepy.tech/project/model-compose)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)

[English](README.md) | [中文](README.zh-cn.md)

</div>

---

# 🤖 Model-Compose

**model-compose**는 `docker-compose`에서 영감을 받아서 만든 선언적 AI 워크플로우 오케스트레이터입니다. 간단한 YAML 파일로 AI 모델 파이프라인을 정의하고 실행하세요 — 코드를 작성할 필요가 없어요. 외부 AI 서비스(OpenAI, Anthropic, Google 등) 연결, 로컬 AI 모델 실행, 벡터 스토어 통합 등으로 강력하고 조합 가능한 워크플로우로 구성할 수 있습니다.

**코드 작성 없이, YAML 설정만으로.**

<div align="center">

[📖 사용자 가이드](docs/user-guide/ko/README.md) · [🚀 빠른 시작](#-빠른-시작) · [💡 예제](examples/README.ko.md) · [🤝 기여하기](#-기여하기)

</div>

---

## ✨ 주요 기능

- 🎨 **노코드**: 순수 YAML 설정 — 코드 작성 불필요
- 🔄 **조합 가능**: 재사용 가능한 컴포넌트와 멀티스텝 워크플로우
- 🚀 **프로덕션 준비**: HTTP/MCP 서버 + Web UI + Docker 배포
- 🔌 **무엇이든 연결**: 외부 AI 서비스, 로컬 모델, 벡터 스토어 등
- ⚡ **스트림 & 확장**: 실시간 스트리밍 및 이벤트 기반 자동화
- ⚙️ **설정**: 환경 변수, 유연한 구성
- 🔗 **통합**: 웹훅, 터널링, HTTP 서버

---


## 📦 설치

```bash
pip install model-compose
```

또는 소스에서 설치:

```bash
git clone https://github.com/hanyeol/model-compose.git
cd model-compose
pip install -e .
```

> 요구사항: Python 3.9 이상

---

## 🚀 빠른 시작

`model-compose.yml` 파일 생성:

```yaml
controller:
  type: http-server
  port: 8080
  webui:
    port: 8081

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

workflows:
  - id: chat
    default: true
    jobs:
      - component: chatgpt
```

`.env` 파일 생성:

```bash
OPENAI_API_KEY=your-key
```

실행:

```bash
model-compose up
```

API는 `http://localhost:8080`에서, Web UI는 `http://localhost:8081`에서 실행됩니다 🎉

> 💡 더 많은 워크플로우는 [예제](examples/README.ko.md)를, 자세한 내용은 [사용자 가이드](docs/user-guide/ko/README.md)를 참조하세요.

---
## 💡 핵심 역량

### 🖥️ 내장 Web UI
단 3줄의 YAML로 시각적 인터페이스 추가:
```yaml
controller:
  webui:
    port: 8081
```
워크플로우를 테스트하고 모니터링할 수 있는 사용자 친화적 인터페이스를 즉시 사용할 수 있습니다. Gradio(기본값)와 커스텀 정적 프론트엔드를 지원합니다.

### 🛰️ MCP 서버 지원
한 줄만 변경하여 워크플로우를 MCP 도구로 변환:
```yaml
controller:
  type: mcp-server  # http-server에서 mcp-server로 변경
```
코드 변경 없이 워크플로우가 Model Context Protocol을 통해 즉시 액세스 가능해집니다.

### 🐳 Docker 배포
내장 Docker 지원으로 어디서나 배포:
```yaml
controller:
  runtime: docker
```
이미지, 볼륨, 포트, 환경 변수를 완전히 제어하며 격리된 컨테이너에서 워크플로우를 실행합니다.

> 📖 자세한 설정은 [사용자 가이드](docs/user-guide/ko/README.md)를, 실행 가능한 샘플은 [예제](examples/README.ko.md)를 참조하세요.

---
## 🏗 아키텍처

![아키텍처 다이어그램](docs/images/architecture-diagram.png)

---

## 🤝 기여하기
모든 기여를 환영합니다!
버그 수정, 문서 개선, 예제 추가 등 — 모든 도움이 도움이 됩니다.

```bash
# 개발 환경 설정
git clone https://github.com/hanyeol/model-compose.git
cd model-compose
pip install -e .[dev]
```

---

## 📄 라이선스
MIT License © 2025 Hanyeol Cho.

---

## 📬 문의
질문, 아이디어, 피드백이 있으신가요? [이슈를 열거나](https://github.com/hanyeol/model-compose/issues) [GitHub Discussions](https://github.com/hanyeol/model-compose/discussions)에서 토론을 시작하세요.

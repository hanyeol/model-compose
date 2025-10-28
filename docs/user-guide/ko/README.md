# model-compose 사용자 가이드

**model-compose** 사용자 가이드에 오신 것을 환영합니다! 이 포괄적인 문서는 기본 개념부터 고급 배포 전략까지 선언적 AI 워크플로우 오케스트레이션을 마스터하는 데 도움을 드립니다.

## 📖 다른 언어로 보기

- **🌍 English**: [English User Guide](../README.md)
- **🇨🇳 简体中文**: [简体中文用户指南](../zh-cn/README.md)

---

## 🚀 빠른 시작

model-compose가 처음이신가요? 여기서 시작하세요:

1. **[시작하기](./01-getting-started.md)** - 설치, 첫 워크플로우, 기본 개념
2. **[핵심 개념](./02-core-concepts.md)** - 컨트롤러, 컴포넌트, 워크플로우 이해하기
3. **[CLI 사용법](./03-cli-usage.md)** - 명령줄 인터페이스 마스터하기

---

## 📚 전체 목차

**[→ 전체 목차 보기](./00-table-of-contents.md)**

### 주요 주제

#### 기초
- [시작하기](./01-getting-started.md) - 설치 및 첫 워크플로우 실행
- [핵심 개념](./02-core-concepts.md) - 아키텍처 및 핵심 컴포넌트
- [CLI 사용법](./03-cli-usage.md) - 명령어 레퍼런스 및 예제

#### 워크플로우 구축
- [컴포넌트 설정](./04-component-configuration.md) - 재사용 가능한 컴포넌트 정의
- [워크플로우 작성](./05-writing-workflows.md) - 다중 단계 파이프라인 생성
- [변수 바인딩](./12-variable-binding.md) - 데이터 흐름 및 변환

#### 컨트롤러 & UI
- [컨트롤러 설정](./06-controller-configuration.md) - HTTP 및 MCP 서버
- [Web UI 설정](./07-webui-configuration.md) - 시각적 워크플로우 관리

#### AI 모델
- [로컬 AI 모델 사용하기](./08-local-ai-models.md) - 로컬에서 모델 실행
- [외부 서비스 통합](./10-external-service-integration.md) - OpenAI, Claude 등 연동
- [스트리밍 모드](./11-streaming-mode.md) - 실시간 출력 스트리밍

#### 시스템 통합
- [시스템 통합](./13-system-integration.md) - 리스너, 트리거, 게이트웨이
  - HTTP Callback 리스너 - 비동기 웹훅 처리
  - HTTP Trigger 리스너 - 이벤트 기반 워크플로우
  - 게이트웨이 지원 - 로컬 서비스 안전하게 공개

#### 배포 & 프로덕션
- [배포](./14-deployment.md) - Docker, 클라우드, 프로덕션 모범 사례
- [실전 예제](./15-practical-examples.md) - 실제 사용 사례
- [문제 해결](./16-troubleshooting.md) - 일반적인 문제 및 해결책

---

## 🎯 예제로 배우기

실습 예제를 찾고 계신가요? 확인해보세요:

- **[실전 예제](./15-practical-examples.md)** - 완전한 작동 예제:
  - 챗봇 (OpenAI, Claude)
  - 음성 생성 파이프라인
  - 이미지 분석 및 편집
  - 벡터 데이터베이스를 활용한 RAG 시스템
  - MCP를 활용한 Slack 봇
  - 멀티모달 워크플로우

- **[Examples 디렉토리](../../../examples/)** - 바로 실행 가능한 YAML 설정

---

## 🔍 빠른 참조

### 일반 작업

| 하고 싶은 것 | 이동할 곳 |
|--------------|----------|
| 설치 및 첫 워크플로우 실행 | [시작하기](./01-getting-started.md) |
| 외부 API 호출 (OpenAI, Claude) | [외부 서비스 통합](./10-external-service-integration.md) |
| 로컬 AI 모델 실행 | [로컬 AI 모델](./08-local-ai-models.md) |
| 다중 단계 워크플로우 생성 | [워크플로우 작성](./05-writing-workflows.md) |
| 실시간 출력 스트리밍 | [스트리밍 모드](./11-streaming-mode.md) |
| 웹훅 및 콜백 처리 | [시스템 통합](./13-system-integration.md) |
| 프로덕션 배포 | [배포](./14-deployment.md) |
| 챗봇 만들기 | [실전 예제 § 15.1](./15-practical-examples.md#151-챗봇-만들기) |
| RAG 시스템 구축 | [실전 예제 § 15.4](./15-practical-examples.md#154-rag-시스템-벡터-db-활용) |
| 문제 디버깅 | [문제 해결](./16-troubleshooting.md) |

### 핵심 개념

- **컨트롤러(Controller)**: 워크플로우를 호스팅하는 HTTP 또는 MCP 서버
- **컴포넌트(Component)**: 재사용 가능한 정의 (API 호출, 모델, 명령어)
- **워크플로우(Workflow)**: 이름이 지정된 작업 순서
- **잡(Job)**: 컴포넌트를 실행하는 단일 단계
- **리스너(Listener)**: HTTP 콜백을 받거나 워크플로우를 트리거
- **게이트웨이(Gateway)**: 로컬 서비스를 인터넷에 터널링

---

## 🛠 설정 레퍼런스

특정 설정 옵션을 찾고 계신가요?

- **[전체 설정 스키마](./17-appendix.md#171-전체-설정-파일-스키마)** - 전체 YAML 레퍼런스
- **[컴포넌트 타입](./04-component-configuration.md#41-컴포넌트-타입)** - 사용 가능한 모든 컴포넌트 타입
- **[변수 바인딩 문법](./12-variable-binding.md)** - 완전한 변수 레퍼런스

---

## 💡 학습 팁

1. **간단하게 시작**: [시작하기](./01-getting-started.md) 가이드부터 시작하세요
2. **실습**: [실전 예제](./15-practical-examples.md)를 시도해보세요
3. **점진적으로**: 한 번에 하나씩 기능을 추가하세요
4. **탐색**: 영감을 얻기 위해 [examples 디렉토리](../../../examples/)를 확인하세요
5. **질문**: 막히면 [이슈](https://github.com/hanyeol/model-compose/issues)를 열어주세요

---

## 🤝 문서 기여하기

오타를 발견하거나 문서를 개선하고 싶으신가요?

1. 저장소 포크
2. `docs/user-guide/` 또는 `docs/user-guide/ko/`의 Markdown 파일 편집
3. Pull Request 제출

모든 기여를 환영합니다!

---

## 📬 도움 받기

- **문서 이슈**: [이슈 제출](https://github.com/hanyeol/model-compose/issues)
- **질문**: [GitHub Discussions](https://github.com/hanyeol/model-compose/discussions)
- **버그 리포트**: [Issue Tracker](https://github.com/hanyeol/model-compose/issues)

---

**즐겁게 컴포즈하세요! 🎉**

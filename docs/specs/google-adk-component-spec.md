# Google ADK Component Specification

## Overview

Google Agent Development Kit (ADK)를 model-compose 프레임워크에 통합하여, 선언적 YAML 구성을 통해 Google의 멀티 에이전트 시스템을 사용할 수 있도록 하는 컴포넌트 스펙입니다.

## Design Goals

1. **선언적 구성**: YAML을 통해 Google ADK 에이전트 정의 및 오케스트레이션
2. **기존 패턴 준수**: model-compose의 컴포넌트/액션 아키텍처 활용
3. **유연한 도구 통합**: 내장 도구, 커스텀 함수, MCP 도구 지원
4. **멀티 에이전트 지원**: 계층적 에이전트 시스템 구성
5. **스트리밍 지원**: 실시간 응답을 위한 비동기 스트리밍

## Architecture

### Component Types

Google ADK 통합을 위해 다음 컴포넌트들을 구현합니다:

#### 1. `google-adk-agent` - 단일 에이전트 실행

Google ADK의 단일 에이전트를 실행하는 기본 컴포넌트입니다.

**Component Type**: `ComponentType.GOOGLE_ADK_AGENT`

**Features**:
- LLM 에이전트 생성 및 실행
- 도구(tools) 통합
- 세션 관리
- 스트리밍 응답
- 메모리 및 상태 관리

#### 2. `google-adk-multi-agent` - 멀티 에이전트 오케스트레이션

여러 에이전트를 계층적으로 구성하고 조율하는 컴포넌트입니다.

**Component Type**: `ComponentType.GOOGLE_ADK_MULTI_AGENT`

**Features**:
- 서브 에이전트 구성
- 에이전트 간 통신 (A2A Protocol)
- 계층적 워크플로우
- 역할 기반 에이전트 분리

## Component Schema

### 1. GoogleAdkAgentComponentConfig

```python
from typing import List, Optional, Dict, Any, Literal, Union
from pydantic import BaseModel, Field
from mindor.dsl.schema.component.impl.common import CommonComponentConfig

class GoogleAdkToolConfig(BaseModel):
    """ADK 도구 구성"""
    # 내장 도구
    type: Literal[
        "google_search",
        "code_executor",
        "tavily_search",
        "firecrawl",
        "github",
        "notion",
        "exa",
        "browserbase",
        "huggingface"
    ] | None = None

    # 커스텀 함수 도구
    function_name: str | None = None
    function_description: str | None = None
    function_parameters: Dict[str, Any] | None = None

    # OpenAPI 도구
    openapi_spec_url: str | None = None

    # MCP 도구
    mcp_server_url: str | None = None
    mcp_tool_name: str | None = None

    # 도구 설정
    config: Dict[str, Any] = Field(default_factory=dict)


class GoogleAdkAgentComponentConfig(CommonComponentConfig):
    """Google ADK 단일 에이전트 컴포넌트 구성"""
    type: Literal[ComponentType.GOOGLE_ADK_AGENT]

    # 에이전트 기본 정보
    agent_name: str = Field(..., description="에이전트 이름")
    model: str = Field(default="gemini-2.5-flash", description="사용할 모델")
    instruction: str = Field(..., description="에이전트 시스템 프롬프트")
    description: str | None = Field(None, description="에이전트 설명")

    # 도구 구성
    tools: List[GoogleAdkToolConfig] = Field(default_factory=list)

    # 세션 및 메모리 설정
    enable_memory: bool = Field(default=True, description="메모리 활성화")
    context_caching: bool = Field(default=True, description="컨텍스트 캐싱")
    max_context_tokens: int | None = Field(None, description="최대 컨텍스트 토큰")

    # 실행 설정 (컴포넌트 레벨 기본값)
    streaming: bool = Field(default=False, description="스트리밍 응답")
    temperature: float | None = Field(None, description="온도 파라미터")
    top_p: float | None = Field(None, description="Top-p 샘플링")
    max_output_tokens: int | None = Field(None, description="최대 출력 토큰")

    # 도구 확인 (HITL)
    tool_confirmation: bool = Field(default=False, description="도구 실행 확인")

    # GCP 설정
    project_id: str | None = Field(None, description="GCP 프로젝트 ID")
    location: str = Field(default="us-central1", description="리전")
    credentials_path: str | None = Field(None, description="서비스 계정 키 경로")

    # 액션 정의
    actions: List["GoogleAdkAgentActionConfig"]


class GoogleAdkAgentActionConfig(CommonActionConfig):
    """Google ADK 에이전트 액션 구성"""

    # 입력 메시지 (필수)
    message: Union[str, Dict[str, Any]] = Field(
        ...,
        description="사용자 메시지 또는 구조화된 입력 (변수 보간 지원)"
    )

    # 세션 관리
    session_id: Union[str, None] = Field(
        None,
        description="세션 ID - 대화 컨텍스트 유지용 (변수 보간 지원)"
    )
    new_session: Union[bool, str] = Field(
        default=False,
        description="새 세션 시작 여부 (변수 보간 지원)"
    )

    # 런타임 파라미터 오버라이드
    temperature: Union[float, str, None] = Field(
        None,
        description="온도 파라미터 오버라이드 (변수 보간: ${input.temperature as number})"
    )
    top_p: Union[float, str, None] = Field(
        None,
        description="Top-p 샘플링 오버라이드 (변수 보간 지원)"
    )
    max_output_tokens: Union[int, str, None] = Field(
        None,
        description="최대 출력 토큰 오버라이드 (변수 보간: ${input.max_tokens as integer})"
    )

    # 실행 옵션
    stream: Union[bool, str, None] = Field(
        None,
        description="스트리밍 오버라이드 (변수 보간: ${input.stream as boolean})"
    )

    # 추가 컨텍스트 및 메타데이터
    context: Union[Dict[str, Any], str] = Field(
        default_factory=dict,
        description="추가 컨텍스트 데이터 (변수 보간 지원)"
    )

    # 시스템 프롬프트 오버라이드
    system_prompt: Union[str, None] = Field(
        None,
        description="런타임 시스템 프롬프트 오버라이드 (변수 보간 지원)"
    )

    # 도구 제어
    allowed_tools: Union[List[str], str, None] = Field(
        None,
        description="이 액션에서 허용할 도구 목록 (변수 보간 지원)"
    )
    disable_tools: Union[bool, str] = Field(
        default=False,
        description="모든 도구 비활성화 여부 (변수 보간 지원)"
    )

    # 타임아웃 설정
    timeout: Union[float, str, None] = Field(
        None,
        description="실행 타임아웃 (초) (변수 보간: ${input.timeout as number})"
    )
```

### 2. GoogleAdkMultiAgentComponentConfig

```python
class GoogleAdkSubAgentConfig(BaseModel):
    """서브 에이전트 구성"""
    agent_name: str = Field(..., description="서브 에이전트 이름")
    model: str = Field(default="gemini-2.5-flash")
    instruction: str = Field(..., description="서브 에이전트 프롬프트")
    description: str = Field(..., description="서브 에이전트 역할 설명")
    tools: List[GoogleAdkToolConfig] = Field(default_factory=list)

    # 서브 에이전트별 설정
    temperature: float | None = None
    max_output_tokens: int | None = None


class GoogleAdkMultiAgentComponentConfig(CommonComponentConfig):
    """Google ADK 멀티 에이전트 컴포넌트 구성"""
    type: Literal[ComponentType.GOOGLE_ADK_MULTI_AGENT]

    # 코디네이터 에이전트
    coordinator_name: str = Field(..., description="코디네이터 이름")
    coordinator_model: str = Field(default="gemini-2.5-flash")
    coordinator_instruction: str = Field(..., description="코디네이터 프롬프트")
    coordinator_description: str = Field(..., description="코디네이터 설명")

    # 서브 에이전트들
    sub_agents: List[GoogleAdkSubAgentConfig] = Field(..., min_length=1)

    # 공통 설정
    streaming: bool = Field(default=False)
    enable_memory: bool = Field(default=True)

    # GCP 설정
    project_id: str | None = None
    location: str = Field(default="us-central1")
    credentials_path: str | None = None

    # 액션 정의
    actions: List["GoogleAdkMultiAgentActionConfig"]


class GoogleAdkMultiAgentActionConfig(CommonActionConfig):
    """멀티 에이전트 액션 구성"""

    # 입력 메시지
    message: str = Field(..., description="사용자 메시지")

    # 세션 관리
    session_id: str | None = None
    new_session: bool = Field(default=False)

    # 타겟 에이전트 (선택적)
    target_agent: str | None = Field(None, description="특정 서브 에이전트 지정")

    # 실행 옵션
    stream: bool | None = None
    context: Dict[str, Any] = Field(default_factory=dict)
```

## Service Implementation

### 1. GoogleAdkAgentService

**Location**: `src/mindor/core/component/services/google_adk/agent.py`

```python
from google.adk.agents import Agent
from google.adk.tools import google_search, code_executor
from mindor.core.component.base import ComponentService
from mindor.core.component.registry import register_component

@register_component(ComponentType.GOOGLE_ADK_AGENT)
class GoogleAdkAgentService(ComponentService):
    """Google ADK 단일 에이전트 서비스"""

    def __init__(self, id: str, config: GoogleAdkAgentComponentConfig,
                 global_configs: Dict, daemon: Any):
        super().__init__(id, config, global_configs, daemon)
        self.agent: Agent | None = None
        self.sessions: Dict[str, Any] = {}

    async def _start(self):
        """에이전트 초기화"""
        # GCP 인증 설정
        if self.config.credentials_path:
            self._setup_credentials()

        # 도구 로드
        tools = await self._load_tools()

        # 에이전트 생성
        self.agent = Agent(
            name=self.config.agent_name,
            model=self.config.model,
            instruction=self.config.instruction,
            description=self.config.description,
            tools=tools,
            # 추가 설정
        )

    async def _run(self, action: GoogleAdkAgentActionConfig,
                   context: ComponentActionContext) -> Any:
        """액션 실행"""
        handler = GoogleAdkAgentActionHandler(action, self.agent, self.sessions)
        return await handler.run(context)

    async def _stop(self):
        """리소스 정리"""
        self.sessions.clear()
        self.agent = None

    def _setup_credentials(self):
        """GCP 인증 설정"""
        # 서비스 계정 키 로드
        pass

    async def _load_tools(self) -> List[Any]:
        """도구 로드"""
        tools = []
        for tool_config in self.config.tools:
            if tool_config.type == "google_search":
                tools.append(google_search)
            elif tool_config.type == "code_executor":
                tools.append(code_executor)
            # 커스텀 함수 도구
            elif tool_config.function_name:
                tool = await self._create_function_tool(tool_config)
                tools.append(tool)
            # 기타 도구들...
        return tools

    async def _create_function_tool(self, config: GoogleAdkToolConfig):
        """커스텀 함수 도구 생성"""
        # 함수 도구 래퍼 생성
        pass


class GoogleAdkAgentActionHandler:
    """에이전트 액션 핸들러"""

    def __init__(self, action: GoogleAdkAgentActionConfig,
                 agent: Agent, sessions: Dict):
        self.action = action
        self.agent = agent
        self.sessions = sessions

    async def run(self, context: ComponentActionContext) -> Dict[str, Any]:
        """액션 실행"""
        # 변수 보간
        message = await context.render_variable(self.action.message)

        # 세션 관리
        session = await self._get_or_create_session()

        # 스트리밍 여부
        should_stream = self.action.stream if self.action.stream is not None \
                        else context.component_config.streaming

        if should_stream:
            return await self._run_streaming(session, message, context)
        else:
            return await self._run_sync(session, message, context)

    async def _get_or_create_session(self):
        """세션 가져오기 또는 생성"""
        if self.action.new_session:
            session_id = str(uuid.uuid4())
            session = self.agent.create_session(session_id)
            self.sessions[session_id] = session
            return session

        if self.action.session_id and self.action.session_id in self.sessions:
            return self.sessions[self.action.session_id]

        # 기본 세션
        session_id = "default"
        if session_id not in self.sessions:
            session = self.agent.create_session(session_id)
            self.sessions[session_id] = session
        return self.sessions[session_id]

    async def _run_sync(self, session: Any, message: str,
                       context: ComponentActionContext) -> Dict[str, Any]:
        """동기 실행"""
        response = await self.agent.run(session, message)

        result = {
            "response": response.text,
            "session_id": session.id,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            "tool_calls": [
                {
                    "name": tc.name,
                    "arguments": tc.arguments,
                    "result": tc.result
                }
                for tc in response.tool_calls
            ] if hasattr(response, "tool_calls") else []
        }

        # 출력 변수 보간
        return await context.render_variable(self.action.output or result)

    async def _run_streaming(self, session: Any, message: str,
                            context: ComponentActionContext):
        """스트리밍 실행"""
        async def stream_generator():
            async for chunk in self.agent.stream(session, message):
                yield {
                    "type": chunk.type,
                    "content": chunk.content,
                    "delta": chunk.delta if hasattr(chunk, "delta") else None
                }

        return stream_generator()
```

### 2. GoogleAdkMultiAgentService

**Location**: `src/mindor/core/component/services/google_adk/multi_agent.py`

```python
from google.adk.agents import LlmAgent

@register_component(ComponentType.GOOGLE_ADK_MULTI_AGENT)
class GoogleAdkMultiAgentService(ComponentService):
    """Google ADK 멀티 에이전트 서비스"""

    def __init__(self, id: str, config: GoogleAdkMultiAgentComponentConfig,
                 global_configs: Dict, daemon: Any):
        super().__init__(id, config, global_configs, daemon)
        self.coordinator: LlmAgent | None = None
        self.sub_agents: Dict[str, LlmAgent] = {}
        self.sessions: Dict[str, Any] = {}

    async def _start(self):
        """멀티 에이전트 시스템 초기화"""
        # GCP 인증
        if self.config.credentials_path:
            self._setup_credentials()

        # 서브 에이전트 생성
        for sub_config in self.config.sub_agents:
            tools = await self._load_tools(sub_config.tools)

            sub_agent = LlmAgent(
                name=sub_config.agent_name,
                model=sub_config.model,
                instruction=sub_config.instruction,
                description=sub_config.description,
                tools=tools,
            )
            self.sub_agents[sub_config.agent_name] = sub_agent

        # 코디네이터 에이전트 생성
        self.coordinator = LlmAgent(
            name=self.config.coordinator_name,
            model=self.config.coordinator_model,
            instruction=self.config.coordinator_instruction,
            description=self.config.coordinator_description,
            sub_agents=list(self.sub_agents.values())
        )

    async def _run(self, action: GoogleAdkMultiAgentActionConfig,
                   context: ComponentActionContext) -> Any:
        """멀티 에이전트 액션 실행"""
        handler = GoogleAdkMultiAgentActionHandler(
            action,
            self.coordinator,
            self.sub_agents,
            self.sessions
        )
        return await handler.run(context)

    async def _stop(self):
        """리소스 정리"""
        self.sessions.clear()
        self.sub_agents.clear()
        self.coordinator = None


class GoogleAdkMultiAgentActionHandler:
    """멀티 에이전트 액션 핸들러"""

    def __init__(self, action: GoogleAdkMultiAgentActionConfig,
                 coordinator: LlmAgent, sub_agents: Dict[str, LlmAgent],
                 sessions: Dict):
        self.action = action
        self.coordinator = coordinator
        self.sub_agents = sub_agents
        self.sessions = sessions

    async def run(self, context: ComponentActionContext) -> Dict[str, Any]:
        """액션 실행"""
        message = await context.render_variable(self.action.message)

        # 특정 서브 에이전트 타겟팅
        if self.action.target_agent:
            agent = self.sub_agents[self.action.target_agent]
        else:
            agent = self.coordinator

        session = await self._get_or_create_session(agent)

        # 실행
        response = await agent.run(session, message)

        result = {
            "response": response.text,
            "session_id": session.id,
            "agent": agent.name,
            "sub_agent_calls": [
                {
                    "agent": call.agent_name,
                    "message": call.message,
                    "response": call.response
                }
                for call in response.sub_agent_calls
            ] if hasattr(response, "sub_agent_calls") else []
        }

        return await context.render_variable(self.action.output or result)
```

## Input Parameters Detail

### Action Input 구조

Google ADK 에이전트 액션은 다음과 같은 계층적 input 구조를 따릅니다:

#### 1. 필수 입력 (Required Inputs)

**`message`** - 에이전트에 전달할 메시지
- **타입**: `str` 또는 `Dict[str, Any]`
- **변수 보간**: 지원
- **용도**: 사용자의 질문, 요청, 또는 구조화된 입력 데이터
- **예시**:
  ```yaml
  # 단순 문자열
  message: ${input.prompt}

  # 변수 보간
  message: "Analyze this data: ${input.data as json}"

  # 구조화된 입력
  message:
    task: ${input.task}
    data: ${input.dataset as json}
    format: ${input.output_format}
  ```

#### 2. 세션 관리 (Session Management)

**`session_id`** - 대화 컨텍스트 유지를 위한 세션 ID
- **타입**: `str` (optional)
- **변수 보간**: 지원
- **기본값**: `None` (자동으로 "default" 세션 사용)
- **용도**: 여러 요청에 걸쳐 대화 히스토리 유지
- **예시**:
  ```yaml
  # 고정 세션
  session_id: "user-123-session"

  # 동적 세션 ID
  session_id: ${input.user_id}

  # 이전 작업의 세션 재사용
  session_id: ${jobs.previous-chat.output.session_id}
  ```

**`new_session`** - 새 세션 시작 여부
- **타입**: `bool` 또는 `str`
- **변수 보간**: 지원
- **기본값**: `false`
- **용도**: 대화 히스토리를 초기화하고 새로 시작
- **예시**:
  ```yaml
  # 항상 새 세션
  new_session: true

  # 조건부 새 세션
  new_session: ${input.reset_context as boolean | false}
  ```

#### 3. 런타임 파라미터 오버라이드 (Runtime Parameters)

**`temperature`** - 생성 온도
- **타입**: `float` 또는 `str` (변수 보간용)
- **변수 보간**: 지원 (`as number`)
- **기본값**: 컴포넌트 레벨 설정
- **범위**: 0.0 ~ 2.0
- **용도**: 응답의 창의성/무작위성 제어
- **예시**:
  ```yaml
  # 고정값
  temperature: 0.7

  # 런타임 입력
  temperature: ${input.temperature as number | 0.7}

  # 조건부 값
  temperature: ${input.creative as boolean ? 1.5 : 0.3}
  ```

**`top_p`** - Nucleus sampling 파라미터
- **타입**: `float` 또는 `str`
- **변수 보간**: 지원 (`as number`)
- **기본값**: 컴포넌트 레벨 설정
- **범위**: 0.0 ~ 1.0
- **예시**:
  ```yaml
  top_p: ${input.top_p as number | 0.95}
  ```

**`max_output_tokens`** - 최대 출력 토큰 수
- **타입**: `int` 또는 `str`
- **변수 보간**: 지원 (`as integer`)
- **기본값**: 컴포넌트 레벨 설정
- **예시**:
  ```yaml
  # 고정값
  max_output_tokens: 2048

  # 런타임 입력
  max_output_tokens: ${input.max_tokens as integer | 1024}

  # 조건부 값 (긴 응답 vs 짧은 응답)
  max_output_tokens: ${input.detailed as boolean ? 4096 : 512}
  ```

#### 4. 실행 옵션 (Execution Options)

**`stream`** - 스트리밍 응답 활성화
- **타입**: `bool` 또는 `str`
- **변수 보간**: 지원 (`as boolean`)
- **기본값**: 컴포넌트 레벨 `streaming` 설정
- **용도**: 실시간 응답 스트리밍
- **예시**:
  ```yaml
  # 항상 스트리밍
  stream: true

  # 런타임 결정
  stream: ${input.stream as boolean | false}
  ```

**`timeout`** - 실행 타임아웃
- **타입**: `float` 또는 `str`
- **변수 보간**: 지원 (`as number`)
- **기본값**: `None` (무제한)
- **단위**: 초
- **예시**:
  ```yaml
  # 고정 타임아웃 (30초)
  timeout: 30.0

  # 런타임 설정
  timeout: ${input.timeout as number | 60.0}
  ```

#### 5. 컨텍스트 및 메타데이터 (Context & Metadata)

**`context`** - 추가 컨텍스트 데이터
- **타입**: `Dict[str, Any]` 또는 `str` (JSON 문자열)
- **변수 보간**: 지원
- **기본값**: `{}`
- **용도**: 에이전트에게 추가 정보 전달 (메타데이터, 환경 정보 등)
- **예시**:
  ```yaml
  # 정적 컨텍스트
  context:
    user_role: "admin"
    environment: "production"

  # 동적 컨텍스트
  context:
    user_id: ${input.user_id}
    timestamp: ${input.timestamp}
    previous_result: ${jobs.previous-step.output}

  # JSON 문자열
  context: ${input.context as json}
  ```

**`system_prompt`** - 시스템 프롬프트 오버라이드
- **타입**: `str` (optional)
- **변수 보간**: 지원
- **기본값**: 컴포넌트 레벨 `instruction`
- **용도**: 특정 액션에 대해 시스템 프롬프트를 동적으로 변경
- **예시**:
  ```yaml
  # 고정 프롬프트
  system_prompt: "You are a code review expert. Focus on security issues."

  # 동적 프롬프트
  system_prompt: ${input.system_instruction}

  # 템플릿 결합
  system_prompt: |
    You are a ${input.role} expert.
    ${input.additional_instructions}
  ```

#### 6. 도구 제어 (Tool Control)

**`allowed_tools`** - 허용된 도구 목록
- **타입**: `List[str]` 또는 `str` (변수 보간용)
- **변수 보간**: 지원
- **기본값**: `None` (모든 도구 허용)
- **용도**: 특정 액션에서 사용 가능한 도구를 제한
- **예시**:
  ```yaml
  # 특정 도구만 허용
  allowed_tools: ["google_search", "code_executor"]

  # 동적 도구 리스트
  allowed_tools: ${input.tools as json}

  # 조건부 도구 허용
  allowed_tools: ${input.allow_code_execution as boolean ? ["google_search", "code_executor"] : ["google_search"]}
  ```

**`disable_tools`** - 모든 도구 비활성화
- **타입**: `bool` 또는 `str`
- **변수 보간**: 지원 (`as boolean`)
- **기본값**: `false`
- **용도**: 도구 없이 순수 텍스트 생성만 수행
- **예시**:
  ```yaml
  # 도구 비활성화
  disable_tools: true

  # 조건부 비활성화
  disable_tools: ${input.no_tools as boolean | false}
  ```

### 변수 보간 패턴 (Variable Interpolation Patterns)

#### 기본 패턴
```yaml
# 입력 필드 직접 참조
message: ${input.prompt}

# 중첩 필드 접근
message: ${input.user.message}

# 배열 인덱싱
message: ${input.messages[0].content}
```

#### 타입 변환 (Type Conversion)
```yaml
# 숫자 변환
temperature: ${input.temp as number}
max_output_tokens: ${input.max_tokens as integer}

# 불리언 변환
stream: ${input.enable_stream as boolean}

# JSON 파싱
context: ${input.metadata as json}
```

#### 기본값 (Default Values)
```yaml
# 파이프 연산자로 기본값 설정
temperature: ${input.temperature as number | 0.7}
max_output_tokens: ${input.max_tokens as integer | 1024}
stream: ${input.stream as boolean | false}
```

#### 이전 작업 결과 참조
```yaml
# 이전 job의 출력 사용
message: "Analyze this: ${jobs.data-collection.output.result}"
session_id: ${jobs.previous-chat.output.session_id}

# 환경 변수
context:
  api_key: ${env.GOOGLE_API_KEY}
  project: ${env.GCP_PROJECT_ID}
```

#### 조건부 표현식
```yaml
# 삼항 연산자 스타일 (의사 코드 - 실제 구현 시 검토 필요)
temperature: ${input.creative_mode ? 1.5 : 0.3}
max_output_tokens: ${input.detailed ? 4096 : 512}
```

### Input 사용 시나리오 예시

#### 시나리오 1: 단순 질문-답변

**model-compose YAML:**
```yaml
actions:
  - id: ask
    message: ${input.question}
    output: ${response}
```

**Google ADK Python 코드:**
```python
from google.adk.agents import Agent

agent = Agent(
    name="qa_assistant",
    model="gemini-2.5-flash",
    instruction="You are a helpful assistant that answers questions."
)

# 동기 실행
session = agent.create_session()
response = await agent.run(session, "What is the capital of France?")
print(response.text)
```

#### 시나리오 2: 세션 기반 대화

**model-compose YAML:**
```yaml
actions:
  - id: chat
    message: ${input.message}
    session_id: ${input.user_id}
    temperature: 0.7
    output:
      response: ${response}
      session: ${session_id}
```

**Google ADK Python 코드:**
```python
from google.adk.agents import Agent

agent = Agent(
    name="chat_assistant",
    model="gemini-2.5-flash",
    instruction="You are a conversational assistant.",
    temperature=0.7
)

# 세션 생성 및 유지
user_id = "user-123"
session = agent.create_session(session_id=user_id)

# 첫 번째 메시지
response1 = await agent.run(session, "My name is Alice")
print(response1.text)

# 두 번째 메시지 (같은 세션)
response2 = await agent.run(session, "What is my name?")
print(response2.text)  # "Your name is Alice"
```

#### 시나리오 3: 파라미터 동적 조정

**model-compose YAML:**
```yaml
actions:
  - id: generate
    message: ${input.prompt}
    temperature: ${input.temperature as number | 0.7}
    max_output_tokens: ${input.max_length as integer | 1024}
    stream: ${input.stream as boolean | false}
```

**Google ADK Python 코드:**
```python
from google.adk.agents import Agent

def create_agent_with_params(temperature: float, max_tokens: int):
    return Agent(
        name="dynamic_assistant",
        model="gemini-2.5-flash",
        instruction="You are a helpful assistant.",
        temperature=temperature,
        max_output_tokens=max_tokens
    )

# 파라미터 동적 설정
agent = create_agent_with_params(temperature=0.7, max_tokens=1024)
session = agent.create_session()

# 스트리밍 실행
async for chunk in agent.stream(session, "Write a poem about AI"):
    print(chunk.content, end="", flush=True)
```

#### 시나리오 4: 컨텍스트 전달

**model-compose YAML:**
```yaml
actions:
  - id: analyze-with-context
    message: ${input.task}
    context:
      user_info: ${input.user}
      previous_results: ${jobs.previous-step.output}
      timestamp: ${input.timestamp}
    output: ${response}
```

**Google ADK Python 코드:**
```python
from google.adk.agents import Agent

agent = Agent(
    name="context_aware_assistant",
    model="gemini-2.5-flash",
    instruction="You are an assistant that uses provided context."
)

# 컨텍스트를 메시지에 포함
context = {
    "user_info": {"name": "Alice", "role": "admin"},
    "previous_results": {"analysis": "positive sentiment"},
    "timestamp": "2025-01-06T10:00:00Z"
}

message = f"""
Task: Analyze the following data

Context:
- User: {context['user_info']['name']} ({context['user_info']['role']})
- Previous analysis: {context['previous_results']['analysis']}
- Time: {context['timestamp']}

Please provide a detailed analysis.
"""

session = agent.create_session()
response = await agent.run(session, message)
print(response.text)
```

#### 시나리오 5: 도구 제어

**model-compose YAML:**
```yaml
actions:
  - id: safe-mode
    message: ${input.query}
    allowed_tools: ["google_search"]  # 검색만 허용
    temperature: 0.3

  - id: full-access
    message: ${input.query}
    allowed_tools: null  # 모든 도구 허용
    temperature: 0.7

  - id: no-tools
    message: ${input.query}
    disable_tools: true  # 도구 없이 순수 생성만
```

**Google ADK Python 코드:**
```python
from google.adk.agents import Agent
from google.adk.tools import google_search, code_executor

# Safe mode: 검색만 허용
safe_agent = Agent(
    name="safe_assistant",
    model="gemini-2.5-flash",
    instruction="You can only use search tools.",
    tools=[google_search],
    temperature=0.3
)

# Full access: 모든 도구 허용
full_agent = Agent(
    name="full_assistant",
    model="gemini-2.5-flash",
    instruction="You have access to all tools.",
    tools=[google_search, code_executor],
    temperature=0.7
)

# No tools: 도구 없이 순수 생성만
no_tools_agent = Agent(
    name="text_only_assistant",
    model="gemini-2.5-flash",
    instruction="You generate text without using any tools.",
    tools=[],  # 빈 리스트
    temperature=0.7
)

# 실행
session_safe = safe_agent.create_session()
response_safe = await safe_agent.run(session_safe, "Search for latest AI news")

session_full = full_agent.create_session()
response_full = await full_agent.run(session_full, "Calculate 2+2 using code")

session_text = no_tools_agent.create_session()
response_text = await no_tools_agent.run(session_text, "Write a story")
```

#### 시나리오 6: 시스템 프롬프트 오버라이드

**model-compose YAML:**
```yaml
actions:
  - id: code-review
    message: ${input.code}
    system_prompt: |
      You are an expert code reviewer specializing in ${input.language}.
      Focus on: ${input.focus_areas}
      Be ${input.strictness_level} in your review.
    context:
      language: ${input.language}
      project_type: ${input.project_type}
```

**Google ADK Python 코드:**
```python
from google.adk.agents import Agent

def create_code_reviewer(language: str, focus_areas: str, strictness: str):
    instruction = f"""
You are an expert code reviewer specializing in {language}.
Focus on: {focus_areas}
Be {strictness} in your review.
"""

    return Agent(
        name="code_reviewer",
        model="gemini-2.5-flash",
        instruction=instruction,
        temperature=0.3
    )

# 동적으로 프롬프트 생성
agent = create_code_reviewer(
    language="Python",
    focus_areas="security vulnerabilities, performance issues",
    strictness="strict"
)

code = """
def authenticate(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return db.execute(query)
"""

session = agent.create_session()
response = await agent.run(session, f"Review this code:\n\n{code}")
print(response.text)
```

#### 시나리오 7: 워크플로우 체인

**model-compose YAML:**
```yaml
workflow:
  jobs:
    # 1단계: 데이터 수집
    - id: collect
      component: data-collector
      input: ${input}

    # 2단계: 에이전트 분석 (이전 결과 사용)
    - id: analyze
      component: google-adk-agent
      action: analyze
      input:
        message: "Analyze this data"
        context:
          data: ${jobs.collect.output.data}
          user: ${input.user_id}

    # 3단계: 후속 분석 (세션 유지)
    - id: follow-up
      component: google-adk-agent
      action: chat
      input:
        message: ${input.follow_up_question}
        session_id: ${jobs.analyze.output.session_id}  # 이전 세션 재사용
```

**Google ADK Python 코드:**
```python
from google.adk.agents import Agent
import subprocess

# 1단계: 데이터 수집 (Shell 명령)
def collect_data():
    result = subprocess.run(
        ["df", "-h"],
        capture_output=True,
        text=True
    )
    return result.stdout

# 2단계: 에이전트 분석
analysis_agent = Agent(
    name="analyzer",
    model="gemini-2.5-flash",
    instruction="You are a data analyst. Analyze the provided data."
)

# 3단계: 후속 질문 (세션 유지)
async def workflow_chain(user_id: str, follow_up_question: str):
    # Step 1: 데이터 수집
    data = collect_data()
    print(f"Collected data:\n{data}\n")

    # Step 2: 분석 (새 세션)
    session_id = f"analysis-{user_id}"
    session = analysis_agent.create_session(session_id=session_id)

    analysis_message = f"""
Analyze this data:

{data}

User ID: {user_id}
"""

    response = await analysis_agent.run(session, analysis_message)
    print(f"Analysis:\n{response.text}\n")

    # Step 3: 후속 질문 (같은 세션 유지)
    follow_up_response = await analysis_agent.run(session, follow_up_question)
    print(f"Follow-up response:\n{follow_up_response.text}")

    return {
        "data": data,
        "analysis": response.text,
        "follow_up": follow_up_response.text,
        "session_id": session_id
    }

# 실행
result = await workflow_chain(
    user_id="user-123",
    follow_up_question="Can you provide recommendations based on your analysis?"
)
```

#### 시나리오 8: 멀티 에이전트 시스템

**model-compose YAML:**
```yaml
components:
  - id: research-team
    type: google-adk-multi-agent
    coordinator_name: ResearchCoordinator
    coordinator_model: gemini-2.5-pro
    coordinator_instruction: |
      You coordinate a research team.
      Delegate to specialists as needed.

    sub_agents:
      - agent_name: web_researcher
        model: gemini-2.5-flash
        instruction: You are a web research specialist.
        tools: [google_search]

      - agent_name: code_analyst
        model: gemini-2.5-flash
        instruction: You analyze code.
        tools: [code_executor]
```

**Google ADK Python 코드:**
```python
from google.adk.agents import LlmAgent
from google.adk.tools import google_search, code_executor

# 서브 에이전트들 생성
web_researcher = LlmAgent(
    name="web_researcher",
    model="gemini-2.5-flash",
    instruction="You are a web research specialist. Use search tools to find information.",
    description="Web research specialist",
    tools=[google_search]
)

code_analyst = LlmAgent(
    name="code_analyst",
    model="gemini-2.5-flash",
    instruction="You are a code analysis expert. Analyze code and provide insights.",
    description="Code analysis specialist",
    tools=[code_executor]
)

data_analyst = LlmAgent(
    name="data_analyst",
    model="gemini-2.5-flash",
    instruction="You analyze data and create insights.",
    description="Data analysis specialist",
    tools=[code_executor]
)

# 코디네이터 에이전트 생성
coordinator = LlmAgent(
    name="ResearchCoordinator",
    model="gemini-2.5-pro",
    instruction="""
You coordinate a research team. Delegate tasks to specialists:
- Use 'web_researcher' for web searches and general information
- Use 'code_analyst' for code analysis and technical questions
- Use 'data_analyst' for data processing and statistics
""",
    description="Research team coordinator",
    sub_agents=[web_researcher, code_analyst, data_analyst]
)

# 실행
session = coordinator.create_session()
response = await coordinator.run(
    session,
    "Research the latest trends in AI and analyze a Python code sample for performance issues."
)

print(response.text)

# 서브 에이전트 호출 확인
if hasattr(response, 'sub_agent_calls'):
    print("\nSub-agent calls:")
    for call in response.sub_agent_calls:
        print(f"- {call.agent_name}: {call.message}")
```

### Input 검증 및 에러 처리

#### 필수 입력 누락
```python
# 런타임에 Pydantic이 자동 검증
ValidationError: message field required
```

#### 타입 불일치
```yaml
# 잘못된 예시
temperature: "not-a-number"  # 변환 실패 시 기본값 또는 에러

# 올바른 예시
temperature: ${input.temp as number | 0.7}  # 기본값으로 안전하게 처리
```

#### 변수 참조 실패
```yaml
# input.unknown이 없을 경우
message: ${input.unknown | "default message"}  # 기본값 사용

# 엄격 모드 (기본값 없음)
message: ${input.required}  # 없으면 에러
```

## YAML Configuration Examples

### Example 1: 단일 에이전트 (웹 검색 도우미)

```yaml
controller:
  type: http-server
  port: 8080

components:
  - id: search-assistant
    type: google-adk-agent
    agent_name: SearchAssistant
    model: gemini-2.5-flash
    instruction: |
      You are a helpful research assistant. Use Google Search to find
      accurate and up-to-date information to answer user questions.
    description: A search-powered assistant

    tools:
      - type: google_search

    streaming: true
    enable_memory: true

    actions:
      - id: search
        message: ${input.query}
        output:
          answer: ${response}
          session: ${session_id}

workflows:
  - id: search-query
    jobs:
      - id: search
        component: search-assistant
        action: search
        input:
          query: ${input.question}
```

### Example 2: 멀티 에이전트 (리서치 팀)

```yaml
components:
  - id: research-team
    type: google-adk-multi-agent

    coordinator_name: ResearchCoordinator
    coordinator_model: gemini-2.5-pro
    coordinator_instruction: |
      You coordinate a research team. Delegate tasks to specialists:
      - Use 'web_researcher' for web searches and general information
      - Use 'code_analyst' for code analysis and technical questions
      - Use 'data_analyst' for data processing and statistics
    coordinator_description: Research team coordinator

    sub_agents:
      - agent_name: web_researcher
        model: gemini-2.5-flash
        instruction: You are a web research specialist. Use search tools to find information.
        description: Web research specialist
        tools:
          - type: google_search
          - type: tavily_search

      - agent_name: code_analyst
        model: gemini-2.5-flash
        instruction: You are a code analysis expert. Analyze code and provide insights.
        description: Code analysis specialist
        tools:
          - type: code_executor
          - type: github

      - agent_name: data_analyst
        model: gemini-2.5-flash
        instruction: You analyze data and create visualizations.
        description: Data analysis specialist
        tools:
          - type: code_executor

    streaming: false
    enable_memory: true

    actions:
      - id: research
        message: ${input.query}
        output:
          result: ${response}
          agents_used: ${sub_agent_calls}

workflows:
  - id: deep-research
    jobs:
      - id: research
        component: research-team
        action: research
        input:
          query: ${input.topic}
```

### Example 3: 커스텀 함수 도구 사용

```yaml
components:
  - id: data-processor
    type: google-adk-agent
    agent_name: DataProcessor
    model: gemini-2.5-flash
    instruction: You process and analyze data using provided tools.

    tools:
      # 내장 도구
      - type: code_executor

      # 커스텀 함수 도구
      - function_name: fetch_database
        function_description: Fetch data from PostgreSQL database
        function_parameters:
          query:
            type: string
            description: SQL query to execute
          limit:
            type: integer
            description: Maximum rows to return
        config:
          connection_string: ${env.DATABASE_URL}

      - function_name: send_slack_notification
        function_description: Send notification to Slack channel
        function_parameters:
          channel:
            type: string
            description: Slack channel name
          message:
            type: string
            description: Message to send
        config:
          slack_token: ${env.SLACK_TOKEN}

    actions:
      - id: process
        message: ${input.task}
```

### Example 4: MCP 도구 통합

```yaml
components:
  - id: mcp-agent
    type: google-adk-agent
    agent_name: McpAssistant
    model: gemini-2.5-flash
    instruction: You can use MCP tools to interact with external systems.

    tools:
      # MCP 서버의 도구 사용
      - mcp_server_url: http://localhost:3000
        mcp_tool_name: filesystem_read

      - mcp_server_url: http://localhost:3000
        mcp_tool_name: filesystem_write

      - mcp_server_url: http://localhost:3001
        mcp_tool_name: github_create_issue

    actions:
      - id: execute
        message: ${input.instruction}
```

## Integration with Existing Components

Google ADK 컴포넌트는 기존 model-compose 컴포넌트들과 워크플로우에서 함께 사용할 수 있습니다:

```yaml
workflows:
  - id: hybrid-workflow
    jobs:
      # 1. Shell 명령으로 데이터 수집
      - id: collect-data
        component: data-collector
        type: shell
        command: ["python", "collect_data.py"]
        output: ${result.stdout}

      # 2. Google ADK 에이전트로 데이터 분석
      - id: analyze
        component: analysis-agent
        type: google-adk-agent
        input:
          data: ${jobs.collect-data.output}
          instruction: "Analyze this data and provide insights"

      # 3. HTTP API로 결과 전송
      - id: send-result
        component: api-client
        type: http-client
        input:
          endpoint: /results
          method: POST
          body:
            analysis: ${jobs.analyze.output.response}
```

## Dependencies

### Python Packages

```txt
# requirements.txt에 추가
google-adk>=0.1.0
google-cloud-aiplatform>=1.40.0
google-auth>=2.25.0
```

### Optional Dependencies

```txt
# MCP 지원
anthropic-mcp>=0.1.0

# 추가 도구들
tavily-python>=0.3.0
firecrawl-py>=0.0.5
PyGithub>=2.1.0
notion-client>=2.0.0
exa-py>=1.0.0
```

## File Structure

```
src/mindor/
├── dsl/
│   └── schema/
│       ├── component/
│       │   └── impl/
│       │       └── google_adk/
│       │           ├── __init__.py
│       │           ├── agent.py          # GoogleAdkAgentComponentConfig
│       │           └── multi_agent.py    # GoogleAdkMultiAgentComponentConfig
│       └── action/
│           └── impl/
│               └── google_adk/
│                   ├── __init__.py
│                   ├── agent.py          # GoogleAdkAgentActionConfig
│                   └── multi_agent.py    # GoogleAdkMultiAgentActionConfig
└── core/
    └── component/
        └── services/
            └── google_adk/
                ├── __init__.py
                ├── agent.py              # GoogleAdkAgentService
                ├── multi_agent.py        # GoogleAdkMultiAgentService
                ├── tools/
                │   ├── __init__.py
                │   ├── builtin.py        # 내장 도구 로더
                │   ├── custom.py         # 커스텀 함수 도구
                │   ├── openapi.py        # OpenAPI 도구
                │   └── mcp.py            # MCP 도구
                └── session.py            # 세션 관리
```

## Implementation Phases

### Phase 1: Core Agent Support (MVP)
- [ ] 단일 에이전트 컴포넌트 구현
- [ ] 기본 액션 실행 (동기)
- [ ] 내장 도구 지원 (google_search, code_executor)
- [ ] 세션 관리
- [ ] GCP 인증

### Phase 2: Advanced Features
- [ ] 스트리밍 응답 지원
- [ ] 멀티 에이전트 컴포넌트
- [ ] 메모리 및 컨텍스트 관리
- [ ] 도구 확인 (HITL)

### Phase 3: Extended Tool Support
- [ ] 커스텀 함수 도구
- [ ] OpenAPI 도구
- [ ] MCP 도구 통합
- [ ] 서드파티 도구들 (Tavily, GitHub, etc.)

### Phase 4: Optimization & Production
- [ ] 성능 최적화
- [ ] 에러 핸들링 강화
- [ ] 로깅 및 모니터링
- [ ] 단위 테스트 및 통합 테스트
- [ ] 문서화

## Testing Strategy

### Unit Tests

```python
# tests/core/component/services/google_adk/test_agent.py

import pytest
from mindor.core.component.services.google_adk.agent import GoogleAdkAgentService

@pytest.mark.asyncio
async def test_agent_initialization():
    config = GoogleAdkAgentComponentConfig(
        id="test-agent",
        type=ComponentType.GOOGLE_ADK_AGENT,
        agent_name="TestAgent",
        model="gemini-2.5-flash",
        instruction="Test instruction",
        tools=[GoogleAdkToolConfig(type="google_search")]
    )

    service = GoogleAdkAgentService("test", config, {}, None)
    await service._start()

    assert service.agent is not None
    assert service.agent.name == "TestAgent"

    await service._stop()

@pytest.mark.asyncio
async def test_agent_run():
    # 에이전트 실행 테스트
    pass

@pytest.mark.asyncio
async def test_streaming_response():
    # 스트리밍 응답 테스트
    pass
```

### Integration Tests

```python
# tests/integration/test_google_adk_workflow.py

@pytest.mark.asyncio
async def test_agent_workflow():
    """전체 워크플로우 테스트"""
    # YAML 로드
    # 워크플로우 실행
    # 결과 검증
    pass
```

## Error Handling

### Common Error Scenarios

1. **GCP 인증 실패**
   - 서비스 계정 키가 없거나 잘못됨
   - 프로젝트 ID 오류
   - 권한 부족

2. **모델 호출 실패**
   - API 할당량 초과
   - 모델 사용 불가
   - 네트워크 오류

3. **도구 실행 실패**
   - 도구 구성 오류
   - 외부 API 오류
   - 타임아웃

4. **세션 관리 오류**
   - 세션 만료
   - 메모리 부족
   - 동시성 문제

### Error Response Format

```json
{
  "error": {
    "type": "GoogleAdkError",
    "code": "AUTHENTICATION_FAILED",
    "message": "Failed to authenticate with GCP",
    "details": {
      "project_id": "my-project",
      "location": "us-central1"
    }
  }
}
```

## Security Considerations

1. **Credentials Management**
   - 서비스 계정 키를 환경 변수로 관리
   - Secrets Manager 통합 고려
   - 키 파일 권한 설정

2. **Tool Execution**
   - 도구 실행 전 입력 검증
   - 샌드박스 환경 사용 (code_executor)
   - Rate limiting

3. **Data Privacy**
   - 민감한 데이터 마스킹
   - 로그에서 개인정보 제거
   - 세션 데이터 암호화

## Performance Considerations

1. **Session Management**
   - 세션 풀링
   - 자동 세션 정리 (TTL)
   - 메모리 사용량 모니터링

2. **Concurrent Execution**
   - `max_concurrent_count` 활용
   - 비동기 실행 최적화
   - 작업 큐 관리

3. **Caching**
   - 컨텍스트 캐싱 활성화
   - 도구 결과 캐싱
   - 모델 응답 캐싱

## Monitoring & Observability

### Metrics

- 에이전트 호출 횟수
- 평균 응답 시간
- 토큰 사용량
- 에러율
- 도구 실행 통계

### Logging

```python
logger.info(
    "Google ADK agent executed",
    extra={
        "agent_name": agent.name,
        "model": config.model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "tools_used": [tc.name for tc in response.tool_calls],
        "duration_ms": duration
    }
)
```

## Future Enhancements

1. **Advanced Orchestration**
   - 워크플로우 에이전트 (sequential, loop, parallel)
   - 동적 에이전트 생성
   - 에이전트 간 데이터 공유

2. **Tool Ecosystem**
   - 커스텀 도구 레지스트리
   - 도구 버전 관리
   - 도구 마켓플레이스

3. **Deployment**
   - Vertex AI Agent Engine 배포
   - Cloud Run 배포
   - 자동 스케일링

4. **Evaluation**
   - 에이전트 평가 프레임워크
   - A/B 테스트
   - 성능 벤치마크

## Input Parameters Quick Reference

### 전체 Input 파라미터 요약 테이블

| 파라미터 | 타입 | 필수 | 기본값 | 변수 보간 | 설명 |
|---------|------|------|--------|----------|------|
| `message` | `str \| Dict[str, Any]` | ✅ | - | ✅ | 에이전트에 전달할 메시지 |
| `session_id` | `str` | ❌ | `None` | ✅ | 세션 ID (대화 컨텍스트 유지) |
| `new_session` | `bool \| str` | ❌ | `false` | ✅ | 새 세션 시작 여부 |
| `temperature` | `float \| str` | ❌ | 컴포넌트 설정 | ✅ (`as number`) | 생성 온도 (0.0-2.0) |
| `top_p` | `float \| str` | ❌ | 컴포넌트 설정 | ✅ (`as number`) | Nucleus sampling (0.0-1.0) |
| `max_output_tokens` | `int \| str` | ❌ | 컴포넌트 설정 | ✅ (`as integer`) | 최대 출력 토큰 수 |
| `stream` | `bool \| str` | ❌ | 컴포넌트 설정 | ✅ (`as boolean`) | 스트리밍 응답 활성화 |
| `timeout` | `float \| str` | ❌ | `None` | ✅ (`as number`) | 실행 타임아웃 (초) |
| `context` | `Dict \| str` | ❌ | `{}` | ✅ | 추가 컨텍스트 데이터 |
| `system_prompt` | `str` | ❌ | 컴포넌트 설정 | ✅ | 시스템 프롬프트 오버라이드 |
| `allowed_tools` | `List[str] \| str` | ❌ | `None` | ✅ | 허용된 도구 목록 |
| `disable_tools` | `bool \| str` | ❌ | `false` | ✅ (`as boolean`) | 모든 도구 비활성화 |

### 변수 보간 타입 변환 참조

| 변환 구문 | 결과 타입 | 예시 |
|----------|----------|------|
| `as number` | `float` | `${input.temp as number}` |
| `as integer` | `int` | `${input.max_tokens as integer}` |
| `as boolean` | `bool` | `${input.stream as boolean}` |
| `as json` | Parsed JSON | `${input.metadata as json}` |
| `as text` | `str` | `${input.prompt as text}` |
| `\| default` | 기본값 폴백 | `${input.temp as number \| 0.7}` |

### 주요 변수 소스

| 소스 | 구문 | 예시 |
|------|------|------|
| 런타임 입력 | `${input.*}` | `${input.query}` |
| 이전 job 결과 | `${jobs.<id>.output.*}` | `${jobs.analyze.output.result}` |
| 환경 변수 | `${env.*}` | `${env.GOOGLE_API_KEY}` |
| 결과 객체 | `${result.*}` | `${result.stdout}` |
| 응답 객체 | `${response.*}` | `${response.choices[0]}` |
| 세션 ID | `${session_id}` | `${session_id}` |
| 게이트웨이 | `${gateway:<port>}` | `${gateway:8000}` |

### 컴포넌트 vs 액션 레벨 설정

| 설정 | 컴포넌트 레벨 | 액션 레벨 | 우선순위 |
|------|--------------|-----------|---------|
| `agent_name` | ✅ | ❌ | - |
| `model` | ✅ | ❌ | - |
| `instruction` | ✅ | ✅ (`system_prompt`) | 액션 > 컴포넌트 |
| `tools` | ✅ | ✅ (`allowed_tools`, `disable_tools`) | 액션 > 컴포넌트 |
| `temperature` | ✅ | ✅ | 액션 > 컴포넌트 |
| `streaming` | ✅ | ✅ (`stream`) | 액션 > 컴포넌트 |
| `max_output_tokens` | ✅ | ✅ | 액션 > 컴포넌트 |
| `message` | ❌ | ✅ | - |
| `session_id` | ❌ | ✅ | - |
| `context` | ❌ | ✅ | - |

## References

- [Google ADK Documentation](https://google.github.io/adk-docs/)
- [Google ADK Python SDK](https://github.com/google/adk-python)
- [Vertex AI Agent Builder](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-development-kit/overview)
- [Model Context Protocol](https://modelcontextprotocol.io/)

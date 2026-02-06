# Agent Component Specification

## Overview

AI 에이전트를 선언적으로 정의하고 실행할 수 있는 `agent` 타입의 컴포넌트를 추가하는 스펙입니다. Agent는 주어진 작업(task)을 자율적으로 수행하며, 필요에 따라 도구(tools)를 사용하고 반복적으로 추론(reasoning)할 수 있습니다.

## Design Goals

1. **선언적 Agent 정의**: YAML 설정으로 Agent의 행동을 완전히 정의
2. **Tool Integration**: 기존 컴포넌트들을 Agent의 도구로 재사용
3. **Model Abstraction**: 다양한 LLM 모델(로컬/API)을 Agent의 추론 엔진으로 사용
4. **Iterative Reasoning**: ReAct 패턴 기반 반복 추론 지원
5. **Context Management**: 대화 히스토리 및 컨텍스트 자동 관리
6. **Workflow Integration**: Agent를 워크플로우의 일부로 통합 가능

## Use Cases

### 1. Research Assistant
웹 검색, 문서 분석, 데이터 수집을 자동으로 수행하는 리서치 에이전트

```yaml
components:
  - id: research-agent
    type: agent
    model: gpt-4o
    system_prompt: |
      You are a research assistant that helps find and analyze information.
      Use the web-search tool to find relevant information, then summarize your findings.
    tools:
      - web-search
      - document-analyzer
    max_iterations: 5
```

### 2. Data Pipeline Orchestrator
여러 데이터 처리 단계를 자동으로 계획하고 실행하는 에이전트

```yaml
components:
  - id: pipeline-agent
    type: agent
    model: claude-sonnet-4
    system_prompt: |
      You orchestrate data processing pipelines.
      Plan and execute steps to clean, transform, and analyze data.
    tools:
      - data-cleaner
      - data-transformer
      - data-analyzer
    max_iterations: 10
```

### 3. Customer Support Bot
고객 질문에 답하고 필요시 데이터베이스를 조회하는 에이전트

```yaml
components:
  - id: support-agent
    type: agent
    model: local-llm
    system_prompt: |
      You are a helpful customer support assistant.
      Use available tools to look up order information and help customers.
    tools:
      - order-lookup
      - faq-search
      - ticket-creator
    max_iterations: 3
    temperature: 0.7
```

## Architecture

### Component Hierarchy

```
AgentComponentConfig (Component Schema)
  ↓
AgentActionConfig (Action Schema)
  ↓
AgentExecutor (Service Layer)
  ↓
ToolRegistry (Tool Management)
```

### Key Components

#### 1. Agent Component
Agent의 전역 설정 (모델, 시스템 프롬프트, 기본 도구)

#### 2. Agent Action
특정 작업(task) 실행을 위한 액션 설정

#### 3. Agent Executor
ReAct 패턴 기반 추론 루프 실행 엔진

#### 4. Tool Registry
Agent가 사용할 수 있는 도구들의 레지스트리

## Schema Design

### 1. AgentToolConfig

**Location**: `src/mindor/dsl/schema/component/impl/agent.py`

Agent가 사용할 도구 정의:

```python
from typing import Union, Optional, Dict, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.component import ComponentConfig

class AgentToolConfig(BaseModel):
    """Agent 도구 설정 (component + action)"""

    component: Union[str, ComponentConfig] = Field(
        ...,
        description="도구로 사용할 컴포넌트 ID 또는 인라인 컴포넌트 정의"
    )

    action: str = Field(
        default="__default__",
        description="실행할 액션 ID. 기본값은 '__default__'"
    )

    name: Optional[str] = Field(
        default=None,
        description="도구 이름 (LLM이 인식할 이름). 미지정 시 component ID 사용"
    )

    description: Optional[str] = Field(
        default=None,
        description="도구 설명 (LLM에게 제공). 미지정 시 액션 스키마에서 자동 생성"
    )

    # 도구 실행 시 추가 컨텍스트
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="도구 실행 시 추가할 컨텍스트 데이터"
    )
```

### 2. AgentComponentConfig

**Location**: `src/mindor/dsl/schema/component/impl/agent.py`

```python
from typing import Literal, List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field, model_validator
from mindor.dsl.schema.action import AgentActionConfig
from .common import ComponentType, CommonComponentConfig

class AgentComponentConfig(CommonComponentConfig):
    """Agent 컴포넌트 설정"""

    type: Literal[ComponentType.AGENT]

    # Model Configuration
    model: str = Field(
        ...,
        description="모델 컴포넌트 ID (예: 'gpt-4o', 'local-llm'). model 타입 컴포넌트를 참조."
    )

    # Agent Behavior
    system_prompt: Optional[str] = Field(
        default=None,
        description="Agent의 시스템 프롬프트 (역할 및 행동 지침)"
    )

    tools: List[Union[str, AgentToolConfig]] = Field(
        default_factory=list,
        description="Agent가 사용할 수 있는 도구 목록. 문자열(컴포넌트 ID) 또는 AgentToolConfig 객체"
    )

    max_iterations: int = Field(
        default=10,
        description="최대 추론 반복 횟수 (무한 루프 방지)"
    )

    # Generation Parameters (Optional Overrides)
    temperature: Optional[float] = Field(
        default=None,
        description="모델 temperature (창의성 조절)"
    )

    max_tokens: Optional[int] = Field(
        default=None,
        description="최대 생성 토큰 수"
    )

    # Memory Configuration
    max_context_messages: int = Field(
        default=20,
        description="컨텍스트로 유지할 최대 메시지 수"
    )

    enable_memory: bool = Field(
        default=True,
        description="대화 히스토리 메모리 활성화 여부"
    )

    # Actions
    actions: List[AgentActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def inflate_single_action(cls, values: Dict[str, Any]):
        """단일 액션 자동 확장"""
        if "actions" not in values:
            action_keys = set(AgentActionConfig.model_fields.keys()) - set(CommonComponentConfig.model_fields.keys())
            if any(k in values for k in action_keys):
                values["actions"] = [{ k: values.pop(k) for k in action_keys if k in values }]
        return values

    @model_validator(mode="after")
    def validate_model_component(self):
        """모델 컴포넌트 참조 검증 (실제 검증은 런타임에)"""
        # TODO: 런타임에 model ID가 실제 model 타입 컴포넌트를 가리키는지 검증
        return self
```

### 2. AgentActionConfig

**Location**: `src/mindor/dsl/schema/action/impl/agent.py`

```python
from typing import Optional, Dict, Any, List
from pydantic import Field
from .common import CommonActionConfig

class AgentActionConfig(CommonActionConfig):
    """Agent 액션 설정"""

    # Task Definition
    task: str = Field(
        ...,
        description="Agent가 수행할 작업 설명"
    )

    input: Optional[Dict[str, Any]] = Field(
        default=None,
        description="작업 수행에 필요한 입력 데이터"
    )

    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="추가 컨텍스트 정보"
    )

    # Override Component Defaults
    system_prompt: Optional[str] = Field(
        default=None,
        description="이 액션에 특화된 시스템 프롬프트 (컴포넌트 기본값 오버라이드)"
    )

    tools: Optional[List[str]] = Field(
        default=None,
        description="이 액션에서 사용할 도구 목록 (컴포넌트 기본값 오버라이드)"
    )

    max_iterations: Optional[int] = Field(
        default=None,
        description="최대 반복 횟수 오버라이드"
    )

    temperature: Optional[float] = Field(
        default=None,
        description="Temperature 오버라이드"
    )

    max_tokens: Optional[int] = Field(
        default=None,
        description="Max tokens 오버라이드"
    )

    # Streaming
    streaming: bool = Field(
        default=False,
        description="스트리밍 출력 여부"
    )
```

## Service Implementation

### 1. AgentExecutor

**Location**: `src/mindor/core/component/services/agent/executor.py`

ReAct (Reasoning + Acting) 패턴 기반 Agent 실행 엔진:

```python
from typing import List, Dict, Any, Optional, AsyncIterator
from pydantic import BaseModel
from mindor.dsl.schema.component import AgentComponentConfig
from mindor.dsl.schema.action import AgentActionConfig
from mindor.core.component.base import ComponentService
from mindor.core.logger import logging

class AgentMessage(BaseModel):
    """Agent 메시지"""
    role: str  # "system", "user", "assistant", "tool"
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None

class AgentExecutor:
    """
    ReAct 패턴 기반 Agent 실행 엔진

    플로우:
    1. User task 수신
    2. Model에게 task + tools 전달
    3. Model이 tool 사용 결정
    4. Tool 실행 및 결과 수집
    5. 결과를 Model에게 전달
    6. 반복 (max_iterations까지)
    7. 최종 답변 반환
    """

    def __init__(
        self,
        component_config: AgentComponentConfig,
        model_service: ComponentService,
        tool_registry: 'ToolRegistry'
    ):
        self.config = component_config
        self.model_service = model_service
        self.tool_registry = tool_registry

        # Conversation history
        self.messages: List[AgentMessage] = []

        # System prompt 초기화
        if self.config.system_prompt:
            self.messages.append(AgentMessage(
                role="system",
                content=self.config.system_prompt
            ))

    async def execute(
        self,
        action_config: AgentActionConfig,
        input_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Agent 액션 실행

        Args:
            action_config: Agent 액션 설정
            input_data: 입력 데이터

        Returns:
            Agent 실행 결과
        """
        # 설정 병합 (action이 component 기본값을 오버라이드)
        effective_config = self._merge_config(action_config)

        # 도구 준비
        tools = self.tool_registry.get_tools(effective_config.tools)

        # User message 추가
        user_message = self._build_user_message(
            action_config.task,
            input_data,
            action_config.context
        )
        self.messages.append(user_message)

        # ReAct 루프
        iteration = 0
        while iteration < effective_config.max_iterations:
            logging.debug(f"Agent iteration {iteration + 1}/{effective_config.max_iterations}")

            # Model 호출 (tool calling 지원)
            response = await self._call_model(
                messages=self.messages,
                tools=tools,
                temperature=effective_config.temperature,
                max_tokens=effective_config.max_tokens
            )

            # Assistant message 추가
            self.messages.append(response)

            # Tool calls 확인
            if response.tool_calls:
                # Tool 실행
                tool_results = await self._execute_tools(response.tool_calls)

                # Tool 결과를 메시지에 추가
                for result in tool_results:
                    self.messages.append(result)

                iteration += 1
                continue

            # Tool call 없음 = 최종 답변
            if self.config.enable_memory:
                # 메모리 크기 제한
                self._trim_messages()
            else:
                # 메모리 비활성화 시 히스토리 초기화
                self._reset_conversation()

            return {
                "response": response.content,
                "iterations": iteration + 1,
                "messages": [m.model_dump() for m in self.messages]
            }

        # Max iterations 도달
        logging.warning(f"Agent reached max iterations ({effective_config.max_iterations})")
        return {
            "response": "I couldn't complete the task within the iteration limit.",
            "iterations": iteration,
            "error": "max_iterations_reached"
        }

    async def execute_stream(
        self,
        action_config: AgentActionConfig,
        input_data: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """스트리밍 실행 (실시간 출력)"""
        # TODO: 스트리밍 구현
        pass

    def _merge_config(self, action_config: AgentActionConfig) -> AgentActionConfig:
        """액션 설정과 컴포넌트 기본값 병합"""
        return AgentActionConfig(
            task=action_config.task,
            input=action_config.input,
            context=action_config.context,
            system_prompt=action_config.system_prompt or self.config.system_prompt,
            tools=action_config.tools or self.config.tools,
            max_iterations=action_config.max_iterations or self.config.max_iterations,
            temperature=action_config.temperature or self.config.temperature,
            max_tokens=action_config.max_tokens or self.config.max_tokens,
            stream=action_config.stream
        )

    def _build_user_message(
        self,
        task: str,
        input_data: Optional[Dict[str, Any]],
        context: Optional[Dict[str, Any]]
    ) -> AgentMessage:
        """User 메시지 생성"""
        content_parts = [f"Task: {task}"]

        if input_data:
            content_parts.append(f"Input: {input_data}")

        if context:
            content_parts.append(f"Context: {context}")

        return AgentMessage(
            role="user",
            content="\n\n".join(content_parts)
        )

    async def _call_model(
        self,
        messages: List[AgentMessage],
        tools: List[Dict[str, Any]],
        temperature: Optional[float],
        max_tokens: Optional[int]
    ) -> AgentMessage:
        """Model 호출 (tool calling 지원)"""
        # model 컴포넌트 호출
        # TODO: model_service를 통해 chat-completion 호출
        # tools를 함수 스펙으로 변환하여 전달

        # 임시 구현
        response = await self.model_service.execute(
            action_id="__default__",
            input_data={
                "messages": [m.model_dump() for m in messages],
                "tools": tools,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
        )

        # 응답 파싱
        return AgentMessage(
            role="assistant",
            content=response.get("content", ""),
            tool_calls=response.get("tool_calls")
        )

    async def _execute_tools(
        self,
        tool_calls: List[Dict[str, Any]]
    ) -> List[AgentMessage]:
        """Tool 실행"""
        results = []

        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["arguments"]
            call_id = tool_call["call_id"]

            try:
                # Tool 실행
                result = await self.tool_registry.execute_tool(
                    tool_name=tool_name,
                    arguments=tool_args
                )

                results.append(AgentMessage(
                    role="tool",
                    content=str(result),
                    tool_call_id=call_id
                ))
            except Exception as e:
                logging.error(f"Tool execution failed: {e}")
                results.append(AgentMessage(
                    role="tool",
                    content=f"Error: {str(e)}",
                    tool_call_id=call_id
                ))

        return results

    def _trim_messages(self):
        """메시지 히스토리 크기 제한"""
        max_messages = self.config.max_context_messages

        if len(self.messages) > max_messages:
            # System message는 유지
            system_messages = [m for m in self.messages if m.role == "system"]
            other_messages = [m for m in self.messages if m.role != "system"]

            # 최근 메시지만 유지
            trimmed = other_messages[-max_messages:]
            self.messages = system_messages + trimmed

    def _reset_conversation(self):
        """대화 히스토리 초기화 (시스템 프롬프트만 유지)"""
        self.messages = [m for m in self.messages if m.role == "system"]
```

### 2. ToolRegistry

**Location**: `src/mindor/core/component/services/agent/tool_registry.py`

Agent가 사용할 도구들을 관리하는 레지스트리:

```python
from typing import Dict, List, Any, Optional
from mindor.core.component.base import ComponentService
from mindor.core.logger import logging

class ToolRegistry:
    """
    Agent가 사용할 도구 레지스트리

    기존 컴포넌트들을 Agent의 도구로 재사용
    """

    def __init__(self, components: Dict[str, ComponentService]):
        """
        Args:
            components: 사용 가능한 컴포넌트들 (id -> service)
        """
        self.components = components

    def get_tools(self, tool_ids: List[str]) -> List[Dict[str, Any]]:
        """
        도구 ID 목록을 OpenAI 함수 스펙으로 변환

        Args:
            tool_ids: 도구 컴포넌트 ID 목록

        Returns:
            OpenAI 함수 스펙 목록
        """
        tools = []

        for tool_id in tool_ids:
            if tool_id not in self.components:
                logging.warning(f"Tool component '{tool_id}' not found")
                continue

            component_service = self.components[tool_id]

            # 컴포넌트를 함수 스펙으로 변환
            tool_spec = self._component_to_function_spec(
                tool_id,
                component_service
            )
            tools.append(tool_spec)

        return tools

    def _component_to_function_spec(
        self,
        component_id: str,
        component_service: ComponentService
    ) -> Dict[str, Any]:
        """
        컴포넌트를 OpenAI 함수 스펙으로 변환

        컴포넌트의 액션 스키마를 함수 파라미터로 변환
        """
        # TODO: 컴포넌트의 액션 스키마에서 자동으로 함수 스펙 생성
        # 현재는 간단한 구현

        return {
            "type": "function",
            "function": {
                "name": component_id,
                "description": f"Execute {component_id} component",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "input": {
                            "type": "object",
                            "description": "Input data for the component"
                        }
                    },
                    "required": []
                }
            }
        }

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """
        도구 실행

        Args:
            tool_name: 도구(컴포넌트) ID
            arguments: 도구 실행 인자

        Returns:
            도구 실행 결과
        """
        if tool_name not in self.components:
            raise ValueError(f"Tool '{tool_name}' not found")

        component_service = self.components[tool_name]

        # 컴포넌트 실행
        result = await component_service.execute(
            action_id="__default__",
            input_data=arguments.get("input", {})
        )

        return result
```

## YAML Configuration Examples

### Example 1: Simple Agent

```yaml
controller:
  type: http-server
  port: 8080

# Model 컴포넌트 정의
components:
  - id: gpt-4o
    type: http-client
    base_url: https://api.openai.com/v1
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
    actions:
      - id: chat
        path: /chat/completions
        method: POST
        body:
          model: gpt-4o
          messages: ${input.messages}
          tools: ${input.tools}
          temperature: ${input.temperature | 0.7}
        output: ${response}

  # Web search 도구
  - id: web-search
    type: http-client
    base_url: https://api.tavily.com
    headers:
      Authorization: Bearer ${env.TAVILY_API_KEY}
    actions:
      - id: search
        path: /search
        method: POST
        body:
          query: ${input.query}
        output: ${response.results}

  # Agent 정의
  - id: research-agent
    type: agent
    model: gpt-4o  # 위에서 정의한 model 컴포넌트 ID
    system_prompt: |
      You are a research assistant. Use the web-search tool to find information.
    tools:
      - web-search
    max_iterations: 5
    task: ${input.query}

# Workflow
workflow:
  component: research-agent
  input: ${input}
  output: ${output.response}
```

### Example 2: Multi-Tool Agent

```yaml
components:
  # Model
  - id: claude-sonnet
    type: http-client
    base_url: https://api.anthropic.com/v1
    headers:
      X-API-Key: ${env.ANTHROPIC_API_KEY}
      Anthropic-Version: "2023-06-01"
    actions:
      - id: chat
        path: /messages
        method: POST
        body:
          model: claude-sonnet-4-20250514
          messages: ${input.messages}
          tools: ${input.tools}
          max_tokens: ${input.max_tokens | 4096}
        output: ${response}

  # Tools
  - id: database-query
    type: http-client
    base_url: ${env.DB_API_URL}
    actions:
      - id: query
        path: /query
        method: POST
        body:
          sql: ${input.sql}
        output: ${response.rows}

  - id: email-sender
    type: http-client
    base_url: ${env.EMAIL_API_URL}
    actions:
      - id: send
        path: /send
        method: POST
        body:
          to: ${input.to}
          subject: ${input.subject}
          body: ${input.body}
        output: ${response}

  # Agent
  - id: support-agent
    type: agent
    model: claude-sonnet
    system_prompt: |
      You are a customer support agent.
      You can query the database to look up order information,
      and send emails to customers.
    tools:
      - database-query
      - email-sender
    max_iterations: 10
    temperature: 0.7
    actions:
      - id: handle-ticket
        task: ${input.customer_question}
        context:
          customer_id: ${input.customer_id}
          ticket_id: ${input.ticket_id}

workflows:
  - id: support-workflow
    component: support-agent
    action: handle-ticket
    input: ${input}
    output: ${output.response}
```

### Example 3: Local Model Agent

```yaml
components:
  # Local model
  - id: local-llm
    type: model
    task: chat-completion
    model: Qwen/Qwen2.5-7B-Instruct
    runtime:
      type: docker
      image: vllm/vllm-openai:latest
      gpus: all
    messages: ${input.messages}
    tools: ${input.tools}

  # Tools (Shell commands)
  - id: file-reader
    type: shell
    command: ["cat", "${input.file_path}"]
    output: ${result.stdout}

  - id: file-writer
    type: shell
    command: ["sh", "-c", "echo '${input.content}' > ${input.file_path}"]
    output: ${result.stdout}

  # Agent
  - id: file-agent
    type: agent
    model: local-llm
    system_prompt: |
      You are a file management agent.
      You can read and write files using available tools.
    tools:
      - file-reader
      - file-writer
    max_iterations: 5

workflow:
  component: file-agent
  task: ${input.task}
  input: ${input}
  output: ${output.response}
```

## Integration with Existing Components

### Model Component Integration

Agent는 `model` 필드에 기존 model 컴포넌트 ID를 참조:

- **http-client**: OpenAI, Anthropic 등 API 호출
- **model**: 로컬 HuggingFace 모델 (chat-completion task)

**중요**: `model` 필드는 문자열이 아닌 **컴포넌트 ID**입니다.

### Tool Component Integration

Agent는 모든 타입의 컴포넌트를 도구로 사용 가능:

- **http-client**: API 호출 도구
- **shell**: 시스템 명령 실행 도구
- **workflow**: 복잡한 서브 워크플로우를 도구로 사용
- **vector-store**: 벡터 검색 도구
- **web-scraper**: 웹 스크래핑 도구

## API Specification

Agent 컴포넌트는 HTTP 컨트롤러를 통해 REST API로 노출됩니다:

### POST /api/workflows/{workflow_id}

```bash
curl -X POST http://localhost:8080/api/workflows/research \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the latest AI trends in 2025?"
  }'
```

**Response**:
```json
{
  "response": "Based on web search results, the latest AI trends in 2025 include...",
  "iterations": 3,
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "...", "tool_calls": [...]},
    {"role": "tool", "content": "...", "tool_call_id": "..."}
  ]
}
```

## ComponentType Update

**Location**: `src/mindor/dsl/schema/component/impl/types.py`

```python
class ComponentType(str, Enum):
    # ... 기존 타입들 ...
    AGENT = "agent"
```

## Registry Update

### Component Registry

**Location**: `src/mindor/dsl/schema/component/impl/__init__.py`

```python
from .agent import *
```

### Action Registry

**Location**: `src/mindor/dsl/schema/action/impl/__init__.py`

```python
from .agent import *
```

## Implementation Phases

### Phase 1: Core Schema (MVP)
- [ ] `AgentComponentConfig` 구현
- [ ] `AgentActionConfig` 구현
- [ ] `ComponentType.AGENT` 추가
- [ ] Registry 업데이트

### Phase 2: Executor Engine
- [ ] `AgentExecutor` 기본 구현
- [ ] ReAct 루프 구현
- [ ] Model 호출 통합
- [ ] Tool 호출 통합

### Phase 3: Tool Integration
- [ ] `ToolRegistry` 구현
- [ ] 컴포넌트 → 함수 스펙 변환
- [ ] Tool 실행 에러 핸들링

### Phase 4: Memory Management
- [ ] 대화 히스토리 관리
- [ ] 컨텍스트 크기 제한
- [ ] 메모리 초기화 옵션

### Phase 5: Advanced Features
- [ ] 스트리밍 출력
- [ ] 비동기 도구 실행
- [ ] 병렬 도구 호출
- [ ] Agent 체이닝

### Phase 6: Production Ready
- [ ] 에러 핸들링 강화
- [ ] 로깅 및 디버깅
- [ ] 성능 최적화
- [ ] 단위 테스트
- [ ] 통합 테스트

## Testing Strategy

### Unit Tests

```python
# tests/dsl/schema/component/test_agent.py

def test_agent_component_config():
    """Agent 컴포넌트 설정 파싱 테스트"""
    config = AgentComponentConfig(
        id="test-agent",
        type="agent",
        model="gpt-4o",
        system_prompt="You are helpful",
        tools=["tool1", "tool2"],
        max_iterations=5
    )

    assert config.type == ComponentType.AGENT
    assert config.model == "gpt-4o"
    assert len(config.tools) == 2

def test_agent_action_config():
    """Agent 액션 설정 파싱 테스트"""
    action = AgentActionConfig(
        id="test-action",
        task="Do something",
        input={"key": "value"},
        max_iterations=3
    )

    assert action.task == "Do something"
    assert action.max_iterations == 3
```

### Integration Tests

```python
# tests/integration/test_agent_executor.py

@pytest.mark.asyncio
async def test_agent_execution():
    """Agent 실행 테스트"""
    # Mock model service
    # Mock tool registry
    # Execute agent
    # Verify result
    pass

@pytest.mark.asyncio
async def test_agent_tool_calling():
    """Agent tool calling 테스트"""
    # Agent가 도구를 올바르게 호출하는지 테스트
    pass
```

## Future Enhancements

1. **Multi-Agent Collaboration**
   - 여러 Agent 간 협업
   - Agent 간 메시지 전달
   - 역할 분담 및 조율

2. **Advanced Memory**
   - Vector store 기반 장기 메모리
   - 중요한 정보 자동 저장
   - 컨텍스트 검색

3. **Planning & Reflection**
   - 작업 계획 자동 생성
   - 실행 결과 반성
   - 전략 개선

4. **Human-in-the-Loop**
   - 중요한 결정에 사람 개입
   - 승인 워크플로우
   - 피드백 수집

5. **Monitoring & Observability**
   - Agent 행동 추적
   - 도구 사용 통계
   - 비용 모니터링

## Security Considerations

1. **Tool Access Control**
   - 민감한 도구에 대한 접근 제한
   - 권한 기반 도구 필터링

2. **Input Validation**
   - Tool 인자 검증
   - SQL Injection 방지
   - Command Injection 방지

3. **Rate Limiting**
   - API 호출 제한
   - 비용 관리

4. **Audit Logging**
   - 모든 Agent 액션 로깅
   - Tool 호출 기록
   - 결과 추적

## References

- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
- [Anthropic Tool Use](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
- [LangChain Agents](https://python.langchain.com/docs/modules/agents/)

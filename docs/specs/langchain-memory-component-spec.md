# LangChain Memory Component Specification

## Overview

LangChain/LangGraph의 메모리 기능을 model-compose 프레임워크에 통합하여, 선언적 YAML 구성을 통해 대화 기록 관리, 상태 저장, 컨텍스트 유지 등의 메모리 기능을 사용할 수 있도록 하는 컴포넌트 스펙입니다.

## Design Goals

1. **선언적 메모리 구성**: YAML을 통해 다양한 메모리 타입 정의
2. **기존 패턴 준수**: model-compose의 컴포넌트/액션 아키텍처 활용
3. **다양한 백엔드 지원**: 인메모리, Redis, PostgreSQL, MongoDB 등
4. **유연한 메모리 전략**: 버퍼, 윈도우, 요약, 벡터 기반 메모리
5. **워크플로우 통합**: 다른 컴포넌트와 자연스러운 데이터 흐름

## Architecture

### Component Types

LangChain 메모리 통합을 위해 다음 컴포넌트들을 구현합니다:

#### 1. `langchain-memory` - 메모리 저장소

대화 기록과 상태를 관리하는 기본 메모리 컴포넌트입니다.

**Component Type**: `ComponentType.LANGCHAIN_MEMORY`

**Features**:
- 다양한 메모리 타입 지원 (버퍼, 윈도우, 요약 등)
- 여러 백엔드 스토리지 지원
- 세션별 메모리 관리
- 메모리 검색 및 조회
- 자동 메모리 정리

#### 2. `langchain-memory-vector` - 벡터 기반 메모리

임베딩을 사용한 시맨틱 메모리 검색 컴포넌트입니다.

**Component Type**: `ComponentType.LANGCHAIN_MEMORY_VECTOR`

**Features**:
- 벡터 스토어 기반 메모리
- 시맨틱 유사도 검색
- 관련성 높은 대화 기록 조회
- 임베딩 모델 선택

#### 3. `langchain-checkpoint` - LangGraph 체크포인트

LangGraph의 상태 체크포인트 기능을 제공하는 컴포넌트입니다.

**Component Type**: `ComponentType.LANGCHAIN_CHECKPOINT`

**Features**:
- 그래프 상태 저장/로드
- 타임 트래블 (상태 이력 조회)
- 브랜치 및 롤백
- 다양한 체크포인트 백엔드

## Component Schema

### 1. LangChainMemoryComponentConfig

```python
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from mindor.dsl.schema.component.impl.common import CommonComponentConfig

class LangChainMemoryType(str, Enum):
    """메모리 타입"""
    BUFFER = "buffer"                           # 전체 대화 기록
    WINDOW = "window"                           # 최근 N개 메시지
    SUMMARY = "summary"                         # 요약 기반
    SUMMARY_BUFFER = "summary_buffer"           # 요약 + 최근 메시지
    TOKEN_BUFFER = "token_buffer"               # 토큰 제한 기반
    CONVERSATION_KG = "conversation_kg"         # 지식 그래프
    ENTITY = "entity"                           # 엔티티 메모리
    VECTOR_STORE = "vector_store"               # 벡터 기반 (별도 컴포넌트)


class LangChainMemoryBackend(str, Enum):
    """메모리 백엔드 타입"""
    IN_MEMORY = "in_memory"                     # 메모리 (개발용)
    REDIS = "redis"                             # Redis
    POSTGRES = "postgres"                       # PostgreSQL
    MONGODB = "mongodb"                         # MongoDB
    SQLITE = "sqlite"                           # SQLite
    DYNAMODB = "dynamodb"                       # AWS DynamoDB
    FIRESTORE = "firestore"                     # Google Firestore


class LangChainMemoryComponentConfig(CommonComponentConfig):
    """LangChain 메모리 컴포넌트 구성"""
    type: Literal[ComponentType.LANGCHAIN_MEMORY]

    # 메모리 타입
    memory_type: LangChainMemoryType = Field(
        default=LangChainMemoryType.BUFFER,
        description="메모리 타입"
    )

    # 백엔드 설정
    backend: LangChainMemoryBackend = Field(
        default=LangChainMemoryBackend.IN_MEMORY,
        description="메모리 백엔드"
    )
    backend_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="백엔드별 설정"
    )

    # 메모리 타입별 설정
    memory_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="메모리 타입별 설정"
    )

    # 윈도우 메모리 설정
    window_size: int | None = Field(
        None,
        description="윈도우 메모리: 유지할 메시지 수 (k)"
    )

    # 토큰 버퍼 설정
    max_tokens: int | None = Field(
        None,
        description="토큰 버퍼: 최대 토큰 수"
    )
    llm_for_counting: str | None = Field(
        None,
        description="토큰 카운팅용 LLM 모델"
    )

    # 요약 메모리 설정
    summarization_llm: str | None = Field(
        None,
        description="요약용 LLM 모델 (model-compose component id 또는 모델명)"
    )
    summary_prompt: str | None = Field(
        None,
        description="요약 프롬프트 템플릿"
    )

    # 엔티티 메모리 설정
    entity_extraction_llm: str | None = Field(
        None,
        description="엔티티 추출용 LLM"
    )
    entity_store: str | None = Field(
        None,
        description="엔티티 저장소"
    )

    # 메시지 키 설정
    input_key: str = Field(
        default="input",
        description="입력 메시지 키"
    )
    output_key: str = Field(
        default="output",
        description="출력 메시지 키"
    )
    memory_key: str = Field(
        default="history",
        description="메모리 변수 키"
    )

    # 세션 관리
    return_messages: bool = Field(
        default=True,
        description="메시지 객체 반환 여부"
    )
    session_ttl: int | None = Field(
        None,
        description="세션 TTL (초)"
    )

    # 액션 정의
    actions: List["LangChainMemoryActionConfig"]


class LangChainMemoryActionConfig(CommonActionConfig):
    """LangChain 메모리 액션 구성"""

    # 액션 타입
    action_type: Literal[
        "save",                 # 메모리 저장
        "load",                 # 메모리 로드
        "search",               # 메모리 검색
        "clear",                # 메모리 삭제
        "get_sessions",         # 세션 목록 조회
        "add_message",          # 메시지 추가
        "get_messages"          # 메시지 조회
    ] = Field(..., description="액션 타입")

    # 세션 ID
    session_id: str = Field(
        default="${input.session_id}",
        description="세션 ID (변수 보간 지원)"
    )

    # save / add_message용
    input_message: str | None = Field(
        None,
        description="사용자 입력 메시지"
    )
    output_message: str | None = Field(
        None,
        description="AI 출력 메시지"
    )

    # save용 (dict 형태)
    inputs: Dict[str, Any] | None = Field(
        None,
        description="입력 데이터 (여러 키 지원)"
    )
    outputs: Dict[str, Any] | None = Field(
        None,
        description="출력 데이터 (여러 키 지원)"
    )

    # search용
    query: str | None = Field(
        None,
        description="검색 쿼리"
    )
    k: int = Field(
        default=4,
        description="반환할 메시지 수"
    )

    # get_messages용
    limit: int | None = Field(
        None,
        description="조회할 메시지 수"
    )
    offset: int = Field(
        default=0,
        description="메시지 오프셋"
    )
```

### 2. LangChainMemoryVectorComponentConfig

```python
class LangChainMemoryVectorComponentConfig(CommonComponentConfig):
    """LangChain 벡터 메모리 컴포넌트 구성"""
    type: Literal[ComponentType.LANGCHAIN_MEMORY_VECTOR]

    # 벡터 스토어 설정
    vector_store_type: Literal[
        "faiss",
        "chroma",
        "pinecone",
        "qdrant",
        "weaviate",
        "milvus",
        "pgvector"
    ] = Field(..., description="벡터 스토어 타입")

    vector_store_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="벡터 스토어 설정"
    )

    # 임베딩 설정
    embedding_model: str = Field(
        default="openai:text-embedding-3-small",
        description="임베딩 모델 (provider:model 형식)"
    )
    embedding_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="임베딩 모델 설정"
    )

    # 메모리 검색 설정
    search_type: Literal["similarity", "mmr", "similarity_score_threshold"] = Field(
        default="similarity",
        description="검색 타입"
    )
    search_kwargs: Dict[str, Any] = Field(
        default_factory=dict,
        description="검색 파라미터"
    )

    # 메모리 키
    memory_key: str = Field(
        default="chat_history",
        description="메모리 변수 키"
    )
    input_key: str = Field(default="input")
    output_key: str = Field(default="output")

    # 액션 정의
    actions: List["LangChainMemoryVectorActionConfig"]


class LangChainMemoryVectorActionConfig(CommonActionConfig):
    """벡터 메모리 액션 구성"""

    action_type: Literal[
        "save",                 # 메모리 저장
        "search",               # 유사도 검색
        "clear",                # 메모리 삭제
        "add_messages"          # 메시지 추가
    ] = Field(..., description="액션 타입")

    session_id: str = Field(default="${input.session_id}")

    # save / add_messages용
    input_message: str | None = None
    output_message: str | None = None
    messages: List[Dict[str, str]] | None = Field(
        None,
        description="메시지 리스트 [{'role': 'user', 'content': '...'}]"
    )

    # search용
    query: str | None = None
    k: int = Field(default=4, description="검색할 메시지 수")
    score_threshold: float | None = Field(
        None,
        description="유사도 임계값 (0-1)"
    )
```

### 3. LangChainCheckpointComponentConfig

```python
class LangChainCheckpointBackend(str, Enum):
    """체크포인트 백엔드"""
    MEMORY = "memory"
    SQLITE = "sqlite"
    POSTGRES = "postgres"
    MONGODB = "mongodb"
    REDIS = "redis"


class LangChainCheckpointComponentConfig(CommonComponentConfig):
    """LangGraph 체크포인트 컴포넌트 구성"""
    type: Literal[ComponentType.LANGCHAIN_CHECKPOINT]

    # 백엔드 설정
    backend: LangChainCheckpointBackend = Field(
        default=LangChainCheckpointBackend.SQLITE,
        description="체크포인트 백엔드"
    )
    backend_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="백엔드 설정"
    )

    # 체크포인트 설정
    checkpoint_namespace: str = Field(
        default="default",
        description="체크포인트 네임스페이스"
    )

    # 자동 저장
    auto_checkpoint: bool = Field(
        default=True,
        description="상태 변경 시 자동 저장"
    )
    checkpoint_interval: int | None = Field(
        None,
        description="체크포인트 저장 간격 (초)"
    )

    # 이력 관리
    max_checkpoints: int | None = Field(
        None,
        description="유지할 최대 체크포인트 수"
    )
    checkpoint_ttl: int | None = Field(
        None,
        description="체크포인트 TTL (초)"
    )

    # 액션 정의
    actions: List["LangChainCheckpointActionConfig"]


class LangChainCheckpointActionConfig(CommonActionConfig):
    """체크포인트 액션 구성"""

    action_type: Literal[
        "save",                 # 체크포인트 저장
        "load",                 # 체크포인트 로드
        "list",                 # 체크포인트 목록
        "rollback",             # 특정 시점으로 롤백
        "delete",               # 체크포인트 삭제
        "get_state",            # 현재 상태 조회
        "update_state"          # 상태 업데이트
    ] = Field(..., description="액션 타입")

    # 쓰레드/세션 ID
    thread_id: str = Field(
        default="${input.thread_id}",
        description="LangGraph 쓰레드 ID"
    )

    # save / update_state용
    state: Dict[str, Any] | None = Field(
        None,
        description="저장할 상태"
    )

    # load / rollback용
    checkpoint_id: str | None = Field(
        None,
        description="체크포인트 ID"
    )
    timestamp: str | None = Field(
        None,
        description="타임스탬프 (ISO 8601)"
    )

    # list용
    limit: int = Field(default=10)
    offset: int = Field(default=0)
```

## Service Implementation

### 1. LangChainMemoryService

**Location**: `src/mindor/core/component/services/langchain/memory.py`

```python
from langchain.memory import (
    ConversationBufferMemory,
    ConversationBufferWindowMemory,
    ConversationSummaryMemory,
    ConversationSummaryBufferMemory,
    ConversationTokenBufferMemory,
    ConversationEntityMemory,
    ConversationKGMemory,
)
from langchain.memory.chat_message_histories import (
    ChatMessageHistory,
    RedisChatMessageHistory,
    PostgresChatMessageHistory,
    MongoDBChatMessageHistory,
)
from mindor.core.component.base import ComponentService
from mindor.core.component.registry import register_component

@register_component(ComponentType.LANGCHAIN_MEMORY)
class LangChainMemoryService(ComponentService):
    """LangChain 메모리 서비스"""

    def __init__(self, id: str, config: LangChainMemoryComponentConfig,
                 global_configs: Dict, daemon: Any):
        super().__init__(id, config, global_configs, daemon)
        self.memories: Dict[str, BaseChatMemory] = {}
        self.message_histories: Dict[str, BaseChatMessageHistory] = {}

    async def _start(self):
        """메모리 초기화"""
        # 백엔드 연결 설정
        await self._setup_backend()

    async def _run(self, action: LangChainMemoryActionConfig,
                   context: ComponentActionContext) -> Any:
        """액션 실행"""
        handler = LangChainMemoryActionHandler(
            action,
            self.config,
            self.memories,
            self.message_histories
        )
        return await handler.run(context)

    async def _stop(self):
        """리소스 정리"""
        self.memories.clear()
        self.message_histories.clear()

    async def _setup_backend(self):
        """백엔드 설정"""
        if self.config.backend == LangChainMemoryBackend.REDIS:
            # Redis 연결 설정
            pass
        elif self.config.backend == LangChainMemoryBackend.POSTGRES:
            # PostgreSQL 연결 설정
            pass
        # 기타 백엔드...

    def _get_or_create_memory(self, session_id: str) -> BaseChatMemory:
        """메모리 인스턴스 가져오기 또는 생성"""
        if session_id not in self.memories:
            # 메시지 히스토리 생성
            history = self._create_message_history(session_id)

            # 메모리 타입에 따라 생성
            if self.config.memory_type == LangChainMemoryType.BUFFER:
                memory = ConversationBufferMemory(
                    chat_memory=history,
                    memory_key=self.config.memory_key,
                    input_key=self.config.input_key,
                    output_key=self.config.output_key,
                    return_messages=self.config.return_messages
                )
            elif self.config.memory_type == LangChainMemoryType.WINDOW:
                memory = ConversationBufferWindowMemory(
                    k=self.config.window_size or 5,
                    chat_memory=history,
                    memory_key=self.config.memory_key,
                    return_messages=self.config.return_messages
                )
            elif self.config.memory_type == LangChainMemoryType.SUMMARY:
                # LLM 가져오기 (model-compose 컴포넌트 또는 직접 생성)
                llm = self._get_llm(self.config.summarization_llm)
                memory = ConversationSummaryMemory(
                    llm=llm,
                    chat_memory=history,
                    memory_key=self.config.memory_key,
                    return_messages=self.config.return_messages
                )
            elif self.config.memory_type == LangChainMemoryType.TOKEN_BUFFER:
                llm = self._get_llm(self.config.llm_for_counting)
                memory = ConversationTokenBufferMemory(
                    llm=llm,
                    max_token_limit=self.config.max_tokens or 2000,
                    chat_memory=history,
                    memory_key=self.config.memory_key,
                    return_messages=self.config.return_messages
                )
            # 기타 메모리 타입...

            self.memories[session_id] = memory

        return self.memories[session_id]

    def _create_message_history(self, session_id: str) -> BaseChatMessageHistory:
        """메시지 히스토리 생성"""
        if self.config.backend == LangChainMemoryBackend.IN_MEMORY:
            return ChatMessageHistory()

        elif self.config.backend == LangChainMemoryBackend.REDIS:
            return RedisChatMessageHistory(
                session_id=session_id,
                url=self.config.backend_config.get("url", "redis://localhost:6379"),
                key_prefix=self.config.backend_config.get("key_prefix", "message_store:"),
                ttl=self.config.session_ttl
            )

        elif self.config.backend == LangChainMemoryBackend.POSTGRES:
            return PostgresChatMessageHistory(
                session_id=session_id,
                connection_string=self.config.backend_config.get("connection_string"),
                table_name=self.config.backend_config.get("table_name", "message_store")
            )

        elif self.config.backend == LangChainMemoryBackend.MONGODB:
            return MongoDBChatMessageHistory(
                session_id=session_id,
                connection_string=self.config.backend_config.get("connection_string"),
                database_name=self.config.backend_config.get("database_name", "chat"),
                collection_name=self.config.backend_config.get("collection_name", "message_store")
            )

        # 기타 백엔드...

        return ChatMessageHistory()

    def _get_llm(self, llm_ref: str | None):
        """LLM 가져오기"""
        if not llm_ref:
            # 기본 LLM
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model="gpt-4o-mini")

        # model-compose 컴포넌트 ID인 경우
        if llm_ref in self.daemon.components:
            # 컴포넌트에서 LLM 추출
            # TODO: 컴포넌트 -> LangChain LLM 변환
            pass

        # 모델명인 경우 (provider:model 형식)
        if ":" in llm_ref:
            provider, model = llm_ref.split(":", 1)
            if provider == "openai":
                from langchain_openai import ChatOpenAI
                return ChatOpenAI(model=model)
            elif provider == "anthropic":
                from langchain_anthropic import ChatAnthropic
                return ChatAnthropic(model=model)
            # 기타 프로바이더...

        # 기본값
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=llm_ref)


class LangChainMemoryActionHandler:
    """메모리 액션 핸들러"""

    def __init__(self, action: LangChainMemoryActionConfig,
                 config: LangChainMemoryComponentConfig,
                 memories: Dict[str, BaseChatMemory],
                 message_histories: Dict[str, BaseChatMessageHistory]):
        self.action = action
        self.config = config
        self.memories = memories
        self.message_histories = message_histories

    async def run(self, context: ComponentActionContext) -> Dict[str, Any]:
        """액션 실행"""
        # 세션 ID 렌더링
        session_id = await context.render_variable(self.action.session_id)

        if self.action.action_type == "save":
            return await self._save(session_id, context)
        elif self.action.action_type == "load":
            return await self._load(session_id, context)
        elif self.action.action_type == "add_message":
            return await self._add_message(session_id, context)
        elif self.action.action_type == "get_messages":
            return await self._get_messages(session_id, context)
        elif self.action.action_type == "search":
            return await self._search(session_id, context)
        elif self.action.action_type == "clear":
            return await self._clear(session_id, context)
        elif self.action.action_type == "get_sessions":
            return await self._get_sessions(context)
        else:
            raise ValueError(f"Unknown action type: {self.action.action_type}")

    async def _save(self, session_id: str, context: ComponentActionContext):
        """메모리 저장"""
        memory = self._get_memory_service()._get_or_create_memory(session_id)

        # inputs/outputs 방식
        if self.action.inputs or self.action.outputs:
            inputs = await context.render_variable(self.action.inputs or {})
            outputs = await context.render_variable(self.action.outputs or {})
            memory.save_context(inputs, outputs)

        # input_message/output_message 방식
        else:
            input_msg = await context.render_variable(self.action.input_message)
            output_msg = await context.render_variable(self.action.output_message)
            memory.save_context(
                {self.config.input_key: input_msg},
                {self.config.output_key: output_msg}
            )

        return {
            "status": "saved",
            "session_id": session_id
        }

    async def _load(self, session_id: str, context: ComponentActionContext):
        """메모리 로드"""
        memory = self._get_memory_service()._get_or_create_memory(session_id)

        # 메모리 변수 로드
        memory_vars = memory.load_memory_variables({})

        return {
            "session_id": session_id,
            "memory": memory_vars
        }

    async def _add_message(self, session_id: str, context: ComponentActionContext):
        """메시지 추가"""
        memory = self._get_memory_service()._get_or_create_memory(session_id)
        history = memory.chat_memory

        input_msg = await context.render_variable(self.action.input_message)
        output_msg = await context.render_variable(self.action.output_message)

        if input_msg:
            from langchain.schema import HumanMessage
            history.add_message(HumanMessage(content=input_msg))

        if output_msg:
            from langchain.schema import AIMessage
            history.add_message(AIMessage(content=output_msg))

        return {
            "status": "added",
            "session_id": session_id
        }

    async def _get_messages(self, session_id: str, context: ComponentActionContext):
        """메시지 조회"""
        memory = self._get_memory_service()._get_or_create_memory(session_id)
        history = memory.chat_memory

        messages = history.messages

        # limit/offset 적용
        if self.action.limit:
            start = self.action.offset
            end = start + self.action.limit
            messages = messages[start:end]

        return {
            "session_id": session_id,
            "messages": [
                {
                    "type": msg.type,
                    "content": msg.content,
                    "additional_kwargs": msg.additional_kwargs
                }
                for msg in messages
            ],
            "total": len(history.messages)
        }

    async def _clear(self, session_id: str, context: ComponentActionContext):
        """메모리 삭제"""
        if session_id in self.memories:
            self.memories[session_id].clear()
            del self.memories[session_id]

        if session_id in self.message_histories:
            del self.message_histories[session_id]

        return {
            "status": "cleared",
            "session_id": session_id
        }

    async def _get_sessions(self, context: ComponentActionContext):
        """세션 목록 조회"""
        return {
            "sessions": list(self.memories.keys()),
            "count": len(self.memories)
        }

    async def _search(self, session_id: str, context: ComponentActionContext):
        """메모리 검색 (기본 메모리는 간단한 검색만)"""
        # 벡터 메모리 컴포넌트 사용 권장
        memory = self._get_memory_service()._get_or_create_memory(session_id)
        history = memory.chat_memory

        query = await context.render_variable(self.action.query)

        # 간단한 텍스트 매칭
        matched_messages = [
            msg for msg in history.messages
            if query.lower() in msg.content.lower()
        ][:self.action.k]

        return {
            "session_id": session_id,
            "query": query,
            "messages": [
                {
                    "type": msg.type,
                    "content": msg.content
                }
                for msg in matched_messages
            ]
        }

    def _get_memory_service(self) -> LangChainMemoryService:
        """메모리 서비스 참조 (헬퍼)"""
        # 실제 구현에서는 context를 통해 서비스 접근
        # 여기서는 임시로 self 사용
        return self
```

### 2. LangChainMemoryVectorService

**Location**: `src/mindor/core/component/services/langchain/memory_vector.py`

```python
from langchain.memory import VectorStoreRetrieverMemory
from langchain.vectorstores import (
    FAISS,
    Chroma,
    Pinecone,
    Qdrant,
    Weaviate,
)
from langchain.embeddings import OpenAIEmbeddings, HuggingFaceEmbeddings

@register_component(ComponentType.LANGCHAIN_MEMORY_VECTOR)
class LangChainMemoryVectorService(ComponentService):
    """LangChain 벡터 메모리 서비스"""

    def __init__(self, id: str, config: LangChainMemoryVectorComponentConfig,
                 global_configs: Dict, daemon: Any):
        super().__init__(id, config, global_configs, daemon)
        self.vector_stores: Dict[str, Any] = {}
        self.memories: Dict[str, VectorStoreRetrieverMemory] = {}
        self.embeddings = None

    async def _start(self):
        """벡터 메모리 초기화"""
        # 임베딩 모델 로드
        self.embeddings = self._create_embeddings()

    async def _run(self, action: LangChainMemoryVectorActionConfig,
                   context: ComponentActionContext) -> Any:
        handler = LangChainMemoryVectorActionHandler(
            action,
            self.config,
            self.vector_stores,
            self.memories,
            self.embeddings
        )
        return await handler.run(context)

    async def _stop(self):
        self.vector_stores.clear()
        self.memories.clear()

    def _create_embeddings(self):
        """임베딩 생성"""
        provider, model = self.config.embedding_model.split(":", 1)

        if provider == "openai":
            return OpenAIEmbeddings(
                model=model,
                **self.config.embedding_config
            )
        elif provider == "huggingface":
            return HuggingFaceEmbeddings(
                model_name=model,
                **self.config.embedding_config
            )
        # 기타 프로바이더...

    def _get_or_create_vector_store(self, session_id: str):
        """벡터 스토어 가져오기 또는 생성"""
        if session_id not in self.vector_stores:
            if self.config.vector_store_type == "faiss":
                # FAISS 인메모리 또는 파일 기반
                persist_path = self.config.vector_store_config.get("persist_directory")
                if persist_path:
                    import os
                    session_path = os.path.join(persist_path, session_id)
                    if os.path.exists(session_path):
                        vector_store = FAISS.load_local(session_path, self.embeddings)
                    else:
                        vector_store = FAISS.from_texts(
                            [""], self.embeddings  # 빈 벡터 스토어
                        )
                else:
                    vector_store = FAISS.from_texts([""], self.embeddings)

            elif self.config.vector_store_type == "chroma":
                vector_store = Chroma(
                    collection_name=f"session_{session_id}",
                    embedding_function=self.embeddings,
                    **self.config.vector_store_config
                )

            # 기타 벡터 스토어...

            self.vector_stores[session_id] = vector_store

        return self.vector_stores[session_id]

    def _get_or_create_memory(self, session_id: str):
        """벡터 메모리 생성"""
        if session_id not in self.memories:
            vector_store = self._get_or_create_vector_store(session_id)
            retriever = vector_store.as_retriever(
                search_type=self.config.search_type,
                search_kwargs={
                    "k": self.config.search_kwargs.get("k", 4),
                    **self.config.search_kwargs
                }
            )

            memory = VectorStoreRetrieverMemory(
                retriever=retriever,
                memory_key=self.config.memory_key,
                input_key=self.config.input_key,
                output_key=self.config.output_key
            )

            self.memories[session_id] = memory

        return self.memories[session_id]


class LangChainMemoryVectorActionHandler:
    """벡터 메모리 액션 핸들러"""
    # save, search, add_messages, clear 구현
    # (LangChainMemoryActionHandler와 유사하지만 벡터 검색 활용)
```

### 3. LangChainCheckpointService

**Location**: `src/mindor/core/component/services/langchain/checkpoint.py`

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.postgres import PostgresSaver

@register_component(ComponentType.LANGCHAIN_CHECKPOINT)
class LangChainCheckpointService(ComponentService):
    """LangGraph 체크포인트 서비스"""

    def __init__(self, id: str, config: LangChainCheckpointComponentConfig,
                 global_configs: Dict, daemon: Any):
        super().__init__(id, config, global_configs, daemon)
        self.checkpointer = None

    async def _start(self):
        """체크포인터 초기화"""
        if self.config.backend == LangChainCheckpointBackend.MEMORY:
            self.checkpointer = MemorySaver()

        elif self.config.backend == LangChainCheckpointBackend.SQLITE:
            db_path = self.config.backend_config.get("db_path", "checkpoints.db")
            self.checkpointer = SqliteSaver.from_conn_string(db_path)

        elif self.config.backend == LangChainCheckpointBackend.POSTGRES:
            conn_string = self.config.backend_config.get("connection_string")
            self.checkpointer = PostgresSaver.from_conn_string(conn_string)

        # 기타 백엔드...

    async def _run(self, action: LangChainCheckpointActionConfig,
                   context: ComponentActionContext) -> Any:
        handler = LangChainCheckpointActionHandler(
            action,
            self.config,
            self.checkpointer
        )
        return await handler.run(context)

    async def _stop(self):
        if hasattr(self.checkpointer, "close"):
            self.checkpointer.close()


class LangChainCheckpointActionHandler:
    """체크포인트 액션 핸들러"""

    def __init__(self, action: LangChainCheckpointActionConfig,
                 config: LangChainCheckpointComponentConfig,
                 checkpointer):
        self.action = action
        self.config = config
        self.checkpointer = checkpointer

    async def run(self, context: ComponentActionContext) -> Dict[str, Any]:
        thread_id = await context.render_variable(self.action.thread_id)

        if self.action.action_type == "save":
            return await self._save(thread_id, context)
        elif self.action.action_type == "load":
            return await self._load(thread_id, context)
        elif self.action.action_type == "list":
            return await self._list(thread_id, context)
        elif self.action.action_type == "rollback":
            return await self._rollback(thread_id, context)
        elif self.action.action_type == "get_state":
            return await self._get_state(thread_id, context)
        elif self.action.action_type == "update_state":
            return await self._update_state(thread_id, context)
        elif self.action.action_type == "delete":
            return await self._delete(thread_id, context)

    async def _save(self, thread_id: str, context: ComponentActionContext):
        """체크포인트 저장"""
        state = await context.render_variable(self.action.state)

        # LangGraph 체크포인트 생성
        config = {"configurable": {"thread_id": thread_id}}
        checkpoint = self.checkpointer.put(config, state)

        return {
            "status": "saved",
            "thread_id": thread_id,
            "checkpoint_id": checkpoint["checkpoint_id"],
            "timestamp": checkpoint["timestamp"]
        }

    async def _load(self, thread_id: str, context: ComponentActionContext):
        """체크포인트 로드"""
        config = {"configurable": {"thread_id": thread_id}}

        if self.action.checkpoint_id:
            config["configurable"]["checkpoint_id"] = self.action.checkpoint_id

        checkpoint = self.checkpointer.get(config)

        return {
            "thread_id": thread_id,
            "checkpoint": checkpoint
        }

    async def _list(self, thread_id: str, context: ComponentActionContext):
        """체크포인트 목록"""
        config = {"configurable": {"thread_id": thread_id}}
        checkpoints = list(self.checkpointer.list(
            config,
            limit=self.action.limit,
            offset=self.action.offset
        ))

        return {
            "thread_id": thread_id,
            "checkpoints": checkpoints,
            "count": len(checkpoints)
        }

    # 기타 메서드...
```

## YAML Configuration Examples

### Example 1: 기본 대화 메모리 (Redis 백엔드)

```yaml
controller:
  type: http-server
  port: 8080

components:
  # 대화 메모리 컴포넌트
  - id: chat-memory
    type: langchain-memory
    memory_type: buffer
    backend: redis
    backend_config:
      url: ${env.REDIS_URL}
      key_prefix: "chat:"
    session_ttl: 3600  # 1시간

    actions:
      - id: save
        action_type: save
        session_id: ${input.user_id}
        input_message: ${input.message}
        output_message: ${input.response}

      - id: load
        action_type: load
        session_id: ${input.user_id}

      - id: get_messages
        action_type: get_messages
        session_id: ${input.user_id}
        limit: 50

  # ChatGPT 모델
  - id: chatgpt
    type: http-client
    base_url: https://api.openai.com/v1
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}

    actions:
      - id: chat
        path: /chat/completions
        method: POST
        body:
          model: gpt-4o-mini
          messages: ${input.messages}

workflows:
  - id: chat-with-memory
    jobs:
      # 1. 메모리 로드
      - id: load-history
        component: chat-memory
        action: load
        input:
          user_id: ${input.user_id}

      # 2. 메시지 구성
      - id: prepare-messages
        component: message-builder
        type: shell
        command: ["python", "-c"]
        args:
          - |
            import json
            import sys

            history = ${jobs.load-history.output.memory.history}
            new_message = {"role": "user", "content": "${input.message}"}

            # 메모리에서 메시지 변환
            messages = []
            for msg in history:
                messages.append({
                    "role": msg["type"],
                    "content": msg["content"]
                })
            messages.append(new_message)

            print(json.dumps({"messages": messages}))

      # 3. ChatGPT 호출
      - id: chat
        component: chatgpt
        action: chat
        input:
          messages: ${jobs.prepare-messages.output.messages}

      # 4. 메모리 저장
      - id: save-to-memory
        component: chat-memory
        action: save
        input:
          user_id: ${input.user_id}
          message: ${input.message}
          response: ${jobs.chat.output.choices[0].message.content}

      # 5. 응답 반환
      - id: return
        output:
          response: ${jobs.chat.output.choices[0].message.content}
          session_id: ${input.user_id}
```

### Example 2: 윈도우 메모리 (최근 10개 메시지)

```yaml
components:
  - id: window-memory
    type: langchain-memory
    memory_type: window
    window_size: 10
    backend: postgres
    backend_config:
      connection_string: ${env.DATABASE_URL}
      table_name: chat_messages

    actions:
      - id: save
        action_type: save
        session_id: ${input.session_id}
        input_message: ${input.user_message}
        output_message: ${input.ai_message}

      - id: load
        action_type: load
        session_id: ${input.session_id}
```

### Example 3: 요약 메모리

```yaml
components:
  - id: summary-memory
    type: langchain-memory
    memory_type: summary
    summarization_llm: openai:gpt-4o-mini
    summary_prompt: |
      Progressively summarize the lines of conversation provided,
      adding onto the previous summary returning a new summary.

      Current summary:
      {summary}

      New lines of conversation:
      {new_lines}

      New summary:

    backend: mongodb
    backend_config:
      connection_string: ${env.MONGODB_URL}
      database_name: chatbot
      collection_name: conversations

    actions:
      - id: save
        action_type: save
        session_id: ${input.session_id}
        inputs:
          input: ${input.user_message}
        outputs:
          output: ${input.ai_message}

      - id: load
        action_type: load
        session_id: ${input.session_id}
```

### Example 4: 벡터 메모리 (시맨틱 검색)

```yaml
components:
  - id: vector-memory
    type: langchain-memory-vector
    vector_store_type: chroma
    vector_store_config:
      persist_directory: ./chroma_db

    embedding_model: openai:text-embedding-3-small
    search_type: similarity
    search_kwargs:
      k: 5

    actions:
      - id: save
        action_type: save
        session_id: ${input.session_id}
        input_message: ${input.user_message}
        output_message: ${input.ai_message}

      - id: search
        action_type: search
        session_id: ${input.session_id}
        query: ${input.query}
        k: 5

workflows:
  - id: semantic-search-memory
    jobs:
      # 1. 유사한 과거 대화 검색
      - id: search-similar
        component: vector-memory
        action: search
        input:
          session_id: ${input.user_id}
          query: ${input.message}

      # 2. 관련 컨텍스트와 함께 LLM 호출
      - id: chat-with-context
        component: chatgpt
        action: chat
        input:
          messages:
            - role: system
              content: |
                Here are some relevant past conversations:
                ${jobs.search-similar.output.messages}
            - role: user
              content: ${input.message}

      # 3. 새 대화 저장
      - id: save-new
        component: vector-memory
        action: save
        input:
          session_id: ${input.user_id}
          user_message: ${input.message}
          ai_message: ${jobs.chat-with-context.output.choices[0].message.content}
```

### Example 5: LangGraph 체크포인트

```yaml
components:
  - id: graph-checkpoint
    type: langchain-checkpoint
    backend: sqlite
    backend_config:
      db_path: ./checkpoints.db

    auto_checkpoint: true
    max_checkpoints: 100

    actions:
      - id: save
        action_type: save
        thread_id: ${input.thread_id}
        state: ${input.state}

      - id: load
        action_type: load
        thread_id: ${input.thread_id}

      - id: list
        action_type: list
        thread_id: ${input.thread_id}
        limit: 10

      - id: rollback
        action_type: rollback
        thread_id: ${input.thread_id}
        checkpoint_id: ${input.checkpoint_id}

workflows:
  - id: stateful-agent
    jobs:
      # 1. 이전 상태 로드
      - id: load-state
        component: graph-checkpoint
        action: load
        input:
          thread_id: ${input.thread_id}

      # 2. 에이전트 실행 (상태 업데이트)
      - id: run-agent
        component: my-agent
        action: run
        input:
          state: ${jobs.load-state.output.checkpoint.state}
          message: ${input.message}

      # 3. 새 상태 저장
      - id: save-state
        component: graph-checkpoint
        action: save
        input:
          thread_id: ${input.thread_id}
          state: ${jobs.run-agent.output.new_state}
```

### Example 6: 복합 메모리 전략

```yaml
components:
  # 단기 메모리 (최근 5개)
  - id: short-term-memory
    type: langchain-memory
    memory_type: window
    window_size: 5
    backend: in_memory

    actions:
      - id: save
        action_type: save
        session_id: ${input.session_id}
        input_message: ${input.message}
        output_message: ${input.response}

      - id: load
        action_type: load
        session_id: ${input.session_id}

  # 장기 메모리 (벡터 검색)
  - id: long-term-memory
    type: langchain-memory-vector
    vector_store_type: faiss
    vector_store_config:
      persist_directory: ./faiss_index

    embedding_model: openai:text-embedding-3-small

    actions:
      - id: save
        action_type: save
        session_id: ${input.session_id}
        input_message: ${input.message}
        output_message: ${input.response}

      - id: search
        action_type: search
        session_id: ${input.session_id}
        query: ${input.message}
        k: 3

workflows:
  - id: hybrid-memory-chat
    jobs:
      # 1. 단기 메모리 로드
      - id: load-recent
        component: short-term-memory
        action: load
        input:
          session_id: ${input.user_id}

      # 2. 장기 메모리 검색
      - id: search-relevant
        component: long-term-memory
        action: search
        input:
          session_id: ${input.user_id}
          message: ${input.message}

      # 3. 메모리 결합 및 LLM 호출
      - id: chat
        component: chatgpt
        action: chat
        input:
          messages:
            - role: system
              content: |
                Recent conversation:
                ${jobs.load-recent.output.memory.history}

                Relevant past context:
                ${jobs.search-relevant.output.messages}
            - role: user
              content: ${input.message}

      # 4. 양쪽 메모리에 저장
      - id: save-short-term
        component: short-term-memory
        action: save
        input:
          session_id: ${input.user_id}
          message: ${input.message}
          response: ${jobs.chat.output.choices[0].message.content}

      - id: save-long-term
        component: long-term-memory
        action: save
        input:
          session_id: ${input.user_id}
          message: ${input.message}
          response: ${jobs.chat.output.choices[0].message.content}
```

## Integration with Existing Components

LangChain 메모리 컴포넌트는 기존 model-compose 컴포넌트들과 함께 사용할 수 있습니다:

```yaml
workflows:
  - id: integrated-workflow
    jobs:
      # 1. 메모리 로드
      - id: load-memory
        component: chat-memory
        action: load

      # 2. 외부 API 호출 (http-client)
      - id: api-call
        component: external-api
        type: http-client
        input:
          context: ${jobs.load-memory.output.memory}

      # 3. 로컬 모델 실행 (model)
      - id: local-model
        component: local-llm
        type: model
        input:
          messages: ${jobs.load-memory.output.memory.history}

      # 4. 메모리 저장
      - id: save-memory
        component: chat-memory
        action: save
        input:
          response: ${jobs.local-model.output.response}
```

## Dependencies

### Python Packages

```txt
# requirements.txt에 추가
langchain>=0.1.0
langchain-community>=0.0.20
langchain-openai>=0.0.5
langchain-anthropic>=0.1.0

# 벡터 스토어
faiss-cpu>=1.7.4  # 또는 faiss-gpu
chromadb>=0.4.0
pinecone-client>=3.0.0
qdrant-client>=1.7.0

# 백엔드
redis>=5.0.0
psycopg2-binary>=2.9.0  # PostgreSQL
pymongo>=4.6.0  # MongoDB
boto3>=1.34.0  # DynamoDB

# LangGraph
langgraph>=0.0.20

# 임베딩
openai>=1.0.0
sentence-transformers>=2.2.0
```

## File Structure

```
src/mindor/
├── dsl/
│   └── schema/
│       ├── component/
│       │   └── impl/
│       │       └── langchain/
│       │           ├── __init__.py
│       │           ├── memory.py              # LangChainMemoryComponentConfig
│       │           ├── memory_vector.py       # LangChainMemoryVectorComponentConfig
│       │           └── checkpoint.py          # LangChainCheckpointComponentConfig
│       └── action/
│           └── impl/
│               └── langchain/
│                   ├── __init__.py
│                   ├── memory.py              # LangChainMemoryActionConfig
│                   ├── memory_vector.py       # LangChainMemoryVectorActionConfig
│                   └── checkpoint.py          # LangChainCheckpointActionConfig
└── core/
    └── component/
        └── services/
            └── langchain/
                ├── __init__.py
                ├── memory.py                  # LangChainMemoryService
                ├── memory_vector.py           # LangChainMemoryVectorService
                ├── checkpoint.py              # LangChainCheckpointService
                ├── backends/
                │   ├── __init__.py
                │   ├── redis.py               # Redis 백엔드
                │   ├── postgres.py            # PostgreSQL 백엔드
                │   ├── mongodb.py             # MongoDB 백엔드
                │   └── dynamodb.py            # DynamoDB 백엔드
                ├── vector_stores/
                │   ├── __init__.py
                │   ├── faiss.py
                │   ├── chroma.py
                │   ├── pinecone.py
                │   └── qdrant.py
                └── utils/
                    ├── __init__.py
                    ├── llm_factory.py         # LLM 생성 헬퍼
                    └── embeddings.py          # 임베딩 헬퍼
```

## Implementation Phases

### Phase 1: Core Memory Support (MVP)
- [ ] 기본 메모리 컴포넌트 (buffer, window)
- [ ] 인메모리 백엔드
- [ ] save, load, clear 액션
- [ ] 세션 관리

### Phase 2: Persistent Backends
- [ ] Redis 백엔드
- [ ] PostgreSQL 백엔드
- [ ] SQLite 백엔드
- [ ] MongoDB 백엔드

### Phase 3: Advanced Memory Types
- [ ] 요약 메모리 (summary)
- [ ] 토큰 버퍼 메모리
- [ ] 엔티티 메모리
- [ ] 지식 그래프 메모리

### Phase 4: Vector Memory
- [ ] 벡터 메모리 컴포넌트
- [ ] FAISS 통합
- [ ] Chroma 통합
- [ ] Pinecone 통합
- [ ] 시맨틱 검색

### Phase 5: LangGraph Checkpoint
- [ ] 체크포인트 컴포넌트
- [ ] SQLite 체크포인터
- [ ] PostgreSQL 체크포인터
- [ ] 상태 관리 (save, load, list, rollback)

### Phase 6: Production Ready
- [ ] 성능 최적화
- [ ] 에러 핸들링
- [ ] 로깅 및 모니터링
- [ ] 단위 테스트
- [ ] 통합 테스트
- [ ] 문서화

## Testing Strategy

### Unit Tests

```python
# tests/core/component/services/langchain/test_memory.py

import pytest
from mindor.core.component.services.langchain.memory import LangChainMemoryService

@pytest.mark.asyncio
async def test_buffer_memory_save_load():
    config = LangChainMemoryComponentConfig(
        id="test-memory",
        type=ComponentType.LANGCHAIN_MEMORY,
        memory_type=LangChainMemoryType.BUFFER,
        backend=LangChainMemoryBackend.IN_MEMORY
    )

    service = LangChainMemoryService("test", config, {}, None)
    await service._start()

    # 저장
    save_action = LangChainMemoryActionConfig(
        action_type="save",
        session_id="test-session",
        input_message="Hello",
        output_message="Hi there!"
    )
    # ... 실행 및 검증

    # 로드
    load_action = LangChainMemoryActionConfig(
        action_type="load",
        session_id="test-session"
    )
    # ... 실행 및 검증

    await service._stop()

@pytest.mark.asyncio
async def test_window_memory():
    # 윈도우 메모리 테스트
    pass

@pytest.mark.asyncio
async def test_redis_backend():
    # Redis 백엔드 테스트
    pass
```

### Integration Tests

```python
# tests/integration/test_langchain_memory_workflow.py

@pytest.mark.asyncio
async def test_chat_with_memory_workflow():
    """메모리를 사용하는 전체 워크플로우 테스트"""
    # YAML 로드
    # 워크플로우 실행
    # 메모리 저장 및 로드 검증
    pass

@pytest.mark.asyncio
async def test_vector_memory_search():
    """벡터 메모리 검색 테스트"""
    pass
```

## Error Handling

### Common Error Scenarios

1. **백엔드 연결 실패**
   - Redis/PostgreSQL 연결 오류
   - 인증 실패
   - 네트워크 오류

2. **메모리 용량 초과**
   - 세션 메모리 한계
   - 벡터 스토어 용량
   - 토큰 제한 초과

3. **세션 관리 오류**
   - 세션 만료
   - 세션 ID 충돌
   - 동시성 문제

4. **임베딩 오류**
   - 임베딩 모델 호출 실패
   - 벡터 스토어 쓰기 오류

### Error Response Format

```json
{
  "error": {
    "type": "LangChainMemoryError",
    "code": "BACKEND_CONNECTION_FAILED",
    "message": "Failed to connect to Redis backend",
    "details": {
      "backend": "redis",
      "url": "redis://localhost:6379"
    }
  }
}
```

## Security Considerations

1. **데이터 암호화**
   - 민감한 대화 내용 암호화
   - Redis/DB 연결 TLS 사용
   - 환경 변수로 크레덴셜 관리

2. **세션 보안**
   - 세션 ID 검증
   - TTL 설정으로 자동 만료
   - 세션 하이재킹 방지

3. **접근 제어**
   - 사용자별 메모리 격리
   - 권한 검증
   - Rate limiting

## Performance Considerations

1. **메모리 관리**
   - 세션 풀링
   - 자동 정리 (TTL)
   - 메모리 사용량 모니터링

2. **벡터 검색 최적화**
   - 인덱스 최적화
   - 캐싱 전략
   - 배치 처리

3. **백엔드 최적화**
   - 연결 풀링
   - 쿼리 최적화
   - 비동기 I/O

## Monitoring & Observability

### Metrics

- 메모리 저장/로드 횟수
- 평균 응답 시간
- 세션 수
- 메모리 사용량
- 벡터 검색 성능

### Logging

```python
logger.info(
    "Memory action executed",
    extra={
        "component_id": self.id,
        "action_type": action.action_type,
        "session_id": session_id,
        "memory_type": config.memory_type,
        "backend": config.backend,
        "duration_ms": duration
    }
)
```

## Future Enhancements

1. **고급 메모리 전략**
   - 하이브리드 메모리 (단기+장기)
   - 계층적 메모리
   - 적응형 메모리 (사용 패턴 기반)

2. **멀티모달 메모리**
   - 이미지 메모리
   - 오디오 메모리
   - 문서 메모리

3. **협업 메모리**
   - 팀 공유 메모리
   - 크로스 세션 메모리
   - 메모리 동기화

4. **AI 기반 메모리**
   - 자동 중요도 판단
   - 스마트 요약
   - 메모리 압축

## References

- [LangChain Memory Documentation](https://python.langchain.com/docs/modules/memory/)
- [LangGraph Checkpointing](https://langchain-ai.github.io/langgraph/how-tos/persistence/)
- [Vector Store Retriever Memory](https://python.langchain.com/docs/modules/memory/types/vectorstore_retriever_memory)
- [Chat Message History Backends](https://python.langchain.com/docs/integrations/memory/)

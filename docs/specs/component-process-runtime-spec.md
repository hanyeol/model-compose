# Component Process Runtime Specification

## Overview

기존 `runtime: native`, `runtime: docker`와 일관성 있게 `runtime: process`를 추가하여 컴포넌트를 별도의 Python 프로세스에서 실행할 수 있는 기능에 대한 스펙입니다.

## Design Goals

1. **일관된 아키텍처**: 기존 runtime 시스템 확장
2. **프로세스 격리**: 컴포넌트를 별도 프로세스에서 실행
3. **리소스 관리**: 독립적인 메모리 및 CPU 자원
4. **선언적 구성**: YAML로 간단하게 설정
5. **투명성**: 기존 컴포넌트 코드 수정 불필요

## Runtime Types

model-compose는 3가지 런타임 환경을 제공합니다:

```yaml
# embedded: 메인 프로세스에 내장되어 실행
runtime: embedded

# process: 별도 Python 프로세스에서 실행
runtime: process

# docker: Docker 컨테이너에서 실행
runtime: docker
```

### Runtime 비교

| Runtime | 실행 위치 | 격리 수준 | 시작 속도 | 사용 시나리오 |
|---------|----------|----------|----------|-------------|
| **embedded** | 메인 프로세스 내 | 없음 | 빠름 | 가벼운 작업, 빠른 응답 필요 |
| **process** | 별도 프로세스 | 프로세스 격리 | 중간 | 무거운 모델, 크래시 격리 |
| **docker** | Docker 컨테이너 | 컨테이너 격리 | 느림 | 프로덕션 배포, 이식성 |

### 격리 수준 시각화

```
격리 수준 낮음 ─────────────────────────▶ 격리 수준 높음

embedded          process           docker
(내장)            (분리)             (격리)
│                 │                  │
├─ 같은 메모리     ├─ 독립 메모리      ├─ 컨테이너
├─ 같은 프로세스   ├─ 별도 프로세스    ├─ 가상화
├─ 빠른 실행       ├─ 중간 오버헤드    ├─ 높은 오버헤드
└─ 크래시 전파     └─ 크래시 격리     └─ 완전 격리
```

## Use Cases

### 1. 무거운 모델 격리
```yaml
component:
  type: model
  runtime: process
  task: chat-completion
  model: meta-llama/Llama-3.1-70B
```

**이점**: 70B 모델이 메인 프로세스 메모리를 점유하지 않음

### 2. 다중 GPU 활용
```yaml
components:
  - id: model-gpu-0
    type: model
    runtime:
      type: process
      env:
        CUDA_VISIBLE_DEVICES: "0"
    model: model-a

  - id: model-gpu-1
    type: model
    runtime:
      type: process
      env:
        CUDA_VISIBLE_DEVICES: "1"
    model: model-b
```

**이점**: 각 모델이 독립적인 GPU 사용

### 3. 크래시 격리
```yaml
component:
  type: google-adk-agent
  runtime:
    type: process
    restart_policy: always
  agent_name: ExperimentalAgent
```

**이점**: 에이전트 크래시 시 메인 서버는 계속 실행

### 4. 블로킹 작업 분리
```yaml
component:
  type: shell
  runtime: process
  command: ["ffmpeg", "-i", "${input.file}", "output.mp4"]
```

**이점**: 긴 작업이 메인 이벤트 루프를 블로킹하지 않음

## Architecture

### Runtime Types Hierarchy

```
RuntimeConfig
├── EmbeddedRuntimeConfig (type: embedded)   # 메인 프로세스
├── ProcessRuntimeConfig (type: process)     # 별도 Python 프로세스 (NEW)
└── DockerRuntimeConfig (type: docker)       # Docker 컨테이너
```

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Main Process                            │
│                                                             │
│  ┌────────────────────────────────────────────────────┐   │
│  │          ComponentService                          │   │
│  │                                                    │   │
│  │  ┌──────────────┐         ┌──────────────┐       │   │
│  │  │  Embedded    │         │   Process    │       │   │
│  │  │  Execution   │         │   Proxy      │       │   │
│  │  └──────────────┘         └───────┬──────┘       │   │
│  │                                    │              │   │
│  └────────────────────────────────────┼──────────────┘   │
│                                       │                  │
└───────────────────────────────────────┼──────────────────┘
                                        │
                                        │ IPC Communication
                                        │ (Queue or Socket)
                                        │
┌───────────────────────────────────────┼──────────────────┐
│                  Subprocess           │                  │
│                                       │                  │
│  ┌────────────────────────────────────▼──────────────┐  │
│  │         ProcessRuntimeWorker                      │  │
│  │                                                   │  │
│  │  ┌─────────────────────────────────────────┐    │  │
│  │  │  ComponentService Instance              │    │  │
│  │  │  (Model, Agent, Shell, etc.)            │    │  │
│  │  └─────────────────────────────────────────┘    │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Schema Definition

### 1. RuntimeType 확장

**Location**: `src/mindor/dsl/schema/runtime/impl/types.py`

```python
from enum import Enum

class RuntimeType(str, Enum):
    EMBEDDED = "embedded"  # Runs embedded in main process (기존 NATIVE)
    PROCESS = "process"    # Runs in separate process (NEW)
    DOCKER = "docker"      # Runs in Docker container
```

### 2. ProcessRuntimeConfig

**Location**: `src/mindor/dsl/schema/runtime/impl/process.py`

```python
from typing import Literal, Optional, Dict, List
from pydantic import BaseModel, Field
from .common import RuntimeType, CommonRuntimeConfig

class RestartPolicy(str, Enum):
    """프로세스 재시작 정책"""
    NO = "no"
    ALWAYS = "always"
    ON_FAILURE = "on-failure"

class IPCMethod(str, Enum):
    """프로세스 간 통신 방식"""
    QUEUE = "queue"          # multiprocessing.Queue
    SOCKET = "socket"        # Unix socket

class ProcessRuntimeConfig(CommonRuntimeConfig):
    """
    별도 Python 프로세스에서 컴포넌트를 실행하는 런타임 설정
    """
    type: Literal[RuntimeType.PROCESS]

    # 환경 설정
    env: Dict[str, str] = Field(
        default_factory=dict,
        description="환경 변수 (예: CUDA_VISIBLE_DEVICES)"
    )

    working_dir: Optional[str] = Field(
        None,
        description="작업 디렉토리"
    )

    # 생명주기 관리
    restart_policy: RestartPolicy = Field(
        default=RestartPolicy.NO,
        description="재시작 정책"
    )

    restart_max_retries: int = Field(
        default=3,
        description="최대 재시작 횟수 (on-failure일 때)"
    )

    start_timeout: int = Field(
        default=60,
        description="시작 타임아웃 (초)"
    )

    stop_timeout: int = Field(
        default=30,
        description="종료 타임아웃 (초)"
    )

    # 통신 설정
    ipc_method: IPCMethod = Field(
        default=IPCMethod.QUEUE,
        description="프로세스 간 통신 방식"
    )

    socket_path: Optional[str] = Field(
        None,
        description="Unix 소켓 경로 (ipc_method=socket일 때)"
    )

    # 리소스 제한
    max_memory: Optional[str] = Field(
        None,
        description="최대 메모리 (예: '4GB', '512MB')"
    )

    cpu_limit: Optional[float] = Field(
        None,
        description="CPU 제한 (코어 수, 예: 2.0)"
    )

    # 헬스체크
    healthcheck_interval: int = Field(
        default=10,
        description="헬스체크 주기 (초)"
    )

    healthcheck_timeout: int = Field(
        default=5,
        description="헬스체크 타임아웃 (초)"
    )
```

### 3. RuntimeConfig Union 업데이트

**Location**: `src/mindor/dsl/schema/runtime/runtime.py`

```python
from typing import Union, Annotated
from pydantic import Field
from .impl import EmbeddedRuntimeConfig, DockerRuntimeConfig, ProcessRuntimeConfig

RuntimeConfig = Annotated[
    Union[
        EmbeddedRuntimeConfig,  # 기존 NativeRuntimeConfig에서 rename
        ProcessRuntimeConfig,   # NEW
        DockerRuntimeConfig
    ],
    Field(discriminator="type")
]
```

### 4. EmbeddedRuntimeConfig (Rename)

**Location**: `src/mindor/dsl/schema/runtime/impl/embedded.py` (기존 native.py에서 rename)

```python
from typing import Literal
from .common import RuntimeType, CommonRuntimeConfig

class EmbeddedRuntimeConfig(CommonRuntimeConfig):
    """
    메인 프로세스에 내장되어 실행되는 런타임
    (기존 NativeRuntimeConfig)
    """
    type: Literal[RuntimeType.EMBEDDED]
```

## IPC Communication Protocol

### Message Format

```python
from typing import Literal, Any, Optional
from pydantic import BaseModel
import time

class MessageType(str, Enum):
    START = "start"
    STOP = "stop"
    RUN = "run"
    RESULT = "result"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    STATUS = "status"
    LOG = "log"

class IPCMessage(BaseModel):
    """프로세스 간 통신 메시지"""
    type: MessageType
    request_id: str
    payload: Optional[Dict[str, Any]] = None
    timestamp: float = Field(default_factory=time.time)
```

### Example Messages

```python
# 액션 실행 요청
{
    "type": "run",
    "request_id": "req-123",
    "payload": {
        "action_id": "generate",
        "run_id": "run-456",
        "input": {"prompt": "Hello"}
    },
    "timestamp": 1234567890.123
}

# 실행 결과
{
    "type": "result",
    "request_id": "req-123",
    "payload": {
        "output": {"generated": "Hello! How can I help?"}
    },
    "timestamp": 1234567891.456
}

# 에러 응답
{
    "type": "error",
    "request_id": "req-123",
    "payload": {
        "error": "Model failed to load"
    },
    "timestamp": 1234567891.789
}
```

### Communication Flow

```
Main Process                          Subprocess
     │                                      │
     │──────── start (config) ─────────────▶│
     │                                      │ (컴포넌트 초기화)
     │◀─────── result (ready) ──────────────│
     │                                      │
     │──────── run (action, input) ─────────▶│
     │                                      │ (액션 실행)
     │◀─────── result (output) ─────────────│
     │                                      │
     │──────── heartbeat ───────────────────▶│
     │◀─────── result (alive) ───────────────│
     │                                      │
     │──────── stop ────────────────────────▶│
     │                                      │ (컴포넌트 종료)
     │◀─────── result (stopped) ────────────│
     │                                      │
```

## Service Implementation

### 1. ProcessRuntimeProxy

메인 프로세스에서 실행되며 서브프로세스와 통신합니다.

**Location**: `src/mindor/core/runtime/process/proxy.py`

```python
from typing import Any, Dict, Optional
from multiprocessing import Process, Queue
import asyncio
import uuid
import time
from mindor.core.component.base import ComponentService, ComponentGlobalConfigs
from mindor.core.component.context import ComponentActionContext
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.action import ActionConfig
from mindor.dsl.schema.runtime import ProcessRuntimeConfig
from mindor.core.logger import logging
from .worker import ProcessRuntimeWorker
from .protocol import IPCMessage, MessageType

class ProcessRuntimeProxy(ComponentService):
    """
    Process runtime에서 실행되는 컴포넌트를 위한 프록시
    실제 컴포넌트는 별도 프로세스에서 실행됨
    """

    def __init__(
        self,
        id: str,
        config: ComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        if not isinstance(config.runtime, ProcessRuntimeConfig):
            raise ValueError("ProcessRuntimeProxy requires ProcessRuntimeConfig")

        self.process_config: ProcessRuntimeConfig = config.runtime
        self.subprocess: Optional[Process] = None
        self.request_queue: Optional[Queue] = None
        self.response_queue: Optional[Queue] = None
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self.healthcheck_task: Optional[asyncio.Task] = None
        self.response_handler_task: Optional[asyncio.Task] = None

    async def _start(self) -> None:
        """서브프로세스 시작"""
        # IPC 큐 생성
        self.request_queue = Queue()
        self.response_queue = Queue()

        # 서브프로세스 생성 및 시작
        self.subprocess = Process(
            target=self._run_worker,
            args=(
                self.id,
                self.config,
                self.global_configs,
                self.request_queue,
                self.response_queue
            ),
            daemon=False
        )

        # 환경 변수 설정
        if self.process_config.env:
            import os
            for key, value in self.process_config.env.items():
                os.environ[key] = value

        self.subprocess.start()
        logging.info(f"Started subprocess for component {self.id} (PID: {self.subprocess.pid})")

        # 준비 완료 대기
        await self._wait_for_ready()

        # 응답 핸들러 시작
        self.response_handler_task = asyncio.create_task(
            self._handle_responses()
        )

        # 헬스체크 시작
        if self.process_config.healthcheck_interval > 0:
            self.healthcheck_task = asyncio.create_task(
                self._healthcheck_loop()
            )

        await super()._start()

    async def _stop(self) -> None:
        """서브프로세스 종료"""
        logging.info(f"Stopping subprocess for component {self.id}")

        # 종료 요청 전송
        stop_message = IPCMessage(
            type=MessageType.STOP,
            request_id=str(uuid.uuid4())
        )
        self.request_queue.put(stop_message.model_dump())

        # 타임아웃과 함께 종료 대기
        try:
            self.subprocess.join(timeout=self.process_config.stop_timeout)
        except TimeoutError:
            logging.warning(f"Process {self.id} did not stop gracefully, terminating")
            self.subprocess.terminate()
            self.subprocess.join(timeout=5)
            if self.subprocess.is_alive():
                logging.error(f"Process {self.id} did not terminate, killing")
                self.subprocess.kill()

        # 태스크 취소
        if self.healthcheck_task:
            self.healthcheck_task.cancel()
        if self.response_handler_task:
            self.response_handler_task.cancel()

        await super()._stop()

    async def _run(
        self,
        action: ActionConfig,
        context: ComponentActionContext
    ) -> Any:
        """액션 실행 요청을 서브프로세스로 전달"""
        request_id = str(uuid.uuid4())

        message = IPCMessage(
            type=MessageType.RUN,
            request_id=request_id,
            payload={
                "action_id": action.id,
                "run_id": context.run_id,
                "input": context.input
            }
        )

        # Future 생성
        future = asyncio.get_event_loop().create_future()
        self.pending_requests[request_id] = future

        # 요청 전송
        self.request_queue.put(message.model_dump())

        # 응답 대기
        try:
            result = await future
            return result
        finally:
            self.pending_requests.pop(request_id, None)

    async def _handle_responses(self) -> None:
        """서브프로세스로부터 응답 처리"""
        while True:
            try:
                if not self.response_queue.empty():
                    message_dict = self.response_queue.get_nowait()
                    message = IPCMessage(**message_dict)

                    if message.request_id in self.pending_requests:
                        future = self.pending_requests[message.request_id]

                        if message.type == MessageType.RESULT:
                            future.set_result(message.payload.get("output"))
                        elif message.type == MessageType.ERROR:
                            error = message.payload.get("error", "Unknown error")
                            future.set_exception(Exception(error))

                await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Error handling response: {e}")

    async def _healthcheck_loop(self) -> None:
        """주기적인 헬스체크"""
        interval = self.process_config.healthcheck_interval
        timeout = self.process_config.healthcheck_timeout

        while True:
            try:
                await asyncio.sleep(interval)

                request_id = str(uuid.uuid4())
                message = IPCMessage(
                    type=MessageType.HEARTBEAT,
                    request_id=request_id
                )

                future = asyncio.get_event_loop().create_future()
                self.pending_requests[request_id] = future

                self.request_queue.put(message.model_dump())

                try:
                    await asyncio.wait_for(future, timeout=timeout)
                except asyncio.TimeoutError:
                    logging.warning(f"Process {self.id} not responding to healthcheck")
                    if self.process_config.restart_policy != RestartPolicy.NO:
                        await self._restart_process()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Healthcheck error: {e}")

    async def _wait_for_ready(self) -> None:
        """서브프로세스 준비 대기"""
        timeout = self.process_config.start_timeout
        start_time = time.time()

        while time.time() - start_time < timeout:
            if not self.response_queue.empty():
                message_dict = self.response_queue.get()
                message = IPCMessage(**message_dict)

                if message.type == MessageType.RESULT and \
                   message.payload.get("status") == "ready":
                    logging.info(f"Subprocess {self.id} is ready")
                    return

            await asyncio.sleep(0.5)

        raise TimeoutError(
            f"Process {self.id} did not start within {timeout}s"
        )

    async def _restart_process(self) -> None:
        """서브프로세스 재시작"""
        logging.info(f"Restarting process {self.id}")
        await self._stop()
        await self._start()

    def _run_worker(
        self,
        component_id: str,
        config: ComponentConfig,
        global_configs: ComponentGlobalConfigs,
        request_queue: Queue,
        response_queue: Queue
    ) -> None:
        """서브프로세스 엔트리포인트"""
        # 새 이벤트 루프 생성
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # 워커 실행
        worker = ProcessRuntimeWorker(
            component_id,
            config,
            global_configs,
            request_queue,
            response_queue
        )

        try:
            loop.run_until_complete(worker.run())
        except KeyboardInterrupt:
            pass
        finally:
            loop.close()
```

### 2. ProcessRuntimeWorker

서브프로세스에서 실제 컴포넌트를 실행합니다.

**Location**: `src/mindor/core/runtime/process/worker.py`

```python
from typing import Any, Dict
from multiprocessing import Queue
import asyncio
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.component import create_component
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.runtime import EmbeddedRuntimeConfig
from mindor.core.logger import logging
from .protocol import IPCMessage, MessageType

class ProcessRuntimeWorker:
    """
    서브프로세스에서 실제 컴포넌트를 실행하는 워커
    """

    def __init__(
        self,
        component_id: str,
        config: ComponentConfig,
        global_configs: ComponentGlobalConfigs,
        request_queue: Queue,
        response_queue: Queue
    ):
        self.component_id = component_id
        self.config = config
        self.global_configs = global_configs
        self.request_queue = request_queue
        self.response_queue = response_queue
        self.component = None
        self.running = True

    async def run(self) -> None:
        """워커 메인 루프"""
        try:
            # Embedded runtime으로 컴포넌트 생성
            # (프로세스는 이미 분리되었으므로 embedded로 실행)
            embedded_config = self.config.model_copy(deep=True)
            embedded_config.runtime = EmbeddedRuntimeConfig(type="embedded")

            self.component = create_component(
                self.component_id,
                embedded_config,
                self.global_configs,
                daemon=True
            )

            # 컴포넌트 시작
            await self.component.setup()
            await self.component.start()

            logging.info(f"Component {self.component_id} started in subprocess")

            # 준비 완료 알림
            ready_message = IPCMessage(
                type=MessageType.RESULT,
                request_id="init",
                payload={"status": "ready"}
            )
            self.response_queue.put(ready_message.model_dump())

            # 요청 처리 루프
            while self.running:
                if not self.request_queue.empty():
                    message_dict = self.request_queue.get()
                    message = IPCMessage(**message_dict)
                    await self._handle_message(message)

                await asyncio.sleep(0.01)

        except Exception as e:
            logging.error(f"Worker error: {e}")
            error_message = IPCMessage(
                type=MessageType.ERROR,
                request_id="worker",
                payload={"error": str(e)}
            )
            self.response_queue.put(error_message.model_dump())

        finally:
            if self.component:
                await self.component.stop()
                await self.component.teardown()

    async def _handle_message(self, message: IPCMessage) -> None:
        """메시지 처리"""
        try:
            if message.type == MessageType.RUN:
                action_id = message.payload["action_id"]
                run_id = message.payload["run_id"]
                input_data = message.payload["input"]

                output = await self.component.run(action_id, run_id, input_data)

                response = IPCMessage(
                    type=MessageType.RESULT,
                    request_id=message.request_id,
                    payload={"output": output}
                )
                self.response_queue.put(response.model_dump())

            elif message.type == MessageType.HEARTBEAT:
                response = IPCMessage(
                    type=MessageType.RESULT,
                    request_id=message.request_id,
                    payload={"status": "alive"}
                )
                self.response_queue.put(response.model_dump())

            elif message.type == MessageType.STOP:
                self.running = False
                response = IPCMessage(
                    type=MessageType.RESULT,
                    request_id=message.request_id,
                    payload={"status": "stopped"}
                )
                self.response_queue.put(response.model_dump())

        except Exception as e:
            logging.error(f"Error handling message: {e}")
            error_response = IPCMessage(
                type=MessageType.ERROR,
                request_id=message.request_id,
                payload={"error": str(e)}
            )
            self.response_queue.put(error_response.model_dump())
```

### 3. Component Factory 수정

**Location**: `src/mindor/core/component/component.py`

```python
from mindor.dsl.schema.runtime import RuntimeType, ProcessRuntimeConfig

def create_component(
    id: str,
    config: ComponentConfig,
    global_configs: ComponentGlobalConfigs,
    daemon: bool
) -> ComponentService:
    try:
        component = ComponentInstances.get(id)
        if component:
            return component

        # Process runtime 체크
        if isinstance(config.runtime, ProcessRuntimeConfig):
            from mindor.core.runtime.process.proxy import ProcessRuntimeProxy
            component = ProcessRuntimeProxy(id, config, global_configs, daemon)
        else:
            # Embedded 또는 Docker runtime
            if not ComponentRegistry:
                from . import services
            component = ComponentRegistry[config.type](id, config, global_configs, daemon)

        ComponentInstances[id] = component
        return component

    except KeyError:
        raise ValueError(f"Unsupported component type: {config.type}")
```

## YAML Configuration Examples

### Example 1: 간단한 프로세스 분리

```yaml
controller:
  type: http-server
  port: 8080

component:
  type: model
  runtime: process  # 간단히 문자열로 지정
  task: chat-completion
  model: meta-llama/Llama-3.1-70B
  messages:
    - role: user
      content: ${input.prompt}
```

### Example 2: 상세한 Process Runtime 설정

```yaml
component:
  type: model
  runtime:
    type: process
    env:
      CUDA_VISIBLE_DEVICES: "0"
      PYTORCH_CUDA_ALLOC_CONF: "max_split_size_mb:512"
    restart_policy: on-failure
    restart_max_retries: 3
    start_timeout: 120
    stop_timeout: 30
    healthcheck_interval: 10
  task: image-generation
  model: stabilityai/stable-diffusion-xl-base-1.0
```

### Example 3: 다중 GPU 모델

```yaml
components:
  - id: text-model
    type: model
    runtime:
      type: process
      env:
        CUDA_VISIBLE_DEVICES: "0"
    task: text-generation
    model: gpt2-large

  - id: image-model
    type: model
    runtime:
      type: process
      env:
        CUDA_VISIBLE_DEVICES: "1"
    task: image-generation
    model: runwayml/stable-diffusion-v1-5

workflows:
  - id: multimodal
    jobs:
      - id: text
        component: text-model
        action: generate
      - id: image
        component: image-model
        action: generate
```

### Example 4: Runtime 비교

```yaml
components:
  # Embedded: 메인 프로세스에서 실행
  - id: fast-model
    type: model
    runtime: embedded
    task: text-generation
    model: gpt2

  # Process: 별도 프로세스에서 실행
  - id: heavy-model
    type: model
    runtime: process
    task: text-generation
    model: meta-llama/Llama-3.1-70B

  # Docker: Docker 컨테이너에서 실행
  - id: isolated-model
    type: model
    runtime:
      type: docker
      image: my-model:latest
      ports: ["8080:8080"]
    task: text-generation
```

### Example 5: 크래시 격리와 재시작

```yaml
component:
  type: google-adk-agent
  runtime:
    type: process
    restart_policy: always
    restart_max_retries: 5
    healthcheck_interval: 10
    healthcheck_timeout: 5
  agent_name: ExperimentalAgent
  model: gemini-2.5-flash
  tools:
    - type: code_executor
    - type: google_search
```

## File Structure

```
src/mindor/
├── dsl/
│   └── schema/
│       └── runtime/
│           ├── __init__.py
│           ├── runtime.py              # (수정) ProcessRuntimeConfig 추가
│           └── impl/
│               ├── __init__.py         # (수정) Export 업데이트
│               ├── types.py            # (수정) EMBEDDED, PROCESS 추가
│               ├── common.py
│               ├── embedded.py         # (rename) native.py → embedded.py
│               ├── process.py          # (신규) ProcessRuntimeConfig
│               └── docker.py
│
└── core/
    ├── component/
    │   └── component.py                # (수정) Process runtime 체크
    └── runtime/
        └── process/
            ├── __init__.py
            ├── protocol.py             # IPCMessage, MessageType
            ├── proxy.py                # ProcessRuntimeProxy
            └── worker.py               # ProcessRuntimeWorker
```

## Implementation Plan

### Phase 1: Core Infrastructure (MVP)
**목표**: 기본 프로세스 분리 동작

**Task List:**
- [ ] Runtime 스키마 확장
  - `RuntimeType.EMBEDDED` 추가 (NATIVE rename)
  - `RuntimeType.PROCESS` 추가
  - `ProcessRuntimeConfig` 정의
  - `EmbeddedRuntimeConfig` (NativeRuntimeConfig rename)
  - `RuntimeConfig` union 업데이트

- [ ] IPC 프로토콜 정의
  - `IPCMessage` 모델
  - `MessageType` enum
  - Protocol 문서화

- [ ] Worker 구현
  - `ProcessRuntimeWorker` 기본 구조
  - 요청/응답 처리
  - 컴포넌트 생성 및 실행

- [ ] Proxy 구현
  - `ProcessRuntimeProxy` 기본 구조
  - 프로세스 생성/관리
  - IPC 통신 (Queue 방식)
  - 요청/응답 매칭

- [ ] Factory 수정
  - Process runtime 체크
  - Proxy 생성 로직
  - Embedded runtime 호환성

**검증:**
- 간단한 shell 컴포넌트 프로세스 분리 테스트
- Model 컴포넌트 프로세스 분리 테스트

### Phase 2: Lifecycle Management
**목표**: 안정적인 생명주기 관리

**Task List:**
- [ ] 헬스체크 구현
  - 주기적인 heartbeat 메시지
  - 타임아웃 감지
  - 프로세스 상태 모니터링

- [ ] 재시작 정책
  - `restart_policy: always`
  - `restart_policy: on-failure`
  - `restart_max_retries` 처리
  - 재시작 간격 제어

- [ ] Graceful shutdown
  - Stop 메시지 전송
  - 컴포넌트 정리 대기
  - 타임아웃 처리
  - 강제 종료 (terminate/kill)

- [ ] 타임아웃 처리
  - `start_timeout` 구현
  - `stop_timeout` 구현
  - `healthcheck_timeout` 구현

**검증:**
- 프로세스 크래시 시나리오 테스트
- Graceful shutdown 테스트
- 재시작 정책 테스트

### Phase 3: Advanced Features
**목표**: 고급 기능 및 최적화

**Task List:**
- [ ] Unix 소켓 IPC 지원
  - `ipc_method: socket` 구현
  - 소켓 경로 관리
  - 성능 벤치마크 (Queue vs Socket)

- [ ] 환경 변수 설정
  - `runtime.env` 적용
  - GPU 디바이스 지정
  - 프로세스별 격리

- [ ] 리소스 제한 (선택적)
  - `max_memory` 제한 구현
  - `cpu_limit` 제한 구현
  - resource.setrlimit 활용

- [ ] 로깅 통합
  - 서브프로세스 로그 수집
  - 메인 프로세스 로거로 전달
  - 로그 레벨 필터링
  - 컴포넌트별 로그 분리

**검증:**
- 환경 변수 격리 테스트
- 리소스 제한 테스트
- 로그 통합 테스트

### Phase 4: Testing & Documentation
**목표**: 안정성 및 문서화

**Task List:**
- [ ] 단위 테스트
  - ProcessRuntimeProxy 테스트
  - ProcessRuntimeWorker 테스트
  - IPC 통신 테스트
  - 에러 시나리오 테스트

- [ ] 통합 테스트
  - 실제 컴포넌트 테스트 (Model, Shell, Agent)
  - 워크플로우 통합 테스트
  - 다중 프로세스 테스트
  - 재시작 시나리오 테스트

- [ ] 성능 테스트
  - IPC 오버헤드 측정
  - 다중 프로세스 부하 테스트
  - 메모리 격리 검증
  - 시작/종료 시간 측정

- [ ] 문서 작성
  - 사용자 가이드
  - Runtime 비교 가이드
  - 트러블슈팅 가이드
  - API 문서

**검증:**
- 모든 테스트 통과
- 성능 기준 달성
- 문서 완성도 확인

## Testing Strategy

### Unit Tests

**Location**: `tests/core/runtime/process/test_proxy.py`

```python
import pytest
from mindor.core.runtime.process.proxy import ProcessRuntimeProxy
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.runtime import ProcessRuntimeConfig

@pytest.mark.asyncio
async def test_proxy_start_stop():
    """프록시 시작/종료 테스트"""
    config = ComponentConfig(
        id="test",
        type="model",
        runtime=ProcessRuntimeConfig(type="process"),
        task="chat-completion",
        model="gpt2"
    )

    proxy = ProcessRuntimeProxy("test", config, global_configs, False)

    # 시작
    await proxy.start()
    assert proxy.subprocess is not None
    assert proxy.subprocess.is_alive()

    # 종료
    await proxy.stop()
    assert not proxy.subprocess.is_alive()

@pytest.mark.asyncio
async def test_proxy_run_action():
    """액션 실행 테스트"""
    proxy = create_test_proxy()
    await proxy.start()

    result = await proxy.run("generate", "run-1", {"prompt": "Hello"})

    assert result is not None
    assert "generated" in result

    await proxy.stop()

@pytest.mark.asyncio
async def test_proxy_healthcheck():
    """헬스체크 테스트"""
    proxy = create_test_proxy()
    await proxy.start()

    # 헬스체크 실행
    await asyncio.sleep(11)  # healthcheck 주기보다 길게

    # 프로세스가 살아있는지 확인
    assert proxy.subprocess.is_alive()

    await proxy.stop()

@pytest.mark.asyncio
async def test_proxy_restart_on_crash():
    """크래시 시 재시작 테스트"""
    config = ComponentConfig(
        id="test",
        type="model",
        runtime=ProcessRuntimeConfig(
            type="process",
            restart_policy="always"
        )
    )

    proxy = ProcessRuntimeProxy("test", config, global_configs, False)
    await proxy.start()

    # 프로세스 강제 종료
    proxy.subprocess.kill()
    await asyncio.sleep(2)

    # 재시작 확인
    assert proxy.subprocess.is_alive()

    await proxy.stop()
```

### Integration Tests

**Location**: `tests/integration/test_process_runtime.py`

```python
@pytest.mark.asyncio
async def test_process_runtime_workflow():
    """프로세스 런타임을 사용하는 워크플로우 테스트"""
    yaml_config = """
    components:
      - id: model
        type: model
        runtime: process
        task: text-generation
        model: gpt2

    workflows:
      - id: test-workflow
        jobs:
          - id: generate
            component: model
            action: generate
            input:
              prompt: "Hello"
    """

    result = await run_workflow_from_yaml(yaml_config, "test-workflow", {})
    assert result is not None

@pytest.mark.asyncio
async def test_multi_process_components():
    """여러 프로세스 컴포넌트 동시 실행 테스트"""
    yaml_config = """
    components:
      - id: model-1
        type: model
        runtime: process
        task: text-generation
        model: gpt2

      - id: model-2
        type: model
        runtime: process
        task: text-generation
        model: gpt2

    workflows:
      - id: parallel-workflow
        jobs:
          - id: gen-1
            component: model-1
            action: generate
          - id: gen-2
            component: model-2
            action: generate
    """

    result = await run_workflow_from_yaml(yaml_config, "parallel-workflow", {})
    assert result is not None

@pytest.mark.asyncio
async def test_gpu_isolation():
    """GPU 격리 테스트"""
    yaml_config = """
    components:
      - id: model-gpu-0
        type: model
        runtime:
          type: process
          env:
            CUDA_VISIBLE_DEVICES: "0"
        model: gpt2

      - id: model-gpu-1
        type: model
        runtime:
          type: process
          env:
            CUDA_VISIBLE_DEVICES: "1"
        model: gpt2
    """

    # GPU 할당 확인
    # 각 프로세스가 다른 GPU를 사용하는지 검증
```

## Error Handling

### Common Error Scenarios

1. **프로세스 시작 실패**
   ```python
   try:
       await proxy.start()
   except TimeoutError:
       logging.error("Component failed to start within timeout")
       # 재시작 정책에 따라 재시도
   ```

2. **프로세스 크래시**
   ```python
   # Heartbeat 실패 감지
   if not subprocess.is_alive():
       if restart_policy == "always":
           await restart_process()
       else:
           raise ProcessCrashedError("Component process crashed")
   ```

3. **IPC 통신 실패**
   ```python
   try:
       result = await send_request(message, timeout=30)
   except asyncio.TimeoutError:
       logging.error("IPC communication timeout")
       # 프로세스 상태 확인 및 재시작
   ```

4. **리소스 부족**
   ```python
   # 메모리 제한 초과 시 OOM 킬러 작동
   # 재시작 정책에 따라 복구 시도
   if restart_policy == "on-failure":
       await restart_process()
   ```

### Error Response Format

```json
{
  "error": {
    "type": "ProcessRuntimeError",
    "code": "PROCESS_CRASHED",
    "message": "Component process crashed unexpectedly",
    "details": {
      "component_id": "heavy-model",
      "pid": 12345,
      "exit_code": -11
    }
  }
}
```

## Performance Considerations

### IPC Overhead

- **Queue 방식**:
  - 안정적이지만 약간 느림 (직렬화 오버헤드)
  - 작은 메시지에 적합

- **Socket 방식**:
  - 더 빠르지만 구현 복잡
  - 큰 데이터 전송에 유리

**권장**: 기본은 Queue, 고성능 필요 시 Socket

### Memory Isolation

- 각 프로세스는 독립적인 메모리 공간
- 큰 모델 여러 개 로드 시 메모리 소비 증가
- `max_memory` 제한으로 제어 가능

### Startup Time

- 서브프로세스 시작: ~1-2초
- 무거운 모델 로딩: 모델 크기에 따라 수십 초
- `start_timeout` 충분히 설정 필요

### Context Switching

- 프로세스 간 컨텍스트 스위칭 비용
- 빈번한 작은 요청보다는 큰 배치 작업에 유리
- Embedded runtime이 더 빠른 경우도 있음

## Security Considerations

1. **프로세스 격리**
   - 각 컴포넌트가 독립 프로세스에서 실행
   - 한 컴포넌트 크래시가 다른 컴포넌트에 영향 없음
   - 메모리 완전 격리

2. **환경 변수 관리**
   - 민감한 환경 변수 주의
   - `.env` 파일과 통합
   - 프로세스별 격리

3. **리소스 제한**
   - `max_memory`, `cpu_limit`로 DoS 방지
   - 악의적인 컴포넌트 격리
   - resource.setrlimit 활용

4. **IPC 통신 보안**
   - Unix 소켓 파일 권한 설정
   - 메시지 검증
   - 타임아웃 설정

## Monitoring & Observability

### Metrics

```python
# 프로세스 상태
process_status = "alive" | "dead" | "restarting"

# 재시작 횟수
restart_count = 0

# IPC 지연 시간
ipc_latency_ms = 1.5

# 메모리 사용량
memory_usage_mb = 2048

# CPU 사용량
cpu_usage_percent = 45.2
```

### Logging

```python
logger.info(
    "Process started",
    extra={
        "component_id": "heavy-model",
        "pid": 12345,
        "runtime_config": {
            "env": {"CUDA_VISIBLE_DEVICES": "0"},
            "restart_policy": "always"
        }
    }
)

logger.warning(
    "Process not responding to healthcheck",
    extra={
        "component_id": "heavy-model",
        "pid": 12345,
        "last_heartbeat": "2025-01-01T00:00:00Z"
    }
)

logger.error(
    "Process crashed",
    extra={
        "component_id": "heavy-model",
        "pid": 12345,
        "exit_code": -11,
        "restart_policy": "always",
        "restart_count": 3
    }
)
```

## Migration Guide

### 기존 Native Runtime

**Before:**
```yaml
component:
  type: model
  runtime: native
  task: chat-completion
  model: gpt2
```

**After (프로세스 분리가 필요한 경우):**
```yaml
component:
  type: model
  runtime: process  # native → process로 변경
  task: chat-completion
  model: gpt2
```

### 하위 호환성

`native` 키워드는 `embedded`의 별칭으로 계속 지원:

```python
# runtime.py
class RuntimeType(str, Enum):
    EMBEDDED = "embedded"
    NATIVE = "embedded"     # Alias for backward compatibility
    PROCESS = "process"
    DOCKER = "docker"
```

## Benefits Summary

### 1. 일관된 아키텍처
- `embedded`, `process`, `docker` 통일된 패턴
- 기존 runtime 시스템에 자연스럽게 통합

### 2. 명확한 의미
- `embedded`: 메인 프로세스에 내장
- `process`: 별도 프로세스로 분리
- `docker`: 컨테이너로 격리

### 3. 유연한 선택
```yaml
# 빠른 작업
runtime: embedded

# 무거운 모델
runtime: process

# 프로덕션 배포
runtime: docker
```

### 4. 점진적 마이그레이션
- 기존 컴포넌트 코드 수정 불필요
- Runtime 설정만 변경
- 하위 호환성 유지

## Future Enhancements

1. **Worker Pool**
   - 여러 워커 프로세스를 풀로 관리
   - 동적 스케일링
   - 로드 밸런싱

2. **Distributed Execution**
   - 원격 머신에서 프로세스 실행
   - Ray, Dask 통합
   - 분산 GPU 활용

3. **Container Runtime (확장)**
   - Kubernetes pod에서 실행
   - 자동 스케일링
   - 서비스 메시 통합

4. **GPU Scheduling**
   - 자동 GPU 할당
   - GPU 사용률 모니터링
   - 멀티 GPU 로드 밸런싱

5. **Advanced IPC**
   - Shared memory 지원
   - Zero-copy 전송
   - gRPC 통신

## References

- Python multiprocessing: https://docs.python.org/3/library/multiprocessing.html
- IPC mechanisms: https://en.wikipedia.org/wiki/Inter-process_communication
- Process management best practices
- Resource limiting: https://docs.python.org/3/library/resource.html
- Python embedded interpreter: https://docs.python.org/3/extending/embedding.html

# Component Process Runtime Specification

## Overview

기존 `runtime: native`, `runtime: docker`와 일관성 있게 `runtime: process`를 추가하여 컴포넌트를 별도의 Python 프로세스에서 실행할 수 있는 기능에 대한 스펙입니다.

> **Important**: When implementing this specification, you MUST follow the [Implementation Guidelines](#implementation-guidelines) section. All code must adhere to the coding standards, comment guidelines, and conventions specified there.

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
├─ 같은 메모리       ├─ 독립 메모리      ├─ 컨테이너
├─ 같은 프로세스     ├─ 별도 프로세스     ├─ 가상화
├─ 빠른 실행        ├─ 중간 오버헤드     ├─ 높은 오버헤드
└─ 크래시 전파       └─ 크래시 격리      └─ 완전 격리
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

### 3. 블로킹 작업 분리
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
│                      Main Process                           │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         ComponentService (예: ModelService)          │   │
│  │                                                      │   │
│  │  create_component()                                  │   │
│  │       │                                              │   │
│  │       ├─ __init__() - 컴포넌트 인스턴스 생성          │   │
│  │       │   └─ self._process_manager = None           │   │
│  │       │                                              │   │
│  │       └─ start() ◄── Runtime 체크 (여기서!)          │   │
│  │            │                                         │   │
│  │            ├─ if ProcessRuntimeConfig:               │   │
│  │            │    ProcessRuntimeManager 생성            │   │
│  │            │          │                              │   │
│  │            │          ├─ start() ──────┐             │   │
│  │            │          └─ run()         │             │   │
│  │            │                           │             │   │
│  │            └─ else (Embedded):         │             │   │
│  │                 super().start()        │             │   │
│  │                 wait_until_ready()     │             │   │
│  │                      │                 │             │   │
│  │                      └─ _start()       │             │   │
│  │                           │            │             │   │
│  │                           └─ work_queue.start() 등   │   │
│  │                                        │             │   │
│  └────────────────────────────────────────┼─────────────┘   │
│                                           │                 │
└───────────────────────────────────────────┼─────────────────┘
                                            │
                          IPC Communication │
                          (Queue or Socket) │
                                            │
┌───────────────────────────────────────────┼─────────────────┐
│                   Subprocess              │                 │
│                                           │                 │
│  ┌────────────────────────────────────────▼──────────────┐  │
│  │  ComponentProcessWorker (extends ProcessWorker)       │  │
│  │  - _initialize(): 컴포넌트 생성 및 시작                │  │
│  │  - _execute_task(): 액션 실행                         │  │
│  │  - _cleanup(): 컴포넌트 정리                          │  │
│  │                                                       │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │  ComponentService (Embedded Runtime)            │  │  │
│  │  │  - _run() 등 서브클래스 구현 실행                │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**핵심 포인트:**
1. `create_component()`는 runtime 타입과 무관하게 실제 컴포넌트 타입(Model, Shell 등) 인스턴스 생성
2. `component.start()`에서 runtime 체크 수행 (중요!)
3. Process runtime인 경우:
   - `ProcessRuntimeManager` 생성 및 시작
   - `wait_until_ready()` 호출 안 함 (별도 프로세스이므로)
4. Embedded runtime인 경우:
   - 기존 플로우: `super().start()` → `_start()` → `wait_until_ready()`
   - work_queue 등 기존 로직 실행

## Schema Definition

### 1. RuntimeType 확장

**Location**: `src/mindor/dsl/schema/runtime/impl/types.py`

```python
from enum import Enum

class RuntimeType(str, Enum):
    NATIVE   = "native"
    EMBEDDED = "embedded"
    PROCESS  = "process"
    DOCKER   = "docker"
```

### 2. ProcessRuntimeConfig

**Location**: `src/mindor/dsl/schema/runtime/impl/process.py`

```python
from typing import Literal, Optional, Dict, List
from pydantic import BaseModel, Field
from .common import RuntimeType, CommonRuntimeConfig

class IpcMethod(str, Enum):
    """프로세스 간 통신 방식"""
    QUEUE       = "queue"        # multiprocessing.Queue (cross-platform)
    UNIX_SOCKET = "unix-socket"  # Unix socket (Linux/macOS only)
    NAMED_PIPE  = "named-pipe"   # Named pipes (Windows only)
    TCP_SOCKET  = "tcp-socket"   # TCP socket on localhost (cross-platform)

class ProcessRuntimeConfig(CommonRuntimeConfig):
    """
    별도 Python 프로세스에서 컴포넌트를 실행하는 런타임 설정
    """
    type: Literal[RuntimeType.PROCESS]

    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    working_dir: Optional[str] = Field(None, description="Working directory")

    start_timeout: str = Field(default="60s", description="Process start timeout")
    stop_timeout: str = Field(default="30s", description="Process stop timeout")

    ipc_method: IpcMethod = Field(default=IpcMethod.QUEUE, description="IPC method")
    socket_path: Optional[str] = Field(None, description="Unix socket path (for unix-socket)")
    pipe_name: Optional[str] = Field(None, description="Named pipe name (for named-pipe)")
    tcp_port: Optional[int] = Field(None, description="TCP port (for tcp-socket)")

    max_memory: Optional[str] = Field(None, description="Maximum memory limit")
    cpu_limit: Optional[float] = Field(None, description="CPU limit in cores")
```

### 3. RuntimeConfig Union 업데이트

**Location**: `src/mindor/dsl/schema/runtime/runtime.py`

```python
from typing import Union, Annotated
from pydantic import Field
from .impl import EmbeddedRuntimeConfig, DockerRuntimeConfig, ProcessRuntimeConfig

RuntimeConfig = Annotated[
    Union[
        NativeRuntimeConfig,
        EmbeddedRuntimeConfig,
        ProcessRuntimeConfig,
        DockerRuntimeConfig
    ],
    Field(discriminator="type")
]
```

### 4. EmbeddedRuntimeConfig (신규)

**Location**: `src/mindor/dsl/schema/runtime/impl/embedded.py` (신규 파일)

```python
from typing import Literal
from .common import RuntimeType, CommonRuntimeConfig

class EmbeddedRuntimeConfig(CommonRuntimeConfig):
    """
    메인 프로세스에 내장되어 실행되는 런타임
    Component용 embedded runtime
    """
    type: Literal[RuntimeType.EMBEDDED]
```

**참고**: 기존 `NativeRuntimeConfig`는 Controller에서 사용하므로 그대로 유지됩니다.

## IPC Communication Protocol

### Message Format

**Location**: `src/mindor/core/foundation/ipc_protocol.py`

```python
from typing import Literal, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field
import time

class IpcMessageType(str, Enum):
    START     = "start"
    STOP      = "stop"
    RUN       = "run"
    RESULT    = "result"
    ERROR     = "error"
    HEARTBEAT = "heartbeat"
    STATUS    = "status"
    LOG       = "log"

class IpcMessage(BaseModel):
    """프로세스 간 통신 메시지"""
    type: IpcMessageType
    request_id: str
    payload: Optional[Dict[str, Any]] = None
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))
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
        "input": { "prompt": "Hello" }
    },
    "timestamp": 1234567890123
}

# 실행 결과
{
    "type": "result",
    "request_id": "req-123",
    "payload": {
        "output": { "generated": "Hello! How can I help?" }
    },
    "timestamp": 1234567891456
}

# 에러 응답
{
    "type": "error",
    "request_id": "req-123",
    "payload": {
        "error": "Model failed to load"
    },
    "timestamp": 1234567891789
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
     │──────── run (action, input) ────────▶│
     │                                      │ (액션 실행)
     │◀─────── result (output) ─────────────│
     │                                      │
     │──────── heartbeat ──────────────────▶│
     │◀─────── result (alive) ──────────────│
     │                                      │
     │──────── stop ───────────────────────▶│
     │                                      │ (컴포넌트 종료)
     │◀─────── result (stopped) ────────────│
     │                                      │
```

## Service Implementation

### 1. ProcessRuntimeManager (Base Class)

범용 프로세스 런타임 매니저입니다. Component 맥락을 모르는 추상 계층입니다.

**Location**: `src/mindor/core/foundation/process_manager.py`

```python
from typing import Any, Dict, Optional, Callable
from multiprocessing import Process, Queue
import asyncio
import uuid
import time
from mindor.dsl.schema.runtime import ProcessRuntimeConfig
from mindor.core.logger import logging
from .ipc_protocol import IpcMessage, IpcMessageType


class ProcessRuntimeManager:
    """
    범용 프로세스 런타임 매니저
    Component, Workflow 등 다양한 용도로 사용 가능
    """

    def __init__(
        self,
        worker_id: str,
        runtime_config: ProcessRuntimeConfig,
        worker_factory: Callable[[str, Queue, Queue], Any]
    ):
        """
        Args:
            worker_id: 워커 식별자
            runtime_config: 프로세스 런타임 설정
            worker_factory: 워커 인스턴스를 생성하는 팩토리 함수
                           (worker_id, request_queue, response_queue) -> Worker
        """
        self.worker_id = worker_id
        self.runtime_config = runtime_config
        self.worker_factory = worker_factory

        self.subprocess: Optional[Process] = None
        self.request_queue: Optional[Queue] = None
        self.response_queue: Optional[Queue] = None
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self.response_handler_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """서브프로세스 시작"""
        # IPC 큐 생성
        self.request_queue  = Queue()
        self.response_queue = Queue()

        # 서브프로세스 생성 및 시작
        self.subprocess = Process(
            target=self._run_worker,
            args=(
                self.worker_id,
                self.request_queue,
                self.response_queue
            ),
            daemon=False
        )

        # 환경 변수 설정
        if self.runtime_config.env:
            import os
            for key, value in self.runtime_config.env.items():
                os.environ[key] = value

        self.subprocess.start()
        logging.info(f"Started subprocess for worker {self.worker_id} (PID: {self.subprocess.pid})")

        # 준비 완료 대기
        await self._wait_for_ready()

        # 응답 핸들러 시작
        self.response_handler_task = asyncio.create_task(
            self._handle_responses()
        )

    async def stop(self) -> None:
        """서브프로세스 종료"""
        logging.info(f"Stopping subprocess for worker {self.worker_id}")

        # 종료 요청 전송
        stop_message = IpcMessage(
            type=IpcMessageType.STOP,
            request_id=str(uuid.uuid4())
        )
        self.request_queue.put(stop_message.model_dump())

        # 타임아웃과 함께 종료 대기
        try:
            self.subprocess.join(timeout=self.runtime_config.stop_timeout)
        except TimeoutError:
            logging.warning(f"Process {self.worker_id} did not stop gracefully, terminating")
            self.subprocess.terminate()
            self.subprocess.join(timeout=5)
            if self.subprocess.is_alive():
                logging.error(f"Process {self.worker_id} did not terminate, killing")
                self.subprocess.kill()

        # 태스크 취소
        if self.response_handler_task:
            self.response_handler_task.cancel()

    async def execute(self, payload: Dict[str, Any]) -> Any:
        """태스크 실행 요청을 서브프로세스로 전달"""
        request_id = str(uuid.uuid4())

        message = IpcMessage(
            type=IpcMessageType.RUN,
            request_id=request_id,
            payload=payload
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
                    message = IpcMessage(**message_dict)

                    if message.request_id in self.pending_requests:
                        future = self.pending_requests[message.request_id]

                        if message.type == IpcMessageType.RESULT:
                            future.set_result(message.payload.get("output"))
                        elif message.type == IpcMessageType.ERROR:
                            error = message.payload.get("error", "Unknown error")
                            future.set_exception(Exception(error))

                await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Error handling response: {e}")

    async def _wait_for_ready(self) -> None:
        """서브프로세스 준비 대기"""
        timeout = self.runtime_config.start_timeout
        start_time = time.time()

        while time.time() - start_time < timeout:
            if not self.response_queue.empty():
                message_dict = self.response_queue.get()
                message = IpcMessage(**message_dict)

                if message.type == IpcMessageType.RESULT and \
                   message.payload.get("status") == "ready":
                    logging.info(f"Subprocess {self.worker_id} is ready")
                    return

            await asyncio.sleep(0.5)

        raise TimeoutError(
            f"Process {self.worker_id} did not start within {timeout}s"
        )

    def _run_worker(
        self,
        worker_id: str,
        request_queue: Queue,
        response_queue: Queue
    ) -> None:
        """서브프로세스 엔트리포인트"""
        # 새 이벤트 루프 생성
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # 워커 팩토리를 통해 워커 생성
        worker = self.worker_factory(worker_id, request_queue, response_queue)

        try:
            loop.run_until_complete(worker.run())
        except KeyboardInterrupt:
            pass
        finally:
            loop.close()
```

### 2. ComponentProcessRuntimeManager

Component 전용 프로세스 런타임 매니저입니다.

**Location**: `src/mindor/core/component/runtime/process_manager.py`

```python
from typing import Any, Dict
from multiprocessing import Queue
from mindor.core.foundation import ProcessRuntimeManager
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.runtime import ComponentProcessWorker
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.runtime import ProcessRuntimeConfig


class ComponentProcessRuntimeManager(ProcessRuntimeManager):
    """
    Component 전용 프로세스 런타임 매니저
    ComponentService의 _start() 시점에 생성됨
    """

    def __init__(
        self,
        component_id: str,
        config: ComponentConfig,
        global_configs: ComponentGlobalConfigs
    ):
        if not isinstance(config.runtime, ProcessRuntimeConfig):
            raise ValueError("ComponentProcessRuntimeManager requires ProcessRuntimeConfig")

        self.config = config
        self.global_configs = global_configs

        # 워커 팩토리 함수 정의
        def worker_factory(worker_id: str, req_queue: Queue, res_queue: Queue):
            return ComponentProcessWorker(
                worker_id,
                config,
                global_configs,
                req_queue,
                res_queue
            )

        # 부모 클래스 초기화
        super().__init__(
            worker_id=component_id,
            runtime_config=config.runtime,
            worker_factory=worker_factory
        )

    async def run(
        self,
        action_id: str,
        run_id: str,
        input_data: Dict[str, Any]
    ) -> Any:
        """Component 액션 실행"""
        payload = {
            "action_id": action_id,
            "run_id": run_id,
            "input": input_data
        }
        return await self.execute(payload)
```

### 3. ProcessWorker (Base Class)

범용 프로세스 워커 기반 클래스입니다. Component 뿐만 아니라 다양한 용도로 확장 가능합니다.

**Location**: `src/mindor/core/foundation/process_worker.py`

```python
from typing import Any, Dict
from abc import ABC, abstractmethod
from multiprocessing import Queue
import asyncio
from mindor.core.logger import logging
from .ipc_protocol import IpcMessage, IpcMessageType


class ProcessWorker(ABC):
    """
    Base class for workers running in separate processes.

    This is a generic process worker that can be extended for various use cases
    beyond just components (e.g., workflow execution, data processing, etc.)
    """

    def __init__(
        self,
        worker_id: str,
        request_queue: Queue,
        response_queue: Queue
    ):
        self.worker_id = worker_id
        self.request_queue = request_queue
        self.response_queue = response_queue
        self.running = True

    async def run(self) -> None:
        """Main worker loop - handles initialization, message processing, and cleanup"""
        try:
            # Initialize the worker
            await self._initialize()

            logging.info(f"ProcessWorker {self.worker_id} initialized in subprocess")

            # Send ready signal
            ready_message = IpcMessage(
                type=IpcMessageType.RESULT,
                request_id="init",
                payload={"status": "ready"}
            )
            self.response_queue.put(ready_message.model_dump())

            # Process messages
            while self.running:
                if not self.request_queue.empty():
                    message_dict = self.request_queue.get()
                    message = IpcMessage(**message_dict)
                    await self._handle_message(message)

                await asyncio.sleep(0.01)

        except Exception as e:
            logging.error(f"Worker error: {e}")
            error_message = IpcMessage(
                type=IpcMessageType.ERROR,
                request_id="worker",
                payload={"error": str(e)}
            )
            self.response_queue.put(error_message.model_dump())

        finally:
            await self._cleanup()

    async def _handle_message(self, message: IpcMessage) -> None:
        """Handle incoming messages from the main process"""
        try:
            if message.type == IpcMessageType.RUN:
                # Execute the task
                output = await self._execute_task(message.payload)

                response = IpcMessage(
                    type=IpcMessageType.RESULT,
                    request_id=message.request_id,
                    payload={"output": output}
                )
                self.response_queue.put(response.model_dump())

            elif message.type == IpcMessageType.HEARTBEAT:
                response = IpcMessage(
                    type=IpcMessageType.RESULT,
                    request_id=message.request_id,
                    payload={"status": "alive"}
                )
                self.response_queue.put(response.model_dump())

            elif message.type == IpcMessageType.STOP:
                self.running = False
                response = IpcMessage(
                    type=IpcMessageType.RESULT,
                    request_id=message.request_id,
                    payload={"status": "stopped"}
                )
                self.response_queue.put(response.model_dump())

        except Exception as e:
            logging.error(f"Error handling message: {e}")
            error_response = IpcMessage(
                type=IpcMessageType.ERROR,
                request_id=message.request_id,
                payload={"error": str(e)}
            )
            self.response_queue.put(error_response.model_dump())

    @abstractmethod
    async def _initialize(self) -> None:
        """
        Initialize the worker (e.g., load models, connect to services, etc.)

        This method is called once when the worker process starts.
        """
        pass

    @abstractmethod
    async def _execute_task(self, payload: Dict[str, Any]) -> Any:
        """
        Execute a task with the given payload.

        This is the main work method that subclasses should implement
        to perform their specific work.

        Args:
            payload: Task-specific data from the main process

        Returns:
            Task result to be sent back to the main process
        """
        pass

    @abstractmethod
    async def _cleanup(self) -> None:
        """
        Clean up resources before the worker exits.

        This method is called when the worker is stopping.
        """
        pass
```

### 4. ComponentProcessWorker

Component를 프로세스에서 실행하는 구체적 구현입니다.

**Location**: `src/mindor/core/component/runtime/process_worker.py`

```python
from typing import Any, Dict
from multiprocessing import Queue
from mindor.core.foundation import ProcessWorker
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.component import create_component
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.runtime import EmbeddedRuntimeConfig
from mindor.core.logger import logging


class ComponentProcessWorker(ProcessWorker):
    """
    Component를 서브프로세스에서 실행하는 워커
    """

    def __init__(
        self,
        component_id: str,
        config: ComponentConfig,
        global_configs: ComponentGlobalConfigs,
        request_queue: Queue,
        response_queue: Queue
    ):
        super().__init__(component_id, request_queue, response_queue)
        self.config = config
        self.global_configs = global_configs
        self.component = None

    async def _initialize(self) -> None:
        """컴포넌트를 초기화하고 시작"""
        # Embedded runtime으로 컴포넌트 생성
        # (프로세스는 이미 분리되었으므로 embedded로 실행)
        embedded_config = self.config.model_copy(deep=True)
        embedded_config.runtime = EmbeddedRuntimeConfig(type="embedded")

        self.component = create_component(
            self.worker_id,
            embedded_config,
            self.global_configs,
            daemon=True
        )

        # 컴포넌트 시작
        await self.component.setup()
        await self.component.start()

        logging.info(f"Component {self.worker_id} started in subprocess")

    async def _execute_task(self, payload: Dict[str, Any]) -> Any:
        """컴포넌트 액션 실행"""
        action_id = payload["action_id"]
        run_id = payload["run_id"]
        input_data = payload["input"]

        output = await self.component.run(action_id, run_id, input_data)
        return output

    async def _cleanup(self) -> None:
        """컴포넌트를 정리"""
        if self.component:
            await self.component.stop()
            await self.component.teardown()
```

### 5. ComponentService Lifecycle 수정

**Location**: `src/mindor/core/component/base.py`

**참고**: `create_component()` 함수는 변경 없음 (runtime 타입과 무관하게 동작)

```python
class ComponentService(AsyncService):
    """Base class for all component services"""

    def __init__(self, id: str, config: ComponentConfig, global_configs: ComponentGlobalConfigs, daemon: bool):
        super().__init__(daemon)
        self.id = id
        self.config = config
        self.global_configs = global_configs
        self.work_queue = None
        self._process_manager = None  # Process runtime용

        if self.config.max_concurrent_count > 0:
            self.work_queue = WorkQueue(self.config.max_concurrent_count, self._run)

    async def start(self, background: bool = False) -> None:
        """
        Public start method - 여기서 runtime 타입에 따라 분기
        """
        # Process runtime인 경우 별도 프로세스에서 실행
        if isinstance(self.config.runtime, ProcessRuntimeConfig):
            from mindor.core.component.runtime import ComponentProcessRuntimeManager

            self._process_manager = ComponentProcessRuntimeManager(
                self.id,
                self.config,
                self.global_configs
            )
            await self._process_manager.start()
            logging.info(f"Component {self.id} started in separate process")
        else:
            # Embedded runtime - 기존 로직 실행
            await super().start(background)
            await self.wait_until_ready()

    async def run(self, action_id: str, run_id: str, input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Public run method - runtime 타입에 따라 분기
        """
        # Process runtime인 경우 프로세스 매니저를 통해 실행
        if self._process_manager:
            return await self._process_manager.run(action_id, run_id, input)

        # Embedded runtime - 기존 로직
        _, action = ActionResolver(self.config.actions).resolve(action_id)
        context = ComponentActionContext(run_id, input)

        if self.work_queue:
            return await (await self.work_queue.schedule(action, context))

        return await self._run(action, context)

    async def _start(self) -> None:
        """
        Internal start method - Embedded runtime에서 실행
        """
        # Embedded runtime - 기존 로직 실행
        if self.work_queue:
            await self.work_queue.start()

        await super()._start()

    async def stop(self) -> None:
        """
        Public stop method - runtime 타입에 따라 분기
        """
        # Process runtime인 경우 프로세스 매니저 종료
        if self._process_manager:
            await self._process_manager.stop()
        else:
            # Embedded runtime - 기존 로직 실행
            await super().stop()

    async def _stop(self) -> None:
        """
        Internal stop method - Embedded runtime에서 실행
        """
        # Embedded runtime - 기존 로직 실행
        if self.work_queue:
            await self.work_queue.stop()

        await super()._stop()

    @abstractmethod
    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        """
        Internal run method - Embedded runtime에서 실행
        서브클래스에서 구현
        """
        pass
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
    start_timeout: 2m
    stop_timeout: 30s
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

### Example 4: 플랫폼별 고성능 IPC 설정

```yaml
# Unix 시스템 (Linux/macOS)에서 고성능 IPC
component:
  type: model
  runtime:
    type: process
    ipc_method: unix-socket
    socket_path: /tmp/model-compose-{component_id}.sock
  task: text-generation
  model: meta-llama/Llama-3.1-70B
```

```yaml
# Windows에서 고성능 IPC
component:
  type: model
  runtime:
    type: process
    ipc_method: named-pipe
    pipe_name: \\.\pipe\model-compose-{component_id}
  task: text-generation
  model: meta-llama/Llama-3.1-70B
```

```yaml
# 크로스 플랫폼 TCP 소켓 (네트워크 오버헤드 있음)
component:
  type: model
  runtime:
    type: process
    ipc_method: tcp-socket
    tcp_port: 0  # 자동 포트 할당
  task: text-generation
  model: meta-llama/Llama-3.1-70B
```

### Example 5: Runtime 비교

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
│               ├── native.py           # (기존) NativeRuntimeConfig (Controller용)
│               ├── embedded.py         # (신규) EmbeddedRuntimeConfig (Component용)
│               ├── process.py          # (신규) ProcessRuntimeConfig
│               └── docker.py
│
└── core/
    ├── foundation/
    │   ├── __init__.py                 # (수정) Export 업데이트
    │   ├── async_service.py            # (기존)
    │   ├── ipc_protocol.py             # (신규) IpcMessage, IpcMessageType
    │   ├── process_manager.py          # (신규) ProcessRuntimeManager (범용)
    │   └── process_worker.py           # (신규) ProcessWorker 기반 클래스
    │
    ├── component/
    │   ├── component.py                # (변경 없음)
    │   ├── base.py                     # (수정) ComponentService 메서드 수정
    │   └── runtime/
    │       ├── __init__.py
    │       ├── process_manager.py      # (신규) ComponentProcessRuntimeManager
    │       └── process_worker.py       # (신규) ComponentProcessWorker
    │
    └── runtime/
        └── process/                    # (삭제 - component/runtime으로 이동)
```

**주요 변경사항:**
- `ProcessRuntimeManager` 범용 기반 클래스를 `core/foundation`에 추가
- `ProcessWorker` 기반 클래스를 `core/foundation`에 추가
- `IpcMessage`, `IpcMessageType`을 `core/foundation/ipc_protocol.py`로 추가
- `ComponentProcessRuntimeManager`를 `core/component/runtime/process_manager.py`에 구현
- `ComponentProcessWorker`를 `core/component/runtime/process_worker.py`에 구현
- `NativeRuntimeConfig`는 Controller용으로 유지
- `EmbeddedRuntimeConfig`를 Component용으로 신규 추가
- `ComponentService.base`에 `_start()`, `_stop()`, `run()` 메서드 수정
- `create_component()`는 변경 없음

## Implementation Guidelines

### Code Style

1. **Comments**
   - Write all comments in English
   - Avoid excessive comments
   - Do not add comments where the code is self-explanatory
   - Focus on "why" rather than "what" when commenting

2. **Pydantic Models (Config Classes)**
   - Follow existing codebase conventions
   - Reference similar config files for consistent style
   - Use Field() for default values and descriptions
   - Maintain consistent ordering: required fields first, optional fields after

3. **Code Organization**
   - Keep methods focused and single-purpose
   - Follow existing patterns in the codebase
   - Use type hints consistently

### Examples

**Good - Minimal, necessary comments:**
```python
class ProcessRuntimeConfig(CommonRuntimeConfig):
    type: Literal[RuntimeType.PROCESS]

    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables")

    # Timeout for process initialization (loading models, etc.)
    start_timeout: str = Field(default="60s", description="Process start timeout")
```

**Bad - Excessive, redundant comments:**
```python
class ProcessRuntimeConfig(CommonRuntimeConfig):
    # The type field
    type: Literal[RuntimeType.PROCESS]

    # Dictionary for environment variables
    env: Dict[str, str] = Field(
        default_factory=dict,  # Use factory for mutable default
        description="Environment variables for the subprocess"
    )

    # Start timeout field - this is the timeout for starting
    start_timeout: str = Field(
        default="60s",  # Default is 60 seconds
        description="Process start timeout in seconds"
    )
```

## Implementation Plan

### Phase 1: Core Infrastructure (MVP)
**목표**: 기본 프로세스 분리 동작

**Task List:**
- [ ] Runtime 스키마 확장
  - `RuntimeType.EMBEDDED` 추가
  - `RuntimeType.PROCESS` 추가
  - `ProcessRuntimeConfig` 정의
  - `EmbeddedRuntimeConfig` 신규 추가 (Component용)
  - `NativeRuntimeConfig` 유지 (Controller용)
  - `RuntimeConfig` union 업데이트

- [ ] IPC 프로토콜 정의 (`core/foundation/ipc_protocol.py`)
  - `IpcMessage` 모델
  - `IpcMessageType` enum
  - Protocol 문서화

- [ ] ProcessWorker 기반 클래스 구현 (`core/foundation/process_worker.py`)
  - 추상 메서드: `_initialize()`, `_execute_task()`, `_cleanup()`
  - 공통 메시지 처리 로직
  - 워커 생명주기 관리

- [ ] ProcessRuntimeManager 범용 구현 (`core/foundation/process_manager.py`)
  - Component 맥락 없는 범용 프로세스 매니저
  - 워커 팩토리 패턴 사용
  - 프로세스 생성/관리
  - IPC 통신 (Queue 방식)
  - 요청/응답 매칭

- [ ] ComponentProcessWorker 구현 (`core/runtime/process/worker.py`)
  - `ProcessWorker` 상속
  - 컴포넌트 생성 및 시작
  - 액션 실행 로직

- [ ] ComponentProcessRuntimeManager 구현 (`core/runtime/process/component_manager.py`)
  - `ProcessRuntimeManager` 상속
  - Component 전용 편의 메서드 (`run`)
  - ComponentProcessWorker 팩토리 제공

- [ ] ComponentService 수정 (`src/mindor/core/component/base.py`)
  - `__init__()`에 `self._process_manager = None` 추가
  - `start()` 메서드에 runtime 체크 로직 추가 (중요: _start()가 아님!)
  - Process runtime인 경우:
    - `ComponentProcessRuntimeManager` 생성 및 시작
    - `wait_until_ready()` 호출 안 함
  - Embedded runtime인 경우:
    - 기존 플로우: `super().start()` → `_start()` → `wait_until_ready()`
  - `stop()` 메서드에 runtime 분기 추가
  - `_stop()` 메서드는 Embedded runtime 로직만 포함
  - `run()` 메서드에 `_process_manager.run()` 호출 추가
  - `_run()`은 기존 추상 메서드 그대로 유지

**검증:**
- 간단한 shell 컴포넌트 프로세스 분리 테스트
- Model 컴포넌트 프로세스 분리 테스트

### Phase 2: Advanced Features
**목표**: 고급 기능 및 최적화

**Task List:**
- [ ] 고성능 IPC 지원
  - `ipc_method: unix-socket` 구현 (Linux/macOS)
  - `ipc_method: named-pipe` 구현 (Windows)
  - `ipc_method: tcp-socket` 구현 (cross-platform fallback)
  - 플랫폼별 자동 선택 로직
  - 성능 벤치마크 (Queue vs Unix Socket vs Named Pipe)

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

### Phase 3: Testing & Documentation
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

**Location**: `tests/core/runtime/process/test_manager.py`

```python
import pytest
from mindor.core.runtime.process.manager import ProcessRuntimeManager
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.runtime import ProcessRuntimeConfig

@pytest.mark.asyncio
async def test_manager_start_stop():
    """매니저 시작/종료 테스트"""
    config = ComponentConfig(
        id="test",
        type="model",
        runtime=ProcessRuntimeConfig(type="process"),
        task="chat-completion",
        model="gpt2"
    )

    manager = ProcessRuntimeManager("test", config, global_configs)

    # 시작
    await manager.start()
    assert manager.subprocess is not None
    assert manager.subprocess.is_alive()

    # 종료
    await manager.stop()
    assert not manager.subprocess.is_alive()

@pytest.mark.asyncio
async def test_manager_run():
    """액션 실행 테스트"""
    manager = create_test_manager()
    await manager.start()

    result = await manager.run("generate", "run-1", {"prompt": "Hello"})

    assert result is not None
    assert "generated" in result

    await manager.stop()

```

**Location**: `tests/core/component/test_component_lifecycle.py`

```python
import pytest
from mindor.core.component.component import create_component
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.runtime import ProcessRuntimeConfig, EmbeddedRuntimeConfig

@pytest.mark.asyncio
async def test_component_process_runtime():
    """Process runtime으로 컴포넌트 시작 테스트"""
    config = ComponentConfig(
        id="test-model",
        type="model",
        runtime=ProcessRuntimeConfig(type="process"),
        task="text-generation",
        model="gpt2"
    )

    # 컴포넌트 생성 (프로세스는 아직 시작 안됨)
    component = create_component("test-model", config, global_configs, False)
    assert component is not None
    assert not hasattr(component, '_process_manager')

    # 시작 (이 시점에 프로세스 시작)
    await component.start()
    assert hasattr(component, '_process_manager')
    assert component._process_manager.subprocess.is_alive()

    # 종료
    await component.stop()
    assert not component._process_manager.subprocess.is_alive()

@pytest.mark.asyncio
async def test_component_embedded_runtime():
    """Embedded runtime으로 컴포넌트 시작 테스트"""
    config = ComponentConfig(
        id="test-model",
        type="model",
        runtime=EmbeddedRuntimeConfig(type="embedded"),
        task="text-generation",
        model="gpt2"
    )

    component = create_component("test-model", config, global_configs, False)

    # 시작 (메인 프로세스에서 실행)
    await component.start()
    assert not hasattr(component, '_process_manager')

    await component.stop()
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
       raise
   ```

2. **프로세스 크래시**
   ```python
   if not subprocess.is_alive():
       raise ProcessCrashedError("Component process crashed")
   ```

3. **IPC 통신 실패**
   ```python
   try:
       result = await send_request(message, timeout=30)
   except asyncio.TimeoutError:
       logging.error("IPC communication timeout")
       raise
   ```

4. **리소스 부족**
   ```python
   # 메모리 제한 초과 시 OOM 킬러 작동
   raise ResourceExhaustedError("Process killed due to resource limits")
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

Different IPC methods have varying performance characteristics:

| IPC Method | Platform | Speed | Overhead | Best For |
|------------|----------|-------|----------|----------|
| **queue** | All | Medium | Medium | Default, reliable cross-platform |
| **unix-socket** | Linux/macOS | Fast | Low | High-performance on Unix systems |
| **named-pipe** | Windows | Fast | Low | High-performance on Windows |
| **tcp-socket** | All | Slow | High | Cross-platform with network overhead |

**권장사항**:
- **기본 사용**: `queue` (모든 플랫폼에서 안정적)
- **고성능 (Unix)**: `unix-socket` (Linux/macOS)
- **고성능 (Windows)**: `named-pipe` (Windows 전용)
- **플랫폼 자동 선택**:
  ```python
  ipc_method = "named-pipe" if platform.system() == "Windows" else "unix-socket"
  ```

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
process_status = "alive" | "dead"

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
            "env": {"CUDA_VISIBLE_DEVICES": "0"}
        }
    }
)

logger.error(
    "Process crashed",
    extra={
        "component_id": "heavy-model",
        "pid": 12345,
        "exit_code": -11
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

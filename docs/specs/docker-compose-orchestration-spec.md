# Docker Compose-like Orchestration Specification

## Overview

Docker Compose와 유사한 멀티 컨테이너 오케스트레이션 기능을 model-compose에 통합하여, 여러 Docker 컨테이너를 선언적으로 정의하고 한번에 관리할 수 있도록 하는 스펙입니다.

## Design Goals

1. **멀티 컨테이너 관리**: 여러 컨테이너를 하나의 설정으로 정의하고 관리
2. **Docker Compose 스타일 출력**: 컨테이너별 색상 구분 및 로그 prefix
3. **생명주기 통합 관리**: 모든 컨테이너를 한번에 시작/중지/재시작
4. **Singleton 패턴**: 전역 오케스트레이션 매니저로 상태 관리
5. **병렬 로그 스트리밍**: 모든 컨테이너의 로그를 실시간으로 병합 출력
6. **의존성 관리**: 컨테이너 간 시작 순서 및 헬스체크 지원

## Architecture

### Registration-Based Orchestration

controller나 component에서 Docker 런타임을 사용할 때, `DockerComposeManager` (Singleton)에 자동으로 등록되고, 매니저가 모든 컨테이너를 한번에 관리합니다.

**플로우**:
1. Controller/Component가 Docker 런타임 설정을 가지고 있음
2. 시작 시 `DockerComposeManager.register(name, config)` 호출
3. 모든 등록이 완료되면 `DockerComposeManager.up()` 한번에 실행
4. 종료 시 `DockerComposeManager.down()` 한번에 중지

### Core Components

#### 1. `DockerComposeManager` - Singleton Orchestrator

**Features**:
- **컨테이너 등록 시스템**: Controller/Component가 동적으로 등록
- **멀티 컨테이너 통합 관리**: 등록된 모든 컨테이너를 한번에 시작/중지
- **컨테이너별 색상 할당**: ANSI colors로 로그 구분
- **병렬 로그 스트리밍**: 모든 컨테이너 로그를 prefix와 함께 출력
- **의존성 순서 관리**: 등록 순서 또는 명시적 의존성에 따라 시작
- **Graceful shutdown**: Ctrl+C 시 모든 컨테이너 정리
- **헬스체크 기반 대기**: 컨테이너가 준비될 때까지 대기

#### 2. `DockerRuntimeManager` - Individual Container Manager

개별 컨테이너를 관리하는 기존 매니저 (수정 필요).

**Features**:
- 단일 컨테이너 생명주기 관리
- **DockerComposeManager 자동 등록**: 생성 시 자동으로 등록
- 로그 스트리밍 (prefix 추가)
- 컨테이너 상태 모니터링

#### 3. `ContainerLogStream` - Log Multiplexer

여러 컨테이너의 로그를 병합하여 출력하는 스트림 핸들러.

**Features**:
- 컨테이너별 로그 prefix 추가
- ANSI 색상 코드 적용
- 타임스탬프 옵션
- Thread-safe 출력

## Component Schema

### Extended DockerRuntimeConfig

기존 `DockerRuntimeConfig`에 필드 추가:

```python
class DockerRuntimeConfig(BaseModel):
    # ... 기존 필드들 ...

    # 의존성 (새로 추가, 옵션)
    depends_on: Optional[List[str]] = Field(
        None,
        description="의존하는 컨테이너 이름 목록"
    )

    # 로그 색상 (새로 추가, 옵션)
    log_color: Optional[str] = Field(
        None,
        description="로그 출력 색상 (ANSI color code)"
    )
```


## Service Implementation

### 1. DockerComposeManager (Singleton)

**Location**: `src/mindor/core/runtime/docker/compose.py`

```python
from typing import Dict, List, Optional, Set
from mindor.dsl.schema.runtime import DockerRuntimeConfig
from mindor.core.runtime.docker import DockerRuntimeManager
from mindor.core.logger import logging
import docker
import asyncio
import sys
from datetime import datetime

class DockerComposeManager:
    """
    Docker Compose 스타일의 멀티 컨테이너 오케스트레이션 매니저 (Singleton)

    Controller/Component가 Docker 런타임을 사용할 때 자동으로 등록되고,
    모든 컨테이너를 한번에 시작/중지합니다.
    """

    _instance: Optional['DockerComposeManager'] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Singleton이므로 이미 초기화된 경우 skip
        if hasattr(self, '_initialized'):
            return

        self.docker_client = docker.from_env()

        # 등록된 컨테이너들 (name -> DockerRuntimeConfig)
        self.containers: Dict[str, DockerRuntimeConfig] = {}
        self.managers: Dict[str, DockerRuntimeManager] = {}

        # 로그 출력 설정
        self.verbose: bool = False
        self.show_timestamp: bool = True
        self.container_name_width: int = 20
        self.use_colors: bool = True

        # 컨테이너 상태
        self.container_states: Dict[str, str] = {}  # name -> status
        self.startup_order: List[str] = []
        self.shutdown_order: List[str] = []

        # 로그 스트리밍
        self.log_streams: Dict[str, asyncio.Task] = {}
        self.shutdown_event: asyncio.Event = asyncio.Event()

        # 색상 팔레트
        self.color_palette = [
            '\033[36m',  # Cyan
            '\033[33m',  # Yellow
            '\033[32m',  # Green
            '\033[35m',  # Magenta
            '\033[34m',  # Blue
            '\033[31m',  # Red
            '\033[96m',  # Bright Cyan
            '\033[93m',  # Bright Yellow
            '\033[92m',  # Bright Green
            '\033[95m',  # Bright Magenta
        ]
        self.color_reset = '\033[0m'
        self.container_colors: Dict[str, str] = {}
        self._next_color_idx = 0

        self._initialized = True

    @classmethod
    async def get_instance(cls) -> 'DockerComposeManager':
        """싱글톤 인스턴스 가져오기 (thread-safe)"""
        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def register(
        self,
        name: str,
        config: DockerRuntimeConfig
    ) -> None:
        """
        컨테이너 등록

        Args:
            name: 컨테이너 식별자 (예: "controller", "redis", "postgres")
            config: Docker 런타임 설정
        """
        if name in self.containers:
            logging.warning(f"Container '{name}' is already registered. Skipping.")
            return

        # 색상 할당 (사용자 지정 또는 자동)
        if not config.log_color:
            config.log_color = self._assign_next_color()

        self.containers[name] = config
        self.container_colors[name] = config.log_color

        logging.debug(f"Registered container '{name}'")

    def _assign_next_color(self) -> str:
        """다음 색상 할당"""
        color = self.color_palette[self._next_color_idx % len(self.color_palette)]
        self._next_color_idx += 1
        return color

    def set_verbose(self, verbose: bool):
        """Verbose 모드 설정"""
        self.verbose = verbose

    async def prepare(self):
        """
        컨테이너 시작 준비
        - 의존성 순서 계산
        - DockerRuntimeManager 인스턴스 생성
        """
        if not self.containers:
            logging.warning("No containers registered")
            return

        # 의존성 순서 계산
        self.startup_order = self._calculate_dependency_order()
        self.shutdown_order = list(reversed(self.startup_order))

        # DockerRuntimeManager 인스턴스 생성
        for name in self.startup_order:
            config = self.containers[name]
            self.managers[name] = DockerRuntimeManager(
                config=config,
                verbose=self.verbose,
                log_prefix=name,  # 로그 prefix로 컨테이너 이름 사용
                log_color=config.log_color
            )

        logging.info(f"Container startup order: {' -> '.join(self.startup_order)}")

    def _calculate_dependency_order(self) -> List[str]:
        """의존성 기반 시작 순서 계산 (Topological Sort)"""
        # 의존성 그래프 구성
        graph: Dict[str, List[str]] = {name: [] for name in self.containers}
        in_degree: Dict[str, int] = {name: 0 for name in self.containers}

        for name, config in self.containers.items():
            if config.depends_on:
                for dep_name in config.depends_on:
                    if dep_name not in self.containers:
                        raise ValueError(f"Container '{name}' depends on unknown container '{dep_name}'")
                    graph[dep_name].append(name)
                    in_degree[name] += 1

        # Topological sort (Kahn's algorithm)
        queue = [name for name, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            current = queue.pop(0)
            result.append(current)

            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # 순환 의존성 체크
        if len(result) != len(self.containers):
            raise ValueError("Circular dependency detected in container dependencies")

        return result

    async def up(self, detach: bool = False):
        """
        모든 컨테이너 시작 (Docker Compose up)

        Args:
            detach: Detached 모드 (백그라운드 실행)
        """
        if not self.containers:
            logging.warning("No containers to start")
            return

        # 준비 (의존성 계산, 매니저 생성)
        await self.prepare()

        self._log_info("Starting containers...")

        try:
            # 순차적으로 시작 (의존성 순서 보장)
            await self._start_containers_sequential(detach)

            if not detach:
                # Foreground 모드: 로그 스트리밍 시작
                await self._stream_all_logs()
        except Exception as e:
            self._log_error(f"Failed to start containers: {e}")
            raise

    async def _start_containers_sequential(self, detach: bool):
        """컨테이너들을 순차적으로 시작 (의존성 순서)"""
        for name in self.startup_order:
            self._log_container_action(name, "Creating")
            manager = self.managers[name]
            config = self.containers[name]

            # 의존성 대기
            if config.depends_on:
                await self._wait_for_dependencies(config.depends_on)

            # 컨테이너 시작
            await manager.start_container(detach=True)
            self.container_states[name] = "running"

            self._log_container_action(name, "Started")

            # 헬스체크 대기 (옵션)
            if config.healthcheck:
                await self._wait_for_healthy(name)

    async def down(self, remove_volumes: bool = False):
        """모든 컨테이너 중지 및 제거 (Docker Compose down)"""
        self._log_info("Stopping containers...")

        # Shutdown 신호
        self.shutdown_event.set()

        # 로그 스트림 중지
        await self._stop_all_log_streams()

        # 컨테이너 중지 (역순)
        for name in self.shutdown_order:
            self._log_container_action(name, "Stopping")
            manager = self.managers[name]

            try:
                await manager.stop_container()
                await manager.remove_container(force=True)
                self._log_container_action(name, "Removed")
            except Exception as e:
                self._log_error(f"Failed to stop {name}: {e}")

        self._log_info("All containers stopped")

    async def _stream_all_logs(self):
        """모든 컨테이너의 로그를 병렬로 스트리밍"""
        # 각 컨테이너의 로그 스트리밍 태스크 생성
        for name in self.containers:
            task = asyncio.create_task(self._stream_container_logs(name))
            self.log_streams[name] = task

        # Shutdown 시그널 대기
        await self.shutdown_event.wait()

    async def _stream_container_logs(self, container_name: str):
        """개별 컨테이너 로그 스트리밍 (with prefix)"""
        try:
            manager = self.managers[container_name]
            config = self.containers[container_name]
            container = self.docker_client.containers.get(
                config.container_name
            )

            # 로그 스트림 시작
            for line in container.logs(stream=True, follow=True, since=int(asyncio.get_event_loop().time())):
                if self.shutdown_event.is_set():
                    break

                # 로그 포맷팅
                formatted_line = self._format_log_line(container_name, line)
                sys.stdout.write(formatted_line)
                sys.stdout.flush()

        except Exception as e:
            self._log_error(f"Error streaming logs from {container_name}: {e}")

    def _format_log_line(self, container_name: str, line: bytes) -> str:
        """로그 라인 포맷팅 (Docker Compose 스타일)"""
        decoded = line.decode('utf-8', errors='replace').rstrip()

        # 타임스탬프
        timestamp = ""
        if self.show_timestamp:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            timestamp = f"[{now}] "

        # 컨테이너 이름 (색상 적용)
        color = self.container_colors.get(container_name, "")
        reset = self.color_reset if self.use_colors else ""

        name_width = self.container_name_width
        padded_name = container_name.ljust(name_width)

        prefix = f"{color}{padded_name}{reset} | "

        return f"{timestamp}{prefix}{decoded}\n"

    async def _wait_for_dependencies(self, dep_names: List[str]):
        """의존성 컨테이너들이 준비될 때까지 대기"""
        for dep_name in dep_names:
            # 시작만 확인
            while dep_name not in self.container_states:
                await asyncio.sleep(0.5)

    async def _wait_for_healthy(self, container_name: str):
        """컨테이너 헬스체크 통과 대기"""
        config = self.containers[container_name]

        if not config.healthcheck:
            return

        retries = 0
        max_retries = 30  # 헬스체크 재시도 횟수

        while retries < max_retries:
            container = self.docker_client.containers.get(config.container_name)

            health = container.attrs.get('State', {}).get('Health', {})
            status = health.get('Status', 'none')

            if status == 'healthy':
                self._log_container_action(container_name, "Healthy")
                return

            await asyncio.sleep(1)  # 헬스체크 간격
            retries += 1

        raise TimeoutError(f"Container {container_name} failed to become healthy")

    async def _stop_all_log_streams(self):
        """모든 로그 스트림 중지"""
        for name, task in self.log_streams.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self.log_streams.clear()

    def _log_info(self, message: str):
        """정보 로그 출력"""
        logging.info(message)

    def _log_error(self, message: str):
        """에러 로그 출력"""
        logging.error(message)

    def _log_container_action(self, container_name: str, action: str):
        """컨테이너 액션 로그 (Docker Compose 스타일)"""
        color = self.container_colors.get(container_name, "")
        reset = self.color_reset if self.config.log_config.use_colors else ""

        print(f"{color}{container_name}{reset} | {action}")
        sys.stdout.flush()
```

### 2. Updated DockerRuntimeManager

**Location**: `src/mindor/core/runtime/docker/docker.py`

기존 `DockerRuntimeManager`에 로그 prefix 지원 추가:

```python
class DockerRuntimeManager:
    def __init__(
        self,
        config: DockerRuntimeConfig,
        verbose: bool,
        log_prefix: Optional[str] = None,  # 새로 추가
        log_color: Optional[str] = None    # 새로 추가
    ):
        self.config: DockerRuntimeConfig = config
        self.verbose: bool = verbose
        self.log_prefix: Optional[str] = log_prefix
        self.log_color: Optional[str] = log_color
        self.color_reset: str = '\033[0m'
        # ... 기존 코드 ...

    async def _stream_container_logs(self, container: Container) -> None:
        """컨테이너 로그 스트리밍 (prefix 지원)"""
        try:
            def _stream_logs_sync(container: Container) -> None:
                for line in container.logs(stream=True, follow=True, since=int(time.time())):
                    # Prefix 추가
                    if self.log_prefix:
                        color = self.log_color or ""
                        reset = self.color_reset if color else ""
                        prefix = f"{color}{self.log_prefix}{reset} | "

                        decoded = line.decode('utf-8', errors='replace')
                        formatted = f"{prefix}{decoded}"
                        sys.stdout.write(formatted)
                    else:
                        sys.stdout.buffer.write(line)

                    sys.stdout.flush()

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _stream_logs_sync, container)
        except Exception as e:
            logging.error("Error while streaming logs from container '%s': %s", container.name, e)
```

### 3. CLI Integration

**Location**: `src/mindor/cli/compose.py`

`up` 및 `down` 커맨드에 멀티 컨테이너 지원 추가:

```python
@click.command(name="up")
@click.option("-d", "--detach", is_flag=True, help="Run in detached mode.")
# ... 기존 옵션들 ...
@click.pass_context
def up_command(ctx: click.Context, detach: bool, ...):
    from mindor.core.runtime.docker.compose import DockerComposeManager

    async def _async_command():
        try:
            config = _load_compose_config(config_files, env_files, env_data)

            # Docker Compose 매니저 사용
            if _has_multiple_docker_containers(config):
                compose_manager = await DockerComposeManager.get_instance()
                compose_config = _build_docker_compose_config(config)
                compose_manager.configure(compose_config, verbose)
                await compose_manager.up(detach)
            else:
                # 기존 단일 컨테이너 로직
                await launch_services(config, detach, verbose)
        except Exception as e:
            # ... 에러 처리 ...

    asyncio.run(_async_command())

def _has_multiple_docker_containers(config: ComposeConfig) -> bool:
    """여러 Docker 컨테이너가 정의되어 있는지 확인"""
    # config를 분석하여 Docker 런타임이 여러 개 있는지 체크
    # 실제 구현은 config 구조에 따라 달라짐
    pass

def _build_docker_compose_config(config: ComposeConfig) -> DockerComposeManagerConfig:
    """ComposeConfig에서 DockerComposeManagerConfig 빌드"""
    # config에서 Docker 컨테이너들을 추출하여 DockerComposeManagerConfig 생성
    pass
```

## YAML Configuration Examples

### Example 1: Controller + Components with Docker Runtime

```yaml
# model-compose.yml

# Controller (HTTP Server) - Docker 런타임 사용
controller:
  type: http-server
  port: 8080

  # Docker 런타임 설정 -> DockerComposeManager에 자동 등록
  runtime:
    type: docker
    container_name: model-compose-web
    image: model-compose:latest
    ports:
      - "8080:8080"
    depends_on:
      - redis      # Redis 컨테이너가 먼저 시작되어야 함
      - postgres   # PostgreSQL 컨테이너가 먼저 시작되어야 함

# Components
components:
  # Redis 캐시 (Docker 런타임)
  - id: redis-cache
    type: docker-service
    runtime:
      type: docker
      image: redis:7-alpine
      container_name: model-compose-redis
      ports:
        - "6379:6379"
      volumes:
        - redis-data:/data
      healthcheck:
        test: ["CMD", "redis-cli", "ping"]
        interval: 5s
        timeout: 3s
        retries: 5
      log_color: "\033[33m"  # Yellow

  # PostgreSQL 데이터베이스 (Docker 런타임)
  - id: postgres-db
    type: docker-service
    runtime:
      type: docker
      image: postgres:15-alpine
      container_name: model-compose-postgres
      ports:
        - "5432:5432"
      environment:
        POSTGRES_USER: ${env.DB_USER}
        POSTGRES_PASSWORD: ${env.DB_PASSWORD}
        POSTGRES_DB: model_compose
      volumes:
        - postgres-data:/var/lib/postgresql/data
      healthcheck:
        test: ["CMD-SHELL", "pg_isready -U ${env.DB_USER}"]
        interval: 5s
        timeout: 3s
        retries: 5
      log_color: "\033[32m"  # Green

  # Vector DB (Docker 런타임, PostgreSQL 의존)
  - id: vector-db
    type: docker-service
    runtime:
      type: docker
      image: qdrant/qdrant:latest
      container_name: model-compose-qdrant
      ports:
        - "6333:6333"
      volumes:
        - qdrant-data:/qdrant/storage
      depends_on:
        - postgres  # PostgreSQL 다음에 시작
      log_color: "\033[36m"  # Cyan

workflows:
  - id: chat
    jobs:
      - id: call-api
        component: some-api
```

**실행 흐름**:
1. `model-compose up` 실행
2. `DockerComposeManager`가 등록된 컨테이너 확인:
   - `redis` (redis-cache component의 runtime)
   - `postgres` (postgres-db component의 runtime)
   - `qdrant` (vector-db component의 runtime)
   - `web` (controller의 runtime)
3. 의존성 순서 계산: `redis` → `postgres` → `qdrant` → `web`
4. 순차적으로 시작하고 모든 로그를 통합 출력:
   ```
   redis     | Ready to accept connections
   postgres  | database system is ready to accept connections
   qdrant    | Qdrant vector database is ready
   web       | Server started on port 8080
   ```
```

### Example 2: 의존성 체인

```yaml
# 모든 component/controller가 Docker 런타임을 가질 때
# DockerComposeManager가 자동으로 의존성 순서대로 시작

components:
  # 1. 데이터베이스 (최우선)
  - id: database
    type: docker-service
    runtime:
      type: docker
      image: postgres:15
      container_name: app-db
      environment:
        POSTGRES_PASSWORD: secret
      healthcheck:
        test: ["CMD", "pg_isready"]
        interval: 5s

  # 2. 캐시 (데이터베이스 다음)
  - id: cache
    type: docker-service
    runtime:
      type: docker
      image: redis:7
      container_name: app-cache
      depends_on:
        - database  # database 컨테이너가 시작된 후 시작

  # 3. 백엔드 API (DB와 캐시 필요)
  - id: backend
    type: docker-service
    runtime:
      type: docker
      image: my-backend:latest
      container_name: app-backend
      ports:
        - "8000:8000"
      depends_on:
        - database
        - cache
      environment:
        DATABASE_URL: postgresql://postgres:secret@database:5432/app
        REDIS_URL: redis://cache:6379

controller:
  type: http-server
  port: 3000
  runtime:
    type: docker
    image: my-frontend:latest
    container_name: app-frontend
    depends_on:
      - backend  # backend 컨테이너가 시작된 후 시작
    environment:
      API_URL: http://backend:8000
```

**시작 순서**: `database` → `cache` → `backend` → `frontend`
```

### Example 3: 색상 커스터마이징

```yaml
components:
  - id: web
    type: docker-service
    runtime:
      type: docker
      image: nginx:alpine
      log_color: "\033[34m"  # Blue

  - id: api
    type: docker-service
    runtime:
      type: docker
      image: my-api:latest
      log_color: "\033[32m"  # Green

  - id: worker
    type: docker-service
    runtime:
      type: docker
      image: my-worker:latest
      log_color: "\033[33m"  # Yellow
```

각 컨테이너의 `log_color` 필드로 로그 출력 색상을 지정할 수 있습니다.
색상을 지정하지 않으면 자동으로 할당됩니다.
```

## CLI Usage

### 모든 컨테이너 시작

```bash
# Foreground 모드 (로그 출력)
# - Controller/Component들의 Docker 런타임이 자동으로 DockerComposeManager에 등록됨
# - 의존성 순서대로 시작
# - 모든 로그를 통합 출력
model-compose up

# Detached 모드
model-compose up -d

# 환경 변수 주입
model-compose up --env DB_PASSWORD=secret
```

### 출력 예시 (Docker Compose 스타일)

Controller와 Component들이 Docker 런타임을 사용할 때:

```
Container startup order: redis -> postgres -> qdrant -> web
Starting containers...

redis     | Creating
postgres  | Creating
qdrant    | Creating
web       | Creating

redis     | Started
postgres  | Started
postgres  | Healthy
qdrant    | Started
web       | Started

redis     | [2025-12-31 10:30:15] * Ready to accept connections
postgres  | [2025-12-31 10:30:15] database system is ready to accept connections
qdrant    | [2025-12-31 10:30:16] Qdrant vector database is ready
web       | [2025-12-31 10:30:17] Server started on port 8080
```

각 컨테이너의 로그가 색상으로 구분되어 출력됩니다.

### 모든 컨테이너 중지

```bash
# 컨테이너 중지 및 제거
model-compose down
```

## Implementation Phases

### Phase 1: Core Orchestration (MVP)
- [x] `DockerComposeManager` singleton 구현
- [x] 멀티 컨테이너 병렬 시작/중지
- [x] 기본 로그 스트리밍 with prefix
- [ ] CLI 통합 (`up`, `down`)

### Phase 2: Log Formatting
- [ ] ANSI 색상 코드 적용
- [ ] 타임스탬프 추가
- [ ] 컨테이너 이름 패딩
- [ ] 색상 커스터마이징

### Phase 3: Dependency Management
- [ ] 의존성 그래프 계산 (Topological sort)
- [ ] `depends_on` 필드 지원
- [ ] 조건부 대기 (started, healthy)
- [ ] 순환 의존성 감지

### Phase 4: Health Checks
- [ ] 헬스체크 대기 로직
- [ ] 헬스체크 타임아웃
- [ ] 재시도 로직
- [ ] 헬스체크 상태 출력

### Phase 5: Advanced Features
- [ ] 컨테이너 재시작 (restart)
- [ ] 로그 필터링
- [ ] 특정 서비스만 시작/중지
- [ ] 스케일링 (replicas)

### Phase 6: Production Ready
- [ ] 에러 핸들링 강화
- [ ] Graceful shutdown 개선
- [ ] 성능 최적화
- [ ] 단위 테스트
- [ ] 통합 테스트

## Testing Strategy

### Unit Tests

```python
# tests/core/runtime/test_docker_compose_manager.py

import pytest
from mindor.core.runtime.docker.compose import DockerComposeManager

@pytest.mark.asyncio
async def test_singleton_pattern():
    """싱글톤 패턴 검증"""
    manager1 = await DockerComposeManager.get_instance()
    manager2 = await DockerComposeManager.get_instance()
    assert manager1 is manager2

@pytest.mark.asyncio
async def test_dependency_order():
    """의존성 순서 계산 테스트"""
    config = DockerComposeManagerConfig(
        containers={
            "db": DockerRuntimeConfig(image="postgres:15"),
            "app": DockerRuntimeConfig(
                image="myapp:latest",
                depends_on=["db"]
            )
        }
    )

    manager = await DockerComposeManager.get_instance()
    manager.configure(config)

    assert manager.startup_order == ["db", "app"]
    assert manager.shutdown_order == ["app", "db"]

@pytest.mark.asyncio
async def test_circular_dependency_detection():
    """순환 의존성 감지 테스트"""
    config = DockerComposeManagerConfig(
        containers={
            "a": DockerRuntimeConfig(image="a:latest", depends_on=["b"]),
            "b": DockerRuntimeConfig(image="b:latest", depends_on=["a"])
        }
    )

    manager = await DockerComposeManager.get_instance()

    with pytest.raises(ValueError, match="Circular dependency"):
        manager.configure(config)
```

### Integration Tests

```python
# tests/integration/test_docker_compose_workflow.py

@pytest.mark.asyncio
async def test_multi_container_startup():
    """멀티 컨테이너 시작 테스트"""
    # Docker Compose 설정 로드
    # 모든 컨테이너 시작
    # 상태 검증
    pass

@pytest.mark.asyncio
async def test_log_streaming():
    """로그 스트리밍 테스트"""
    # 컨테이너 시작
    # 로그 출력 캡처
    # Prefix 및 색상 검증
    pass
```

## Performance Considerations

1. **병렬 시작 최적화**
   - 의존성이 없는 컨테이너는 동시에 시작
   - asyncio 활용한 비동기 처리
   - 타임아웃 관리

2. **로그 스트리밍 효율**
   - 각 컨테이너별 독립 태스크
   - 버퍼링 최소화
   - Thread-safe 출력

3. **메모리 관리**
   - 싱글톤 패턴으로 인스턴스 공유
   - 로그 스트림 정리
   - 컨테이너 상태 캐싱

## Security Considerations

1. **컨테이너 격리**
   - 네트워크 격리
   - 볼륨 권한 관리
   - 시크릿 관리

2. **로그 보안**
   - 민감 정보 필터링
   - 로그 접근 제어

## Future Enhancements

1. **Docker Compose 파일 직접 지원**
   - `docker-compose.yml` 파싱
   - Docker Compose v2/v3 스펙 호환

2. **고급 네트워킹**
   - 커스텀 네트워크 생성
   - 서비스 디스커버리
   - 로드 밸런싱

3. **모니터링**
   - 컨테이너 리소스 사용량
   - 헬스체크 대시보드
   - 메트릭 수집

4. **배포 전략**
   - Rolling update
   - Blue-green deployment
   - Canary deployment

## References

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Docker Python SDK](https://docker-py.readthedocs.io/)
- [ANSI Color Codes](https://en.wikipedia.org/wiki/ANSI_escape_code)

# Dynamic Configuration Management Specification

## Overview

Controller 런타임 중에 컴포넌트와 워크플로우를 동적으로 추가, 수정, 삭제할 수 있는 기능을 제공하는 스펙입니다. 서버를 재시작하지 않고도 설정을 변경하여 즉시 반영할 수 있습니다.

## Design Goals

1. **런타임 설정 변경**: 서버 재시작 없이 컴포넌트/워크플로우 추가/수정/삭제
2. **Hot-reload**: 변경사항 즉시 반영 및 실행
3. **안전한 검증**: 설정 변경 전 유효성 검증 및 의존성 체크
4. **REST API 제공**: HTTP 컨트롤러를 통한 CRUD 엔드포인트
5. **Thread-safe**: 동시 요청에도 안전한 상태 관리
6. **Backward Compatible**: 기존 정적 설정 방식과 공존

## Use Cases

### 1. A/B Testing
서로 다른 프롬프트나 모델 설정을 동적으로 추가하여 실시간으로 테스트

```bash
# 새로운 실험용 컴포넌트 추가
curl -X POST http://localhost:8080/components \
  -H "Content-Type: application/json" \
  -d '{
    "id": "gpt4-turbo-test",
    "type": "http-client",
    "config": {...}
  }'
```

### 2. 긴급 패치
운영 중 발견된 버그를 즉시 수정

```bash
# 기존 컴포넌트 설정 업데이트
curl -X PUT http://localhost:8080/components/openai-client \
  -H "Content-Type: application/json" \
  -d '{
    "id": "openai-client",
    "type": "http-client",
    "config": {
      "max_retries": 5  # 재시도 횟수 증가
    }
  }'
```

### 3. 동적 워크플로우 생성
사용자 요청에 따라 맞춤형 워크플로우 생성

```bash
# 새 워크플로우 등록
curl -X POST http://localhost:8080/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "id": "custom-pipeline",
    "jobs": [...]
  }'
```

### 4. 리소스 정리
사용하지 않는 컴포넌트 제거

```bash
# 컴포넌트 삭제
curl -X DELETE http://localhost:8080/components/unused-component
```

## Architecture

### Core Design Principles

**ControllerService 확장 방식**
- 별도의 Manager 클래스 없이 `ControllerService` 베이스 클래스에 직접 메서드 추가
- 기존 구조와 자연스럽게 통합
- 모든 컨트롤러 타입(HTTP, MCP)에서 공통으로 사용 가능

### Components

#### 1. `ControllerService` - Extended with Dynamic Management

**새로 추가되는 메서드**:

```python
class ControllerService(AsyncService):
    # ... existing code ...

    # Component CRUD
    def add_component(self, component_config: ComponentConfig) -> ComponentConfig
    def get_component(self, component_id: str) -> Optional[ComponentConfig]
    def update_component(self, component_id: str, component_config: ComponentConfig) -> ComponentConfig
    def delete_component(self, component_id: str) -> bool
    def list_components(self) -> List[ComponentConfig]

    # Workflow CRUD
    def add_workflow(self, workflow_config: WorkflowConfig) -> WorkflowConfig
    def get_workflow(self, workflow_id: str) -> Optional[WorkflowConfig]
    def update_workflow(self, workflow_id: str, workflow_config: WorkflowConfig) -> WorkflowConfig
    def delete_workflow(self, workflow_id: str) -> bool
    def list_workflows(self) -> List[WorkflowConfig]

    # Service lifecycle (hot-reload)
    async def reload_component(self, component_id: str) -> ComponentService
    async def reload_workflow(self, workflow_id: str) -> None
```

**Thread Safety**:
- `self._component_lock = Lock()` 추가
- `self._workflow_lock = Lock()` 추가
- 모든 CRUD 작업은 lock으로 보호

**Validation**:
- Pydantic 스키마 자동 검증
- 의존성 체크 (워크플로우가 참조하는 컴포넌트 존재 여부)
- ID 중복 체크

#### 2. `HttpServerController` - REST API Endpoints

**새로 추가되는 엔드포인트**:

```python
# Components
POST   /components              # 새 컴포넌트 추가
GET    /components              # 전체 컴포넌트 목록
GET    /components/{id}         # 특정 컴포넌트 조회
PUT    /components/{id}         # 컴포넌트 수정
DELETE /components/{id}         # 컴포넌트 삭제
POST   /components/{id}/reload  # 컴포넌트 hot-reload

# Workflows (기존 GET 엔드포인트 확장)
POST   /workflows               # 새 워크플로우 추가
GET    /workflows               # 전체 워크플로우 목록 (기존)
GET    /workflows/{id}          # 워크플로우 조회 (기존 schema 엔드포인트와 통합)
PUT    /workflows/{id}          # 워크플로우 수정
DELETE /workflows/{id}          # 워크플로우 삭제
POST   /workflows/{id}/reload   # 워크플로우 스키마 재빌드
```

## API Specification

### Component Management

#### POST /components
새로운 컴포넌트 추가

**Request Body**:
```json
{
  "id": "new-component",
  "type": "http-client",
  "url": "https://api.example.com",
  "headers": {
    "Authorization": "Bearer ${env.API_KEY}"
  }
}
```

**Response** (201 Created):
```json
{
  "id": "new-component",
  "type": "http-client",
  "url": "https://api.example.com",
  "headers": {
    "Authorization": "Bearer ${env.API_KEY}"
  }
}
```

**Error Cases**:
- `409 Conflict`: 동일한 ID의 컴포넌트가 이미 존재
- `400 Bad Request`: 잘못된 컴포넌트 설정 (Pydantic validation 실패)

#### GET /components
전체 컴포넌트 목록 조회

**Response** (200 OK):
```json
[
  {
    "id": "component-1",
    "type": "http-client",
    ...
  },
  {
    "id": "component-2",
    "type": "model",
    ...
  }
]
```

#### GET /components/{id}
특정 컴포넌트 조회

**Response** (200 OK):
```json
{
  "id": "component-1",
  "type": "http-client",
  ...
}
```

**Error Cases**:
- `404 Not Found`: 컴포넌트가 존재하지 않음

#### PUT /components/{id}
컴포넌트 수정

**Request Body**:
```json
{
  "id": "component-1",
  "type": "http-client",
  "url": "https://api.new-endpoint.com",
  ...
}
```

**Response** (200 OK):
```json
{
  "id": "component-1",
  "type": "http-client",
  "url": "https://api.new-endpoint.com",
  ...
}
```

**Error Cases**:
- `404 Not Found`: 컴포넌트가 존재하지 않음
- `400 Bad Request`: 잘못된 설정

#### DELETE /components/{id}
컴포넌트 삭제

**Response** (204 No Content)

**Error Cases**:
- `404 Not Found`: 컴포넌트가 존재하지 않음
- `409 Conflict`: 워크플로우에서 사용 중인 컴포넌트 (의존성 체크 실패)

#### POST /components/{id}/reload
컴포넌트 hot-reload (실행 중인 서비스 재시작)

**Response** (200 OK):
```json
{
  "id": "component-1",
  "status": "reloaded",
  "timestamp": "2025-12-31T10:00:00Z"
}
```

**Error Cases**:
- `404 Not Found`: 컴포넌트가 존재하지 않음
- `500 Internal Server Error`: reload 실패

### Workflow Management

#### POST /workflows
새로운 워크플로우 추가

**Request Body**:
```json
{
  "id": "new-workflow",
  "title": "New Workflow",
  "description": "Dynamic workflow",
  "jobs": [
    {
      "id": "job1",
      "component": "component-1",
      "input": {...}
    }
  ]
}
```

**Response** (201 Created):
```json
{
  "id": "new-workflow",
  "title": "New Workflow",
  ...
}
```

**Error Cases**:
- `409 Conflict`: 동일한 ID의 워크플로우가 이미 존재
- `400 Bad Request`: 잘못된 워크플로우 설정
- `422 Unprocessable Entity`: 존재하지 않는 컴포넌트 참조

#### PUT /workflows/{id}
워크플로우 수정

**Request Body**:
```json
{
  "id": "workflow-1",
  "jobs": [...]
}
```

**Response** (200 OK):
```json
{
  "id": "workflow-1",
  "jobs": [...]
}
```

**Error Cases**:
- `404 Not Found`: 워크플로우가 존재하지 않음
- `400 Bad Request`: 잘못된 설정
- `422 Unprocessable Entity`: 존재하지 않는 컴포넌트 참조

#### DELETE /workflows/{id}
워크플로우 삭제

**Response** (204 No Content)

**Error Cases**:
- `404 Not Found`: 워크플로우가 존재하지 않음

#### POST /workflows/{id}/reload
워크플로우 스키마 재빌드 (컴포넌트 변경 후 스키마 갱신)

**Response** (200 OK):
```json
{
  "workflow_id": "workflow-1",
  "status": "reloaded",
  "schema": {...}
}
```

## Implementation Details

### 1. Thread-Safe State Management

```python
class ControllerService(AsyncService):
    def __init__(self, ...):
        # ... existing code ...
        self._component_lock = Lock()
        self._workflow_lock = Lock()

    def add_component(self, component_config: ComponentConfig) -> ComponentConfig:
        with self._component_lock:
            # ID 중복 체크
            if any(c.id == component_config.id for c in self.components):
                raise ValueError(f"Component '{component_config.id}' already exists")

            # 추가
            self.components.append(component_config)

            # 워크플로우 스키마 재빌드
            self._rebuild_workflow_schemas()

            return component_config
```

### 2. Workflow Schema Rebuild

컴포넌트나 워크플로우가 변경될 때마다 `workflow_schemas` 재생성:

```python
def _rebuild_workflow_schemas(self) -> None:
    """Rebuild workflow schemas from current configurations."""
    from mindor.core.workflow.schema import create_workflow_schemas

    with self._workflow_lock:
        self.workflow_schemas = create_workflow_schemas(
            self.workflows,
            self.components
        )
```

### 3. Dependency Validation

워크플로우 추가/수정 시 참조하는 컴포넌트 존재 여부 확인:

```python
def _validate_workflow_components(self, workflow: WorkflowConfig) -> None:
    """Validate that all components referenced in workflow exist."""
    component_ids = {c.id for c in self.components}

    for job in workflow.jobs:
        if job.component and job.component not in component_ids:
            raise ValueError(
                f"Workflow references non-existent component: '{job.component}'"
            )
```

### 4. Component Hot-Reload

실행 중인 컴포넌트 서비스를 재시작:

```python
async def reload_component(self, component_id: str) -> ComponentService:
    """Reload a component with updated configuration."""
    component_config = self.get_component(component_id)
    if not component_config:
        raise ValueError(f"Component '{component_id}' not found")

    # 기존 서비스 중지 (실행 중이라면)
    # TODO: track running component services

    # 새 설정으로 서비스 생성 및 시작
    global_configs = self._get_component_global_configs()
    service = create_component(
        component_id,
        component_config,
        global_configs,
        self.daemon
    )

    if self.daemon:
        await service.setup()
        await service.start()

    return service
```

### 5. HTTP Endpoints Implementation

```python
@self.router.post("/components")
async def create_component(request: Request):
    try:
        body = await request.json()
        component_config = ComponentConfig(**body)
        result = self.add_component(component_config)
        return JSONResponse(content=result.model_dump(), status_code=201)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@self.router.get("/components")
async def list_components():
    components = self.list_components()
    return JSONResponse(content=[c.model_dump() for c in components])

@self.router.get("/components/{component_id}")
async def get_component(component_id: str):
    component = self.get_component(component_id)
    if not component:
        raise HTTPException(status_code=404, detail="Component not found")
    return JSONResponse(content=component.model_dump())

@self.router.put("/components/{component_id}")
async def update_component(component_id: str, request: Request):
    try:
        body = await request.json()
        component_config = ComponentConfig(**body)
        result = self.update_component(component_id, component_config)
        return JSONResponse(content=result.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@self.router.delete("/components/{component_id}")
async def delete_component(component_id: str):
    try:
        self.delete_component(component_id)
        return Response(status_code=204)
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=409, detail=str(e))

@self.router.post("/components/{component_id}/reload")
async def reload_component(component_id: str):
    try:
        await self.reload_component(component_id)
        return JSONResponse(content={
            "id": component_id,
            "status": "reloaded"
        })
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## Security Considerations

### 1. Authentication & Authorization
동적 설정 변경은 민감한 작업이므로 인증/권한 필요:

```python
# TODO: Add authentication middleware
@self.router.post("/components")
async def create_component(
    request: Request,
    api_key: str = Header(None, alias="X-API-Key")
):
    if not self._verify_api_key(api_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    ...
```

### 2. Rate Limiting
과도한 요청 방지:

```python
# TODO: Add rate limiting
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@limiter.limit("10/minute")
@self.router.post("/components")
async def create_component(...):
    ...
```

### 3. Audit Logging
모든 설정 변경 기록:

```python
def add_component(self, component_config: ComponentConfig) -> ComponentConfig:
    with self._component_lock:
        ...
        self._log_config_change("ADD_COMPONENT", component_config.id)
        return component_config
```

## WebUI Integration

### Challenge
`ControllerWebUI`는 초기화 시점에 `workflow_schemas`를 한 번만 빌드하므로, 런타임 중 컴포넌트/워크플로우가 변경되어도 UI에 반영되지 않습니다.

### Solution Options

#### Option 1: WebUI 재시작 (간단하지만 권장하지 않음)
설정 변경 시 WebUI 서버를 재시작:

```python
async def reload_webui(self) -> None:
    """Restart WebUI with updated configurations."""
    if self.config.webui and hasattr(self, 'webui'):
        await self._stop_webui()
        await self._start_webui()
```

**단점**:
- 사용자 세션 중단
- 진행 중인 워크플로우 실행 손실
- 사용자 경험 저하

#### Option 2: 동적 UI 업데이트 (권장)
Gradio의 동적 업데이트 기능 활용:

**구현 방법**:

1. **ControllerWebUI 수정**: `workflow_schemas`를 직접 저장하지 않고 ControllerService 참조

```python
class ControllerWebUI(AsyncService):
    def __init__(
        self,
        config: ControllerWebUIConfig,
        controller_service: ControllerService,  # 전체 서비스 참조
        daemon: bool
    ):
        super().__init__(daemon)
        self.config = config
        self.controller_service = controller_service  # 동적으로 schemas 가져오기

    def _configure_driver(self) -> None:
        if self.config.driver == ControllerWebUIDriver.GRADIO:
            blocks = GradioWebUIBuilder().build(
                get_workflow_schemas=lambda: self.controller_service.workflow_schemas,  # 함수로 전달
                workflow_runner=self._run_workflow
            )
            ...
```

2. **GradioWebUIBuilder 수정**: 스키마를 함수로 받아서 매번 최신 스키마 조회

```python
class GradioWebUIBuilder:
    def build(
        self,
        get_workflow_schemas: Callable[[], Dict[str, WorkflowSchema]],  # 변경
        workflow_runner: Callable[[Optional[str], Any], Awaitable[Any]]
    ) -> gr.Blocks:
        with gr.Blocks() as blocks:
            # 페이지 로드/새로고침 시 최신 스키마 가져오기
            @blocks.load
            def refresh_workflows():
                workflow_schemas = get_workflow_schemas()
                return self._render_workflows(workflow_schemas, workflow_runner)

            # 또는 초기 렌더링
            workflow_schemas = get_workflow_schemas()
            self._render_workflows(workflow_schemas, workflow_runner)

        return blocks

    def _render_workflows(self, workflow_schemas, workflow_runner):
        for workflow_id, workflow in workflow_schemas.items():
            # ... 기존 UI 빌드 로직
```

3. **설정 변경 후 UI 갱신 트리거** (선택적)

Gradio는 기본적으로 페이지 새로고침 시 `blocks.load` 이벤트를 트리거합니다. 추가로 실시간 업데이트를 원한다면:

```python
# HttpServerController에 WebSocket 또는 SSE 엔드포인트 추가
@self.router.get("/config-updates")
async def config_update_stream():
    async def event_generator():
        while True:
            # 설정 변경 이벤트 대기
            event = await self.config_update_queue.get()
            yield {
                "event": "config_updated",
                "data": json.dumps({"type": event.type})
            }

    return EventSourceResponse(event_generator())
```

**권장 접근법**:
- **Phase 1**: 페이지 새로고침으로 최신 스키마 로드 (간단하고 충분)
- **Phase 2**: 실시간 UI 업데이트 (필요시 구현)

### Implementation Changes

**ControllerService 수정**:
```python
def _rebuild_workflow_schemas(self) -> None:
    """Rebuild workflow schemas and notify WebUI if needed."""
    from mindor.core.workflow.schema import create_workflow_schemas

    with self._workflow_lock:
        self.workflow_schemas = create_workflow_schemas(
            self.workflows,
            self.components
        )

    # WebUI에 변경 알림 (선택적)
    self._notify_webui_update()
```

**ControllerBase 수정** ([src/mindor/core/controller/base.py](src/mindor/core/controller/base.py:269)):
```python
def _create_webui(self) -> ControllerWebUI:
    # 변경 전: workflows와 components를 직접 전달
    # return ControllerWebUI(self.config.webui, self.config, self.components, self.workflows, self.daemon)

    # 변경 후: ControllerService 인스턴스 전달
    return ControllerWebUI(self.config.webui, self, self.daemon)
```

## Testing Strategy

### 1. Unit Tests
- 각 CRUD 메서드 테스트
- 동시성 테스트 (thread-safe)
- Validation 테스트
- WebUI 스키마 갱신 테스트

### 2. Integration Tests
- API 엔드포인트 테스트
- Hot-reload 동작 확인
- 의존성 체크 테스트
- WebUI 동적 업데이트 테스트

### 3. Example Test Cases

```python
# tests/test_dynamic_config.py

async def test_add_component():
    controller = create_test_controller()

    component = ComponentConfig(
        id="test-component",
        type="http-client",
        url="https://api.test.com"
    )

    result = controller.add_component(component)
    assert result.id == "test-component"
    assert len(controller.components) == 1

async def test_add_duplicate_component():
    controller = create_test_controller()
    component = ComponentConfig(id="test", type="http-client")

    controller.add_component(component)

    with pytest.raises(ValueError, match="already exists"):
        controller.add_component(component)

async def test_delete_component_in_use():
    controller = create_test_controller()

    # Add component
    component = ComponentConfig(id="test-comp", type="http-client")
    controller.add_component(component)

    # Add workflow using component
    workflow = WorkflowConfig(
        id="test-wf",
        jobs=[{"id": "job1", "component": "test-comp"}]
    )
    controller.add_workflow(workflow)

    # Try to delete - should fail
    with pytest.raises(ValueError, match="in use"):
        controller.delete_component("test-comp")
```

## Migration Guide

### Backward Compatibility
기존 정적 설정 방식은 그대로 유지:

```yaml
# model-compose.yml (기존 방식 그대로 작동)
controller:
  type: http-server
  port: 8080

components:
  - id: static-component
    type: http-client
    url: https://api.example.com

workflows:
  - id: static-workflow
    jobs: [...]
```

동적 관리는 런타임에 추가로 사용 가능:
```bash
# 정적 설정으로 시작
model-compose up

# 런타임에 동적으로 추가
curl -X POST http://localhost:8080/components -d '{...}'
```

## Future Enhancements

1. **설정 영속화**: 동적으로 추가된 설정을 파일로 저장
2. **Versioning**: 설정 변경 이력 관리
3. **Rollback**: 이전 설정으로 되돌리기
4. **WebUI 통합**: 웹 인터페이스에서 드래그 앤 드롭으로 설정 관리
5. **MCP Server 지원**: MCP 프로토콜을 통한 동적 관리
6. **Git Integration**: 설정 변경을 자동으로 커밋
7. **Diff View**: 변경 전후 비교 UI

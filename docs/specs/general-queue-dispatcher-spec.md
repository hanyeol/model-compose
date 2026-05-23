# General Queue Dispatcher Spec

## Context

현재 queue dispatcher가 workflow를 queue로 보내려면, dispatcher 쪽에 래퍼 workflow+component를 일일이 정의해야 함. 이는 subscriber의 모든 workflow를 미리 알아야 하는 강한 결합을 만듦. **queue가 설정된 dispatcher가 로컬에 없는 workflow_id를 받으면 자동으로 queue로 dispatch**하도록 개선.

## 현재 병목 (2곳)

1. **HTTP 어댑터** (`http_server.py:599`): `workflow_id not in self.controller.workflow_schemas` → 404 반환
2. **WebSocket 핸들러** (`http_server.py:469`): 동일한 검증 → 에러 반환

`ControllerService._run_workflow` 내부의 queue dispatch 로직(`base.py:523`)까지 도달하기 전에 어댑터 레벨에서 막힘.

## 수정 방안

**전략**: queue가 설정된 경우, 로컬에 없는 workflow_id를 어댑터에서 거부하지 않고 `ControllerService.run_workflow`로 통과시킴. `run_workflow`에서 queue dispatch를 직접 처리.

### 1. HTTP 어댑터 수정 (`http_server.py`)

**1a. `_handle_workflow_run_request` (line 599)**:
```python
# before
if not workflow_id or workflow_id not in self.controller.workflow_schemas:
    raise HTTPException(status_code=404, ...)

# after
if not workflow_id or not self.controller.is_workflow_available(workflow_id):
    raise HTTPException(status_code=404, ...)
```

**1b. `_websocket_run_workflow` (line 469)**: 동일한 패턴 적용

**1c. `GET /workflows/{workflow_id}/schema` (line 286)**: 이건 스키마 조회이므로 변경 불필요 (로컬에 없으면 스키마를 알 수 없음)

### 2. `ControllerService`에 `is_workflow_available` 메서드 추가 (`base.py`)

```python
def is_workflow_available(self, workflow_id: str) -> bool:
    if workflow_id in self.workflow_schemas:
        return True
    if self._queue:
        return True
    return False
```

로컬에 있거나, queue가 설정되어 있으면 처리 가능으로 판단.

### 3. Queue Subscriber 자동 workflow 등록 (`redis.py`)

현재 subscriber는 `workflows` 필드에 workflow ID를 명시해야만 해당 queue를 listen함. 생략 시 `["__default__"]`만 listen하므로, 로컬에 여러 workflow가 있어도 하나만 처리 가능.

**변경**: `workflows` 기본값을 로컬에 정의된 non-private workflow 목록으로 자동 설정.

**3a. 스키마 기본값 변경** (`common.py`):
```python
# before
workflows: List[str] = Field(default=["__default__"], ...)

# after
workflows: Optional[List[str]] = Field(default=None, ...)
```

**3b. Redis subscriber에서 workflow 목록 resolve** (`redis.py:43`):
```python
# before
queue_keys = [ f"{self.config.name}:{workflow_id}" for workflow_id in self.config.workflows ]

# after
workflows = self.config.workflows or list(self.controller.workflow_schemas.keys())
queue_keys = [ f"{self.config.name}:{workflow_id}" for workflow_id in workflows ]
```

`controller.workflow_schemas`는 이미 `exclude_private=True`로 생성되므로 별도 필터 불필요.

**동작 요약**:

| `workflows` 설정 | 동작 |
|---|---|
| 생략 (`None`) | 로컬 non-private workflow 전체 자동 등록 |
| 명시 (예: `[echo, chat]`) | 해당 workflow만 listen |

## 수정 파일 목록

| 파일 | 변경 내용 |
|---|---|
| `src/mindor/core/controller/base.py` | `is_workflow_available` 메서드 추가 |
| `src/mindor/core/controller/adapters/services/http_server.py` | HTTP/WebSocket 핸들러에서 `is_workflow_available`로 검증 |
| `src/mindor/dsl/schema/controller/adapter/impl/queue_subscriber/impl/common.py` | `workflows` 기본값을 `None`으로 변경 |
| `src/mindor/core/controller/adapters/services/queue_subscriber/drivers/redis.py` | `workflows`가 `None`이면 로컬 non-private workflow 자동 사용 |

## 검증

1. 기존 예제 (`examples/workflow-queue/`) 정상 동작 확인
2. queue 설정 없이 미등록 workflow_id 요청 시 기존대로 404 반환
3. queue 설정 + 미등록 workflow_id 요청 시 queue로 dispatch 확인
4. subscriber에서 `workflows` 생략 시 로컬 non-private workflow 전체 listen 확인
5. subscriber에서 `workflows` 명시 시 해당 workflow만 listen 확인
6. `python -m pytest tests/` 테스트 통과

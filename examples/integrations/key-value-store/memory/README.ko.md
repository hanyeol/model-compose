# In-Memory Key-Value Store 예제

이 예제는 워크플로우에서 데이터를 저장, 조회, 관리하기 위해 model-compose를 인메모리 key-value 스토어와 함께 사용하는 방법을 보여줍니다.

## 개요

이 워크플로우는 기본적인 key-value 스토어 연산을 제공합니다:

1. **Set**: 선택적 TTL(유효 기간)과 함께 값 저장
2. **Get**: 키로 저장된 값 조회
3. **Delete**: 스토어에서 키 삭제
4. **Exists**: 키 존재 여부 확인

메모리 드라이버는 모든 엔트리를 컨트롤러 프로세스 내에 보관합니다. 데이터는 **영속화되지 않으며**, 컨트롤러가 중지되면 모두 사라집니다. 따라서 로컬 개발, 테스트, 짧은 수명의 데이터 캐싱, 또는 외부 서비스에 의존하고 싶지 않은 예제에 적합합니다.

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능

외부 서비스나 추가 의존성은 필요하지 않습니다.

### 환경 구성

이 예제 디렉토리로 이동:
```bash
cd examples/integrations/key-value-store/memory
```

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행:**

   **값 저장:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "set-value", "input": {"key": "greeting", "value": "Hello, World!", "ttl": 3600}}'
   ```

   **값 조회:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "get-value", "input": {"key": "greeting"}}'
   ```

   **키 존재 확인:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "check-value", "input": {"key": "greeting"}}'
   ```

   **키 삭제:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "delete-value", "input": {"key": "greeting"}}'
   ```

   **웹 UI 사용:**
   - 웹 UI 열기: http://localhost:8081
   - 원하는 워크플로우 선택 (set, get, delete, exists)
   - 입력 매개변수 입력
   - "Run Workflow" 버튼 클릭

   **CLI 사용:**
   ```bash
   # TTL과 함께 값 저장
   model-compose run set-value --input '{"key": "user:1", "value": {"name": "Alice", "role": "admin"}, "ttl": 86400}'

   # 값 조회
   model-compose run get-value --input '{"key": "user:1"}'

   # 존재 여부 확인
   model-compose run check-value --input '{"key": "user:1"}'

   # 키 삭제
   model-compose run delete-value --input '{"key": "user:1"}'
   ```

## 컴포넌트 세부사항

### In-Memory Key-Value Store 컴포넌트 (kv)
- **유형**: Key-value store 컴포넌트
- **목적**: 키-값 쌍 저장 및 조회
- **드라이버**: Memory (인프로세스)
- **기능**:
  - 기본 CRUD 연산 (get, set, delete, exists)
  - 자동 키 만료를 위한 TTL 지원
  - JSON 직렬화 가능한 모든 값 지원
  - 외부 의존성 없음

> **참고**: 데이터는 컨트롤러 프로세스가 살아 있는 동안만 유지됩니다. `model-compose`를 재시작하면 모든 엔트리가 삭제됩니다.

## 워크플로우 세부사항

### "Set Value" 워크플로우

**설명**: 선택적 TTL과 함께 메모리에 키-값 쌍을 저장합니다.

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `key` | string | 예 | - | 저장할 키 |
| `value` | any | 예 | - | 저장할 값 (문자열, 숫자, 객체, 배열) |
| `ttl` | integer | 아니오 | null | 유효 기간(초). null = 만료 없음 |

#### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| `success` | boolean | 연산 성공 여부 |

### "Get Value" 워크플로우

**설명**: 메모리에서 키로 값을 조회합니다.

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `key` | string | 예 | - | 조회할 키 |

#### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| `value` | any \| null | 저장된 값. 키가 존재하지 않으면 null |

### "Delete Value" 워크플로우

**설명**: 메모리에서 키를 삭제합니다.

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `key` | string | 예 | - | 삭제할 키 |

#### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| `count` | integer | 삭제된 키 수 (0 또는 1) |

### "Check Exists" 워크플로우

**설명**: 메모리에서 키의 존재 여부를 확인합니다.

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `key` | string | 예 | - | 확인할 키 |

#### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| `exists` | boolean | 키 존재 여부 |

## 사용자 정의

### 드라이버 전환

메모리 드라이버는 선언 외에 추가 구성이 필요하지 않습니다:

```yaml
components:
  - id: kv
    type: key-value-store
    driver: memory
```

재시작 후에도 데이터가 유지되어야 한다면 `sqlite` 또는 `redis` 드라이버로 전환하세요. 액션 정의와 워크플로우 입력은 그대로 유지됩니다. `examples/integrations/key-value-store/` 아래의 형제 예제를 참고하세요.

### 값 유형

컴포넌트는 JSON 직렬화 가능한 모든 값을 허용합니다: 문자열, 숫자, 불리언, 객체, 배열. 값은 저장된 형태 그대로 반환됩니다.

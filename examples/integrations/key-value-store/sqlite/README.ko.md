# SQLite Key-Value Store 예제

이 예제는 워크플로우에서 데이터를 저장, 조회, 관리하기 위해 model-compose를 SQLite key-value 스토어와 함께 사용하는 방법을 보여줍니다.

## 개요

이 워크플로우는 기본적인 key-value 스토어 연산을 제공합니다:

1. **Set**: 선택적 TTL(유효 기간)과 함께 값 저장
2. **Get**: 키로 저장된 값 조회
3. **Delete**: 스토어에서 키 삭제
4. **Exists**: 키 존재 여부 확인

SQLite 드라이버는 로컬 데이터베이스 파일에 엔트리를 영속화하므로 컨트롤러를 재시작해도 데이터가 유지됩니다. 외부 서버가 필요하지 않아, 영속성이 필요하지만 네트워크로 접근 가능한 완전한 스토어까지는 필요 없을 때 Redis의 경량 대안으로 적합합니다.

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능

외부 서비스는 필요하지 않습니다. SQLite는 임베디드이며 데이터베이스 파일은 최초 사용 시 자동 생성됩니다.

### 환경 구성

이 예제 디렉토리로 이동:
```bash
cd examples/integrations/key-value-store/sqlite
```

이 예제는 기본적으로 `storage/kv-store.sqlite` 파일(이 디렉토리 기준)에 기록합니다. 컨트롤러가 시작될 때 `storage/` 디렉토리와 데이터베이스 파일이 자동으로 생성됩니다.

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

### SQLite Key-Value Store 컴포넌트 (kv)
- **유형**: Key-value store 컴포넌트
- **목적**: 키-값 쌍 저장 및 조회
- **드라이버**: SQLite (임베디드)
- **기능**:
  - 기본 CRUD 연산 (get, set, delete, exists)
  - 자동 키 만료를 위한 TTL 지원
  - 복합 값에 대한 JSON 직렬화/역직렬화
  - 단일 데이터베이스 파일에 영속 저장
  - 외부 서버 불필요

## 워크플로우 세부사항

### "Set Value" 워크플로우

**설명**: 선택적 TTL과 함께 SQLite에 키-값 쌍을 저장합니다.

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

**설명**: SQLite에서 키로 값을 조회합니다.

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `key` | string | 예 | - | 조회할 키 |

#### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| `value` | any \| null | 저장된 값. 키가 존재하지 않으면 null |

### "Delete Value" 워크플로우

**설명**: SQLite에서 키를 삭제합니다.

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `key` | string | 예 | - | 삭제할 키 |

#### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| `count` | integer | 삭제된 키 수 (0 또는 1) |

### "Check Exists" 워크플로우

**설명**: SQLite에서 키의 존재 여부를 확인합니다.

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `key` | string | 예 | - | 확인할 키 |

#### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| `exists` | boolean | 키 존재 여부 |

## 사용자 정의

### 데이터베이스 위치

SQLite 파일의 위치를 제어하려면 `path`를 설정합니다. 상대 경로는 예제 디렉토리를 기준으로 해석됩니다. 데이터베이스를 다른 위치에 두려면 절대 경로를 사용하고, 영속화가 필요 없는 인메모리 데이터베이스가 필요하면 `:memory:`를 사용하세요.

```yaml
components:
  - id: kv
    type: key-value-store
    driver: sqlite
    path: /var/lib/model-compose/kv-store.sqlite
```

```yaml
components:
  - id: kv
    type: key-value-store
    driver: sqlite
    path: ":memory:"
```

### 테이블 이름

기본적으로 엔트리는 `kv_store` 테이블에 저장됩니다. 하나의 데이터베이스 파일에 여러 스토어를 함께 두고 싶다면 `table`로 재정의하세요:

```yaml
components:
  - id: sessions
    type: key-value-store
    driver: sqlite
    path: app.sqlite
    table: sessions

  - id: cache
    type: key-value-store
    driver: sqlite
    path: app.sqlite
    table: cache
```

### 값 유형

컴포넌트가 자동으로 직렬화를 처리합니다:
- **문자열**: 그대로 저장
- **객체/배열**: JSON으로 직렬화, 조회 시 자동 역직렬화
- **숫자/불리언**: 저장 시 문자열로 변환

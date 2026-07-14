# ArangoDB Graph Store 예제

이 예제는 소셜 그래프를 구축하고 쿼리하기 위해 model-compose를 ArangoDB 그래프 스토어와 함께 사용하는 방법을 보여줍니다.

## 개요

이 워크플로우는 ArangoDB를 사용한 그래프 데이터베이스 연산을 제공합니다:

1. **Add Person**: 그래프에 사람 문서 삽입
2. **Find Friends**: AQL(ArangoDB Query Language)을 사용하여 친구 검색
3. **Find Connections**: 소셜 그래프를 순회하여 연결 탐색

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- ArangoDB 서버 실행 중 (로컬 또는 원격)

### ArangoDB 설치

**Docker 사용:**
```bash
docker run -d --name arangodb \
  -p 8529:8529 \
  -e ARANGO_ROOT_PASSWORD=password \
  arangodb
```

**Homebrew 사용 (macOS):**
```bash
brew install arangodb
brew services start arangodb
```

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/graph-store/arangodb
   ```

2. ArangoDB가 `localhost:8529`에서 실행 중인지 확인합니다 (기본 포트).

3. http://localhost:8529 에서 ArangoDB 웹 UI에 접속하여 연결을 확인합니다.

4. 데이터베이스와 컬렉션을 생성합니다:
   - `social`이라는 이름의 데이터베이스 생성
   - `persons`라는 이름의 문서 컬렉션 생성
   - `friendships`라는 이름의 엣지 컬렉션 생성
   - `social_graph`라는 이름의 그래프 생성 (엣지 정의: `friendships`, from: `persons`, to: `persons`)

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행:**

   **사람 추가:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "add-person", "input": {"name": "Alice", "age": 30}}'
   ```

   **친구 검색:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "find-friends", "input": {"name": "Alice"}}'
   ```

   **연결 탐색:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "find-connections", "input": {"node_id": "persons/12345"}}'
   ```

   **웹 UI 사용:**
   - 웹 UI 열기: http://localhost:8081
   - 원하는 워크플로우 선택
   - 입력 매개변수 입력
   - "Run Workflow" 버튼 클릭

   **CLI 사용:**
   ```bash
   # 사람 추가
   model-compose run add-person --input '{"name": "Alice", "age": 30}'

   # 이름으로 친구 검색
   model-compose run find-friends --input '{"name": "Alice"}'

   # 연결 탐색 (순회)
   model-compose run find-connections --input '{"node_id": "persons/12345"}'
   ```

## 컴포넌트 세부사항

### ArangoDB Graph Store 컴포넌트 (social-graph)
- **유형**: Graph store 컴포넌트
- **목적**: 그래프 구조 데이터 저장 및 쿼리
- **드라이버**: ArangoDB
- **기능**:
  - 문서 및 엣지 CRUD 연산
  - AQL 쿼리 실행
  - 구성 가능한 깊이 및 방향의 명명된 그래프 순회
  - URL 또는 host/port를 통한 연결

## 워크플로우 세부사항

### "Add Person" 워크플로우

**설명**: 그래프에 사람 문서를 삽입합니다.

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `name` | string | 예 | - | 사람 이름 |
| `age` | integer | 예 | - | 사람 나이 |

#### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| `ids` | array | 생성된 문서 ID 목록 |
| `created_nodes` | integer | 생성된 문서 수 |
| `created_relationships` | integer | 생성된 엣지 수 |

### "Find Friends" 워크플로우

**설명**: AQL을 사용하여 이름으로 친구를 검색합니다.

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `name` | string | 예 | - | 검색할 사람 이름 |

#### 출력 형식

속성이 포함된 일치하는 문서 목록을 반환합니다.

### "Find Connections" 워크플로우

**설명**: 소셜 그래프를 순회하여 2홉 이내의 연결을 찾습니다.

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `node_id` | string | 예 | - | 시작 문서 ID (예: `persons/12345`) |

#### 출력 형식

깊이 및 경로 정보가 포함된 연결 문서 목록을 반환합니다.

## 사용자 정의

### ArangoDB 연결

#### URL 사용
```yaml
components:
  - id: social-graph
    type: graph-store
    driver: arangodb
    url: http://localhost:8529
    username: root
    password: password
    database: social
```

#### Host/Port 사용
```yaml
components:
  - id: social-graph
    type: graph-store
    driver: arangodb
    host: arangodb.example.com
    port: 8529
    protocol: https
    username: root
    password: ${env.ARANGO_PASSWORD}
    database: social
```

### ArangoDB 고유 기능

- **명명된 그래프**: 액션에서 `graph` 필드를 사용하여 ArangoDB의 명명된 그래프 기능을 순회에 활용
- **컬렉션**: 문서 연산에는 `collection`, 엣지 연산에는 `edge_collection` 지정
- **AQL 쿼리**: 바인드 매개변수가 포함된 사용자 정의 AQL 쿼리로 유연한 데이터 접근

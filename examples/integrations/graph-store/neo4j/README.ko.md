# Neo4j Graph Store 예제

이 예제는 지식 그래프를 구축하고 쿼리하기 위해 model-compose를 Neo4j 그래프 스토어와 함께 사용하는 방법을 보여줍니다.

## 개요

이 워크플로우는 Neo4j를 사용한 그래프 데이터베이스 연산을 제공합니다:

1. **Add Person**: 지식 그래프에 사람 노드 삽입
2. **Add Friendship**: 두 사람 사이에 KNOWS 관계 생성
3. **Find Person**: Cypher를 사용하여 이름으로 사람 검색
4. **Find Connections**: 그래프를 순회하여 연결된 사람 탐색

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- Neo4j 서버 실행 중 (로컬 또는 원격)

### Neo4j 설치

**Docker 사용:**
```bash
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j
```

**Homebrew 사용 (macOS):**
```bash
brew install neo4j
neo4j start
```

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/graph-store/neo4j
   ```

2. Neo4j가 `localhost:7687`에서 실행 중인지 확인합니다 (기본 Bolt 포트).

3. http://localhost:7474 에서 Neo4j Browser에 접속하여 연결을 확인합니다.

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

   **친구 관계 추가:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "add-friendship", "input": {"from_id": "<node_id_1>", "to_id": "<node_id_2>", "since": "2024-01-01"}}'
   ```

   **사람 검색:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "find-person", "input": {"name": "Alice"}}'
   ```

   **연결 탐색:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "find-connections", "input": {"node_id": "<node_id>"}}'
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

   # 사람 검색
   model-compose run find-person --input '{"name": "Alice"}'

   # 연결 탐색 (순회)
   model-compose run find-connections --input '{"node_id": "<node_id>"}'
   ```

## 컴포넌트 세부사항

### Neo4j Graph Store 컴포넌트 (knowledge-graph)
- **유형**: Graph store 컴포넌트
- **목적**: 그래프 구조 데이터 저장 및 쿼리
- **드라이버**: Neo4j
- **기능**:
  - 노드 및 관계 CRUD 연산
  - Cypher 쿼리 실행
  - 구성 가능한 깊이 및 방향의 그래프 순회
  - URL 또는 host/port를 통한 연결

## 워크플로우 세부사항

### "Add Person" 워크플로우

**설명**: 지식 그래프에 사람 노드를 삽입합니다.

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `name` | string | 예 | - | 사람 이름 |
| `age` | integer | 예 | - | 사람 나이 |

#### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| `ids` | array | 생성된 노드 요소 ID 목록 |
| `created_nodes` | integer | 생성된 노드 수 |
| `created_relationships` | integer | 생성된 관계 수 |

### "Add Friendship" 워크플로우

**설명**: 두 사람 사이에 KNOWS 관계를 생성합니다.

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `from_id` | string | 예 | - | 출발 노드 요소 ID |
| `to_id` | string | 예 | - | 도착 노드 요소 ID |
| `since` | string | 예 | - | 친구 관계 시작 날짜 |

#### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| `ids` | array | 생성된 관계 요소 ID 목록 |
| `created_nodes` | integer | 생성된 노드 수 |
| `created_relationships` | integer | 생성된 관계 수 |

### "Find Person" 워크플로우

**설명**: Cypher 쿼리를 사용하여 이름으로 사람을 검색합니다.

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `name` | string | 예 | - | 검색할 사람 이름 |

#### 출력 형식

노드 속성이 포함된 일치하는 레코드 목록을 반환합니다.

### "Find Connections" 워크플로우

**설명**: 그래프를 순회하여 2홉 이내의 연결된 사람을 찾습니다.

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `node_id` | string | 예 | - | 시작 노드 요소 ID |

#### 출력 형식

깊이 및 관계 유형 정보가 포함된 연결 노드 목록을 반환합니다.

## 사용자 정의

### Neo4j 연결

#### URL 사용
```yaml
components:
  - id: knowledge-graph
    type: graph-store
    driver: neo4j
    url: bolt://localhost:7687
```

#### Host/Port 사용
```yaml
components:
  - id: knowledge-graph
    type: graph-store
    driver: neo4j
    host: neo4j.example.com
    port: 7687
    protocol: neo4j+s
    username: neo4j
    password: ${env.NEO4J_PASSWORD}
```

### 지원 프로토콜

| 프로토콜 | 설명 |
|---------|------|
| `bolt` | 비암호화 Bolt 연결 |
| `bolt+s` | TLS Bolt 연결 (검증된 인증서) |
| `bolt+ssc` | TLS Bolt 연결 (자체 서명 인증서) |
| `neo4j` | Neo4j 프로토콜 (라우팅 지원) |
| `neo4j+s` | TLS Neo4j 프로토콜 (검증된 인증서) |
| `neo4j+ssc` | TLS Neo4j 프로토콜 (자체 서명 인증서) |

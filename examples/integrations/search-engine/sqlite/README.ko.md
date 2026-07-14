# SQLite Search Engine 예제

이 예제는 워크플로우에서 문서를 인덱싱, 검색, 관리하기 위해 model-compose를 SQLite FTS5 풀텍스트 검색 엔진과 함께 사용하는 방법을 보여줍니다.

## 개요

이 워크플로우는 SQLite FTS5 기반의 풀텍스트 검색 연산을 제공합니다:

1. **Index**: 검색 인덱스에 문서 삽입
2. **Search**: 인덱싱된 문서에 대해 BM25 정렬 키워드 검색 수행
3. **Delete**: id 기반으로 인덱스에서 문서 제거

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- Python 3.11+ (공식 빌드에 포함된 `sqlite3` 모듈은 FTS5가 기본 활성화되어 있음)

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/search-engine/sqlite
   ```

2. 외부 서비스가 필요하지 않습니다. 인덱스는 `./data/search.db` 경로의 단일 SQLite 데이터베이스 파일로 저장되며, 첫 `index` 액션 실행 시 자동으로 생성됩니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행:**

   **문서 인덱싱:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "index-documents", "input": {"documents": [
       {"document_id": "1", "title": "Python tutorial", "content": "Learn Python basics"},
       {"document_id": "2", "title": "JavaScript guide", "content": "Modern JavaScript features"},
       {"document_id": "3", "title": "Rust handbook", "content": "Systems programming in Rust"}
     ]}}'
   ```

   **문서 검색:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "search-documents", "input": {"query": "Python", "limit": 5}}'
   ```

   **문서 삭제:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "delete-documents", "input": {"document_ids": ["1", "3"]}}'
   ```

   **웹 UI 사용:**
   - 웹 UI 열기: http://localhost:8081
   - 원하는 워크플로우 선택 (index, search, delete)
   - 입력 매개변수 입력
   - "Run Workflow" 버튼 클릭

   **CLI 사용:**
   ```bash
   # 문서 인덱싱
   model-compose run index-documents --input '{"documents": [
     {"document_id": "1", "title": "Python tutorial", "content": "Learn Python basics"},
     {"document_id": "2", "title": "JavaScript guide", "content": "Modern JavaScript features"}
   ]}'

   # 필드 필터를 사용한 검색
   model-compose run search-documents --input '{"query": "Modern", "search_fields": ["content"], "limit": 5}'

   # 문서 삭제
   model-compose run delete-documents --input '{"document_ids": ["1"]}'
   ```

## 컴포넌트 세부사항

### SQLite Search Engine 컴포넌트 (search)
- **유형**: Search-engine 컴포넌트
- **목적**: 사용자가 제공한 문서에 대한 풀텍스트 키워드 검색
- **드라이버**: SQLite FTS5
- **기능**:
  - Zero-dependency (Python 내장 `sqlite3`의 FTS5 사용)
  - BM25 순위 내장
  - 단일 데이터베이스 파일에 여러 인덱스 공존
  - `id` 필드 선언 시 upsert 의미론 지원
  - 데이터베이스가 없는 상태에서 `search` / `delete` 시 명시적 `FileNotFoundError` 발생 (조용한 빈 파일 생성 안 함)

## 워크플로우 세부사항

### "Index Documents" 워크플로우

**설명**: 문서 묶음을 FTS5 인덱스에 삽입합니다. 첫 실행 시 데이터베이스 파일과 인덱스를 자동으로 생성합니다.

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `documents` | object 배열 | 예 | - | 인덱싱할 문서 목록. 각 객체의 키는 선언된 필드명과 일치해야 함 |

#### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| `indexed` | integer | 이번 호출에서 삽입된 문서 수 |
| `total` | integer | 현재 인덱스 내 전체 문서 수 |

### "Search Documents" 워크플로우

**설명**: 인덱스에 대해 BM25 정렬 키워드 검색을 수행합니다.

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `query` | string | 예 | - | FTS5 쿼리 표현식 |
| `search_fields` | string 배열 | 아니오 | null | 매칭을 제한할 필드 목록. 생략 시 모든 text 필드에서 검색 |
| `limit` | integer | 아니오 | 10 | 반환할 최대 hit 수 |

#### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| `hits` | object 배열 | 매칭 문서 목록 (`score` 내림차순) |
| `count` | integer | 반환된 hit 수 |

각 hit은 인덱싱된 필드 값과 `score` 필드를 포함합니다 (값이 클수록 관련성이 높음).

### "Delete Documents" 워크플로우

**설명**: id 필드 값으로 인덱스에서 문서를 제거합니다.

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `document_ids` | string 배열 | 예 | - | 삭제할 문서의 `id` 타입 필드 값 목록 |

#### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| `deleted` | integer | 삭제된 문서 수 |

## 사용자 정의

### 저장 위치

```yaml
components:
  - id: search
    type: search-engine
    driver: sqlite
    storage_dir: /var/lib/myapp/search
    database: knowledge.db
```

전체 데이터베이스 경로는 `${storage_dir}/${database}` 입니다. 여러 인덱스는 같은 파일 안에 독립된 FTS5 가상 테이블로 공존합니다.

### 필드 유형

| 유형 | 동작 |
|------|------|
| `text` | 토큰화되어 풀텍스트 MATCH로 검색 가능 |
| `id` | upsert 및 delete에 사용되는 고유 식별자 |
| `keyword` | 태그 스타일 값 (FTS5 내에서는 text로 저장) |

```yaml
fields:
  - name: document_id
    type: id
  - name: title
    type: text
  - name: tags
    type: keyword
```

### 단일 컴포넌트의 다중 인덱스

`index` 파라미터를 액션마다 다르게 지정하면 하나의 컴포넌트가 여러 인덱스를 운영할 수 있습니다. 같은 데이터베이스 파일을 공유하되 독립된 FTS5 가상 테이블에 저장됩니다:

```yaml
actions:
  - id: index-articles
    method: index
    index: articles
    fields:
      - { name: document_id, type: id }
      - { name: body, type: text }
    documents: ${input.documents}

  - id: index-comments
    method: index
    index: comments
    fields:
      - { name: document_id, type: id }
      - { name: body, type: text }
    documents: ${input.documents}
```

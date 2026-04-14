# Korea DART MCP 서버 예제

한국 금융감독원의 [DART(전자공시시스템)](https://opendart.fss.or.kr) 데이터를 조회하는 MCP 서버 예제입니다.

[dart-mcp](https://github.com/2geonhyup/dart-mcp)에서 영감을 받았습니다.

## 개요

한국 상장기업(KOSPI/KOSDAQ)의 재무 데이터를 조회하는 MCP 서버입니다:

1. **공시 검색**: 정기공시 검색 및 주요 재무지표 추출
2. **재무제표 조회**: 구조화된 재무 데이터 조회 (재무상태표, 손익계산서, 현금흐름표)
3. **기업 개황**: 기본 기업 정보 조회 (종목코드, 대표이사, 업종 등)
4. **기업코드 검색**: 기업명으로 DART 고유번호 조회
5. **배당 정보**: 주당배당금, 배당수익률, 배당성향 조회
6. **주요주주 현황**: 주요주주 및 지분 정보 조회

## 사전 준비

### 필수 조건

- model-compose가 설치되어 PATH에 등록되어 있어야 합니다
- DART Open API 인증키

### DART API 키 발급

1. [DART Open API](https://opendart.fss.or.kr) 방문
2. 회원가입
3. API 인증키 신청
4. 인증키 발급 (무료)

### 환경 설정

1. 예제 디렉토리로 이동:
   ```bash
   cd examples/mcp-servers/korea-dart-mcp
   ```

2. 환경 파일 복사:
   ```bash
   cp .env.sample .env
   ```

3. `.env` 파일에 DART API 키 입력:
   ```env
   DART_API_KEY=발급받은-dart-api-키
   ```

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행:**

   **MCP 클라이언트:**
   - MCP 서버 연결: http://localhost:8080/mcp
   - 사용 가능한 워크플로우: search-disclosure, get-financial-statements, get-company-overview, get-company-code, get-dividend-info, get-major-shareholders
   - MCP 호환 클라이언트에서 워크플로우 실행

   **웹 UI:**
   - 웹 UI 열기: http://localhost:8081
   - 원하는 워크플로우 선택
   - 필수 파라미터 입력
   - "Run" 버튼 클릭

   **CLI:**
   ```bash
   # 기업코드 조회
   model-compose run get-company-code --input '{"corp_name": "삼성전자"}'

   # 공시 검색
   model-compose run search-disclosure --input '{
     "corp_code": "00126380",
     "bgn_de": "20240101",
     "end_de": "20241231"
   }'

   # 연간 재무제표 조회 (연결)
   model-compose run get-financial-statements --input '{
     "corp_code": "00126380",
     "bsns_year": "2024",
     "reprt_code": "11011",
     "fs_div": "CFS"
   }'

   # 기업 개황 조회
   model-compose run get-company-overview --input '{"corp_code": "00126380"}'

   # 배당 정보 조회
   model-compose run get-dividend-info --input '{
     "corp_code": "00126380",
     "bsns_year": "2024"
   }'

   # 주요주주 현황 조회
   model-compose run get-major-shareholders --input '{
     "corp_code": "00126380",
     "bsns_year": "2024"
   }'
   ```

## 컴포넌트 상세

### 기업코드 조회 (Shell 컴포넌트)
- **ID**: `corp-code-lookup`
- **타입**: Shell 컴포넌트 (Python 스크립트)
- **목적**: DART 고유번호 ZIP/XML 파일을 다운로드하여 기업명으로 검색
- **인증**: `DART_API_KEY` 환경변수 사용

### DART Open API HTTP 클라이언트 컴포넌트
- **ID**: `dart-api`
- **타입**: 다중 액션 HTTP 클라이언트 컴포넌트
- **목적**: DART Open API 연동
- **Base URL**: `https://opendart.fss.or.kr/api`
- **인증**: 쿼리 파라미터로 API 키 전달
- **액션**:
  - **search-disclosure**: 정기공시 검색
  - **get-financial-statements**: 재무제표 전체 조회
  - **get-company-overview**: 기업 개황 조회
  - **get-dividend-info**: 배당 정보 조회
  - **get-major-shareholders**: 주요주주 현황 조회

## 워크플로우 상세

### "공시 검색" 워크플로우

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `corp_code` | text | 예 | - | DART 고유번호 (8자리) |
| `bgn_de` | text | 예 | - | 검색 시작일 (YYYYMMDD) |
| `end_de` | text | 예 | - | 검색 종료일 (YYYYMMDD) |
| `last_reprt_at` | text | 아니오 | `Y` | 최종보고서만 조회 (Y/N) |
| `pblntf_ty` | text | 아니오 | `A` | 공시유형 (A=정기공시, B=주요사항, C=발행공시) |

### "재무제표 조회" 워크플로우

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `corp_code` | text | 예 | - | DART 고유번호 (8자리) |
| `bsns_year` | text | 예 | - | 사업연도 (YYYY) |
| `reprt_code` | text | 아니오 | `11011` | 보고서 코드 (11011=사업보고서, 11012=반기, 11013=1분기, 11014=3분기) |
| `fs_div` | text | 아니오 | `CFS` | 재무제표 구분 (CFS=연결, OFS=개별) |

### "기업 개황 조회" 워크플로우

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `corp_code` | text | 예 | - | DART 고유번호 (8자리) |

### "기업코드 검색" 워크플로우

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `corp_name` | text | 예 | - | 검색할 기업명 (한글 또는 영문) |

### "배당 정보 조회" 워크플로우

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `corp_code` | text | 예 | - | DART 고유번호 (8자리) |
| `bsns_year` | text | 예 | - | 사업연도 (YYYY) |
| `reprt_code` | text | 아니오 | `11011` | 보고서 코드 |

### "주요주주 현황" 워크플로우

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `corp_code` | text | 예 | - | DART 고유번호 (8자리) |
| `bsns_year` | text | 예 | - | 사업연도 (YYYY) |
| `reprt_code` | text | 아니오 | `11011` | 보고서 코드 |

## MCP 서버 연동

### 연결 정보
- **전송 방식**: HTTP
- **엔드포인트**: `http://localhost:8080/mcp`
- **프로토콜**: Model Context Protocol v1.0

### 사용 가능한 도구
AI 에이전트에서 아래 워크플로우를 도구로 사용할 수 있습니다:
- `search-disclosure`: 공시 검색
- `get-financial-statements`: 재무제표 조회
- `get-company-overview`: 기업 개황 조회
- `get-company-code`: 기업명으로 고유번호 검색
- `get-dividend-info`: 배당 정보 조회
- `get-major-shareholders`: 주요주주 현황 조회

## DART Open API 참고

### 사용 엔드포인트

1. **list.json** - 공시검색
   - 문서: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001

2. **fnlttSinglAcntAll.json** - 단일회사 전체 재무제표
   - 문서: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019020

3. **company.json** - 기업개황
   - 문서: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019002

4. **corpCode.xml** - 고유번호
   - 문서: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019018

5. **alotMatter.json** - 배당에 관한 사항
   - 문서: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS004&apiId=2019006

6. **hyslrSttus.json** - 주요주주 소유현황
   - 문서: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS004&apiId=2019004

## 오류 처리

### 주요 API 오류

| 상태 | 메시지 | 해결 방법 |
|------|--------|----------|
| `010` | 등록되지 않은 인증키 | `DART_API_KEY` 확인 |
| `011` | 사용 한도 초과 | 대기 후 재시도 (일일 한도) |
| `012` | 해당 데이터 없음 | corp_code와 날짜 범위 확인 |
| `013` | 미공시 데이터 | 해당 기간 데이터 미공개 |
| `020` | 파라미터 오류 | 파라미터 형식 및 값 확인 |
| `800` | 허용되지 않은 IP | DART 설정에서 IP 등록 |
| `900` | 정의되지 않은 오류 | DART 고객센터 문의 |

## 문제 해결

### 자주 발생하는 문제

1. **결과가 없음**: `corp_code`가 올바른지 확인 (`get-company-code`로 먼저 조회)
2. **인증 오류**: `.env`에 `DART_API_KEY`가 올바르게 설정되어 있는지 확인
3. **재무 데이터 없음**: 해당 기업이 요청한 기간에 보고서를 제출하지 않았을 수 있음
4. **get-company-code가 느림**: 고유번호 API는 약 3MB ZIP 파일을 매번 다운로드하므로 시간이 걸릴 수 있음

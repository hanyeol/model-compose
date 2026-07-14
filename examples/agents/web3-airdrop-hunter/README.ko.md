# Web3 에어드롭 헌터 에이전트 예제

이 예제는 DeFi API와 웹 스크래핑을 결합하여 최신 에어드롭 기회와 DeFi 수익률 정보를 찾아내는 자율 에이전트를 보여줍니다.

## 개요

에이전트는 ReAct 루프를 통해 작동합니다:

1. **요청 수신**: 사용자가 에어드롭 또는 DeFi 수익률에 대한 질문을 제공
2. **API 조회**: 에이전트가 신뢰할 수 있는 DeFiLlama에서 수익률 및 프로토콜 데이터 조회
3. **소스 스크래핑**: airdrops.io에서 트렌드 에어드롭 이름과 상세 페이지를 스크래핑
4. **리포트 작성**: 수집한 데이터를 출처와 함께 잘 정리된 마크다운 리포트로 종합

### 사용 가능한 도구

| 도구 | 설명 |
|------|------|
| `fetch_hottest_airdrops` | airdrops.io에서 트렌드 에어드롭 프로젝트 이름 조회 |
| `fetch_defi_yields` | DeFiLlama API에서 상위 DeFi 수익 풀 조회 (APY, TVL, 체인, 프로토콜) |
| `fetch_defi_protocols` | DeFiLlama API에서 상위 DeFi 프로토콜 조회 (TVL, 카테고리, 체인) |
| `fetch_page` | 웹 페이지 URL에서 본문 텍스트 콘텐츠 조회 |
| `extract_links` | 웹 페이지의 모든 하이퍼링크(href URL) 추출 |
| `extract_elements` | CSS 셀렉터로 특정 요소의 텍스트 추출 |

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- OpenAI API 키

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/agents/web3-airdrop-hunter
   ```

2. 샘플 환경 파일 복사:
   ```bash
   cp .env.sample .env
   ```

3. `.env` 파일을 편집하여 OpenAI API 키 추가:
   ```env
   OPENAI_API_KEY=your-openai-api-key
   ```

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행:**

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"question": "지금 가장 핫한 에어드롭과 최고의 DeFi 수익률은?"}'
   ```

   **웹 UI 사용:**
   - Web UI 열기: http://localhost:8081
   - 질문을 입력하고 "Run Workflow" 버튼 클릭

   **CLI 사용:**
   ```bash
   model-compose run --input '{"question": "Arbitrum 상위 스테이블코인 수익률 찾아줘"}'
   ```

## 컴포넌트 세부사항

### OpenAI GPT-4o 컴포넌트 (gpt-4o)
- **유형**: HTTP client 컴포넌트
- **목적**: 에이전트 추론 및 리포트 생성용 LLM
- **API**: OpenAI GPT-4o Chat Completions (function calling)

### DeFiLlama API 컴포넌트 (defillama-yields, defillama-protocols)
- **유형**: HTTP client 컴포넌트
- **목적**: DeFi 수익률 및 프로토콜 데이터를 위한 신뢰성 있는 API 기반 데이터 소스
- **엔드포인트**: `https://yields.llama.fi/pools`, `https://api.llama.fi/protocols`

### Web Scraper 컴포넌트 (airdrops-io-titles, page-scraper, link-scraper, element-scraper)
- **유형**: Web scraper 컴포넌트
- **목적**: 브라우저 User-Agent를 사용한 HTML 스크래핑, 30초 타임아웃
- **추출 모드**: `text` 또는 `attribute`

### 헌터 에이전트 컴포넌트 (hunter-agent)
- **유형**: Agent 컴포넌트
- **목적**: 크립토 데이터를 수집하고 리포트를 작성하는 자율 에이전트
- **최대 반복 횟수**: 10

## 워크플로우 세부사항

### 도구: fetch_hottest_airdrops

**설명**: airdrops.io에서 가장 핫한 에어드롭 목록을 조회합니다. 트렌드 에어드롭 프로젝트 이름의 JSON 목록을 반환합니다.

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `query` | string | 아니오 | `all` | 무시됨, 아무 값이나 전달 |

### 도구: fetch_defi_yields

**설명**: DeFiLlama API에서 상위 DeFi 수익 파밍 풀을 조회합니다. TVL 기준으로 정렬된 풀 목록을 project, chain, symbol, tvlUsd, apy, apyBase, apyReward, pool URL과 함께 반환합니다.

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `chain` | string | 아니오 | `all` | 블록체인 체인 이름으로 필터링 (예: "Ethereum", "Arbitrum", "Solana") |

### 도구: fetch_defi_protocols

**설명**: DeFiLlama API에서 상위 DeFi 프로토콜을 조회합니다. name, chain, tvl, change_1d, change_7d, category가 포함된 JSON 목록을 반환합니다.

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `category` | string | 아니오 | `all` | 카테고리로 필터링 (예: "Dexes", "Lending", "Bridge") |

### 도구: fetch_page

**설명**: 웹 페이지 URL에서 본문 텍스트 콘텐츠를 조회합니다.

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `url` | string | 예 | - | 조회할 웹 페이지의 URL |

### 도구: extract_links

**설명**: 웹 페이지에서 모든 하이퍼링크(href URL)를 추출합니다.

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `url` | string | 예 | - | 링크를 추출할 웹 페이지의 URL |

### 도구: extract_elements

**설명**: CSS 셀렉터로 특정 요소의 텍스트를 추출합니다.

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `url` | string | 예 | - | 웹 페이지의 URL |
| `selector` | string | 예 | - | 대상 요소의 CSS 셀렉터 (예: "h2", "table tr", "li") |

## 참고사항

- 에이전트는 Cloudflare로 보호되는 CoinMarketCap, DappRadar, DeFiLlama 웹 페이지는 스크래핑하지 않도록 지시받습니다. 대신 API 도구를 사용합니다.
- 에이전트는 항상 사용자에게 에어드롭이나 DeFi 프로토콜 참여 전 DYOR(Do Your Own Research)를 상기시킵니다.

## 사용자 정의

- `gpt-4o`를 function calling을 지원하는 다른 모델로 교체
- 더 많은 데이터 소스 추가 (예: CoinGecko API, Dune Analytics)
- `max_iteration_count`를 조정하여 더 깊은 리서치 허용
- DeFiLlama 결과 수량 (현재 `[:20]`)을 변경하여 데이터 범위 확장/축소

# 뮤직 신디사이저 예제

이 예제는 `music-synthesizer` 컴포넌트를 보여줍니다 — 오디오 입력 없이 악보(score) 하나만으로 스테레오 WAV를 렌더링하는 비트 타임라인 시퀀서입니다. 곡 전체는 트랙, 비트 앵커드 이벤트, 마스터 셰이핑, 사이드체인 더킹이 담긴 JSON 악보 하나로 기술됩니다.

## 개요

이 예제는 **Bake Soundtrack From Score** 워크플로우 하나를 두 단계 파이프로 노출합니다:

1. **Load Score** — `file-store` 잡이 compose 파일 옆에 있는 악보 JSON을 읽어 필드 단위로 파싱합니다.
2. **Bake** — `music-synthesizer` 잡이 모든 필드를 그대로 `sequence` 액션에 흘려 보내고 WAV 스트림을 돌려줍니다.

신디사이저가 이해하는 모든 파라미터(bpm, beats, seed, tracks, master, sidechain)가 악보 JSON에 담겨 있어서, compose 파일을 손대지 않고도 `score.json`을 다른 파일로 바꾸면 다른 곡이 구워집니다.

기본 제공되는 `score.json`은 32비트, 128 BPM 데모입니다: 4비트 카운트인, 킥/하이햇/스네어 그루브, 8비트 스네어 빌드업, 트랜지션 whoosh, 두 마디의 드롭, 킥이 트리거하는 pad/hats/fx 사이드체인 더킹, 마지막 페이드로 구성되어 있습니다.

## 준비

### 사전 요건

- model-compose가 설치되어 PATH에 등록되어 있어야 함
- Python 의존성은 최초 실행 시 자동으로 설치됩니다:
  - `numpy`, `scipy` (`native` 드라이버가 사용)

### 설정

예제 디렉터리로 이동합니다:
```bash
cd examples/media-processing/music-synthesizer
```

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

   서비스가 시작됩니다:
   - API 엔드포인트: http://localhost:8080/api
   - Web UI: http://localhost:8081

2. **워크플로우 실행:**

   **Web UI 사용:**
   - Web UI 열기: http://localhost:8081
   - 기본 제공되는 `score.json`을 사용하려면 `score_path`를 비워 두거나, 다른 악보 파일을 가리키게 합니다
   - "Run Workflow"를 눌러 결과 WAV를 인라인으로 미리 듣습니다

   **CLI 사용:**
   ```bash
   # 기본 제공되는 데모 악보 굽기
   model-compose run bake-soundtrack --input '{}'

   # compose 파일 옆에 놓인 다른 악보 굽기
   model-compose run bake-soundtrack --input '{
     "score_path": "my-score.json"
   }'
   ```

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=bake-soundtrack"
   ```

## 컴포넌트 상세

### Music Synthesizer 컴포넌트

- **타입**: `music-synthesizer`
- **드라이버**: `native` (numpy + scipy)
- **용도**: 트랙과 이벤트가 담긴 비트 앵커드 악보로부터 스테레오 WAV를 렌더링한 뒤, 사이드체인 더킹과 마스터 체인(소프트 클립 → 정규화 → silences → fades)을 적용합니다.

액션은 항상 WAV `audio`를 반환합니다. 이미 존재하는 오디오를 후처리하려면 [`audio-processor`](../audio-processor/)를, 여러 오디오를 합치려면 [`audio-mixer`](../audio-mixer/)를 사용하세요.

### File Store 컴포넌트

- **타입**: `file-store`
- **드라이버**: `local`
- **용도**: 예제 디렉터리에서 악보 JSON을 읽어 옵니다. `${output.content as json}`이 원시 바이트를 dict로 파싱해서 두 번째 잡이 필드 이름으로 접근할 수 있게 합니다.

## 악보 포맷

악보 JSON은 `sequence` 액션의 필드를 1:1 그대로 반영합니다. compose 파일이 필드 단위로 신디사이저에 전달하며, 도중에 이름을 바꾸지 않습니다.

### 최상위 필드

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `bpm` | number | 예 | 분당 비트 수; 곡 전체의 비트-시간 변환을 결정 |
| `beats` | number | 예 | 곡 전체 길이(비트 단위) |
| `seed` | integer | 아니오 | 노이즈 기반 악기의 재현 가능한 시드; 지정하지 않으면 비결정론적 출력 |
| `tracks` | array | 예 | 믹스를 구성하는 트랙 |
| `master` | object | 아니오 | 마스터 버스 셰이핑 — 소프트 클립, 정규화, silences, fades |
| `sidechain` | object | 아니오 | 합산 이전에 적용되는 킥 트리거 더킹 |

### 트랙 필드

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `id` | string | 필수 | 트랙 식별자; `sidechain.trigger`와 `sidechain.targets`가 참조 |
| `gain` | number | `1.0` | 트랙 전체의 선형 게인 배율 |
| `pan` | number -1..1 | `0.0` | 트랙 전체의 스테레오 팬 |
| `events` | array | `[]` | 이 트랙에 렌더링되는 이벤트 |

### 이벤트 필드

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `beat` | number \| array \| `{start, end, step, phase}` | 필수 | 이벤트가 발생하는 비트 위치 |
| `instrument` | string | 필수 | 악기 보이스 — `kick`, `snare`, `hat`, `tick`, `tom`, `pop`, `whoosh`, `chord`, `sub-bass`, `sine`, `noise-burst` |
| `length` | number | `null` | 지속형 악기(`chord`, `sine`, `sub-bass`, `whoosh`, `noise-burst`)의 비트 길이; 타격형은 무시 |
| `gain` | number | `1.0` | 이 이벤트의 선형 게인 배율 |
| `pan` | number -1..1 | `0.0` | 이 이벤트의 스테레오 팬; 트랙 팬과 결합 |
| `params` | object | `{}` | 악기별 파라미터 |

`beat`는 세 가지 형태를 받습니다:
- 단일 숫자 — 해당 비트에서 한 번 발생
- 숫자 배열 — 나열된 각 비트에서 발생
- `{start, end, step, phase}` 객체 — 위치가 `< end`인 모든 `n`에 대해 `start + n*step + phase`에서 발생

### 마스터 필드

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `soft_clip` | number | `1.2` | 소프트 클립 단계의 tanh 드라이브 양; `0`이면 클리핑 비활성화 |
| `normalize_level` | number \| null | `-1.0` | 정규화 후 목표 피크(dBFS); `null`이면 비활성화 |
| `silences` | array | `[]` | 마스터링 이후 적용되는 하드 무음 구간 |
| `fades` | array | `[]` | 마스터링 이후 적용되는 페이드 구간 |

### 사이드체인 필드

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `trigger` | string | 필수 | 이벤트가 더킹 엔벨로프를 여는 트랙 id |
| `targets` | array of strings | 필수 | 각 트리거 히트마다 감쇠되는 트랙 id 목록 |
| `depth` | number 0..1 | `0.78` | 히트당 최대 게인 감쇠 (`0` = 감쇠 없음, `1` = 완전 뮤트) |
| `attack_time` | duration | `2ms` | 최대 감쇠에 도달하는 시간 |
| `release_time` | duration | `70ms` | 유니티까지 회복하는 시간 |

## 워크플로우 상세

### Bake Soundtrack From Score

**ID**: `bake-soundtrack`

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `score_path` | string | 아니오 | `score.json` | 예제 디렉터리 기준 상대 경로의 악보 JSON 경로 |

#### 출력

| 필드 | 타입 | 설명 |
|------|------|------|
| `audio` | audio | 곡 전체의 렌더링된 스테레오 WAV |

## 커스터마이징

### 다른 악보 굽기

새 JSON 파일을 compose 파일 옆에 두고 `score_path`가 그 파일을 가리키게 하세요. compose 파일은 순수 파이프라서, 악보의 최상위 필드가 모두 그대로 `sequence`에 전달되므로 악보만 바꾸면 됩니다.

```bash
model-compose run bake-soundtrack --input '{"score_path": "my-score.json"}'
```

### 악기 참조

모든 이벤트는 `instrument`를 지정합니다. 신디사이저는 11개의 내장 보이스와 함께 제공됩니다:

- **타격형 히트** (`length` 무시): `kick`, `snare`, `hat`, `tick`, `tom`, `pop`
- **지속형 보이스** (`length` 비트 단위): `chord`, `sub-bass`, `sine`, `whoosh`, `noise-burst`

각 보이스의 `params`는 [`music-synthesizer` 컴포넌트 레퍼런스](../../../docs/reference/compose/components/music-synthesizer.md)를 참고하세요.

### 사이드체인 더킹

기본 제공 악보는 킥이 발생할 때마다 `pad`, `hats`, `fx`를 더킹합니다. `sidechain` 블록을 지우면 모두 원 레벨로 유지되며, `trigger`를 다른 트랙(예: `snares`)으로 바꾸면 스네어에서 효과를 들을 수 있습니다.

### 마스터 체인

`master.soft_clip`은 tanh 클리퍼를 구동합니다 — 값이 클수록 믹스가 뭉치지만 트랜지언트가 눌립니다. `master.normalize_level`은 최종 피크(dBFS)를 지정하며, `null`이면 원 합산을 그대로 유지합니다. 마스터 버스에 하드 컷과 테일 페이드가 필요하면 `silences`와 `fades`를 사용하세요.

## 팁

- **악보가 전부**: 결과물을 결정짓는 모든 것 — 템포, 길이, 트랙, 마스터, 사이드체인 — 이 악보 JSON 안에 있습니다. 다른 곡을 굽기 위해 compose 파일을 손댈 필요가 없습니다.
- **재현 가능한 노이즈**: 여러 실행에서 결정론적인 스네어/하이햇/whoosh 출력이 필요하면 `seed`를 지정하세요.
- **패턴이 목록보다 낫다**: 반복 리듬은 긴 비트 목록보다 `{ start, end, step }`이 편집하기 쉽고, `phase`로 위상만 이동시키기도 좋습니다.
- **지속형 vs 타격형**: `length`는 지속형 보이스만 읽습니다. `kick`에 지정해도 무해하지만 아무 효과가 없습니다.
- **사이드체인 라우팅에는 유효한 id**: `trigger`와 `targets`의 모든 항목이 `tracks`의 기존 `id`와 일치해야 하며, 그렇지 않으면 스키마 검증에서 실패합니다.

## 문제 해결

### 자주 발생하는 문제

1. **`bpm must be positive`** / **`beats must be positive`**: 0 이하의 템포나 길이는 유효하지 않은 악보입니다. 둘 다 양수로 지정하세요.
2. **`channels must be 1 or 2`**: 신디사이저는 모노나 스테레오 WAV만 씁니다. 그 외 값은 거부됩니다.
3. **`Duplicate track ids`**: `tracks[].id`는 모두 고유해야 합니다 — 사이드체인 라우팅과 진단이 여기에 의존합니다.
4. **`Sidechain trigger '...' does not match any track id`** / **`Sidechain targets not found among tracks`**: `sidechain` 블록의 오타를 고치거나 누락된 트랙을 추가하세요.
5. **`Beat-pattern step must be positive`**: `{ start, end, step }` 비트 패턴은 `step > 0`이 필요합니다. 음의 step 대신 `phase`로 오프셋하세요.
6. **끝부분이 무음으로 출력됨**: `master.silences`를 확인하세요 — 마지막 이벤트 뒤에 걸린 하드 무음 구간은 렌더가 "끊긴 것처럼" 보이게 만듭니다.
7. **악보 파일을 찾을 수 없음**: `score_path`는 예제 디렉터리 기준으로 해석됩니다 (`file-store`의 `base_path: .`). `base_path`를 넓히지 않는 한 절대 경로가 아니라 `model-compose.yml` 옆에 있는 파일명을 지정하세요.

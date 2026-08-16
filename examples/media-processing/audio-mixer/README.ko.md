# 오디오 믹서 예제

이 예제는 ffmpeg를 사용해 여러 오디오 소스를 하나의 결과물로
결합하는 `audio-mixer` 컴포넌트를 보여줍니다. 두 가지 믹싱 방식을
다룹니다:

- **concat**: 여러 오디오를 이어 붙여 하나의 긴 오디오로 만듭니다
- **overlay**: 하나 이상의 오버레이 오디오를 베이스 오디오에
  섞습니다 (내레이션 아래에 깔리는 배경 음악, 여러 겹의 효과음 등)

## 개요

이 예제는 동일한 `audio-mixer` 컴포넌트 위에 세 개의 워크플로우를
노출합니다:

1. **Concatenate Audios**: 여러 오디오를 하나의 결과물로 이어 붙이기
2. **Overlay Single Audio**: 시작 시간, 게인, 페이드를 설정 가능한
   오버레이 하나를 베이스 오디오에 믹싱
3. **Overlay Multiple Audios**: 여러 오버레이를 베이스 오디오에
   각각의 타이밍, 게인, 팬, 페이드로 레이어링

## 준비

### 사전 요건

- model-compose가 설치되어 PATH에 등록되어 있어야 함
- [ffmpeg](https://ffmpeg.org/)가 설치되어 PATH에 등록되어 있어야 함

### 설정

예제 디렉터리로 이동합니다:
```bash
cd examples/media-processing/audio-mixer
```

ffmpeg가 설치되어 있는지 확인합니다:
```bash
ffmpeg -version
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
   - 드롭다운에서 워크플로우 선택
   - 필요한 오디오 파일을 업로드하고 placement 필드를 설정
   - "Run Workflow" 클릭

   **CLI 사용:**
   ```bash
   # 두 개의 클립을 하나의 오디오로 이어 붙이기
   model-compose run concat --input '{
     "first": "/path/to/intro.mp3",
     "second": "/path/to/main.mp3"
   }'

   # 배경 트랙 위에 내레이션 믹싱
   model-compose run overlay-single --input '{
     "base": "/path/to/background.mp3",
     "overlay": "/path/to/narration.mp3",
     "start_time": "2s",
     "gain": 0.8
   }'

   # 베이스 트랙 위에 내레이션과 효과음을 레이어링
   model-compose run overlay-multiple --input '{
     "base": "/path/to/background.mp3",
     "narration": "/path/to/narration.mp3",
     "sfx": "/path/to/effect.mp3"
   }'
   ```

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=overlay-single" \
     -F "base=@/path/to/background.mp3" \
     -F "overlay=@/path/to/narration.mp3" \
     -F "start_time=2s" \
     -F "gain=0.8"
   ```

## 컴포넌트 상세

### Audio Mixer 컴포넌트

- **Type**: `audio-mixer`
- **Driver**: `ffmpeg`
- **역할**: ffmpeg 필터(`concat`으로 이어 붙이기, `amix`로 오버레이)를
  사용해 여러 오디오를 하나의 결과물로 결합합니다.

ffmpeg 필터 그래프는 스트림 복사(stream-copy)된 입력에는 동작할 수
없으므로, 믹싱 시에는 항상 재인코딩이 일어납니다. `format` 필드로
출력 컨테이너를 지정하며(기본값 `wav`), `encoding` 필드로 코덱,
비트레이트, 샘플레이트, 채널 수를 제어합니다. `encoding`을 생략하면
포맷별 합리적인 기본값이 선택됩니다 (mp3 → libmp3lame,
wav → pcm_s16le, aac/m4a → aac, opus → libopus, ...).

### Concat 방식

ffmpeg의 `concat` 필터로 여러 오디오를 끝과 끝으로 이어 붙입니다.
모든 입력은 샘플레이트와 채널 레이아웃이 동일해야 합니다 — 그렇지
않으면 concat 필터가 `Input link ... parameters do not match` 오류로
실패합니다. `concat`에 넣기 전에 `audio-converter`와 같은 컴포넌트로
입력을 정규화하세요.

#### 주요 필드

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| `audios` | 오디오 소스 리스트 | 예 | - | 이어 붙일 오디오들, 순서대로 (최소 2개) |
| `crossfade` | duration | 아니오 | - | 향후 지원 예정, 현재 미구현 |
| `format` | string | 아니오 | `wav` | 출력 컨테이너 포맷 |
| `encoding` | object | 아니오 | 포맷 기본값 | 출력 코덱 / 비트레이트 / 샘플레이트 / 채널 |
| `batch_size` | integer | 아니오 | `1` | `audios`가 리스트의 리스트 또는 스트림일 때 배치당 처리되는 *세트* 수 |
| `streaming` | boolean | 아니오 | `false` | 임시 파일 대신 바이트 스트림으로 출력 |

### Overlay 방식

베이스 오디오에 하나 이상의 오버레이 오디오를 믹싱합니다. 모든
오버레이는 베이스와 동시에 재생되며 — 타이밍은
`start_time`/`end_time`으로 오버레이마다 개별 제어합니다. 각
오버레이는 자신의 전처리 체인(delay → trim → gain → pan → fade)을
거친 후 ffmpeg의 `amix` 필터로 결합됩니다.

#### 주요 필드

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| `audio` | 오디오 소스 또는 리스트 | 예 | - | 베이스 오디오 (리스트를 넘기면 배치 모드가 되어 베이스당 하나의 출력 생성) |
| `overlay` | 문자열 또는 문자열 리스트 | 예 | - | 오버레이 오디오. 단일 문자열은 자동으로 1개짜리 리스트로 감싸짐 |
| `placement` | object 또는 object 리스트 | 아니오 | 기본 placement 1개 | 오버레이당 하나의 placement. 단일 object는 모든 오버레이에 브로드캐스트, 리스트는 위치로 매칭 |
| `duration_mode` | `base` \| `longest` \| `shortest` | 아니오 | `base` | 베이스/오버레이 대비 출력이 얼마나 재생될지 |
| `format` | string | 아니오 | `wav` | 출력 컨테이너 포맷 |
| `encoding` | object | 아니오 | 포맷 기본값 | 출력 코덱 / 비트레이트 / 샘플레이트 / 채널 |
| `batch_size` | integer | 아니오 | `1` | `audio`가 리스트/스트림일 때 배치당 처리되는 베이스 오디오 수 |
| `streaming` | boolean | 아니오 | `false` | 임시 파일 대신 바이트 스트림으로 출력 |

#### Placement 필드

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `start_time` | duration | - | 오버레이가 처음 재생되는 시각 (베이스 타임라인 기준, 기본값 `0s`) |
| `end_time` | duration | - | 오버레이 재생이 멈추는 시각 (기본값은 오버레이의 자연스러운 끝까지) |
| `gain` | float | `1.0` | 선형 볼륨 배수 (1.0 = 변화 없음, 0.5 = -6dB, 2.0 = +6dB) |
| `pan` | float -1..1 | `0.0` | 스테레오 팬 (-1.0 = 완전 좌측, 0.0 = 중앙, +1.0 = 완전 우측) |
| `fade_in` | duration | - | `start_time`에서 시작하는 페이드인 지속 시간 |
| `fade_out` | duration | - | `end_time`에서 끝나는 페이드아웃 지속 시간 (`end_time` 필요) |

`start_time`, `end_time`, `fade_in`, `fade_out`은 다음을 허용합니다:
- 숫자 (초): `10`, `10.5`
- Duration 문자열: `"10s"`, `"1m"`, `"250ms"`
- 타임코드: `"00:00:10"`, `"01:23:45"`

#### 길이 정책

- **base** (기본): 베이스 오디오가 끝날 때 출력이 정지됩니다. 더
  일찍 끝나는 오버레이는 사라지고, 베이스보다 긴 오버레이는
  잘립니다.
- **longest**: 마지막 스트림이 끝날 때까지 출력이 재생됩니다. 지연된
  오버레이가 베이스 종료 후에도 계속 재생되어야 할 때 유용합니다.
- **shortest**: 어떤 입력이든(베이스든 오버레이든) 하나가 끝나는 순간
  출력이 정지됩니다. 오버레이가 전체 길이를 결정해야 할 때 유용합니다.

`base`는 베이스에 한 번의 `ffprobe`를 실행해 출력 길이를 제한하고,
`longest`/`shortest`는 `amix`의 `duration` 옵션으로 직접 처리됩니다.

## 워크플로우 상세

### 1. Concatenate Audios

**설명**: ffmpeg의 `concat` 필터를 통해 재인코딩하며 두 오디오를
하나로 이어 붙입니다.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| `first` | file | 예 | 출력에서 먼저 등장하는 오디오 |
| `second` | file | 예 | 출력에서 두 번째로 등장하는 오디오 |

#### 출력

| 필드 | 타입 | 설명 |
|------|------|------|
| `audio` | audio | 이어 붙여진 결과 |

### 2. Overlay Single Audio

**설명**: 단일 오버레이(내레이션, 효과음 등)를 베이스 오디오에
믹싱합니다.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `base` | file | 예 | - | 베이스 오디오 |
| `overlay` | file | 예 | - | 오버레이 오디오 |
| `start_time` | duration | 아니오 | `2s` | 오버레이가 베이스 타임라인에서 처음 재생되는 시각 |
| `gain` | float | 아니오 | `0.8` | 오버레이의 선형 볼륨 배수 |

#### 출력

| 필드 | 타입 | 설명 |
|------|------|------|
| `audio` | audio | 오버레이가 믹싱된 베이스 오디오 |

### 3. Overlay Multiple Audios

**설명**: 내레이션과 효과음을 베이스 트랙 위에 각각의 타이밍과
게인으로 레이어링합니다.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| `base` | file | 예 | 베이스 오디오 |
| `narration` | file | 예 | 내레이션 오버레이, `1s`부터 재생 |
| `sfx` | file | 예 | 효과음 오버레이, `5s`~`7s` 사이 우측 팬으로 재생 |

#### 출력

| 필드 | 타입 | 설명 |
|------|------|------|
| `audio` | audio | 두 오버레이가 모두 믹싱된 베이스 오디오 |

## 팁

- **재인코딩은 피할 수 없음**: 믹싱 작업은 ffmpeg의 필터 그래프를
  거치는데, 이는 스트림 복사된 입력에는 동작하지 않습니다. 기본값이
  대상 출력과 맞지 않으면 `encoding`을 지정하세요.
- **Placement 브로드캐스트**: 단일 `placement` object는 모든
  오버레이에 적용됩니다. 오버레이마다 타이밍, 게인, 팬이 달라야 할
  때만 리스트를 사용하세요.
- **오버레이 동시성**: 비디오 오버레이와 달리 z-order가 없습니다 —
  모든 오버레이가 동시에 재생되어 베이스에 합산됩니다. `overlay`
  리스트의 순서는 결과에 영향을 주지 않습니다.
- **타이밍 시맨틱**: `start_time`은 베이스 타임라인 기준이므로,
  `start_time: 5s`는 오버레이를 5초 뒤로 미룹니다. `end_time`은 지연된
  타임라인의 절대 시각에서 오버레이를 잘라냅니다.
- **페이드아웃에는 `end_time` 필요**: 페이드아웃은 `end_time`에서
  끝나므로, `end_time`을 생략하면 `fade_out`이 비활성화됩니다. 끝에
  페이드를 넣으려면 둘 다 설정하세요.
- **배치 모드**: 베이스 오디오를 리스트로 넘기면 베이스마다 오버레이
  작업이 한 번씩 실행되며, 출력이 리스트로 반환됩니다. 베이스별로
  파라미터를 따로 지정하지 않는 한, 동일한 오버레이 세트가 모든
  베이스에 브로드캐스트됩니다.
- **스트리밍 입력**: 파일이 아닌 오디오 소스(바이트, HTTP 업로드
  등)는 ffmpeg가 시크할 수 있도록 믹싱 전에 임시 파일로
  스풀링됩니다.

## 문제 해결

### 일반적인 문제

1. **ffmpeg not found**: ffmpeg가 설치되어 있고 `PATH`에 있는지
   확인하세요.
2. **`'audios' must contain at least two entries for concat`**: concat은
   최소 두 개의 입력이 필요합니다. 단일 오디오 작업에는 `overlay`나
   다른 컴포넌트를 사용하세요.
3. **concat 시 `Input link ... parameters do not match`**: ffmpeg
   concat 필터는 모든 입력이 샘플레이트와 채널 레이아웃을 동일하게
   가져야 합니다. 이어 붙이기 전에 `audio-converter` 같은 컴포넌트로
   입력을 정규화하세요.
4. **`overlay/placement cardinality mismatch`**: `placement`가 리스트일
   때는 그 길이가 오버레이 개수와 같아야 합니다. 단일 placement
   object는 대신 모든 오버레이에 브로드캐스트됩니다.
5. **믹싱 후 오버레이가 너무 작거나 너무 큼**: 이 컴포넌트의 `amix`는
   정규화 없이 입력을 합산하므로(`normalize=0`) 원래 레벨이
   유지됩니다. 각 오버레이의 `gain`을 조정하거나 — 또는 베이스를
   상류에서 낮춰 — 균형이 맞을 때까지 조정하세요.
6. **페이드아웃이 동작하지 않음**: `fade_out`은 페이드 꼬리를 고정할
   `end_time`이 필요합니다. 둘 다 설정하세요.
7. **concat 후 포맷 불일치**: 출력 포맷은 액션의 `format` 필드에서
   결정됩니다 (기본값: `wav`). 해당 포맷의 기본 코덱이 목적에 맞지
   않는다면 `encoding.codec`을 명시적으로 설정하세요.

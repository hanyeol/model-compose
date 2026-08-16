# 비디오 믹서 예제

이 예제는 ffmpeg를 사용해 여러 영상을 하나의 결과물로 합성하는
`video-mixer` 컴포넌트를 보여줍니다. 두 가지 믹싱 방식을 다룹니다:

- **concat**: 여러 영상을 이어 붙여 하나의 긴 영상으로 만듭니다
- **overlay**: 하나 이상의 영상을 베이스 영상 위에 합성합니다
  (워터마크, PIP, 좌우 분할 레이아웃 등)

## 개요

이 예제는 동일한 `video-mixer` 컴포넌트 위에 세 개의 워크플로우를
노출합니다:

1. **Concatenate Videos**: 여러 영상을 하나의 결과물로 이어 붙이기
2. **Overlay Single Video**: 하나의 오버레이(워터마크 / PIP)를
   베이스 영상 위에 합성
3. **Overlay Multiple Videos**: 여러 오버레이를 베이스 영상 위에
   각각 다른 위치로 쌓아 올리기

## 준비

### 사전 요건

- model-compose가 설치되어 PATH에 등록되어 있어야 함
- [ffmpeg](https://ffmpeg.org/)가 설치되어 PATH에 등록되어 있어야 함

### 설정

예제 디렉터리로 이동합니다:
```bash
cd examples/media-processing/video-mixer
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
   - 필요한 영상 파일을 업로드하고 위치 필드를 설정
   - "Run Workflow" 클릭

   **CLI 사용:**
   ```bash
   # 두 개의 클립을 하나의 영상으로 이어 붙이기
   model-compose run concat --input '{
     "first": "/path/to/intro.mp4",
     "second": "/path/to/main.mp4"
   }'

   # 베이스 영상 위에 PIP 합성
   model-compose run overlay-single --input '{
     "base": "/path/to/lecture.mp4",
     "overlay": "/path/to/webcam.mp4",
     "x": 20,
     "y": 20,
     "width": 320
   }'

   # 베이스 영상 위에 두 개의 오버레이를 각각 다른 위치로 쌓기
   model-compose run overlay-multiple --input '{
     "base": "/path/to/main.mp4",
     "overlay_a": "/path/to/left.mp4",
     "overlay_b": "/path/to/right.mp4"
   }'
   ```

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=overlay-single" \
     -F "base=@/path/to/lecture.mp4" \
     -F "overlay=@/path/to/webcam.mp4" \
     -F "x=20" \
     -F "y=20" \
     -F "width=320"
   ```

## 컴포넌트 상세

### Video Mixer 컴포넌트

- **Type**: `video-mixer`
- **Driver**: `ffmpeg`
- **역할**: ffmpeg 필터(`concat`으로 이어 붙이기, `overlay`로 합성)를
  사용해 여러 영상을 하나의 결과물로 결합합니다.

ffmpeg 필터 그래프는 스트림 복사(stream-copy)된 입력에는 동작할 수
없으므로, 믹싱 시에는 항상 재인코딩이 일어납니다. `encoding` 필드로
출력 컨테이너/코덱을 제어하며, 생략하면 포맷별 합리적인 기본값이
선택됩니다 (mp4 → libx264 + aac, webm → libvpx-vp9 + libopus, ...).

### Concat 방식

ffmpeg의 `concat` 필터로 여러 영상을 끝과 끝으로 이어 붙입니다.
모든 입력은 해상도, SAR, 픽셀 포맷, 프레임레이트, 오디오 샘플레이트,
채널 레이아웃이 모두 동일해야 합니다 — 그렇지 않으면 concat 필터가
`Input link ... parameters do not match` 오류로 실패합니다. `concat`에
넣기 전에 `video-converter`와 같은 컴포넌트로 입력을 정규화하세요.

`encoding` 필드를 통한 재인코딩은 출력 스트림만 제어하며, 서로 다른
입력을 조화시켜 주지는 않습니다. 비디오와 오디오 트랙 모두 이어
붙여지며, 오디오가 없는 입력은 무음으로 처리됩니다.

#### 주요 필드

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| `videos` | 비디오 소스 리스트 | 예 | - | 이어 붙일 영상들, 순서대로 (최소 2개) |
| `crossfade` | duration | 아니오 | - | 향후 지원 예정, 현재 미구현 |
| `encoding` | object | 아니오 | mp4 기본값 | 출력 컨테이너/코덱 |
| `batch_size` | integer | 아니오 | `1` | `videos`가 리스트의 리스트 또는 스트림일 때 배치당 처리되는 *세트* 수 |
| `streaming` | boolean | 아니오 | `false` | 임시 파일 대신 바이트 스트림으로 출력 |

### Overlay 방식

베이스 영상 위에 하나 이상의 오버레이 영상을 합성합니다. 오버레이는
리스트 순서대로 쌓입니다 — 첫 번째 오버레이가 베이스 위에, 두 번째는
그 결과 위에, ... 이런 식이므로 인덱스가 뒤로 갈수록 위에
표시됩니다.

#### 주요 필드

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| `video` | 비디오 소스 또는 리스트 | 예 | - | 베이스 영상 (리스트를 넘기면 배치 모드가 되어 베이스당 하나의 출력 생성) |
| `overlay` | 문자열 또는 문자열 리스트 | 예 | - | 오버레이 영상. 단일 문자열은 자동으로 1개짜리 리스트로 감싸짐 |
| `placement` | object 또는 object 리스트 | 아니오 | 기본 placement 1개 | 오버레이당 하나의 placement. 단일 object는 모든 오버레이에 브로드캐스트, 리스트는 위치로 매칭 |
| `audio_mode` | `base` \| `overlay` \| `mix` \| `none` | 아니오 | `base` | 출력에 어떤 오디오 트랙을 담을지 |
| `duration_mode` | `base` \| `longest` \| `shortest` | 아니오 | `base` | 베이스/오버레이 대비 출력이 얼마나 재생될지 |
| `encoding` | object | 아니오 | mp4 기본값 | 출력 컨테이너/코덱 |
| `batch_size` | integer | 아니오 | `1` | `video`가 리스트/스트림일 때 배치당 처리되는 베이스 영상 수 |
| `streaming` | boolean | 아니오 | `false` | 임시 파일 대신 바이트 스트림으로 출력 |

#### Placement 필드

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `x` | integer | `0` | 오버레이가 배치될 베이스 영상의 X 좌표 |
| `y` | integer | `0` | 오버레이가 배치될 베이스 영상의 Y 좌표 |
| `width` | integer | - | 오버레이를 지정한 너비(픽셀)로 리사이즈 (한쪽만 지정하면 종횡비 유지) |
| `height` | integer | - | 오버레이를 지정한 높이(픽셀)로 리사이즈 |
| `anchor` | `top-left` \| `top-center` \| `top-right` \| `center-left` \| `center` \| `center-right` \| `bottom-left` \| `bottom-center` \| `bottom-right` | `top-left` | `(x, y)`에 정렬되는 오버레이의 기준점 |
| `opacity` | float 0..1 | `1.0` | 알파 배수 |
| `start` | duration | - | 오버레이가 나타나는 시각 (기본값 `0s`) |
| `end` | duration | - | 오버레이가 사라지는 시각 (기본값은 베이스 끝까지) |

`start`/`end`는 다음을 허용합니다:
- 숫자 (초): `10`, `10.5`
- Duration 문자열: `"10s"`, `"1m"`, `"250ms"`
- 타임코드: `"00:00:10"`, `"01:23:45"`

#### 오디오 정책

- **base**: 베이스 영상의 오디오 트랙만 유지 (워터마크 / PIP 시 일반적)
- **overlay**: 오버레이의 오디오 트랙만 유지. 오버레이가 여러 개면
  그 오디오들이 믹싱됩니다
- **mix**: 베이스와 모든 오버레이의 오디오 트랙을 믹싱
- **none**: 출력에서 오디오를 제거

#### 길이 정책

- **base** (기본): 베이스 영상이 끝날 때 출력이 정지됩니다.
  더 일찍 끝나는 오버레이는 사라지고, 베이스보다 긴 오버레이는
  잘립니다.
- **longest**: 마지막 스트림이 끝날 때까지 출력이 재생됩니다. 오버레이
  필터가 계속 합성할 수 있도록 베이스의 마지막 프레임을 복제해
  (`tpad`) 자신의 끝을 넘어서까지 연장합니다.
- **shortest**: 어떤 입력이든(베이스든 오버레이든) 하나가 끝나는 순간
  출력이 정지됩니다. 오버레이가 전체 길이를 결정해야 할 때 유용합니다.

`base`는 베이스에 한 번의 `ffprobe`를 실행해 출력 길이를 제한하고,
`longest`는 pad 길이를 계산하기 위해 모든 입력을 probe하며,
`shortest`는 probe하지 않습니다.

## 워크플로우 상세

### 1. Concatenate Videos

**설명**: ffmpeg의 `concat` 필터를 통해 재인코딩하며 두 영상을 하나로
이어 붙입니다.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| `first` | file | 예 | 출력에서 먼저 등장하는 영상 |
| `second` | file | 예 | 출력에서 두 번째로 등장하는 영상 |

#### 출력

| 필드 | 타입 | 설명 |
|------|------|------|
| `video` | video | 이어 붙여진 결과 |

### 2. Overlay Single Video

**설명**: 단일 오버레이(워터마크, PIP 등)를 베이스 영상 위에
배치합니다.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `base` | file | 예 | - | 베이스 영상 |
| `overlay` | file | 예 | - | 오버레이 영상 |
| `x` | integer | 아니오 | `20` | 베이스 영상의 X 좌표 |
| `y` | integer | 아니오 | `20` | 베이스 영상의 Y 좌표 |
| `width` | integer | 아니오 | `320` | 오버레이를 지정한 너비로 리사이즈 |

#### 출력

| 필드 | 타입 | 설명 |
|------|------|------|
| `video` | video | 오버레이가 위에 합성된 베이스 영상 |

### 3. Overlay Multiple Videos

**설명**: 두 개의 오버레이를 베이스 영상 위에 각각 다른 위치로
합성합니다. 오버레이는 리스트 순서대로 쌓입니다.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| `base` | file | 예 | 베이스 영상 |
| `overlay_a` | file | 예 | 첫 번째 오버레이 (교차 시 `overlay_b` 아래에 그려짐) |
| `overlay_b` | file | 예 | 두 번째 오버레이 (교차 시 `overlay_a` 위에 그려짐) |

#### 출력

| 필드 | 타입 | 설명 |
|------|------|------|
| `video` | video | 두 오버레이가 모두 위에 합성된 베이스 영상 |

## 팁

- **재인코딩은 피할 수 없음**: 믹싱 작업은 ffmpeg의 필터 그래프를
  거치는데, 이는 스트림 복사된 입력에는 동작하지 않습니다. 기본값이
  대상 컨테이너와 맞지 않으면 `encoding`을 지정하세요.
- **Placement 브로드캐스트**: 단일 `placement` object는 모든
  오버레이에 적용됩니다. 오버레이마다 좌표, 크기, 타이밍이 달라야 할
  때만 리스트를 사용하세요.
- **오버레이 스택 순서**: 리스트의 첫 번째 오버레이가 먼저 합성되므로,
  영역이 겹칠 때는 뒤쪽 오버레이가 위에 표시됩니다. 리스트는 아래부터
  위 순서로 정렬하세요.
- **Anchor 시맨틱**: `anchor`는 오버레이를 `(x, y)` 기준으로
  이동시킵니다. 예를 들어 `anchor: center`는 좌측 상단 대신 오버레이의
  *중심*을 `(x, y)`에 배치합니다.
- **시간 제한 오버레이**: `start`/`end`로 특정 시간대에만 오버레이가
  보이도록 할 수 있습니다 — 몇 초만 나오는 하단 자막이나, 나중에
  등장하는 워터마크 등에 유용합니다.
- **배치 모드**: 베이스 영상을 리스트로 넘기면 베이스마다 오버레이
  작업이 한 번씩 실행되며, 출력이 리스트로 반환됩니다. 베이스별로
  파라미터를 따로 지정하지 않는 한, 동일한 오버레이 세트가 모든
  베이스에 브로드캐스트됩니다.
- **스트리밍 입력**: 파일이 아닌 비디오 소스(바이트, HTTP 업로드 등)는
  ffmpeg가 시크할 수 있도록 믹싱 전에 임시 파일로 스풀링됩니다.

## 문제 해결

### 일반적인 문제

1. **ffmpeg not found**: ffmpeg가 설치되어 있고 `PATH`에 있는지
   확인하세요.
2. **`'videos' must contain at least two entries for concat`**: concat은
   최소 두 개의 입력이 필요합니다. 단일 영상 작업에는 `overlay`나 다른
   컴포넌트를 사용하세요.
3. **concat 시 `Input link ... parameters do not match`**: ffmpeg
   concat 필터는 모든 입력이 해상도, SAR, 픽셀 포맷, 프레임레이트,
   오디오 샘플레이트, 채널 레이아웃을 동일하게 가져야 합니다.
   이어 붙이기 전에 `video-converter` 같은 컴포넌트로 입력을
   정규화하세요.
4. **`overlay/placement cardinality mismatch`**: `placement`가 리스트일
   때는 그 길이가 오버레이 개수와 같아야 합니다. 단일 placement
   object는 대신 모든 오버레이에 브로드캐스트됩니다.
5. **overlay-multiple의 잘못된 z-order**: 오버레이는 리스트 순서대로
   쌓입니다 (첫 번째가 먼저 그려지고, 마지막이 위에 표시). 순서를
   변경하려면 리스트를 재정렬하세요.
6. **`audio_mode: overlay` 사용 시 무음 출력**: 오버레이 영상에 오디오
   트랙이 없을 수 있습니다. 베이스에 유지하고 싶은 오디오가 있다면
   `audio_mode: base` 또는 `audio_mode: mix`로 전환하세요.
7. **concat 후 포맷 불일치**: 출력 포맷은 `encoding.format`에서
   결정됩니다 (기본값: `mp4`). 입력에 특이한 코덱이 있다면
   `encoding.video.codec` / `encoding.audio.codec`를 명시적으로
   설정하세요.

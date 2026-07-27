# 화면 캡처 예제

이 예제는 `screen-capture` 컴포넌트를 사용해 로컬 화면, 영역, 마이크를 연속 인코딩 스트림으로 캡처하고 `file-store`로 로컬 파일에 저장하는 방법을 보여줍니다.

## 개요

세 가지 워크플로우가 MVP 캡처 모드 세 가지를 시연합니다:

1. **데스크탑 클립 캡처** — 지정한 framerate로 전체 화면 캡처, MPEG-TS 파일로 저장
2. **화면 영역 캡처** — 화면의 직사각형 영역만 캡처 (Windows/Linux는 네이티브 region 플래그, macOS는 디코드 후 crop 필터)
3. **마이크 오디오 캡처** — 기본 마이크에서 오디오만 캡처, AAC로 저장 (화면 기록 권한 불필요)

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- `ffmpeg` 바이너리
- 이 예제는 macOS 시스템 오디오 캡처를 사용하지 않지만, 필요하다면 [`audiotee`](https://github.com/makeusabrew/audiotee) CLI가 필요합니다. 마이크 전용 캡처는 audiotee 없이도 됩니다.

### 플랫폼 권한

첫 화면 캡처 실행 시:

- **macOS**: 화면 기록 권한 프롬프트가 뜹니다. 거부하면 예외 없이 빈 스트림이 나옵니다.
- **Linux Wayland**: PipeWire 포털을 통한 세션별 사용자 승인이 필요합니다.

마이크 캡처는 별도의 OS 권한(마이크)만 쓰므로, macOS에서 화면 기록 권한 없이 파이프라인을 검증하기에 적합합니다.

### macOS 디스플레이 인덱스

macOS에서 `display` 필드는 avfoundation 디바이스 인덱스이며, 비디오 카메라 뒤에 오프셋으로 붙습니다. 다음 명령으로 확인하세요:

```bash
ffmpeg -f avfoundation -list_devices true -i ""
```

`[4] Capture screen 0` 같은 줄을 찾아서 `--input '{"display": 4}'`로 지정합니다. Windows와 Linux에서는 보통 기본값 `0`으로 충분합니다.

### 설정

```bash
cd examples/media-processing/screen-capture
```

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

   - API 엔드포인트: http://localhost:8080/api
   - 웹 UI: http://localhost:8081
   - 캡처된 클립은 이 디렉토리의 `./output/`에 저장됩니다.

2. **워크플로우 실행:**

   **CLI 사용:**
   ```bash
   # 15 fps로 5초짜리 데스크탑 클립 (macOS에서는 display 인덱스 조정)
   model-compose run capture-desktop-clip --input '{"duration": "5s", "framerate": 15, "display": 0}'

   # 좌측 상단에서 100px 오프셋된 720p 영역, 3초짜리
   model-compose run capture-region-clip --input '{
     "duration": "3s",
     "x": 100,
     "y": 100,
     "width": 1280,
     "height": 720
   }'

   # 3초짜리 마이크 클립
   model-compose run capture-microphone-clip --input '{"duration": "3s"}'
   ```

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow": "capture-desktop-clip", "input": {"duration": "5s"}}'
   ```

3. **결과 확인:**

   ```bash
   ls -lh output/
   ffprobe output/desktop-*.ts
   ```

## 컴포넌트 세부사항

### 화면 캡처 컴포넌트

- **유형**: `screen-capture`
- **목적**: 로컬 화면과 시스템/마이크 오디오의 라이브 캡처
- **드라이버**: `ffmpeg` (OS 자동 감지: 비디오는 avfoundation / gdigrab / x11grab, 마이크는 avfoundation / dshow / pulse)

### 파일 스토어 컴포넌트

- **유형**: `file-store`
- **목적**: 인코딩된 스트림 청크가 도착하는 대로 로컬 파일에 저장

## 워크플로우 세부사항

### 1. 데스크탑 클립 캡처

**ID**: `capture-desktop-clip`
**설명**: 지정한 duration만큼 전체 화면을 캡처해 MPEG-TS로 저장합니다.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `duration` | string | 아니요 | `5s` | 캡처 길이 (예: `5s`, `30s`, `2m`) |
| `framerate` | number | 아니요 | `15` | 비디오 프레임레이트 |
| `display` | integer | 아니요 | `0` | 디스플레이 / avfoundation 디바이스 인덱스 (위 macOS 노트 참고) |
| `filename` | string | 아니요 | 타임스탬프 | 파일명 stem (확장자 제외) |

#### 출력

```json
{ "file": "output/desktop-1730000000.ts" }
```

---

### 2. 화면 영역 캡처

**ID**: `capture-region-clip`
**설명**: 화면의 직사각형 영역만 캡처합니다. Windows `gdigrab`와 Linux `x11grab`는 네이티브 region 플래그를, macOS는 디코드 후 `-vf crop` 필터를 사용합니다.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `duration` | string | 아니요 | `5s` | 캡처 길이 |
| `framerate` | number | 아니요 | `15` | 비디오 프레임레이트 |
| `display` | integer | 아니요 | `0` | 디스플레이 / avfoundation 디바이스 인덱스 |
| `x` | integer | 아니요 | `0` | 영역 좌측 (픽셀) |
| `y` | integer | 아니요 | `0` | 영역 상단 (픽셀) |
| `width` | integer | 아니요 | `640` | 영역 너비 (픽셀) |
| `height` | integer | 아니요 | `480` | 영역 높이 (픽셀) |
| `filename` | string | 아니요 | 타임스탬프 | 파일명 stem |

#### 출력

```json
{ "file": "output/region-1730000000.ts" }
```

---

### 3. 마이크 오디오 캡처

**ID**: `capture-microphone-clip`
**설명**: 오디오 전용 캡처. 화면 기록 권한을 우회하므로 파이프라인 검증에 가장 편합니다.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `duration` | string | 아니요 | `3s` | 캡처 길이 |
| `filename` | string | 아니요 | 타임스탬프 | 파일명 stem |

#### 출력

```json
{ "file": "output/mic-1730000000.aac" }
```

## 커스터마이징

### 컨테이너 포맷 변경

기본 MPEG-TS 컨테이너는 첫 바이트 지연이 낮고 중단에 강해서 선택했습니다. MP4나 WebM으로 방출하려면 액션의 `encoding.format`을 지정합니다:

```yaml
- id: desktop
  video_source: display
  encoding:
    format: mp4         # 파이프 출력용 fragmented mp4 플래그가 자동으로 추가됨
    video:
      codec: libx264
      bitrate: 6M
```

`save` job의 `path` 확장자도 함께 바꿔야 합니다.

### 무한 캡처

`duration`을 빼면 컨슈머(이 예제에선 `file-store`)가 닫힐 때까지 무한 스트리밍됩니다. 다른 다운스트림이 중단 시점을 결정할 때 유용하지만, 이 예제의 파일 저장 데모는 캡처가 멈춰야 워크플로우가 완료되므로 제한이 있습니다.

### 시스템 오디오 (macOS)

macOS는 ffmpeg에서 시스템 오디오 루프백을 직접 잡지 못하게 막습니다. 스피커에서 나오는 소리를 캡처하려면 [`audiotee`](https://github.com/makeusabrew/audiotee)를 설치하고 액션에 `audio_source: system`을 설정하세요. Core Audio process-tap API의 특성상 시작 후 첫 청크까지 4–5초의 지연이 있습니다.

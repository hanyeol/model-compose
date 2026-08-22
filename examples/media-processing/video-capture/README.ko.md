# Video Capture 예제

이 예제는 `video-capture` 컴포넌트를 사용해 로컬 카메라를 캡처하고 인코딩된 영상을 **HTTP 응답에 직접** fragmented MP4 스트림으로 반환합니다. 파일 저장이나 중간 버퍼링 단계가 없습니다.

OS가 카메라로 노출하는 장치라면 무엇이든 동작합니다: 물리 웹캠, USB 캡처 카드, 가상 카메라(OBS Virtual Camera, Snap Camera 등)가 모두 ffmpeg 관점에서는 동일한 비디오 디바이스로 취급됩니다.

## 개요

단일 워크플로우 `capture-webcam`이 기본 카메라를 열고 fragmented MP4 스트림을 인코딩해 HTTP 응답으로 반환합니다. 첫 fragment가 전달되는 순간부터 재생이 가능하므로, MP4 over HTTP를 지원하는 downstream 도구는 캡처가 끝날 때까지 기다리지 않고 즉시 디코딩을 시작할 수 있습니다.

macOS에서는 인코더 기본값이 `h264_videotoolbox`(하드웨어)이므로 1080p30 실시간 처리가 가능하고, Windows/Linux는 `libx264`가 기본입니다.

## 준비

### 사전 요구사항

- model-compose가 PATH에 설치되어 있어야 함
- `ffmpeg`이 시스템 PATH에 있어야 함 (macOS Homebrew 빌드는 하드웨어 인코더 지원 포함)

### 플랫폼 권한

카메라 캡처를 처음 실행할 때:

- **macOS**는 카메라 권한을 요청합니다. 거부 시 빈 스트림이 반환됩니다 (예외 아님).
- **Windows / Linux**는 현재 사용자 세션의 디바이스 권한을 사용하며 별도 프롬프트가 없습니다.

### 카메라 찾기

플랫폼 기본값이 일반적인 경우를 처리하지만, 카메라가 여러 대이거나 가상 카메라를 대상으로 하려면 먼저 디바이스 목록을 확인하세요:

```bash
# macOS
ffmpeg -f avfoundation -list_devices true -i ""

# Windows
ffmpeg -f dshow -list_devices true -i dummy

# Linux
v4l2-ctl --list-devices
```

액션의 `device` 필드로 지정합니다 (아래 [커스터마이징](#커스터마이징) 참고).

### 설정

```bash
cd examples/media-processing/video-capture
```

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

   - API 엔드포인트: http://localhost:8080/api
   - Web UI: http://localhost:8081

2. **워크플로우 실행:**

   **CLI 사용 (스트리밍 MP4를 파일로 저장):**
   ```bash
   # 720p 30fps로 10초 캡처 → webcam.mp4
   model-compose run capture-webcam \
     --input '{"duration": "10s", "framerate": 30, "width": 1280, "height": 720}' \
     --output webcam.mp4
   ```

   **API 사용 (curl):**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow": "capture-webcam", "input": {"duration": "5s"}}' \
     --output webcam.mp4
   ```

   **결과 재생:**
   ```bash
   open webcam.mp4         # macOS
   xdg-open webcam.mp4     # Linux
   start webcam.mp4        # Windows
   ```

   또는 http://localhost:8081 웹 UI를 열면 인코딩된 영상이 브라우저에서 바로 재생됩니다.

## 컴포넌트 상세

### Video Capture Component

- **타입**: `video-capture`
- **목적**: 로컬 카메라 / 캡처 카드 / 가상 카메라의 실시간 캡처
- **드라이버**: `ffmpeg` — `avfoundation`(macOS) / `dshow`(Windows) / `v4l2`(Linux) 자동 선택
- **기본 인코더**: macOS는 `h264_videotoolbox`, 나머지 플랫폼은 `libx264`

## 워크플로우 상세

### Capture Webcam

**ID**: `capture-webcam`
**설명**: fragmented MP4를 HTTP 응답으로 바로 스트리밍하는 카메라 캡처.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|-----|------|--------|-----|
| `duration` | string | 아니오 | `10s` | 캡처 길이 (예: `10s`, `30s`, `2m`) |
| `framerate` | number | 아니오 | `30` | 비디오 프레임레이트 |
| `width` | integer | 아니오 | `1280` | 프레임 너비 (픽셀) |
| `height` | integer | 아니오 | `720` | 프레임 높이 (픽셀) |

#### 출력

응답 본문 자체가 fragmented MP4 스트림입니다. `model-compose run --output`으로 호출하면 바이트를 `.mp4` 파일로 저장한 뒤 미디어 플레이어나 브라우저로 재생하면 됩니다.

## 커스터마이징

### 특정 카메라 선택

액션에 `device`를 추가해 인덱스나 이름으로 지정합니다:

```yaml
- id: webcam
  source: camera
  device: 1               # macOS avfoundation 인덱스 (위 `-list_devices` 결과 참고)
  # device: "OBS Virtual Camera"      # macOS/Windows: 이름을 정확히 일치시켜야 함
  # device: /dev/video2               # Linux
  framerate: ${input.framerate}
  ...
```

Windows에서는 `device`가 필수입니다 — dshow는 숫자 인덱스를 지원하지 않으므로 반드시 디바이스 이름을 전달해야 합니다.

### 고해상도 / 고프레임레이트

요청에 `width`/`height`/`framerate`를 올려서 캡처합니다:

```bash
model-compose run capture-webcam \
  --input '{"width": 1920, "height": 1080, "framerate": 60, "duration": "5s"}' \
  --output webcam-1080p60.mp4
```

macOS 기본 인코더(`h264_videotoolbox`)는 1080p60을 여유롭게 처리합니다. Windows/Linux의 `libx264`로 1080p60 실시간을 맞추기 어렵다면 `encoding.video.bitrate`를 올리거나 하드웨어 코덱(`h264_nvenc` — NVIDIA, `h264_qsv` — Intel Quick Sync, `h264_vaapi` — Linux VA-API)으로 오버라이드하세요.

### 코덱 / 비트레이트 오버라이드

액션에 `encoding`을 명시합니다:

```yaml
- id: webcam
  source: camera
  ...
  encoding:
    format: mp4
    video:
      codec: h264_nvenc   # 또는 libx264, h264_qsv, h264_vaapi 등
      bitrate: 8M
```

### 다른 컨테이너로 출력

`encoding.format`을 `ts`(MPEG-TS — first-byte latency가 낮고, 캡처가 중단되어도 재생 가능)나 `webm`(VP9)으로 바꿉니다. `mp4` / `mov` / `m4v`인 경우 fragmented MP4 플래그가 자동으로 추가되므로 별도 튜닝 없이 HTTP로 그대로 스트리밍됩니다.

### 무제한 캡처

입력에서 `duration`을 제거(또는 null)하면 클라이언트가 연결을 닫을 때까지 무한정 스트리밍됩니다. 소비자 쪽에서 정지 시점을 결정하는 경우에 유용합니다. 위의 "파일로 저장" 데모에서는 캡처가 멈춰야 응답이 완료되므로 큰 의미는 없습니다.

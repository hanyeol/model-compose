# Audio Capture 예제

이 예제는 `audio-capture` 컴포넌트를 사용해 로컬 마이크나 시스템 오디오(루프백)를 캡처하고, 인코딩된 오디오를 **HTTP 응답에 직접** AAC 스트림으로 반환합니다. 파일 저장이나 중간 버퍼링 단계가 없습니다.

## 개요

두 개의 워크플로우가 하나의 `audio-capture` 컴포넌트를 공유합니다:

1. **Capture Microphone** — 기본 마이크를 녹음합니다. 마이크 권한만 필요해서 파이프라인 스모크 테스트에 가장 빠릅니다.
2. **Capture System Audio** — OS가 재생 중인 오디오(루프백)를 녹음합니다. macOS는 [`audiotee`](https://github.com/makeusabrew/audiotee) 헬퍼가 필요하고, Windows는 DirectShow `virtual-audio-capturer`를, Linux는 기본 sink의 PulseAudio monitor를 사용합니다.

두 워크플로우 모두 AAC(ADTS)로 인코딩하고 바이트가 도착하는 즉시 응답으로 스트리밍하므로, downstream 소비자는 캡처가 끝날 때까지 기다리지 않고 즉시 디코딩을 시작할 수 있습니다.

## 준비

### 사전 요구사항

- model-compose가 PATH에 설치되어 있어야 함
- `ffmpeg`이 시스템 PATH에 있어야 함
- **macOS 시스템 오디오 전용**: [`audiotee`](https://github.com/makeusabrew/audiotee) CLI가 PATH에 있어야 함. `brew install audiotee`로 설치. 마이크 캡처는 필요 없음.

### 플랫폼 권한

각 워크플로우를 처음 실행할 때:

- **macOS 마이크**는 마이크 권한을 요청합니다.
- **macOS 시스템 오디오**는 추가로 `audiotee`의 Core Audio process-tap 권한을 한 번 더 요청합니다.
- **Windows / Linux**는 현재 사용자 세션의 권한을 사용하며 별도 프롬프트가 없습니다.

### 오디오 디바이스 찾기

플랫폼 기본값이 일반적인 경우를 처리하지만, 여러 입력 장치가 있거나 특정 장치를 지정하려면 먼저 디바이스 목록을 확인하세요:

```bash
# macOS
ffmpeg -f avfoundation -list_devices true -i ""

# Windows
ffmpeg -f dshow -list_devices true -i dummy

# Linux
pactl list sources short
```

액션의 `device` 필드로 지정합니다 (아래 [커스터마이징](#커스터마이징) 참고).

### 설정

```bash
cd examples/media-processing/audio-capture
```

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

   - API 엔드포인트: http://localhost:8080/api
   - Web UI: http://localhost:8081

2. **워크플로우 실행:**

   **CLI 사용 (스트리밍 AAC를 파일로 저장):**
   ```bash
   # 마이크 10초 클립 → mic.aac
   model-compose run capture-microphone \
     --input '{"duration": "10s"}' \
     --output mic.aac

   # 시스템 오디오 10초 클립 → system.aac
   model-compose run capture-system-audio \
     --input '{"duration": "10s"}' \
     --output system.aac
   ```

   **API 사용 (curl):**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow": "capture-microphone", "input": {"duration": "5s"}}' \
     --output mic.aac
   ```

   **결과 재생:**
   ```bash
   open mic.aac         # macOS
   xdg-open mic.aac     # Linux
   start mic.aac        # Windows
   ```

   또는 http://localhost:8081 웹 UI를 열면 인코딩된 오디오가 브라우저에서 바로 재생됩니다.

## 컴포넌트 상세

### Audio Capture Component

- **타입**: `audio-capture`
- **목적**: 로컬 마이크 또는 시스템 오디오 루프백의 실시간 캡처
- **드라이버**: `ffmpeg` — `avfoundation`(macOS) / `dshow`(Windows) / `pulse`(Linux) 자동 선택. macOS 시스템 오디오는 `audiotee` 사이드카를 함께 실행합니다.
- **기본 코덱/컨테이너**: ADTS로 감싼 `aac`

## 워크플로우 상세

### 1. Capture Microphone

**ID**: `capture-microphone`
**설명**: 기본 마이크를 녹음해 응답으로 AAC를 스트리밍.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|-----|------|--------|-----|
| `duration` | string | 아니오 | `10s` | 캡처 길이 (예: `10s`, `30s`, `2m`) |

#### 출력

응답 본문 자체가 AAC(ADTS) 스트림입니다. `model-compose run --output`으로 호출하면 바이트를 `.aac` 파일로 저장한 뒤 미디어 플레이어나 브라우저로 재생하면 됩니다.

---

### 2. Capture System Audio

**ID**: `capture-system-audio`
**설명**: OS가 재생 중인 오디오(루프백)를 녹음해 응답으로 AAC를 스트리밍.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|-----|------|--------|-----|
| `duration` | string | 아니오 | `10s` | 캡처 길이 |

#### 출력

마이크와 동일한 구조: 응답 본문에 AAC 바이트.

#### 플랫폼 노트

- **macOS**는 PATH에 `audiotee`가 필요합니다. 첫 시스템 오디오 청크가 도착하기까지 약 4~5초가 걸릴 수 있는데, 이는 Core Audio process-tap의 시작 특성이며 드라이버 문제는 아닙니다.
- **Windows**는 `virtual-audio-capturer` DirectShow 디바이스에 의존합니다. 설치되어 있지 않다면 [screen-capture-recorder](https://github.com/rdp/screen-capture-recorder-to-video-windows-free)를 설치하세요.
- **Linux**는 기본 sink의 PulseAudio monitor(`default.monitor`)를 읽습니다. PipeWire의 PulseAudio 호환 레이어도 동일하게 동작합니다.

## 커스터마이징

### 특정 디바이스 선택

액션에 `device`를 추가해 인덱스나 이름으로 지정합니다:

```yaml
- id: microphone
  source: microphone
  device: 1                          # macOS avfoundation 인덱스 (위 `-list_devices` 참고)
  # device: "Microphone (USB Audio)"  # Windows: 이름을 정확히 일치시켜야 함
  # device: "alsa_input.usb-...-mono" # Linux (`pactl list sources short` 결과)
  duration: ${input.duration}
```

### 샘플레이트 / 채널 변경

STT 파이프라인은 보통 16 kHz 모노를 요구합니다. 기본값은 디바이스가 선택하도록 위임합니다. 소스 단계에서 다운샘플링/다운믹싱하면 대역폭을 절약할 수 있습니다:

```yaml
- id: microphone
  source: microphone
  sample_rate: 16000
  channels: 1
  duration: ${input.duration}
```

### 코덱 / 비트레이트 오버라이드

액션에 `encoding`을 명시합니다:

```yaml
- id: microphone
  source: microphone
  ...
  encoding:
    format: m4a          # 또는 ogg, mp3, wav 등
    audio:
      codec: aac         # ogg는 libopus 사용
      bitrate: 192k
```

비디오 지향 컨테이너(`mp4`, `webm`)는 오디오 전용 컨테이너(`m4a`, `ogg`)로 자동 매핑되므로 downstream 도구가 항상 디코딩 가능한 오디오 스트림을 받습니다.

### 무제한 캡처

입력에서 `duration`을 제거(또는 null)하면 클라이언트가 연결을 닫을 때까지 무한정 스트리밍됩니다. 소비자 쪽에서 정지 시점을 결정하는 경우에 유용합니다. 위의 "파일로 저장" 데모에서는 캡처가 멈춰야 응답이 완료되므로 큰 의미는 없습니다.

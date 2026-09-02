# 비디오 리파이너 예제

비디오의 오디오 트랙에서 Silero VAD로 음성 구간을 검출하고, 원본 비디오에서 그 구간만 잘라내 하나의 "음성만 있는" mp4로 합치는 워크플로우 예제입니다. Silero VAD는 스트리밍 모드로 동작해서, 확정된 음성 세그먼트가 나오는 즉시 clipper로 흐릅니다 — 전체 오디오 분석이 끝날 때까지 기다리지 않습니다.

## 개요

입력 비디오를 받아, 사람이 말하는 구간만 남긴 리파인 비디오를 반환합니다.

전략:

1. **업로드 스트림을 fan-out** — `fan-out` 작업을 `spool: true` 모드로 실행. 업로드는 1회 소비이고, clipper는 VAD가 세그먼트를 하나 이상 emit한 후에야 소비 시작 — 평범한 인메모리 fan-out 큐라면 VAD가 오디오를 훑는 동안 업로드 전체를 버퍼링해야 함. spool 모드는 업로드를 tempfile에 한 번 랜딩하고 각 브랜치에 파일 기반 StreamResource를 넘겨서, 큐 backpressure 없이 서로 다른 속도로 seek/read 가능. 두 브랜치가 모두 close되면 tempfile 삭제.
2. **오디오 트랙 분리** — `audio-extractor`로 비디오에서 오디오만 뽑아둠 (`format: wav` — 비압축; Silero가 내부에서 16 kHz mono로 downmix/resample).
3. **음성 구간 검출** — Silero VAD를 `streaming: true`로 실행. 각 확정 세그먼트가 `{start_time, end_time, confidence}` 형태로 즉시 emit되므로, clipper는 전체 오디오 분석 완료를 기다리지 않고 곧바로 작업 시작.
4. **자르기 + 이어붙이기** — `video-clipper`(`merge: true`)가 VAD 세그먼트 스트림을 소비. 각 `[start_time, end_time]` 슬라이스를 `ffmpeg -c copy`로 spool된 비디오에서 잘라내고 (재인코딩 없음), ffmpeg의 `concat` 데뮤서로 모든 클립을 하나의 mp4로 합침.

### 왜 spool fan-out인가

업로드 스트림은 1회 소비 — `audio-extractor`와 `video-clipper` 둘 다 같은 원본 바이트를 읽어야 함. 일반 fan-out은 업로드를 두 개의 인메모리 브랜치로 tee하지만, 두 브랜치가 비슷한 속도로 소비할 때만 메모리가 유계입니다. 이 워크플로우에서는 clipper가 VAD에 의해 gate됨 (VAD가 마지막 세그먼트를 내기 전에 오디오 전체를 훑고, 이후에도 계속 진행) — 그래서 clipper 브랜치가 오디오 브랜치보다 임의로 뒤처지고, fan-out 큐가 업로드 전체를 버퍼링해야 하는 상황이 됨. `spool: true`는 인메모리 큐를 tempfile로 대체 — 업로드가 도착하는 대로 디스크에 한 번 쓰이고, 두 브랜치가 각자 파일을 열고, 마지막 브랜치 close 시 파일 삭제. 별도 `file-store` 컴포넌트 없이도 워크플로우는 end-to-end 스트리밍을 유지하며 메모리도 유계.

### 왜 스트리밍 VAD

Silero의 non-streaming 모드는 오디오 전체 처리 완료 후에 세그먼트 리스트를 반환하므로, VAD가 끝나기 전엔 clipper가 시작할 수 없습니다. `streaming: true`이면 clipper가 첫 세그먼트 확정 즉시 자르기 시작하고 ffmpeg concat 단계가 도착하는 클립들을 이어붙임 — 파이프라인이 순차적으로 도는 대신 VAD와 clipping이 겹쳐 실행됩니다.

## 준비

### 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- FFmpeg(및 `ffprobe`)가 설치되어 PATH에서 사용 가능 — `audio-extractor`와 `video-clipper` 둘 다 사용
- Silero VAD 의존성 (첫 실행 시 자동 설치):
  - `silero-vad`, `torch`, `torchaudio`, `numpy`

### 설정

1. 예제 디렉터리로 이동:
   ```bash
   cd examples/media-processing/video-refiner
   ```

2. 리파인할 비디오 파일 준비. spool tempfile은 OS 기본 임시 디렉터리에 쓰이고 워크플로우 종료 후 자동 정리됨 — 예제 디렉터리에 별도 스토리지 폴더가 만들어지지 않음.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행:**

   **Web UI:**
   - Web UI 열기: http://localhost:8081
   - 비디오 업로드하고 필요 시 `threshold` / `min_speech_duration` / `min_silence_duration` / `speech_padding_time` 조정
   - "Run Workflow" 클릭 후 리파인된 비디오 다운로드

   **API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F 'input={"threshold": 0.5, "min_speech_duration": "250ms"};type=application/json' \
     -F 'video=@./recording.mp4'
   ```

   **CLI:**
   ```bash
   model-compose run --input '{
     "video": "./recording.mp4",
     "threshold": 0.5,
     "min_speech_duration": "250ms",
     "min_silence_duration": "500ms",
     "speech_padding_time": "100ms"
   }'
   ```

## 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `video` | video (file) | Yes | - | 리파인할 입력 비디오 |
| `threshold` | number | No | `0.5` | Silero 음성 확률 임계값 (0.0 – 1.0). 높을수록 엄격 — 경계선 음성을 더 버리려면 올리고, 애매한 순간을 더 포착하려면 낮추세요 |
| `min_speech_duration` | duration | No | `250ms` | 이보다 짧은 확정 음성 chunk는 버림 |
| `min_silence_duration` | duration | No | `500ms` | 인접 음성 chunk 사이에 이 정도 무음이 있어야 별개 세그먼트로 취급 |
| `speech_padding_time` | duration | No | `100ms` | 각 검출된 세그먼트의 양쪽에 추가하는 패딩. Silero의 프레임 단위 임계값 때문에 발생하는 어두 자음 잘림 방지 |

duration 필드는 `"250ms"`, `"0.5s"`, 또는 순수 숫자(초)로 지정.

## 작업 상세

### Fan-Out (`fanout-video`)
- **타입**: `fan-out` (`spool: true`)
- **역할**: 1회 소비인 업로드 스트림을 두 개의 독립 브랜치로 tee — `for-audio` (`extract` → VAD로 흐름)와 `for-clip` (clipper로 흐름). `spool: true`이므로 업로드가 tempfile에 한 번 쓰이고, 각 브랜치가 각자 파일을 오픈; 두 브랜치가 모두 close되면 tempfile 삭제. clipper 브랜치는 VAD가 오디오 상당 부분을 처리한 후에야 소비 시작하므로 일반 fan-out 경로였다면 큐 backpressure에 걸림 — spool이 그 문제를 회피.

## 컴포넌트 상세

### Audio Extractor (`extractor`)
- **타입**: `audio-extractor`
- **드라이버**: `ffmpeg`
- **역할**: 입력을 비압축 WAV로 읽음. 상류 spool fan-out의 `for-audio` 브랜치에서 흘러들어와 clipper와 병렬로 업로드를 소비 (공유 스토리지에 비디오를 랜딩하지 않음). Silero가 내부에서 16 kHz mono로 downmix/resample하므로 WAV가 자연스러운 선택.

### VAD (`vad`)
- **타입**: `model` — `voice-activity-detection` 태스크
- **드라이버**: `custom` (Silero family)
- **역할**: 추출된 오디오에서 Silero VAD를 `streaming: true`로 실행. 각 확정 음성 세그먼트가 `{start_time, end_time, confidence}` 형태로 즉시 emit됨. 모델은 `silero-vad` pip 패키지에 번들되어 있어서 별도 다운로드 불필요. `max_concurrent_count: 1`로 모델 인스턴스 접근을 직렬화.

### Clipper (`clipper`)
- **타입**: `video-clipper`
- **드라이버**: `ffmpeg`
- **역할**: VAD 세그먼트 스트림을 소비해서 각 `[start_time, end_time]` 슬라이스를 spool된 비디오에서 `ffmpeg -c copy`로 잘라냄 (재인코딩 없음). `merge: true`라서 모든 클립을 ffmpeg의 `concat` 데뮤서로 하나의 mp4로 합치므로, 워크플로우 output은 개별 클립 스트림이 아니라 하나의 재생 가능한 리파인 비디오. VAD의 추가 `confidence` 필드는 그냥 통과 — clipper는 `start_time` / `end_time`만 읽음.

## 참고와 튜닝

- **Threshold**: 클립이 하나도 생성 안 되면 `threshold`가 너무 엄격일 가능성. 낮추거나(예: `0.3`) `min_speech_duration`을 줄이세요. 오탐지가 많으면 `threshold`를 올리세요(예: `0.6`).
- **패딩**: `speech_padding_time` 100–200 ms면 대개 Silero의 프레임 단위 임계값 때문에 발생하는 어두 자음 잘림을 방지합니다. 여전히 첫 자음이 잘리면 더 올리세요.
- **무손실 클리핑**: clipper가 `-c copy`를 쓰므로 컷 포인트가 가장 가까운 이전 키프레임에 스냅됩니다. h.264 / hevc 콘텐츠에서는 개별 컷이 수십 ms 어긋날 수 있음. 프레임 정확도가 필요하면 clipper 뒤에 `video-encoder`를 연결하세요 — "재인코딩 없음" 특성은 잃지만 정확한 경계를 얻음.
- **스트리밍 VAD, 이어붙인 output**: VAD가 스트리밍 모드라서 세그먼트 검출과 clipping이 겹쳐 실행되지만, clipper의 `merge: true`는 전체 세그먼트 스트림 완료를 기다린 후 이어붙임. 클립을 완성되는 대로 하나씩 yield하고 싶으면 `merge: false`로 바꾸고 워크플로우 output을 스트림 형태로 변경.
- **Spool tempfile 위치**: spool은 `tempfile.NamedTemporaryFile`이 반환하는 OS 임시 디렉터리에 씀. `TMPDIR`이 작은 파티션을 가리키는 시스템에서는 override 필요 (예: `TMPDIR=/data/tmp model-compose up`) — 그렇지 않으면 업로드 크기가 파티션 용량을 초과할 수 있음.
- **언제 spool이 맞는 선택인가**: `spool: true`는 한 fan-out 브랜치가 다른 브랜치보다 훨씬 느리게 소비하거나 (또는 하류 신호를 기다린 후에야 소비 시작할 때) 쓰기 좋은 노브. 모든 브랜치가 비슷한 속도로 흐르면 기본 인메모리 fan-out이 저렴. spool은 RAM을 디스크로 교환하고 실행당 tempfile write 한 번을 추가.

## 문제 해결

### 흔한 이슈

1. **클립이 하나도 안 나옴 / output이 비어 있음**: `threshold`가 너무 엄격. 낮추거나(예: `0.3`) `min_speech_duration`을 줄이세요.
2. **세그먼트 경계에서 단어가 잘림**: `speech_padding_time`을 올리세요(예: `200ms`).
3. **`ffmpeg` 없음**: FFmpeg과 `ffprobe`를 설치하고 둘 다 `PATH`에 있는지 확인.
4. **Spool tempfile write 실패 / "No space left on device"**: OS 임시 디렉터리 공간 부족. 업로드가 들어갈 파티션으로 `TMPDIR` 설정하거나, `spool: true` 대신 큰 디스크를 가진 `file-store` 사용.
5. **"Upload stream already consumed" 에러**: 업로드 스트림은 1회 소비. 이 워크플로우는 정확히 그 이유로 fan-out에 `spool: true` 사용. `fanout-video` 작업을 건너뛰도록 커스터마이즈하면 `${input.video}`의 두 번째 리더가 실패함 — spool fan-out을 유지하거나, `file-store`(또는 재-읽기 가능한 경로를 주는 다른 메커니즘)로 저장 후 여러 소비자로 팬아웃하세요.

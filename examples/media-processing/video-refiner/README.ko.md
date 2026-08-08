# Video Refiner 예제

이 예제는 **file-store**, **`audio-extractor`**, **Silero VAD**, **`video-clipper`** 를 연결해 감지된 음성 구간만 포함하는 비디오를 생성합니다. 파이프라인 전체가 스트리밍 방식으로 동작합니다: VAD는 감지되는 즉시 speech segment를 방출하고, clipper는 도착한 segment에 맞춰 즉시 클립을 생성합니다.

## 개요

네 개의 job이 하나의 스트리밍 파이프라인으로 연결됩니다:

1. **`store`** — 업로드된 비디오를 로컬 `file-store`에 저장. 오디오 추출과 각 segment별 클리핑이 원본 비디오를 독립적으로 다시 읽을 수 있도록 준비. `StreamResource`는 single-use이므로 이 단계 없이는 처음 읽는 job이 원본 스트림을 다 소비해버립니다.
2. **`extract`** — 저장된 비디오에서 `audio-extractor`(ffmpeg)로 오디오 트랙을 추출. 오디오는 그대로 VAD로 흘러갑니다.
3. **`detect`** — Silero VAD를 **스트리밍 모드**(`streaming: true`)로 실행. 각 speech segment가 확정되는 즉시 `{start_time, end_time, confidence}` 형태로 방출되어, 전체 오디오 분석이 끝날 때까지 기다리지 않습니다.
4. **`refine`** — `"|"` split 연산자로 VAD segment 스트림을 `(video, span)` 쌍으로 fan-out해 `video-clipper`에 전달. 도착한 segment마다 clipper가 저장된 비디오를 다시 열어 `[start_time, end_time]`으로 seek하여 무손실 클립을 방출합니다. 클립은 완성되는 대로 하나씩 스트림으로 나옵니다.

VAD의 segment 스키마(`start_time`, `end_time`)가 clipper의 span 스키마와 1:1 매칭되므로 별도의 형변환이 필요 없습니다. segment의 추가 `confidence` 필드는 clipper가 무시합니다.

일반적인 사용 사례:
- 원본 녹화 영상의 "음성 전용" 컷을 만들어 리뷰나 캡션 작업에 활용
- 인터뷰/팟캐스트 비디오를 트랜스크립션 서비스에 업로드하기 전 정리 — 비용 절감 + 침묵 구간 hallucination 감소
- 화자가 말하는 부분만 필요한 scene classifier나 ASR 파이프라인에 연결

## 파이프라인

```
input.video ── store ─┐
                      │
                      ├──► extract ──► detect (streaming) ──┐
                      │                                     │
                      │                    "|": vad output   ← fan-out
                      │                    video: 저장된 경로
                      │                    span:  ${item}
                      │                                     │
                      └────────────────────────────────► refine ──► 클립 스트림
```

`"|"` split 연산자는(자세한 내용은 [variable-binding 레퍼런스](../../../docs/user-guide/14-variable-binding.md) 참고) VAD segment 스트림을 소스로 받아 두 개의 병렬 per-item 스트림을 만듭니다: 하나는 항상 저장된 비디오 경로로 resolve되고, 다른 하나는 현재 segment로 resolve됩니다. 각 `(video, span)` 쌍이 하나의 ffmpeg stream-copy 클립을 트리거합니다.

## 준비

### 필수 요구사항

- PATH에 등록된 model-compose
- PATH에 등록된 [ffmpeg](https://ffmpeg.org/) (`audio-extractor`와 `video-clipper` 모두 사용)
- Python 의존성은 첫 실행 시 자동 설치됩니다:
  - `silero-vad`, `torch`, `torchaudio`, `numpy` — VAD 모델

### 설정

예제 디렉터리로 이동:

```bash
cd examples/media-processing/video-refiner
```

ffmpeg 설치 확인:

```bash
ffmpeg -version
```

로컬 file-store는 기본으로 `./storage/`에 기록합니다 (`model-compose.yml`의 `storage` 컴포넌트 참고). 별도 설정 없이 첫 실행 시 디렉터리가 생성됩니다.

## 실행 방법

1. **서비스 시작:**

   ```bash
   model-compose up
   ```

   - API 엔드포인트: http://localhost:8080/api
   - 웹 UI: http://localhost:8081

2. **워크플로우 실행:**

   **웹 UI 사용:**
   - http://localhost:8081 열기
   - 비디오 파일 업로드
   - 필요시 `threshold`, `min_speech_duration`, `min_silence_duration`, `speech_padding_time` 조정
   - **Run Workflow** 클릭 후 도착하는 대로 refined 클립 다운로드

   **CLI 사용:**

   ```bash
   # 기본 파라미터
   model-compose run --input '{"video": "/path/to/recording.mp4"}'

   # 더 엄격한 VAD (경계선 음성 제거), 워드 컷 방지를 위한 패딩 추가
   model-compose run --input '{
     "video": "/path/to/recording.mp4",
     "threshold": 0.6,
     "min_speech_duration": "500ms",
     "speech_padding_time": "200ms"
   }'
   ```

   **API 사용:**

   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "video=@/path/to/recording.mp4" \
     -F 'input={"video": "@video", "threshold": 0.6}'
   ```

## 컴포넌트 상세

### `storage` — File Store

- **타입**: `file-store`
- **드라이버**: `local`
- **목적**: 업로드된 비디오를 저장해 `extract`와 `refine`이 각각 다시 읽을 수 있게 함. 이 단계가 없으면 single-use 업로드 스트림이 먼저 읽는 job에서 소비됩니다.
- **참고**:
  - `base_path: ./storage`로 모든 저장물을 예제 디렉터리 하위에 유지. 공유/클라우드 저장소가 필요하면 드라이버를 `aws-s3` / `gcp-storage` / `azure-blob`로 교체.
  - `${context.run_id}`로 run별 스토리지 키를 분리해 병렬 실행 간 충돌 방지.

### `extractor` — Audio Extractor

- **타입**: `audio-extractor`
- **드라이버**: `ffmpeg`
- **목적**: 저장된 비디오에서 오디오 트랙을 추출해 VAD에 공급. WAV로 방출.

### `vad` — Voice Activity Detection

- **타입**: `voice-activity-detection` 태스크의 모델 컴포넌트
- **드라이버**: `custom`
- **패밀리**: `silero`
- **목적**: 추출된 오디오에서 음성 구간 감지
- **참고**:
  - `streaming: true`는 확정된 각 segment를 즉시 방출 (전체 리스트를 기다리지 않음)
  - 모델이 `silero-vad` pip 패키지에 포함되어 HuggingFace 다운로드 불필요
  - 입력은 내부적으로 16kHz mono로 resample됨

### `clipper` — Video Clipper

- **타입**: `video-clipper`
- **드라이버**: `ffmpeg`
- **목적**: 도착하는 각 `(video, span)` 쌍에 대해 저장된 비디오에서 span을 `ffmpeg -c copy`(재인코딩 없음)로 잘라냄
- **참고**:
  - `merge`는 기본값 `false`로 두어 클립이 도착 즉시 스트림으로 방출됨. 하나의 파일로 이어붙이려면 `merge: true` 설정 - [커스터마이징](#커스터마이징) 참고
  - 재인코딩을 하지 않으므로 컷 지점은 컨테이너가 지원하는 가장 가까운 이전 키프레임으로 스냅. 프레임 정확도가 필요하면 clip 후 `video-encoder`로 재인코딩

## 워크플로우 상세

### "Video Refiner" 워크플로우

**설명**: Silero VAD로 음성 구간을 감지하고 refined 비디오 클립을 segment별로 스트림 방출.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `video` | video | 예 | - | 원본 비디오 파일 (MP4, MOV, MKV 등) |
| `threshold` | number | 아니오 | `0.5` | Silero 음성 확률 임계값 (0.0-1.0); 높을수록 엄격 |
| `min_speech_duration` | duration | 아니오 | `250ms` | 이보다 짧은 음성 청크는 제거 |
| `min_silence_duration` | duration | 아니오 | `500ms` | 인접 청크 분리에 필요한 침묵 길이 |
| `speech_padding_time` | duration | 아니오 | `100ms` | 감지된 청크 양쪽에 추가할 패딩 |

Duration 필드는 `"250ms"`, `"0.5s"`, 또는 초 단위 숫자를 지원합니다.

#### 출력

| 필드 | 타입 | 설명 |
|-------|------|-------------|
| `video` | video (stream) | refined 비디오 클립 스트림 - 감지된 speech segment마다 하나씩, 완성되는 대로 방출 |

## 커스터마이징

### 모든 클립을 하나의 refined 비디오로 이어붙이기

clipper 액션에 `merge: true`를 설정하고 워크플로우 출력을 스트림에서 단일 비디오로 변경:

```yaml
components:
  - id: clipper
    type: video-clipper
    action:
      video: ${input.video}
      span: ${input.span}
      merge: true
```

`merge: true`인 경우 clipper는 전체 span 스트림이 도착할 때까지 대기했다가 ffmpeg의 `concat` demuxer를 실행하므로, 파이프라인이 더 이상 chunk-by-chunk 스트리밍이 아닙니다 - 대신 바로 재생 가능한 단일 파일이 출력됩니다.

### 로컬 디스크 대신 클라우드 오브젝트 스토리지에 저장

`storage` 컴포넌트의 드라이버를 `aws-s3` / `gcp-storage` / `azure-blob`로 교체:

```yaml
components:
  - id: storage
    type: file-store
    driver: aws-s3
    bucket: ${env.S3_BUCKET}
    region: ${env.AWS_REGION | us-east-1}
    access_key_id: ${env.AWS_ACCESS_KEY_ID}
    secret_access_key: ${env.AWS_SECRET_ACCESS_KEY}
    base_path: video-refiner/
```

나머지 워크플로우는 변경할 필요가 없습니다 - `put`이 반환하는 논리 경로를 이후 job이 그대로 소비합니다.

### refined 클립을 다운스트림 ASR로 전달

각 스트림 클립을 받아 `speech-to-text` 모델 컴포넌트로 처리하는 job을 추가하세요. 클립이 스트림으로 도착하므로 전체 비디오가 끝날 때까지 기다리지 않고 도착 즉시 처리됩니다.

## 팁

- **End-to-end 스트리밍**: 파이프라인의 어떤 단계도 완결을 기다리지 않습니다. VAD는 감지되는 즉시 segment 방출, clipper는 도착 즉시 컷, 각 클립은 ffmpeg가 끝나는 대로 전달됩니다.
- **무손실 클리핑**: clipper는 `ffmpeg -c copy`를 사용하므로 클립 경계가 컨테이너가 지원하는 가장 가까운 키프레임에 맞춰집니다. lossy 코덱(h.264, hevc)의 경우 몇 ms 오차가 생길 수 있으며, 프레임 정확도가 필요하면 clip 후 `video-encoder`로 재인코딩하세요.
- **패딩의 중요성**: Silero의 frame-level 임계값 때문에 단어 시작 부분이 잘리는 것을 방지하려면 `speech_padding_time`을 100-200ms로 설정하세요.
- **스토리지 정리**: `storage` 컴포넌트는 업로드를 `./storage/uploads/` 아래에 보관합니다. 스케일링 시에는 주기적 정리 job을 추가하거나 run 단위로 스토리지를 분리하고 완료 후 삭제하세요.

## 문제 해결

### 자주 발생하는 문제

1. **클립이 생성되지 않음 / 스트림이 바로 종료**: threshold가 너무 엄격할 수 있습니다 - `threshold` 낮추기(예: `0.3`) 또는 `min_speech_duration` 축소.
2. **클립 경계에서 단어가 잘림**: `speech_padding_time` 증가(예: `200ms`).
3. **`ffmpeg` not found**: ffmpeg(및 ffprobe) 설치 후 `PATH`에 등록되어 있는지 확인.
4. **스토리지 디렉터리 권한 오류**: `./storage/`에 프로세스가 쓸 수 있는지 확인. 다른 위치가 필요하면 `model-compose.yml`의 `storage.base_path`를 변경하세요.
5. **`StreamResource` already consumed 에러**: 이 예제는 그 문제를 피하기 위해 업로드를 먼저 file-store에 저장합니다. `store` job을 생략하도록 커스터마이징하는 경우 `${input.video}`는 한 번만 소비 가능하다는 점을 기억하세요 - 디스크에 저장(`save_to`)하거나 fan-out 전에 `file-store`로 영속화해야 합니다.

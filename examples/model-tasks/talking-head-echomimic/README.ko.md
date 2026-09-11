# Talking Head Model Task 예제 (EchoMimic)

이 예제는 model-compose의 내장 talking-head 작업으로 EchoMimic(Alibaba/Ant Group의 디퓨전 기반 파이프라인)을 실행하여, 정지 이미지와 구동 오디오 클립으로부터 인물(또는 반신) talking-head 영상을 생성하는 방법을 보여줍니다.

## 개요

이 워크플로우는 다음과 같은 로컬 talking-head 생성을 제공합니다:

1. **로컬 EchoMimic 디퓨전 파이프라인**: 외부 API 없이 EchoMimic의 `Audio2VideoPipeline` (v1, 인물) 또는 `EchoMimicV2Pipeline` (v2, 반신)을 처음부터 끝까지 로컬에서 실행
2. **두 가지 프리셋**: `v1`은 오디오 기반 얼굴 마스크를 사용한 인물 전용 립싱크; `v2`는 프레임별 포즈 시퀀스(npy 파일)로 구동되는 반신 애니메이션
3. **컨텍스트 윈도우 렌더링**: `context_frames` / `context_overlap`이 시간적 윈도우 크기와 오버랩을 제어해 긴 오디오에서도 부드러운 모션 제공
4. **자동 모델 관리**: 첫 실행 시 해당 EchoMimic 체크포인트 번들을 Hugging Face에서 다운로드; upstream의 `src/` 레이아웃이 그 자리에서 리네임되어 model-compose 소스 트리와 충돌하지 않음

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- **최소 16 GB VRAM** (v2 반신은 24 GB)의 CUDA 지원 GPU 권장
- torch/torchvision 및 EchoMimic 의존성 체인 (`diffusers`, `transformers`, `librosa`, `moviepy`, `insightface`, `av`, ...)이 설치될 수 있는 Python 환경 — 첫 실행에서 샌드박스 venv에 자동 설치됨

### 로컬 talking-head를 사용하는 이유

클라우드 talking-head 서비스와 달리 EchoMimic을 로컬에서 실행하는 것은 다음을 제공합니다:

**로컬 처리의 이점:**
- **프라이버시**: 인물 사진과 음성 녹음이 기기 밖으로 나가지 않음
- **비용**: 초당·렌더당 API 요금 없음
- **오프라인**: 초기 체크포인트 다운로드 후 인터넷 연결 없이 작동
- **파이프라인 친화적**: 다른 model-compose 작업과 자연스럽게 조합되어 종단 간 아바타 파이프라인 구성 가능

**트레이드오프:**
- **하드웨어 요구사항**: v1은 ~16 GB VRAM, v2는 ~24 GB 필요; 첫 실행 시 수 GB의 체크포인트 다운로드
- **실시간 아님**: 30단계 디퓨전 루프이므로 출력 오디오 1초당 수 초의 GPU 시간
- **라이센스**: EchoMimic 가중치는 **비상업적 연구 용도 전용**으로 배포됨

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/talking-head-echomimic
   ```

2. 추가 환경 구성 불필요 — EchoMimic 체크포인트 번들 (v1은 `BadToBest/EchoMimic`, v2는 `BadToBest/EchoMimicV2`)이 Hugging Face에서 첫 실행 시 자동 다운로드 및 캐시됩니다.

3. 이 예제는 모델 워커를 전용 **virtualenv** (`.venv/echomimic`)에서 실행합니다. EchoMimic의 SD/diffusers 버전 핀이 컨트롤러의 site-packages와 충돌하지 않도록 격리하기 위해서입니다. venv는 첫 실행 시 생성되고 이후 재사용됩니다.

4. **v2 전용:** 반신 애니메이션은 프레임별 포즈 `.npy` 파일 디렉토리가 필요합니다 (EchoMimic의 `dwpose` 전처리기로 생성). `params.pose`에 해당 디렉토리를 지정하세요.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```
   > 첫 시작에서는 EchoMimic 소스를 받고, Python 의존성을 설치하고, 체크포인트 번들을 다운로드합니다. 컨트롤러가 준비 완료를 보고할 때까지 10분 이상 및 수 GB의 다운로드가 필요합니다.

2. **워크플로우 실행:**

   **API 사용 (v1 인물):**
   ```bash
   # 최소 호출 — 인물 사진을 구동 오디오 클립으로 애니메이션화
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice"}'

   # 더 높은 해상도로 렌더링
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "width": 768, "height": 768}'
   ```

   **API 사용 (v2 반신):**
   ```bash
   # v2는 프레임별 포즈 시퀀스 디렉토리가 필요
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "pose": "/path/to/pose_frames_dir"}'
   ```

   **Web UI 사용:**
   - Web UI 열기: http://localhost:8081
   - `image` (정면 인물 사진이 가장 잘 작동) 및 `audio` 클립 (WAV/MP3) 업로드
   - 선택적으로 `width` / `height`, `inference_steps`, `cfg_scale`, 컨텍스트 윈도우 조정
   - "Run Workflow" 버튼을 클릭하면 MP4를 받습니다

## 설정 참조

### 컴포넌트 필드

| 필드     | 설명                                                                                                | 기본값  |
|----------|-----------------------------------------------------------------------------------------------------|---------|
| `task`   | `talking-head`이어야 함.                                                                            | —       |
| `driver` | `custom`이어야 함.                                                                                  | —       |
| `family` | Talking-head 모델 패밀리. `echomimic`으로 설정.                                                     | —       |
| `preset` | EchoMimic 릴리스: `v1` (인물) 또는 `v2` (반신).                                                     | `v1`    |
| `model`  | 체크포인트 번들. Hugging Face repo id (예: `BadToBest/EchoMimic`) 또는 로컬 디렉토리.                | —       |

### 액션 필드

| 필드                        | 설명                                                                                                          | 기본값  |
|-----------------------------|---------------------------------------------------------------------------------------------------------------|---------|
| `image`                     | 애니메이션화할 아이덴티티를 제공하는 소스 인물 사진 (또는 사진의 리스트/스트림).                              | —       |
| `audio`                     | 입이 따라갈 구동 오디오 클립 (또는 클립 리스트).                                                              | —       |
| `params.pose`               | (v2 전용) 반신 모션을 구동하는 프레임별 `.npy` 포즈 파일 디렉토리.                                            | (없음)  |
| `params.width` / `height`   | 출력 프레임 너비/높이, 픽셀 단위.                                                                             | `512`   |
| `params.inference_steps`    | 디퓨전 추론 스텝 수.                                                                                          | `30`    |
| `params.cfg_scale`          | Classifier-free guidance 스케일.                                                                              | `2.5`   |
| `params.context_frames`     | 시간적 컨텍스트 윈도우당 처리되는 프레임 수.                                                                  | `12`    |
| `params.context_overlap`    | 연속된 시간적 윈도우 사이의 프레임 오버랩.                                                                    | `3`     |
| `params.motion_sync`        | 참조 `pose` 비디오에서 모션 신호를 추출하는 motion-sync 모드 활성화.                                          | `false` |
| `params.sample_rate`        | 모델이 기대하는 오디오 샘플 레이트; 입력이 다르면 리샘플링됨.                                                 | `16000` |
| `params.fps`                | 출력 비디오 프레임 레이트.                                                                                    | `25`    |
| `batch_size`                | 두 입력이 모두 리스트/스트림일 때 배치당 처리되는 `(image, audio)` 쌍의 수.                                   | `1`     |
| `seed`                      | 재현성을 위한 랜덤 시드. 매 호출마다 새 샘플을 원하면 미설정.                                                 | (없음)  |

## 참고사항

- **첫 실행은 느림**: 컨트롤러가 EchoMimic 소스를 받고, 의존성을 설치하고, 체크포인트 번들을 다운로드해야 합니다. 이후 실행은 캐시된 설치와 모델 파일을 재사용합니다.
- **v2 포즈 시퀀스**: v2는 `pose` 디렉토리 없이는 렌더링을 거부합니다. upstream repo는 `dwpose_util/` 아래에 참조 비디오에서 포즈를 추출하는 헬퍼 스크립트를 포함합니다.
- **컨텍스트 윈도우**: 더 큰 `context_frames`는 더 부드러운 모션을 주지만 VRAM 비용이 증가; `context_overlap`은 `context_frames`의 약 25%가 좋은 기본값.
- **프리셋 전환**: `preset`을 `v1`에서 `v2`로 바꾸면 `model` repo id도 `BadToBest/EchoMimicV2` (또는 해당 로컬 스냅샷)로 바꿔야 합니다.
- **파이프라인 조합**: 상류에 `text-to-speech`를 두어 생성된 음성을 `audio`로 전달하고, 하류에 `image-upscale`을 두면 완전한 로컬 텍스트-투-아바타 파이프라인을 구성할 수 있습니다.

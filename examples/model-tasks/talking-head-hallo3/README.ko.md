# Talking Head Model Task 예제 (Hallo3)

이 예제는 model-compose의 내장 talking-head 작업으로 Hallo3(CogVideoX-5B 기반)를 실행하여, 정지 인물 사진, 구동 오디오, 그리고 선택적 텍스트 프롬프트로부터 DiT 기반 talking-head 영상을 생성하는 방법을 보여줍니다.

## 개요

이 워크플로우는 다음과 같은 로컬 talking-head 생성을 제공합니다:

1. **로컬 Hallo3 DiT 파이프라인**: 외부 API 없이 Hallo3의 CogVideoX 기반 `SATVideoDiffusionEngine`을 처음부터 끝까지 로컬에서 실행
2. **텍스트 안내 모션**: 선택적 `prompt`가 구동 오디오와 함께 T5-xxl 텍스트 인코더에 조건화되어, 장면·스타일·모션을 조종 가능 (예: "cinematic close-up, warm lighting")
3. **슬라이딩 윈도우 롱 비디오**: Hallo3가 DiT 윈도우를 내부적으로 이어붙여, 하나의 윈도우보다 긴 오디오도 일관된 단일 출력으로 렌더링
4. **자동 모델 관리**: 첫 실행 시 Hallo3 체크포인트 번들을 Hugging Face에서 다운로드; 파이프라인이 설치된 repo 루트에서 config 상대 경로를 해석

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- **최소 24 GB VRAM**을 갖춘 CUDA 지원 GPU 강력 권장; CogVideoX-5B는 이 컬렉션에서 가장 무거운 talking-head 백본
- torch/torchvision 및 Hallo3 의존성 체인 (`diffusers`, `transformers`, `sat`, `sentencepiece`, `librosa`, `audio-separator`, `insightface`, `moviepy`, `av`, ...)이 설치될 수 있는 Python 환경 — 첫 실행에서 샌드박스 venv에 자동 설치됨

### 로컬 talking-head를 사용하는 이유

클라우드 talking-head 서비스와 달리 Hallo3를 로컬에서 실행하는 것은 다음을 제공합니다:

**로컬 처리의 이점:**
- **프라이버시**: 인물 사진과 음성 녹음이 기기 밖으로 나가지 않음
- **비용**: 초당·렌더당 API 요금 없음
- **오프라인**: 초기 체크포인트 다운로드 후 인터넷 연결 없이 작동
- **파이프라인 친화적**: 다른 model-compose 작업과 자연스럽게 조합되어 종단 간 아바타 파이프라인 구성 가능

**트레이드오프:**
- **하드웨어 요구사항**: 기본 해상도에서 ~24 GB VRAM 필요; 첫 실행 시 ~15 GB의 CogVideoX 가중치 다운로드
- **실시간 아님**: CogVideoX-5B 위 50단계 DiT 루프이므로 H100급 하드웨어에서도 매 초당 지연이 매우 큼
- **라이센스**: Hallo3 가중치는 **비상업적 연구 용도 전용**으로 배포됨

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/talking-head-hallo3
   ```

2. 추가 환경 구성 불필요 — Hallo3 체크포인트 번들 (`fudan-generative-ai/hallo3`)이 Hugging Face에서 첫 실행 시 자동 다운로드 및 캐시됩니다.

3. 이 예제는 모델 워커를 전용 **virtualenv** (`.venv/hallo3`)에서 실행합니다. Hallo3의 CogVideoX SAT 툴킷과 transformers 버전 핀이 컨트롤러의 site-packages와 충돌하지 않도록 격리하기 위해서입니다. venv는 첫 실행 시 생성되고 이후 재사용됩니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```
   > 첫 시작에서는 Hallo3 소스를 받고, Python 의존성을 설치하고, CogVideoX-5B 체크포인트 번들을 다운로드합니다. 컨트롤러가 준비 완료를 보고할 때까지 20분 이상 및 ~15 GB의 다운로드가 필요합니다.

2. **워크플로우 실행:**

   **API 사용:**
   ```bash
   # 최소 호출 — 오디오 구동만
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice"}'

   # 텍스트 프롬프트로 장면 안내
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "prompt": "cinematic close-up, warm evening lighting, subtle head movement"}'

   # 더 적은 DiT 스텝으로 빠른 프리뷰
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "inference_steps": 25}'
   ```

   **Web UI 사용:**
   - Web UI 열기: http://localhost:8081
   - `image` (정면 인물 사진이 가장 잘 작동) 및 `audio` 클립 (WAV/MP3) 업로드
   - 선택적으로 `prompt` 추가 또는 `inference_steps`, `guidance_scale`, `audio_guidance_scale`, `resolution` 조정
   - "Run Workflow" 버튼을 클릭하면 MP4를 받습니다

## 설정 참조

### 컴포넌트 필드

| 필드     | 설명                                                                                                | 기본값  |
|----------|-----------------------------------------------------------------------------------------------------|---------|
| `task`   | `talking-head`이어야 함.                                                                            | —       |
| `driver` | `custom`이어야 함.                                                                                  | —       |
| `family` | Talking-head 모델 패밀리. `hallo3`로 설정.                                                          | —       |
| `model`  | 체크포인트 번들. Hugging Face repo id (예: `fudan-generative-ai/hallo3`) 또는 로컬 디렉토리.        | —       |

### 액션 필드

| 필드                            | 설명                                                                                                          | 기본값  |
|---------------------------------|---------------------------------------------------------------------------------------------------------------|---------|
| `image`                         | 애니메이션화할 아이덴티티를 제공하는 소스 인물 사진 (또는 사진의 리스트/스트림).                              | —       |
| `audio`                         | 입이 따라갈 구동 오디오 클립 (또는 클립 리스트).                                                              | —       |
| `params.prompt`                 | T5-xxl 텍스트 인코더로 장면·스타일·모션을 안내하는 선택적 텍스트 프롬프트.                                   | (비어있음) |
| `params.negative_prompt`        | 피해야 할 내용을 기술하는 텍스트.                                                                             | (없음)  |
| `params.inference_steps`        | DiT 추론 스텝 수.                                                                                             | `50`    |
| `params.guidance_scale`         | 텍스트 조건화용 classifier-free guidance 스케일.                                                              | `6.0`   |
| `params.audio_guidance_scale`   | 오디오 조건화 분기에 적용되는 guidance 스케일.                                                                | `3.0`   |
| `params.resolution`             | 출력 프레임 해상도 (짧은 변 길이, 픽셀 단위).                                                                 | `480`   |
| `params.num_frames`             | DiT 윈도우당 생성되는 프레임 수.                                                                              | `97`    |
| `params.shift`                  | 스케줄러에 적용되는 Flow-matching timestep shift.                                                             | `5.0`   |
| `params.long_video`             | 하나의 DiT 윈도우보다 긴 오디오를 위한 long-video 모드(윈도우-앤-블렌드) 활성화.                              | `true`  |
| `params.fps`                    | 출력 비디오 프레임 레이트.                                                                                    | `25`    |
| `batch_size`                    | 두 입력이 모두 리스트/스트림일 때 배치당 처리되는 `(image, audio)` 쌍의 수.                                   | `1`     |
| `seed`                          | 재현성을 위한 랜덤 시드. 매 호출마다 새 샘플을 원하면 미설정.                                                 | (없음)  |

## 참고사항

- **첫 실행은 느림**: 컨트롤러가 Hallo3 소스를 받고, 의존성을 설치하고, CogVideoX-5B 체크포인트를 다운로드해야 합니다. 이후 실행은 캐시된 설치와 모델 파일을 재사용합니다.
- **긴 오디오**: 생성 시간은 오디오 길이에 선형으로 비례; 단일 24 GB GPU에서 대략 출력 오디오 1초당 3~5분.
- **프롬프트 튜닝**: T5-xxl 텍스트 인코더는 강력하지만 민감함 — 짧은 시네마틱 서술어 ("cinematic portrait, soft key light")로 시작해 반복 조정. 매우 긴 프롬프트 (>226 토큰)는 잘림.
- **`long_video`**: 하나의 DiT 윈도우 (기본 설정에서 ~4초)보다 긴 것은 이 옵션을 켜두세요. 끄면 오디오가 하나의 윈도우로 잘림.
- **`resolution`**: 720으로 올리면 VRAM과 지연시간이 상당히 증가; 기본 `480`이 24 GB GPU에서 프리뷰/프로덕션 균형이 좋음.
- **파이프라인 조합**: 상류에 `text-to-speech`를 두어 생성된 음성을 `audio`로 전달하고, 하류에 `image-upscale`을 두면 완전한 로컬 텍스트-투-아바타 파이프라인을 구성할 수 있습니다.

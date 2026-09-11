# Talking Head Model Task 예제 (Hallo2)

이 예제는 model-compose의 내장 talking-head 작업으로 Hallo2를 실행하여, 정지 인물 사진과 구동 오디오 클립으로부터 고해상도 장시간 talking-head 영상을 생성하는 방법을 보여줍니다.

## 개요

이 워크플로우는 다음과 같은 로컬 talking-head 생성을 제공합니다:

1. **로컬 Hallo2 디퓨전 파이프라인**: 외부 API 없이 Hallo2의 `FaceAnimatePipeline` (reference UNet + denoising UNet + face locator + motion module)을 처음부터 끝까지 로컬에서 실행
2. **긴 오디오 지원**: Hallo2는 긴 오디오를 60초 세그먼트로 청킹해 각각 애니메이션화한 뒤 내장 `merge_videos` 단계로 하나의 출력으로 이어붙임 — 수 분 길이 클립에 사용 가능
3. **모션 가중치 조건화**: 별도의 `pose_weight` / `face_weight` / `lip_weight` 스케일로 구동 오디오가 암시하는 모션이 소스 인물의 정적 포즈를 얼마나 강하게 오버라이드할지 조정
4. **자동 모델 관리**: 첫 실행 시 Hallo2 체크포인트 번들을 Hugging Face에서 다운로드; Hallo2는 이미 깔끔한 `hallo/` 패키지 레이아웃을 제공하므로 SadTalker 스타일의 재작성은 불필요

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- CUDA 지원 GPU 강력 권장; 40단계 디퓨전 루프는 CPU에서 비현실적으로 느림
- torch/torchvision 및 Hallo2 의존성 체인 (`diffusers`, `transformers`, `librosa`, `audio-separator`, `insightface`, `moviepy`, `av`, ...)이 설치될 수 있는 Python 환경 — 첫 실행에서 샌드박스 venv에 자동 설치됨

### 로컬 talking-head를 사용하는 이유

클라우드 talking-head 서비스와 달리 Hallo2를 로컬에서 실행하는 것은 다음을 제공합니다:

**로컬 처리의 이점:**
- **프라이버시**: 인물 사진과 음성 녹음이 기기 밖으로 나가지 않음
- **비용**: 초당·렌더당 API 요금 없음; 동일한 사진을 저렴하게 재구동 가능
- **오프라인**: 초기 체크포인트 다운로드 후 인터넷 연결 없이 작동
- **파이프라인 친화적**: 다른 model-compose 작업(상류의 text-to-speech, 하류의 image-upscale 등)과 자연스럽게 조합되어 종단 간 아바타 파이프라인 구성 가능

**트레이드오프:**
- **하드웨어 요구사항**: 기본 해상도에서 ~12 GB VRAM 필요; 첫 실행 시 수 GB의 체크포인트 다운로드도 발생
- **실시간 아님**: 디퓨전 루프에 세그먼트 스티칭까지 더해져 출력 오디오 1초당 수 초의 지연 발생, 고성능 GPU에서도 마찬가지
- **라이센스**: Hallo2 가중치는 **비상업적 연구 용도 전용**으로 배포됨

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/talking-head-hallo2
   ```

2. 추가 환경 구성 불필요 — Hallo2 체크포인트 번들 (`fudan-generative-ai/hallo2`)이 Hugging Face에서 첫 실행 시 자동 다운로드 및 캐시됩니다.

3. 이 예제는 모델 워커를 전용 **virtualenv** (`.venv/hallo2`)에서 실행합니다. Hallo2의 diffusers/transformers 버전 핀이 컨트롤러의 site-packages와 충돌하지 않도록 격리하기 위해서입니다. venv는 첫 실행 시 생성되고 이후 재사용됩니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```
   > 첫 시작에서는 Hallo2 소스를 받고, Python 의존성을 설치하고, 체크포인트 번들을 다운로드합니다. 컨트롤러가 준비 완료를 보고할 때까지 10분 이상 및 수 GB의 다운로드가 필요합니다.

2. **워크플로우 실행:**

   **API 사용:**
   ```bash
   # 최소 호출 — 인물 사진을 구동 오디오 클립으로 애니메이션화
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice"}'

   # 립/얼굴 가중치를 올려 오디오 구동 모션을 더 강하게 밀어붙이기
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "lip_weight": 1.4, "face_weight": 1.3}'

   # 더 적은 디퓨전 스텝으로 빠른 프리뷰
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "inference_steps": 20}'
   ```

   **Web UI 사용:**
   - Web UI 열기: http://localhost:8081
   - `image` (정면 인물 사진이 가장 잘 작동) 및 `audio` 클립 (WAV/MP3) 업로드
   - 선택적으로 모션 가중치, `face_expand_ratio`, `inference_steps`, `cfg_scale` 조정
   - "Run Workflow" 버튼을 클릭하면 MP4를 받습니다

## 설정 참조

### 컴포넌트 필드

| 필드     | 설명                                                                                                | 기본값  |
|----------|-----------------------------------------------------------------------------------------------------|---------|
| `task`   | `talking-head`이어야 함.                                                                            | —       |
| `driver` | `custom`이어야 함.                                                                                  | —       |
| `family` | Talking-head 모델 패밀리. `hallo2`로 설정.                                                          | —       |
| `model`  | 체크포인트 번들. Hugging Face repo id (예: `fudan-generative-ai/hallo2`) 또는 로컬 디렉토리.        | —       |

### 액션 필드

| 필드                          | 설명                                                                                                          | 기본값  |
|-------------------------------|---------------------------------------------------------------------------------------------------------------|---------|
| `image`                       | 애니메이션화할 아이덴티티를 제공하는 소스 인물 사진 (또는 사진의 리스트/스트림).                              | —       |
| `audio`                       | 입이 따라갈 구동 오디오 클립 (또는 클립 리스트).                                                              | —       |
| `params.pose_weight`          | Motion module 조건화 시 구동 포즈 신호에 적용되는 가중치.                                                     | `1.1`   |
| `params.face_weight`          | Motion module 조건화 시 구동 얼굴 신호에 적용되는 가중치.                                                     | `1.1`   |
| `params.lip_weight`           | Motion module 조건화 시 구동 입술 신호에 적용되는 가중치.                                                     | `1.1`   |
| `params.face_expand_ratio`    | 감지된 얼굴 박스 주위의 얼굴 크롭 확장 비율.                                                                  | `1.2`   |
| `params.inference_steps`      | 디노이징 루프당 디퓨전 추론 스텝 수.                                                                          | `40`    |
| `params.cfg_scale`            | Classifier-free guidance 스케일.                                                                              | `3.5`   |
| `params.motion_module_frames` | Motion module 윈도우당 처리되는 프레임 수.                                                                    | `16`    |
| `params.long_video`           | 하나의 윈도우보다 긴 오디오를 위한 Hallo2의 long-video 모드(청크-앤-블렌드) 활성화.                          | `true`  |
| `params.high_resolution`      | 더 높은 해상도 출력을 위한 내장 초해상도 패스 실행.                                                           | `false` |
| `params.fps`                  | 출력 비디오 프레임 레이트.                                                                                    | `25`    |
| `batch_size`                  | 두 입력이 모두 리스트/스트림일 때 배치당 처리되는 `(image, audio)` 쌍의 수.                                   | `1`     |
| `seed`                        | 재현성을 위한 랜덤 시드. 매 호출마다 새 샘플을 원하면 미설정.                                                 | (없음)  |

## 참고사항

- **첫 실행은 느림**: 컨트롤러가 Hallo2 소스를 받고, 의존성을 설치하고, 체크포인트 번들을 다운로드해야 합니다. 이후 실행은 캐시된 설치와 모델 파일을 재사용합니다.
- **긴 오디오**: 생성 시간은 오디오 길이에 선형으로 비례합니다. 수 분 길이 입력이 기본으로 지원되며, 런타임도 비례해 늘어납니다.
- **모션 가중치**: `lip_weight`와 `face_weight`를 1.0 이상으로 올리면 발화 기반 모션이 더 두드러지지만 아이덴티티 충실도는 떨어질 수 있습니다. `pose_weight`는 모델이 얼마나 많은 헤드 모션을 도입할지 조절합니다.
- **`long_video`**: 기본 모션 윈도우보다 긴 것은 이 옵션을 켜두세요 — Hallo2의 세그먼트/스티치 파이프라인이 수 분 길이 출력을 가능하게 합니다.
- **`high_resolution`**: 업샘플러는 별도의 디퓨전 패스입니다; 활성화 시 대략 지연시간과 VRAM이 두 배로 증가합니다.
- **파이프라인 조합**: 상류에 `text-to-speech`를 두어 생성된 음성을 `audio`로 전달하고, 하류에 `image-upscale`을 두면 완전한 로컬 텍스트-투-아바타 파이프라인을 구성할 수 있습니다.

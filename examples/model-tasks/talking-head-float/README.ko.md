# Talking Head Model Task 예제 (Float)

이 예제는 model-compose의 내장 talking-head 작업으로 Float(DeepBrain AI, 명시적 감정 레이블을 지원하는 flow-matching 파이프라인)를 실행하여, 정지 인물 사진과 구동 오디오 클립으로부터 감정 조건화된 talking-head 영상을 생성하는 방법을 보여줍니다.

## 개요

이 워크플로우는 다음과 같은 로컬 talking-head 생성을 제공합니다:

1. **로컬 Float flow-matching 파이프라인**: 외부 API 없이 Float의 `InferenceAgent.run_inference()`를 처음부터 끝까지 로컬에서 실행 — 인물 + 오디오 latent에 대한 flow-matching과 wav2vec2 오디오 인코더 사용
2. **명시적 감정 레이블**: `happy`, `sad`, `angry`, `fear`, `disgust`, `surprise`, `neutral` 중 선택하거나, `S2E` 센티넬을 유지해 Float가 오디오에서 직접 감정을 유도하도록 위임
3. **빠른 추론**: 기본 10 flow-matching NFE; 이 컬렉션에서 가장 빠른 talking-head 백본 중 하나
4. **자동 모델 관리**: 첫 실행 시 Float 체크포인트 번들(Float 가중치 + wav2vec2-base-960h + 감정 인식 헤드)을 Hugging Face에서 다운로드; upstream의 평탄한 repo 레이아웃이 하나의 `float_talker/` 패키지로 감싸져 `models/`, `options/` 같은 최상위 이름이 site-packages의 다른 항목과 충돌하지 않음

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- CUDA 지원 GPU 강력 권장; CPU 추론은 훨씬 느림
- torch/torchvision 및 Float 의존성 체인 (`diffusers`, `transformers`, `librosa`, `face-alignment`, `torchdiffeq`, `moviepy`, ...)이 설치될 수 있는 Python 환경 — 첫 실행에서 샌드박스 venv에 자동 설치됨

### 로컬 talking-head를 사용하는 이유

클라우드 talking-head 서비스와 달리 Float을 로컬에서 실행하는 것은 다음을 제공합니다:

**로컬 처리의 이점:**
- **프라이버시**: 인물 사진과 음성 녹음이 기기 밖으로 나가지 않음
- **비용**: 초당·렌더당 API 요금 없음
- **오프라인**: 초기 체크포인트 다운로드 후 인터넷 연결 없이 작동
- **파이프라인 친화적**: 다른 model-compose 작업과 자연스럽게 조합되어 종단 간 아바타 파이프라인 구성 가능

**트레이드오프:**
- **하드웨어 요구사항**: 상대적으로 가벼움 (~8 GB VRAM), 하지만 고성능 카드에서 더 빠름
- **영어 중심 감정 헤드**: 번들된 감정 인식기는 영어 음성으로 학습됨; 비영어 오디오에서는 명시적 `emotion` 레이블이 안전한 폴백
- **라이센스**: Float 가중치는 **비상업적 연구 용도 전용**으로 배포됨

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/talking-head-float
   ```

2. 추가 환경 구성 불필요 — Float 체크포인트 번들 (`yuvraj108c/float`)이 Hugging Face에서 첫 실행 시 자동 다운로드 및 캐시됩니다.

3. 이 예제는 모델 워커를 전용 **virtualenv** (`.venv/float`)에서 실행합니다. 설치 시 `float_talker.models` / `float_talker.options`로 리네임된 Float의 `models/`, `options/` 패키지가 컨트롤러의 site-packages와 충돌하지 않도록 격리하기 위해서입니다. venv는 첫 실행 시 생성되고 이후 재사용됩니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```
   > 첫 시작에서는 Float 소스를 받고, Python 의존성을 설치하고, 체크포인트 번들을 다운로드합니다. 컨트롤러가 준비 완료를 보고할 때까지 수 분 및 수 GB의 다운로드가 필요합니다.

2. **워크플로우 실행:**

   **API 사용:**
   ```bash
   # 최소 호출 — 감정 자동 감지
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice"}'

   # 명시적 감정 레이블 지정
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "emotion": "happy"}'

   # 얼굴 크롭 생략, 전체 프레임 렌더링 (인물이 이미 상류에서 타이트하게 크롭된 경우 유용)
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "crop": false}'
   ```

   **Web UI 사용:**
   - Web UI 열기: http://localhost:8081
   - `image` (정면 인물 사진이 가장 잘 작동) 및 `audio` 클립 (WAV/MP3) 업로드
   - 선택적으로 `emotion` 선택 또는 `inference_steps`, `cfg_scale`, `a_cfg_scale`, `e_cfg_scale` 조정
   - "Run Workflow" 버튼을 클릭하면 MP4를 받습니다

## 설정 참조

### 컴포넌트 필드

| 필드     | 설명                                                                                                | 기본값  |
|----------|-----------------------------------------------------------------------------------------------------|---------|
| `task`   | `talking-head`이어야 함.                                                                            | —       |
| `driver` | `custom`이어야 함.                                                                                  | —       |
| `family` | Talking-head 모델 패밀리. `float`로 설정.                                                           | —       |
| `model`  | 체크포인트 번들. Hugging Face repo id (예: `yuvraj108c/float`) 또는 로컬 디렉토리.                  | —       |

### 액션 필드

| 필드                        | 설명                                                                                                          | 기본값  |
|-----------------------------|---------------------------------------------------------------------------------------------------------------|---------|
| `image`                     | 애니메이션화할 아이덴티티를 제공하는 소스 인물 사진 (또는 사진의 리스트/스트림).                              | —       |
| `audio`                     | 입이 따라갈 구동 오디오 클립 (또는 클립 리스트).                                                              | —       |
| `params.emotion`            | 감정 레이블: `happy`, `sad`, `angry`, `fear`, `disgust`, `surprise`, `neutral`, 또는 자동 감지를 위한 `S2E`. | `S2E`   |
| `params.emotion_scale`      | 감정 조건화 강도에 적용되는 배수.                                                                             | `1.0`   |
| `params.inference_steps`    | Flow-matching 추론 스텝 수 (NFE).                                                                             | `10`    |
| `params.cfg_scale`          | 참조 분기에 적용되는 classifier-free guidance 스케일.                                                         | `2.0`   |
| `params.a_cfg_scale`        | 오디오 조건화 분기에 적용되는 guidance 스케일.                                                                | `2.0`   |
| `params.e_cfg_scale`        | 감정 조건화 분기에 적용되는 guidance 스케일.                                                                  | `1.0`   |
| `params.crop`               | 렌더링 전에 소스 인물 사진을 감지된 얼굴로 크롭; 비활성화 시 전체 프레임 렌더링.                              | `true`  |
| `params.fps`                | 출력 비디오 프레임 레이트.                                                                                    | `25`    |
| `batch_size`                | 두 입력이 모두 리스트/스트림일 때 배치당 처리되는 `(image, audio)` 쌍의 수.                                   | `1`     |
| `seed`                      | 재현성을 위한 랜덤 시드. 매 호출마다 Float 기본값(25)을 재사용하려면 미설정.                                  | `25`    |

## 참고사항

- **첫 실행은 느림**: 컨트롤러가 Float 소스를 받고, 의존성을 설치하고, 체크포인트 번들을 다운로드해야 합니다. 이후 실행은 캐시된 설치와 모델 파일을 재사용합니다.
- **`S2E` vs 명시적 감정**: 영어 음성에서는 `S2E`가 자연스러운 결과를 제공; 다른 언어에서는 명시적 레이블 (`happy`, `sad`, ...)이 영어 중심 감정 헤드의 오예측을 방지.
- **`e_cfg_scale`**: 이 값을 올리면 감정 조건화가 더 직접적으로 반영됨; 강하게 스타일화된 출력을 위해 명시적 `emotion` 레이블과 조합.
- **`crop: false`**: 입력 인물 사진이 이미 타이트하게 크롭된 경우 (예: 상류의 `image-upscale` 컴포넌트에서), Float의 얼굴 크롭 단계를 생략해 더 깔끔한 프레이밍 획득.
- **얼굴 감지 실패**: 소스 이미지에서 얼굴이 감지되지 않으면 Float의 내장 전처리기가 정렬 오류를 발생시킵니다. 더 선명하고 크며 정면을 향한 인물 사진을 사용하세요.
- **파이프라인 조합**: 상류에 `text-to-speech`를 두어 생성된 음성을 `audio`로 전달하고, 하류에 `image-upscale`을 두면 완전한 로컬 텍스트-투-아바타 파이프라인을 구성할 수 있습니다.

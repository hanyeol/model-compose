# Talking Head Model Task 예제 (Sonic)

이 예제는 model-compose의 내장 talking-head 작업으로 Sonic(Tencent)을 실행하여, 정지 이미지와 구동 오디오 클립으로부터 인물 talking-head 영상을 생성하는 방법을 보여줍니다.

## 개요

이 워크플로우는 다음과 같은 로컬 talking-head 생성을 제공합니다:

1. **로컬 Sonic SVD 파이프라인**: 외부 API 없이 Sonic의 `Sonic.process()`를 처음부터 끝까지 로컬에서 실행 — SVD-XT 백본, whisper-tiny 오디오 인코더, audio2token / audio2bucket 모션 예측기, RIFE 프레임 보간
2. **글로벌 오디오 인식**: Sonic은 전체 오디오 클립을 앞에서 조건화하여, 윈도우 전용 베이스라인보다 부드러운 수초 단위 모션 제공
3. **빠른 추론**: 기본 25 디퓨전 스텝; 유사한 아이덴티티 충실도에서 무거운 DiT 기반 베이스라인보다 대략 2~3배 빠르게 렌더링
4. **자동 모델 관리**: 첫 실행 시 Sonic 체크포인트 번들(Sonic + SVD-XT + whisper-tiny + RIFE + yoloface)을 Hugging Face에서 다운로드; upstream의 `src/` 레이아웃이 그 자리에서 리네임되어 model-compose 소스 트리와 충돌하지 않음

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- **최소 16 GB VRAM**의 CUDA 지원 GPU 권장 (SVD-XT가 메모리 하한)
- torch/torchvision 및 Sonic 의존성 체인 (`diffusers`, `transformers`, `librosa`, `moviepy`, `insightface`, `av`, ...)이 설치될 수 있는 Python 환경 — 첫 실행에서 샌드박스 venv에 자동 설치됨

### 로컬 talking-head를 사용하는 이유

클라우드 talking-head 서비스와 달리 Sonic을 로컬에서 실행하는 것은 다음을 제공합니다:

**로컬 처리의 이점:**
- **프라이버시**: 인물 사진과 음성 녹음이 기기 밖으로 나가지 않음
- **비용**: 초당·렌더당 API 요금 없음
- **오프라인**: 초기 체크포인트 다운로드 후 인터넷 연결 없이 작동
- **파이프라인 친화적**: 다른 model-compose 작업과 자연스럽게 조합되어 종단 간 아바타 파이프라인 구성 가능

**트레이드오프:**
- **하드웨어 요구사항**: ~16 GB VRAM 필요; 첫 실행 시 수 GB의 체크포인트 다운로드
- **실시간 아님**: 대부분의 경쟁 모델보다 빠르지만, 여전히 출력 오디오 1초당 ~0.5~1초의 GPU 시간
- **라이센스**: Sonic 가중치는 **비상업적 연구 용도 전용**으로 배포됨

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/talking-head-sonic
   ```

2. 추가 환경 구성 불필요 — Sonic 체크포인트 번들 (`LeonJoe13/Sonic`)이 Hugging Face에서 첫 실행 시 자동 다운로드 및 캐시됩니다.

3. 이 예제는 모델 워커를 전용 **virtualenv** (`.venv/sonic`)에서 실행합니다. Sonic의 SVD/diffusers 버전 핀이 컨트롤러의 site-packages와 충돌하지 않도록 격리하기 위해서입니다. venv는 첫 실행 시 생성되고 이후 재사용됩니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```
   > 첫 시작에서는 Sonic 소스를 받고, Python 의존성을 설치하고, 체크포인트 번들을 다운로드합니다. 컨트롤러가 준비 완료를 보고할 때까지 10분 이상 및 수 GB의 다운로드가 필요합니다.

2. **워크플로우 실행:**

   **API 사용:**
   ```bash
   # 최소 호출 — 인물 사진을 구동 오디오 클립으로 애니메이션화
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice"}'

   # dynamic scale 배수로 더 표정이 풍부한 모션
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "dynamic_scale": 1.5}'

   # 입력의 원본 해상도 유지 (512 최소 리사이즈 생략)
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "keep_resolution": true}'
   ```

   **Web UI 사용:**
   - Web UI 열기: http://localhost:8081
   - `image` (정면 인물 사진이 가장 잘 작동) 및 `audio` 클립 (WAV/MP3) 업로드
   - 선택적으로 `dynamic_scale`, `inference_steps`, `min_resolution` 조정 또는 `keep_resolution` 토글
   - "Run Workflow" 버튼을 클릭하면 MP4를 받습니다

## 설정 참조

### 컴포넌트 필드

| 필드     | 설명                                                                                                | 기본값  |
|----------|-----------------------------------------------------------------------------------------------------|---------|
| `task`   | `talking-head`이어야 함.                                                                            | —       |
| `driver` | `custom`이어야 함.                                                                                  | —       |
| `family` | Talking-head 모델 패밀리. `sonic`으로 설정.                                                         | —       |
| `model`  | 체크포인트 번들. Hugging Face repo id (예: `LeonJoe13/Sonic`) 또는 로컬 디렉토리.                   | —       |

### 액션 필드

| 필드                        | 설명                                                                                                          | 기본값  |
|-----------------------------|---------------------------------------------------------------------------------------------------------------|---------|
| `image`                     | 애니메이션화할 아이덴티티를 제공하는 소스 인물 사진 (또는 사진의 리스트/스트림).                              | —       |
| `audio`                     | 입이 따라갈 구동 오디오 클립 (또는 클립 리스트).                                                              | —       |
| `params.dynamic_scale`      | 모션 다이나믹 스케일; 큰 값일수록 더 표정이 풍부한 헤드 및 얼굴 모션 생성.                                    | `1.0`   |
| `params.inference_steps`    | 디퓨전 추론 스텝 수.                                                                                          | `25`    |
| `params.min_resolution`     | 렌더링 전에 얼굴 크롭이 리사이즈되는 최소 짧은 변 해상도.                                                     | `512`   |
| `params.keep_resolution`    | `min_resolution`으로 리사이즈하지 않고 입력 인물 사진의 원본 해상도 유지.                                    | `false` |
| `params.fps`                | 출력 비디오 프레임 레이트.                                                                                    | `25`    |
| `batch_size`                | 두 입력이 모두 리스트/스트림일 때 배치당 처리되는 `(image, audio)` 쌍의 수.                                   | `1`     |
| `seed`                      | 재현성을 위한 랜덤 시드. 매 호출마다 새 샘플을 원하면 미설정.                                                 | (없음)  |

## 참고사항

- **첫 실행은 느림**: 컨트롤러가 Sonic 소스를 받고, 의존성을 설치하고, 체크포인트 번들을 다운로드해야 합니다. 이후 실행은 캐시된 설치와 모델 파일을 재사용합니다.
- **긴 오디오**: Sonic의 글로벌 오디오 인식은 1분 이상 클립도 잘 스케일 함; 출력 오디오 1초당 대략 0.5~1초의 GPU 시간.
- **`dynamic_scale`**: 1.0 이상으로 올리면 헤드/얼굴 모션이 더 극적으로 보임; 지나친 값(>1.7)은 부자연스러울 수 있음.
- **`keep_resolution`**: 소스 해상도 유지는 고품질 인물 사진에서 충실도를 개선할 수 있으나 추가 지연시간과 VRAM 비용 발생.
- **얼굴 감지 실패**: 소스 이미지에서 얼굴이 감지되지 않으면 워크플로우가 "Sonic failed to render the talking-head video"를 발생시킵니다. 더 선명하고 크며 정면을 향한 인물 사진을 사용하세요.
- **파이프라인 조합**: 상류에 `text-to-speech`를 두어 생성된 음성을 `audio`로 전달하고, 하류에 `image-upscale`을 두면 완전한 로컬 텍스트-투-아바타 파이프라인을 구성할 수 있습니다.

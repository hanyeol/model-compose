# Talking Head Model Task 예제 (SadTalker)

이 예제는 model-compose의 내장 talking-head 작업으로 SadTalker를 실행하여, 정지 인물 사진이 구동 오디오 클립과 립싱크(그리고 부드러운 헤드 모션)를 하도록 애니메이션화하는 방법을 보여줍니다.

## 개요

이 워크플로우는 다음과 같은 로컬 talking-head 생성을 제공합니다:

1. **로컬 SadTalker 파이프라인**: 외부 API 없이 SadTalker의 Audio2Coeff + 얼굴 렌더러를 처음부터 끝까지 로컬에서 실행
2. **오디오 기반 립싱크**: 구동 오디오에서 헤드 포즈와 표정 계수를 직접 예측한 뒤, 인물 사진의 입과 얼굴이 발화를 따라가는 영상을 렌더링
3. **자동 얼굴 감지 및 크롭**: 소스 인물 사진에서 얼굴을 감지·정렬; 전체 프레임 배경 유지 또는 얼굴만 타이트하게 크롭하는 모드 지원
4. **선택적 얼굴 향상**: GFPGAN(또는 RestoreFormer)을 프레임별 얼굴 인핸서로 실행해 더 선명한 얼굴 제공
5. **자동 모델 관리**: 첫 실행 시 SadTalker 체크포인트 번들을 Hugging Face에서 다운로드; 파이프라인 코드가 그 자리에서 리네임되고 import가 재작성되어 upstream의 `src/` 레이아웃이 model-compose의 소스 트리와 충돌하지 않음

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- CUDA 지원 GPU 강력 권장; CPU 전용 실행은 실사용 길이의 오디오에서는 비현실적으로 느림
- torch/torchvision 및 SadTalker의 의존성 체인 (`librosa`, `numba`, `face-alignment`, `gfpgan`, `basicsr`, `facexlib`, `av`, ...)이 설치될 수 있는 Python 환경 — 첫 실행에서 자동 설치됨

### 로컬 talking-head를 사용하는 이유

클라우드 talking-head 서비스와 달리 SadTalker를 로컬에서 실행하는 것은 다음을 제공합니다:

**로컬 처리의 이점:**
- **프라이버시**: 인물 사진과 음성 녹음이 기기 밖으로 나가지 않음
- **비용**: 초당·렌더당 API 요금 없음; 동일한 사진을 저렴하게 재구동 가능
- **오프라인**: 초기 체크포인트 다운로드 후 인터넷 연결 없이 작동
- **파이프라인 친화적**: 다른 model-compose 작업(상류의 text-to-speech, 하류의 image-upscale 등)과 자연스럽게 조합되어 종단 간 아바타 파이프라인 구성 가능

**트레이드오프:**
- **하드웨어 요구사항**: 256 프리셋은 ~6 GB VRAM, 512 프리셋은 ~12 GB VRAM 필요. 첫 실행 시 수 GB의 체크포인트 다운로드도 발생
- **실시간 아님**: SadTalker는 일관된 헤드 포즈/표정 시퀀스를 풀기 위해 오디오 전체를 소비 — 스트리밍 입력을 지원하지 않음
- **라이센스**: SadTalker 가중치는 **비상업적 연구 용도 전용**으로 배포됨

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/talking-head-sadtalker
   ```

2. 추가 환경 구성 불필요 — SadTalker 체크포인트 번들 (`vinthony/SadTalker`)이 Hugging Face에서 첫 실행 시 자동 다운로드 및 캐시됩니다.

3. 이 예제는 모델 워커를 전용 **virtualenv** (`.venv/sadtalker`)에서 실행합니다. SadTalker의 오래된 numpy/numba/librosa 버전 핀이 컨트롤러의 site-packages와 충돌하지 않도록 격리하기 위해서입니다. venv는 첫 실행 시 생성되고 이후 재사용됩니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```
   > 첫 시작에서는 SadTalker 소스를 받고, Python 의존성을 설치하고, 체크포인트 번들을 다운로드합니다. 컨트롤러가 준비 완료를 보고할 때까지 수 분 및 수 GB의 다운로드가 필요합니다.

2. **워크플로우 실행:**

   **API 사용:**
   ```bash
   # 최소 호출 — 인물 사진을 구동 오디오 클립으로 애니메이션화
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice"}'

   # 전체 프레임을 유지하고 입만 움직이는 렌더링 (몸/배경이 있는 사진에 권장)
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "preprocess": "full", "still": true}'

   # 더 표정이 풍부한 얼굴 모션, GFPGAN 인핸서 없이
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "expression_scale": 1.4, "enhancer": null}'
   ```

   **Web UI 사용:**
   - Web UI 열기: http://localhost:8081
   - `image` (정면 인물 사진이 가장 잘 작동) 및 `audio` 클립 (WAV/MP3) 업로드
   - 선택적으로 `preprocess` 조정, `still` 토글, `enhancer` 선택, `expression_scale` / `pose_style` 다이얼링
   - "Run Workflow" 버튼을 클릭하면 MP4를 받습니다

## 설정 참조

### 컴포넌트 필드

| 필드     | 설명                                                                                                | 기본값         |
|----------|-----------------------------------------------------------------------------------------------------|----------------|
| `task`   | `talking-head`이어야 함.                                                                            | —              |
| `driver` | `custom`이어야 함.                                                                                  | —              |
| `family` | Talking-head 모델 패밀리. 현재는 `sadtalker`만 지원.                                                | —              |
| `preset` | SadTalker 체크포인트 변형: `v0.0.2-256` (256×256, 가벼움) 또는 `v0.0.2-512` (512×512, 더 선명).      | `v0.0.2-256`   |
| `model`  | 체크포인트 번들. Hugging Face repo id (예: `vinthony/SadTalker`) 또는 로컬 디렉토리 경로.           | —              |

### 액션 필드

| 필드                   | 설명                                                                                                          | 기본값        |
|------------------------|---------------------------------------------------------------------------------------------------------------|---------------|
| `image`                | 애니메이션화할 아이덴티티를 제공하는 소스 인물 사진 (또는 사진의 리스트/스트림).                              | —             |
| `audio`                | 입이 따라갈 구동 오디오 클립 (또는 클립 리스트).                                                              | —             |
| `params.preprocess`    | 얼굴 전처리 모드: `crop`, `extcrop`, `resize`, `full`, `extfull`. 사진 전체를 유지하려면 `full` 사용.         | `crop`        |
| `params.still`         | 헤드를 정지 상태로 유지 (입만 움직임). `preprocess`가 `full`일 때 권장.                                        | `false`       |
| `params.enhancer`      | 프레임별 얼굴 인핸서: `gfpgan` 또는 `RestoreFormer`. 미설정 시 인핸서 패스 생략.                              | (없음)        |
| `params.background_enhancer` | 배경 초해상 인핸서: `realesrgan`. 미설정 시 생략.                                                       | (없음)        |
| `params.expression_scale`    | 예측된 얼굴 표정 강도에 적용되는 배수. 큰 값일수록 더 극적으로 보임.                                    | `1.0`         |
| `params.pose_style`    | `[0, 46]` 범위의 헤드 포즈 스타일 인덱스. 같은 오디오에서 다른 값은 다른 포즈 패턴을 샘플링.                  | `0`           |
| `params.ref_eyeblink`  | 눈 깜빡임 모션을 출력에 전이할 선택적 참조 비디오.                                                            | (없음)        |
| `params.ref_pose`      | 헤드 포즈 모션을 출력에 전이할 선택적 참조 비디오.                                                            | (없음)        |
| `params.input_yaw` / `input_pitch` / `input_roll` | 도 단위의 수동 헤드 회전 키프레임 (int 리스트). 예측된 회전을 오버라이드.               | (없음)        |
| `params.face3dvis`     | 출력과 함께 3D 얼굴 디버그 비디오도 추가로 렌더링.                                                            | `false`       |
| `params.size`          | 얼굴 렌더러 해상도. 로드된 프리셋과 일치해야 함 (`v0.0.2-256`은 `256`, `v0.0.2-512`는 `512`).                | `256`         |
| `params.facerender_batch_size` | 얼굴 렌더러 추론 루프에서 사용하는 배치 크기.                                                          | `2`           |
| `params.fps`           | 출력 비디오 프레임 레이트. SadTalker 렌더러는 내부적으로 25 fps를 목표로 함.                                  | `25`          |
| `batch_size`           | 두 입력이 모두 리스트/스트림일 때 배치당 처리되는 `(image, audio)` 쌍의 수.                                   | `1`           |
| `seed`                 | 재현성을 위한 랜덤 시드. 매 호출마다 새 샘플을 원하면 미설정.                                                 | (없음)        |

## 참고사항

- **첫 실행은 느림**: 컨트롤러가 SadTalker 소스를 받고, 의존성을 설치하고, 체크포인트 번들을 다운로드해야 합니다. 이후 실행은 캐시된 설치와 모델 파일을 재사용합니다.
- **긴 오디오**: 생성 시간은 오디오 길이에 선형으로 비례합니다. 긴 클립은 단락 단위로 분할해 처리하고 하류에서 이어붙이는 것을 고려하세요.
- **얼굴 감지 실패**: 소스 이미지에서 얼굴이 감지되지 않으면 워크플로우가 "SadTalker failed to detect a face in the input image"를 발생시킵니다. 더 선명하고 크며 정면을 향한 인물 사진을 사용하세요.
- **전체 프레임 사진**: 인물이 프레임의 일부만 차지하는 사진의 경우 `preprocess: full`과 `still: true`를 함께 사용하면 배경은 정적으로 유지되면서 입만 자연스럽게 애니메이션됩니다.
- **인핸서는 시간 비용이 큼**: GFPGAN은 의미 있는 프레임당 지연시간을 추가합니다. 프리뷰에서는 끄고 최종 렌더링에서만 활성화하세요.
- **파이프라인 조합**: 상류에 `text-to-speech`를 두어 생성된 음성을 `audio`로 전달하고, 하류에 `image-upscale`을 두면 완전한 로컬 텍스트-투-아바타 파이프라인을 구성할 수 있습니다.

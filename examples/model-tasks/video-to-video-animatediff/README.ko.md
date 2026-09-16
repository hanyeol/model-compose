# Video-to-Video 모델 태스크 예제

이 예제는 Stable Diffusion 1.5 체크포인트 위에 AnimateDiff를 올려 기존 영상의 모션을 유지한 채 텍스트 프롬프트로 스타일을 다시 입히는 방법을 보여줍니다. model-compose의 내장 video-to-video 태스크로 노출됩니다.

## 개요

이 워크플로우는 모션을 보존하면서 영상을 로컬에서 리스타일하는 기능을 제공합니다:

1. **로컬 AnimateDiff 파이프라인**: HuggingFace diffusers를 통해 Stable Diffusion 1.5와 AnimateDiff 모션 어댑터를 엔드투엔드로 실행 — 외부 API 없음.
2. **소스 모션 보존**: 입력 영상이 구도와 시간적 모션을 모두 공급하고, 프롬프트는 외형과 스타일만 조정합니다.
3. **프레임별 스타일 조절**: `denoise_strength` 하나로 "프롬프트를 더 강하게 반영" 대 "원본 영상에 가깝게 유지" 간의 균형을 조절합니다.
4. **선택적 레퍼런스 이미지**: IP-Adapter를 통해 `reference_image`를 제공하면 그 이미지의 외형(색감·질감·피사체)이 리스타일된 영상에 반영됩니다.
5. **자동 모델 관리**: 베이스 체크포인트, 모션 어댑터, IP-Adapter 가중치는 첫 실행 시 HuggingFace Hub에서 다운로드되어 로컬에 캐시됩니다.

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- 16프레임 512×512 `float16` 기준 **최소 8 GB VRAM**을 갖춘 CUDA GPU. Apple Silicon(MPS)은 테스트되지 않았고 속도상 실용적이지 않습니다. 순수 CPU 추론은 사실상 불가능합니다.
- `torch`와 `diffusers`를 설치할 수 있는 Python 환경 — 첫 실행 시 자동으로 설치됩니다.

### 로컬 Video-to-Video를 사용하는 이유

클라우드 기반 영상 리스타일링 서비스와 비교했을 때:

**로컬 처리의 이점:**
- **프라이버시**: 원본 영상과 프롬프트가 로컬 밖으로 나가지 않습니다.
- **비용**: 초 단위/렌더 단위 API 요금이 없습니다.
- **모델 선택**: HuggingFace Hub의 어떤 SD 1.5 파인튜닝이든 외형 백본으로 사용 가능 — `model.repository`만 바꾸면 전체 미학이 바뀝니다.
- **파이프라인 친화적**: 다른 model-compose 태스크(상류의 video-clipper, 하류의 video-processor 등)와 조합하여 엔드투엔드 리스타일링 파이프라인을 구성할 수 있습니다.

**트레이드오프:**
- **하드웨어 요구사항**: 짧은 클립은 8 GB VRAM으로 여유롭지만, 클립이 길어지거나 해상도가 높아지면 프레임 수에 비례하여 VRAM 사용량이 선형으로 증가합니다.
- **모션 범위**: AnimateDiff의 모션 어댑터는 짧은 클립으로 학습되어 있어, ~16프레임까지 일관된 모션을 기대할 수 있고 ~32프레임을 넘어가면 품질이 저하됩니다.
- **라이선스**: 상업적 사용 전에 베이스 모델과 모션 어댑터 각각의 라이선스를 확인하세요.

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/video-to-video-animatediff
   ```

2. 추가 환경 구성은 필요하지 않습니다 — 베이스 체크포인트(`Realistic_Vision_V5.1_noVAE`), 모션 어댑터(`animatediff-motion-adapter-v1-5-3`), IP-Adapter(`h94/IP-Adapter`)가 첫 실행 시 HuggingFace Hub에서 다운로드되어 `~/.cache/huggingface/` 아래에 캐시됩니다.

3. 다른 미학을 원한다면 `model-compose.yml`의 `model.repository`를 편집하세요. 모션 어댑터가 동일한 베이스 아키텍처를 대상으로 한다면, 애니메·일러스트 모델을 비롯한 어떤 SD 1.5 파인튜닝이라도 사용할 수 있습니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```
   > 첫 실행 시 베이스 체크포인트(~2 GB)와 모션 어댑터(~1.6 GB)를 다운로드합니다. 컨트롤러가 준비 상태를 보고할 때까지 수 분이 소요될 수 있습니다.

2. **워크플로우 실행:**

   **API 사용:**
   ```bash
   # 최소 호출 — 영상에 프롬프트로 스타일을 입히고 나머지는 기본값
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "clip=@/path/to/source.mp4" \
     -F 'input={"video": "@clip", "prompt": "cinematic shot, film grain, warm sunset lighting"}'

   # 특정 시드와 함께 더 강한 스타일 전이(denoise_strength 상향)
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "clip=@/path/to/source.mp4" \
     -F 'input={"video": "@clip", "prompt": "watercolor painting, soft brushstrokes", "denoise_strength": 0.7, "seed": 42}'

   # 32프레임, 12 fps로 더 긴 출력
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "clip=@/path/to/source.mp4" \
     -F 'input={"video": "@clip", "prompt": "neon cyberpunk city, rain, reflections", "num_frames": 32, "fps": 12}'

   # 레퍼런스 이미지 기반 스타일 전이 (IP-Adapter)
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "clip=@/path/to/source.mp4" \
     -F "ref=@/path/to/reference.jpg" \
     -F 'input={"video": "@clip", "reference_image": "@ref", "prompt": "in the style of the reference image", "ip_adapter_scale": 0.7}'
   ```

   **Web UI 사용:**
   - Web UI 열기: http://localhost:8081
   - `video`를 업로드하고(모델이 ~16프레임 창으로 학습되었으므로 짧은 클립이 가장 잘 동작합니다) `prompt`를 입력합니다
   - 선택적으로 `denoise_strength`, `num_frames`, `fps`, `guidance_scale`을 조정하거나 `seed`를 설정합니다
   - "Run Workflow" 버튼을 클릭하면 MP4가 반환됩니다

## 구성 참조

### 컴포넌트 필드

| 필드             | 설명                                                                                                                          | 기본값                                                |
|------------------|-------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------|
| `task`           | `video-to-video`여야 합니다.                                                                                                  | —                                                     |
| `driver`         | `huggingface`여야 합니다.                                                                                                     | —                                                     |
| `architecture`   | Video-to-video 아키텍처. 현재는 `animatediff`만 지원됩니다.                                                                   | —                                                     |
| `model`          | 베이스 SD 1.5 스타일 체크포인트(HuggingFace 저장소 또는 로컬 경로). 어떤 SD 1.5 파인튜닝이든 동작합니다.                       | —                                                     |
| `motion_adapter` | 베이스 아키텍처에 대응하는 AnimateDiff 모션 어댑터.                                                                           | —                                                     |
| `ip_adapter`     | 액션에서 `reference_image`를 사용할 때 로드되는 IP-Adapter 가중치. `filename`을 `<sub_dir>/<weight_name>` 형식으로 지정.      | —                                                     |
| `device`         | 연산 디바이스(`cuda`, `cuda:0` 등). `auto`는 사용 가능한 최적 디바이스를 선택합니다.                                          | `auto`                                                |

### 액션 필드

| 필드                          | 설명                                                                                                                    | 기본값                                                   |
|-------------------------------|-------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------|
| `video`                       | 모션을 보존할 원본 영상(또는 영상 리스트/스트림).                                                                       | —                                                        |
| `prompt`                      | 리스타일된 외형을 유도하는 텍스트 프롬프트.                                                                             | (없음)                                                   |
| `negative_prompt`             | 생성 결과에서 피하고 싶은 내용을 기술하는 텍스트.                                                                        | `"bad quality, worst quality, low resolution"`           |
| `reference_image`             | 외형을 참조하도록 IP-Adapter에 전달되는 이미지. 컴포넌트의 `ip_adapter`가 설정되어 있어야 합니다.                        | (없음)                                                   |
| `seed`                        | 재현성을 위한 랜덤 시드. 지정하지 않으면 매 호출마다 새로운 샘플을 사용합니다.                                          | (없음)                                                   |
| `params.num_frames`           | 입력 영상에서 샘플링해 출력할 프레임 수. 비워두면 입력의 모든 프레임을 사용합니다 — FreeNoise가 슬라이딩 컨텍스트 창으로 긴 클립을 처리합니다. | (입력 프레임 전체)                                        |
| `params.fps`                  | 출력 영상 프레임 레이트. 비워두면 입력 클립의 원본 fps를 따르며, 결과가 원본 재생 시간을 유지합니다.                    | (원본 fps)                                                |
| `params.height` / `.width`    | 출력 영상 해상도. 지정하지 않으면 입력 영상의 크기를 그대로 사용합니다.                                                | (소스 크기)                                              |
| `params.denoise_strength`     | 디노이즈 강도. `0.4-0.5`는 모션을 강하게 보존, `0.6-0.7`은 프롬프트를 더 강하게 반영.                                   | `0.5`                                                    |
| `params.guidance_scale`       | Classifier-free guidance 스케일.                                                                                        | `7.5`                                                    |
| `params.inference_steps`      | 프레임당 diffusion 추론 스텝. 스텝이 많을수록 품질은 좋아지고 속도는 느려집니다.                                        | `25`                                                     |
| `params.ip_adapter_scale`     | `reference_image`가 제공될 때 IP-Adapter의 영향력. 0은 비활성화, 1은 레퍼런스에 완전히 의존.                            | `0.6`                                                    |
| `batch_size`                  | 입력이 리스트나 스트림일 때 배치당 처리하는 `(video, prompt)` 쌍의 수.                                                  | `1`                                                      |

## 참고 사항

- **첫 실행은 느립니다**: 컨트롤러가 베이스 체크포인트와 모션 어댑터를 모두 가져와야 합니다. 이후 실행은 캐시된 파일을 재사용합니다.
- **프레임 수가 중요합니다**: AnimateDiff는 ~16프레임 창으로 학습되었습니다. FreeNoise가 항상 켜져 있어 긴 입력도 렌더링되지만, 학습 창을 크게 넘어갈수록 드리프트가 누적되고 모션이 부드러워집니다 — 원본 클립이 아주 길다면 상류에서 `video-clipper`로 잘라서 사용하세요.
- **강도의 스위트스팟**: `0.4` 미만은 입력을 거의 바꾸지 않고, `0.7` 초과는 종종 모션 일관성을 무너뜨립니다. `0.5`에서 시작해 조정하세요.
- **미학 스왑**: 리얼리스틱에서 애니 스타일로 이동하려면 `model.repository`를 SD 1.5 애니 파인튜닝(예: `Meina/MeinaMix_V11` 등)으로 변경하세요. 모션 어댑터는 그대로 유지합니다.
- **프롬프트 무게**: AnimateDiff는 씬을 재구성하지 못하고 재채색·재스타일링만 하므로, 사물 중심 프롬프트보다 서술적이고 스타일 중심인 프롬프트가 잘 동작합니다.
- **레퍼런스 이미지 팁**: IP-Adapter는 `reference_image`의 색감·질감·피사체 단서를 전이합니다. 입력 클립과 구도가 비슷한 스틸을 고르세요. `ip_adapter_scale: 0.6`에서 시작해, 레퍼런스가 모션을 압도하면 `0.3`쪽으로 내리고, 효과가 약하면 `0.8`쪽으로 올립니다.
- **VRAM 계획**: 16프레임 512×512 `float16` 기준 대략 8-10 GB VRAM, 24프레임은 ~1.6배. OOM이 발생하면 `num_frames`나 해상도를 줄이세요.
- **파이프라인 조합**: 상류의 `video-clipper`와 조합해 리스타일 전에 특정 구간만 잘라내거나, 하류의 `video-processor`와 조합해 리스타일된 클립을 더 긴 편집본에 합성하세요.

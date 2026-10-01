# 모션 생성 (Kimodo) 모델 태스크 예제

이 예제는 NVIDIA의 Kimodo 디퓨전 모델을 사용해 텍스트 프롬프트로부터 3D 휴먼 모션 시퀀스를 생성하며, model-compose의 내장 모델 태스크 기능을 통해 로컬에서 실행됩니다. Kimodo는 약 700시간의 광학 모션 캡처 데이터로 학습된 kinematic 모션 디퓨전 모델이며, 출력은 3D 애니메이션 도구나 물리 기반 시뮬레이션에서 바로 사용할 수 있는 관절 위치, 회전 행렬, 발 접촉 레이블의 시퀀스입니다.

## 개요

이 예제는 하나의 `generate` 워크플로우를 노출합니다. 자연어 프롬프트를 받아 NPZ 파일 형태의 모션 시퀀스를 반환합니다.

응답 페이로드에는 다음과 같은 항목이 포함됩니다:

- `posed_joints` — 월드 공간에서의 관절 위치, 형상 `[T, J, 3]`
- `global_rot_mats` / `local_rot_mats` — 관절별 회전 행렬, 형상 `[T, J, 3, 3]`
- `foot_contacts` — 왼쪽 뒤꿈치, 왼쪽 발끝, 오른쪽 뒤꿈치, 오른쪽 발끝의 이진 레이블, 형상 `[T, 4]`
- `root_positions`, `smooth_root_pos`, `global_root_heading`
- `fps` — 모델이 생성에 사용한 프레임레이트

`T`는 프레임 수, `J`는 선택한 스켈레톤의 관절 수입니다.

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- **NVIDIA GPU 강력 권장**. Kimodo는 RTX 3090 / 4090 / A100에서 테스트되었습니다. Mac / CPU 상황은 아래 [시스템 요구사항](#시스템-요구사항)을 참고하세요.
- 첫 실행 시 인터넷 액세스 필요 (체크포인트와 텍스트 인코더가 Hugging Face에서 다운로드됨)
- ~20–30 GB 디스크 공간 (Kimodo 체크포인트 + LLM2Vec-Llama-3-8B 텍스트 인코더 가중치)

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/motion-generation-kimodo
   ```

2. 추가 환경 구성은 필요하지 않습니다 — Kimodo와 PyTorch 종속성은 첫 실행 시 자동 설치됩니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **모션 생성:**

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "prompt": "a person walks forward, then waves with the right hand",
         "duration": 6.0,
         "diffusion_steps": 20,
         "seed": 42
       }
     }' \
     --output motion.npz
   ```

   **웹 UI 사용:**
   - 웹 UI 열기: http://localhost:8081
   - 모션 프롬프트를 입력하고 duration / diffusion steps 조정
   - "Run Workflow"를 클릭하고 결과 NPZ 다운로드

   **CLI 사용:**
   ```bash
   model-compose run generate --input '{"prompt": "a person jumps and lands"}' --output motion.npz
   ```

3. **NPZ 확인 또는 시각화** — NumPy 아카이브를 읽을 수 있는 도구라면 무엇이든 사용 가능합니다. 예: SMPL / SOMA 임포터를 통해 Blender로 로드하거나, G1 스켈레톤 출력을 MuJoCo에 공급하거나, SMPL-X 출력을 다운스트림 리타겟팅 파이프라인으로 전달.

## 컴포넌트 세부사항

### Kimodo 모션 생성 컴포넌트
- **Type**: `motion-generation` 태스크를 갖는 모델 컴포넌트
- **Driver / Family**: `custom` / `kimodo`
- **Preset**: `Kimodo-SOMA-RP-v1.1` (SOMA 77-관절 스켈레톤, 700시간 Bones Rigplay로 학습)
- **Model**: `nvidia/Kimodo-SOMA-RP-v1.1` (`preset`에서 자동 유도; 필요 시 `model:`로 오버라이드)
- **Device**: `cuda` 권장
- **Output Format**: NPZ 파일 (`application/x-npz`)
- **Concurrency**: 1 (한 번에 하나의 요청만 처리)

### 모델 정보: Kimodo
- **개발자**: NVIDIA Toronto AI Lab ([Kimodo 프로젝트 페이지](https://research.nvidia.com/labs/sil/projects/kimodo/) 참고)
- **유형**: DDIM 샘플링과 classifier-free guidance를 사용하는 트랜스포머 기반 모션 디퓨전 모델
- **사용 가능한 프리셋**:
  - `Kimodo-SOMA-RP-v1.1` *(기본)* — SOMA 스켈레톤, Bones Rigplay 1
  - `Kimodo-SOMA-SEED-v1.1` — SOMA 스켈레톤, BONES-SEED 서브셋
  - `Kimodo-G1-RP-v1` — Unitree G1 로봇 스켈레톤
  - `Kimodo-G1-SEED-v1` — Unitree G1, BONES-SEED 서브셋
  - `Kimodo-SMPLX-RP-v1` — SMPL-X 스켈레톤 (research 라이선스)
- **CFG 유형**: `nocfg`, `regular`, `separated` *(기본)*. `separated`에서는 `cfg_weight`를 `[text, constraint]` 두 원소 쌍으로 지정할 수 있습니다.
- **텍스트 인코더**: LLM2Vec-Llama-3-8B. VRAM 절감을 위해 CPU로 강제할 수 있습니다 — [VRAM 사용량 줄이기](#vram-사용량-줄이기) 참고.

## 워크플로우 세부사항

### "Generate" 워크플로우 (기본)

**설명**: 자연어 프롬프트로부터 모션 시퀀스를 생성합니다.

#### 입력 매개변수

| 매개변수           | 유형    | 필수 | 기본값   | 설명 |
|-------------------|---------|------|---------|------|
| `prompt`          | text    | 예   | —       | 원하는 모션에 대한 자연어 설명 |
| `duration`        | number  | 아니오 | `4.0` | 모션 지속 시간 (초) |
| `num_samples`     | integer | 아니오 | `1`   | 생성할 모션 변형 수 |
| `diffusion_steps` | integer | 아니오 | `10`  | DDIM 디노이징 스텝 수; 많을수록 품질 향상, 속도는 저하 |
| `cfg_weight`      | number  | 아니오 | `2.0` | Classifier-free guidance 가중치; `separated` CFG 사용 시 `[text, constraint]` 두 원소 리스트 |
| `post_processing` | boolean | 아니오 | `true` | 출력에 발 미끄러짐 및 제약 조건 정리 적용 |
| `seed`            | integer | 아니오 | —     | 재현성을 위한 랜덤 시드 |

#### 출력 형식

| 필드 | 유형                | 설명 |
|------|---------------------|------|
| —    | `application/x-npz` | `posed_joints`, `global_rot_mats`, `local_rot_mats`, `foot_contacts`, `root_positions`, `smooth_root_pos`, `global_root_heading`, `fps`를 포함하는 NPZ 아카이브 |

## 시스템 요구사항

### 최소 요구사항

- **GPU**: NVIDIA GPU 권장. Kimodo는 RTX 3090 / 4090 / A100에서 전체 GPU 추론 시 ~17 GB VRAM, 또는 저 VRAM 환경에서는 `<3 GB VRAM + CPU 텍스트 인코더`로 테스트되었습니다.
- **RAM**: 32 GB 권장 (텍스트 인코더가 CPU로 강제될 때 8B 파라미터 모델이 됩니다)
- **디스크 공간**: Kimodo 체크포인트와 LLM2Vec 텍스트 인코더 캐시용 ~20–30 GB
- **인터넷**: 최초 Hugging Face 다운로드에만 필요

### Apple Silicon / Mac

Kimodo는 **macOS에서 공식 지원되지 않습니다**. 업스트림 프로젝트는 CUDA만 테스트합니다. `device: cpu`로 실행하는 것은 가능하지만 매우 느립니다 (생성당 수 분). 8B 파라미터 텍스트 인코더도 CPU에서 실행해야 하기 때문입니다. `device: mps` 실행은 지원되지 않는 연산자에서 실패할 수 있습니다 — model-compose는 설정을 받아들이지만 Kimodo 자체가 추론 시점에 에러를 낼 수 있습니다.

### 성능 참고사항

- 첫 실행은 Kimodo 체크포인트 + LLM2Vec 가중치를 Hugging Face에서 다운로드
- 비양자화 텍스트 인코더가 VRAM의 대부분을 차지 — `text_encoder_device: cpu`로 GPU 사용량을 ~3 GB 미만으로 줄일 수 있으나 텍스트 인코딩이 느려짐
- VRAM 고갈 방지를 위해 컴포넌트당 동시 요청 1개

## 커스터마이징

### VRAM 사용량 줄이기

```yaml
component:
  text_encoder_device: cpu    # LLM2Vec을 CPU에 유지; GPU 사용량 <3 GB로 감소
  text_encoder_fp32: false    # 기본 bf16이 더 빠르고 메모리 사용량도 적음
```

### 스켈레톤 / 데이터셋 전환

```yaml
component:
  # model은 nvidia/<preset>으로 자동 유도됨; 미러를 호스팅할 때만 오버라이드.
  preset: Kimodo-G1-RP-v1     # Unitree G1 로봇 스켈레톤
```

사용 가능한 프리셋은 [모델 정보](#모델-정보-kimodo) 참고.

### Classifier-Free Guidance 튜닝

```yaml
component:
  cfg_type: separated         # nocfg | regular | separated

actions:
  - method: generate
    params:
      cfg_weight: [2.0, 2.0]  # `separated`에서 [text, constraint]
```

`nocfg` / `regular`에는 단일 숫자, `separated`에는 두 원소 리스트를 사용하세요 (Kimodo CLI의 `--cfg_weight` 동작과 일치).

### 프롬프트당 다중 변형

```yaml
actions:
  - method: generate
    params:
      num_samples: 4
```

Kimodo는 배치 텐서를 반환하며, 생성된 NPZ는 모든 샘플을 선두 축을 따라 담습니다.

## 제한사항

- **제약 조건 미지원**: Kimodo의 풀바디 키프레임, 2D 웨이포인트, 엔드이펙터 제약 조건 트랙은 Python 측 제약 객체를 요구하며 이 예제의 DSL로는 노출되지 않습니다. 현재는 텍스트 기반 생성만 지원합니다. 제약 조건 지원은 DSL 표면이 설계된 뒤 후속으로 추가될 수 있습니다.

## 관련 예제

- **[image-to-3d-pixal3d](../image-to-3d-pixal3d/)**: 단일 이미지에서 3D 메시 생성
- **[talking-head-sonic](../talking-head-sonic/)**: 초상화와 오디오로 토킹헤드 비디오 생성
- **[music-generation-yue2](../music-generation-yue2/)**: YuE2를 사용한 로컬 음악 생성

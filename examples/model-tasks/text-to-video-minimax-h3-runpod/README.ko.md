# RunPod에서 실행하는 텍스트-투-비디오 (MiniMax-H3)

[text-to-video-minimax-h3](../text-to-video-minimax-h3/)와 동일한 워크플로이지만, ~33B 파라미터의 MiniMax-H3 Omni-Transformer를 로컬이 아닌 원격 [RunPod](https://www.runpod.io/) GPU 파드에서 실행합니다. 선언형 설정은 동일하며 — `component.runtime`만 바뀝니다.

## 왜 원격인가

- 체크포인트는 ~70 GB이고 모델은 33B 파라미터입니다. 단일 컨슈머 GPU는 `cpu_offload: true`가 필요하고 느립니다. H100 급 하드웨어는 편안하게 돌아가지만 소유하기엔 비현실적입니다.
- RunPod에서는 파드가 `idle_timeout` 후 자동 정지되므로, 생성하는 동안만 GPU 비용을 지불합니다. ~70 GB 가중치는 정지/재개를 거쳐도 네트워크 볼륨에 유지되므로 1회성 다운로드 비용이 상각됩니다.

## 필수 요건

1. 결제가 설정된 [RunPod](https://www.runpod.io/) 계정.
2. H100 재고가 있는 데이터센터의 **네트워크 볼륨**. 실용적 최소치는 100 GB: 가중치 ~70 GB + pip 캐시. 볼륨 ID를 기록해 두세요.
3. [RunPod API 키](https://www.runpod.io/console/user/settings).
4. [`MiniMaxAI/MiniMax-H3`](https://huggingface.co/MiniMaxAI/MiniMax-H3) Hugging Face 접근 권한. 가중치는 MiniMax H3 Community License로 게이트됩니다 — 모델 페이지에서 라이선스에 동의하고 `.env`에 `HF_TOKEN`을 설정하세요 (아래 참조).

## 설정

이 디렉터리에 `.env` 파일을 만들거나 셸에 변수를 export합니다:

```bash
RUNPOD_API_KEY=your-runpod-api-key
RUNPOD_VOLUME_ID=your-volume-id
HF_TOKEN=your-huggingface-token
```

`HF_TOKEN`은 호스트에서 `${env.HF_TOKEN}`으로 해석되어 compose 파일의 `component.model.token`을 통해 파드로 전달됩니다. 파드의 모델 프로비저너가 이 토큰으로 게이트된 가중치를 네트워크 볼륨 캐시에 다운로드합니다. 호스트 환경 변수는 파드로 **자동 전달되지 않으므로**, 호스트에 `HF_TOKEN`만 있어도 파드 내부의 `huggingface_hub`에는 도달하지 않습니다.

## 실행

```bash
model-compose up
model-compose run --input '{"prompt": "a quiet alleyway at dusk, warm neon reflections on wet pavement, slow dolly in"}'
```

최초 `model-compose up` 시 수행되는 과정:

1. 이전 세션에서 남은 고아 파드를 종료합니다.
2. 네트워크 볼륨이 위치한 데이터센터에 새 H100 SXM 파드를 생성합니다. Secure cloud에서 `RUNNING` 상태까지 ~30–90초 소요.
3. 파드가 볼륨의 pip 캐시에 model-compose를 설치하고 WebSocket 워커를 시작합니다.
4. model-compose가 세션별 bearer 토큰으로 `wss://<pod_id>-8000.proxy.runpod.net`에 연결합니다.
5. 첫 요청 시 Hugging Face 샤드(~70 GB)가 네트워크 볼륨으로 다운로드되고(RunPod 네트워크 기준 15–30분), bfloat16으로 VRAM에 로드됩니다(추가 3–5분). compose 파일의 `start_timeout: 60m`은 이 전체 체인을 커버하도록 잡혀 있습니다 — 그렇지 않으면 호스트가 중간에 포기하고 파드를 정지시킵니다. 이후 재개는 캐시된 샤드를 재사용하므로 초 단위로 끝납니다.

이후 요청은 실행 중인 파드를 재사용합니다. 마지막 요청으로부터 10분 후 파드가 자동 정지되어 GPU 과금이 멈추며, 다음 요청에서 재개됩니다.

## 비용 개요

- H100 SXM Secure cloud: 실행 중 시간당 ~$3.99
- 100 GB 네트워크 볼륨: 월 ~$7
- 첫 요청에는 1회성 ~70 GB 다운로드가 포함됩니다(RunPod 네트워크 기준 시간이 아닌 분 단위). 이후 요청은 생성 자체 비용만 지불합니다.

## GPU 변경

예제는 H100 SXM을 기본으로 하는데, 이는 offload 없이 전체 모델이 올라가기 때문입니다. 두 가지 대안:

- **더 저렴한 H100.** `gpu_type`을 `NVIDIA H100 PCIe`로 변경 — 동일한 80 GB, 약간 낮은 처리량, 낮은 시간당 요금.
- **24 GB 컨슈머 GPU.** `gpu_type`을 `NVIDIA GeForce RTX 4090`으로, `cloud_type: ALL`, component에 `cpu_offload: true` 설정. 파드는 offload로 모델을 올리지만 각 생성이 눈에 띄게 느려집니다.

## 정리

```bash
model-compose down
```

이 명령이 파드를 종료합니다. 네트워크 볼륨(과 캐시된 ~70 GB 체크포인트)은 model-compose가 손대지 않으므로, 더 이상 필요 없을 때 대시보드에서 수동으로 삭제하세요.

재시작 사이에 파드를 유지하고 싶다면 `down` 대신 `model-compose stop`을 사용하세요 — stop은 파드를 프로비저닝된 상태(일시 정지)로 유지하므로, 다음 `start`에서 초 단위로 재개됩니다.

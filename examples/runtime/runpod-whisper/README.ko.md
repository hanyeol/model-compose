# RunPod 런타임 (Whisper 음성 인식)

원격 [RunPod](https://www.runpod.io/) GPU 포드에서 Whisper `large-v3-turbo`
음성-텍스트 모델을 실행합니다. 짧은 오디오 파일을 넣으면 전사 결과를
반환합니다.

더 큰 모델로 넘어가기 전에 `runpod` 런타임을 엔드투엔드로 검증하는 용도로
이 예제를 사용하세요 — Whisper 가중치는 ~1.6 GB에 불과하며 단일 RTX 4090에서
수 초 안에 모델이 로드됩니다.

## 준비사항

1. 결제 수단이 등록된 [RunPod](https://www.runpod.io/) 계정.
2. RTX 4090을 사용할 수 있는 데이터 센터에 생성한 **네트워크 볼륨**.
   20 GB 볼륨(~월 $1.4)이면 Whisper와 pip 캐시를 담기에 충분합니다.
   볼륨 ID를 메모해 두세요.
3. [RunPod API 키](https://www.runpod.io/console/user/settings).

## 환경 설정

이 디렉터리에 `.env` 파일을 만들거나 (또는 셸에서 변수를 export):

```bash
RUNPOD_API_KEY=your-runpod-api-key
RUNPOD_VOLUME_ID=your-volume-id
```

## 실행 방법

```bash
model-compose up
model-compose run --input '{"audio": "./sample.wav"}'
```

최초 `model-compose up` 실행 시 수행되는 작업:

1. 이전 세션에서 남은 `mindor-whisper` 이름의 고아 포드가 있다면 종료합니다.
2. 네트워크 볼륨이 위치한 데이터 센터에 RTX 4090 포드를 새로 생성합니다.
   Community 클라우드에서는 `RUNNING` 상태까지 ~30–90초 걸립니다.
3. 포드가 GitHub에서 model-compose를 볼륨의 pip 캐시로 설치하고
   WebSocket 워커를 시작합니다.
4. model-compose가 세션별 bearer 토큰으로
   `wss://<pod_id>-8000.proxy.runpod.net`에 연결합니다. 이제 컴포넌트가
   사용 가능한 상태입니다.

그 뒤 `model-compose run`을 실행하면:

- 오디오가 WS 프록시를 통해 전달되고, 포드의 GPU에서 Whisper가 실행된 뒤
  전사 결과가 돌아옵니다.
- 마지막 요청으로부터 5분이 지나면 포드가 자동으로 중지되어 GPU 과금이
  멈춥니다. 볼륨(과 캐시된 가중치)은 유지됩니다. 다음 실행에서는 동일한
  포드가 수 초 안에 재개됩니다.

## 정리

`model-compose down`은 포드를 종료합니다. 네트워크 볼륨은 model-compose가
전혀 건드리지 않으므로 더 이상 필요 없을 때 대시보드에서 직접 삭제하세요.

재시작 간에 포드를 유지하고 싶다면 `down` 대신 `model-compose stop`을
사용하세요 — stop은 포드를 프로비저닝된 상태(단지 일시정지)로 유지하므로
다음 `start`에서 수 초 내에 재개됩니다.

## 비용 예시

- RTX 4090 Community: 실행 중 시간당 ~$0.34–0.44
- 20 GB 네트워크 볼륨: 월 ~$1.4
- 이 예제의 단일 전사 작업은 1분도 안 되는 GPU 시간이면 끝나므로,
  실질적인 실행당 비용의 대부분은 첫 요청 시 ~30–90초의 콜드 스타트입니다.

## 왜 이 예제에 RunPod을 쓰는가

Whisper 자체는 원격 GPU가 *필요하지는* 않습니다 — 이 예제는 반복 비용이
저렴할 만큼 작은 모델로 RunPod 런타임 파이프라인의 모든 단계(포드 생성,
부트스트랩, WS 접속, 유휴 중지, 재개)를 검증하기 위해 존재합니다. 엔드투엔드로
동작하는 것을 확인한 뒤 `component.model`과 GPU 타입을 바꿔 더 큰 워크로드를
검증하세요.

# Vast.ai 런타임 (Whisper 음성 인식)

원격 [Vast.ai](https://vast.ai/) GPU 인스턴스에서 Whisper `large-v3-turbo`
음성-텍스트 모델을 실행합니다. 짧은 오디오 파일을 넣으면 전사 결과를
반환합니다.

더 큰 모델로 넘어가기 전에 `vastai` 런타임을 엔드투엔드로 검증하는 용도로
이 예제를 사용하세요 — Whisper 가중치는 ~1.6 GB에 불과하며 단일 RTX 4090에서
수 초 안에 모델이 로드됩니다.

## 준비사항

1. 결제 수단이 등록된 [Vast.ai](https://vast.ai/) 계정.
2. Vast.ai 대시보드에서 생성한 **네트워크 볼륨**. 20 GB 볼륨이면
   Whisper와 pip 캐시를 담기에 충분합니다. 볼륨 ID를 메모해 두세요.
3. [Vast.ai API 키](https://cloud.vast.ai/account/).

## 환경 설정

이 디렉터리에 `.env` 파일을 만들거나 (또는 셸에서 변수를 export):

```bash
VASTAI_API_KEY=your-vastai-api-key
VASTAI_VOLUME_ID=your-volume-id
```

## 실행 방법

```bash
model-compose up
model-compose run --input '{"audio": "./sample.wav"}'
```

최초 `model-compose up` 실행 시 수행되는 작업:

1. 이전 세션에서 남은 `mindor-whisper` 레이블의 고아 인스턴스가 있다면
   삭제합니다.
2. Vast.ai 마켓플레이스에서 검증된 호스트의 가장 저렴한 RTX 4090 오퍼를
   찾아 임대합니다. `running` 상태까지 ~30–90초 걸립니다.
3. 인스턴스가 볼륨의 pip 캐시로 model-compose를 설치하고 Vast가 매핑해준
   호스트 포트에서 WebSocket 워커를 시작합니다.
4. model-compose가 세션별 bearer 토큰으로
   `ws://<public_ip>:<mapped_port>`에 연결합니다. 이제 컴포넌트가 사용
   가능한 상태입니다.

그 뒤 `model-compose run`을 실행하면:

- 오디오가 WS 연결을 통해 전달되고, 인스턴스의 GPU에서 Whisper가 실행된
  뒤 전사 결과가 돌아옵니다.
- 마지막 요청으로부터 5분이 지나면 인스턴스가 자동으로 중지되어 GPU
  과금이 멈춥니다. 볼륨(과 캐시된 가중치)은 유지됩니다. 다음 실행에서는
  동일한 인스턴스가 수 초 안에 재개됩니다.

## 정리

`model-compose down`은 인스턴스를 삭제합니다. 네트워크 볼륨은
model-compose가 전혀 건드리지 않으므로 더 이상 필요 없을 때 대시보드에서
직접 삭제하세요.

재시작 간에 인스턴스를 유지하고 싶다면 `down` 대신 `model-compose stop`을
사용하세요 — stop은 인스턴스를 프로비저닝된 상태(단지 일시정지)로
유지하므로 다음 `start`에서 수 초 내에 재개됩니다.

## 비용 예시

- RTX 4090 verified 호스트: 실행 중 시간당 ~$0.25–0.45
- 20 GB 네트워크 볼륨: 호스트별로 다름 (보통 월 몇 센트 수준)
- 이 예제의 단일 전사 작업은 1분도 안 되는 GPU 시간이면 끝나므로,
  실질적인 실행당 비용의 대부분은 첫 요청 시 ~30–90초의 콜드 스타트입니다.

## 왜 이 예제에 Vast.ai를 쓰는가

Whisper 자체는 원격 GPU가 *필요하지는* 않습니다 — 이 예제는 반복 비용이
저렴할 만큼 작은 모델로 Vast.ai 런타임 파이프라인의 모든 단계(오퍼 검색,
인스턴스 생성, 부트스트랩, WS 접속, 유휴 중지, 재개)를 검증하기 위해
존재합니다. 엔드투엔드로 동작하는 것을 확인한 뒤 `component.model`과 GPU
타입을 바꿔 더 큰 워크로드를 검증하세요.

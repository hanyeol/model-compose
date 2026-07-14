# VibeVoice Realtime TTS

WebSocket을 통해 Docker 컨테이너에서 실행되는 [Microsoft VibeVoice Realtime (0.5B)](https://github.com/microsoft/VibeVoice)을 사용한 텍스트 음성 변환.

## 요구 사항

- NVIDIA GPU를 지원하는 Docker (`nvidia-container-toolkit`)
- 최소 4GB VRAM을 가진 NVIDIA GPU

## 사용법

```bash
model-compose up
```

이는 다음을 수행합니다:
1. Docker 이미지 빌드 (첫 실행은 몇 분 걸림)
2. HuggingFace에서 모델 다운로드 (~2GB)
3. 포트 3000에서 VibeVoice WebSocket 서버 시작
4. 포트 8080에서 model-compose API 시작
5. 포트 8081에서 Gradio WebUI 시작

## API

```bash
curl -X POST http://localhost:8080/api/workflows/runs \
  -H "Content-Type: application/json" \
  -d '{"input": {"text": "Hello, world!", "voice": "Carter"}}'
```

### 입력 매개변수

| 매개변수     | 유형   | 기본값   | 설명                              |
|-------------|--------|----------|-----------------------------------|
| `text`      | string | 필수     | 합성할 텍스트                     |
| `voice`     | string | Carter   | 보이스 프리셋 이름                |
| `cfg_scale` | number | 1.5      | Classifier-free guidance scale    |

### 사용 가능한 보이스

25개의 사전 학습된 보이스가 포함됩니다: Alloy, Ash, Ballad, Carter, Coral, Echo, Ember, Fable, Juniper, Lark, Onyx, Nova, Sage, Shimmer, Vale, Verse 등.

## 작동 방식

`websocket-server` 컴포넌트는:
1. VibeVoice의 데모 WebSocket 서버를 실행하는 Docker 컨테이너를 빌드하고 시작합니다
2. 각 요청 시 텍스트/보이스를 쿼리 매개변수로 `ws://localhost:3000/stream`에 연결합니다
3. WebSocket을 통해 전송된 바이너리 PCM16 오디오 청크를 수집합니다
4. 조립된 오디오를 WAV 응답으로 반환합니다

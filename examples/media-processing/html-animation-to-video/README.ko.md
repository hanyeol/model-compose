# HTML → 비디오 (프레임 렌더링) 예제

`html-frame-renderer`와 `video-encoder` 컴포넌트를 연결하여
HTML 애니메이션을 MP4 비디오로 렌더링합니다.

## 개요

`html-frame-renderer`는 헤드리스 Chromium에서 HTML 페이지를 열고
작은 페이지 측 계약(최상위 `window.render(t)`와 `window.__renderer`의
`duration`)을 통해 프레임을 한 번에 하나씩 그리도록 요청합니다.
엔진은 PNG 바이트를 `video-encoder`로 스트리밍하며, 이는 ffmpeg에
파이프되어 H.264로 인코딩됩니다.

## 페이지 계약

페이지는 최상위 `window.render(t)`를 정의하고 캡처 준비가 끝나면
`ready`를 뒤집습니다. 전체 길이는 액션의 `duration:` 필드(`model-compose.yml`)
에서 오고, `window.__renderer.duration` 으로 주입됩니다:

```js
const duration = window.__renderer.duration;   // 액션의 `duration:` 에서 옴

window.render = (t) => {              // 스크린샷 전에 프레임당 한 번씩 호출됨
  // 시각 t의 상태에 맞게 DOM / 캔버스 / 애니메이션 타임라인을 갱신
};
window.__renderer.ready = true;       // "캡처 준비 완료" 선언 — 엔진은 이
                                      // 플래그가 true가 된 뒤에만 렌더링을
                                      // 시작합니다. 비동기 셋업(웹폰트,
                                      // 이미지, 텍스처)이 필요하면 그걸
                                      // 먼저 await 하고 플래그를 세팅하세요.
```

엔진은 페이지 스크립트가 실행되기 전에 두 개의 필드를 시드합니다:

- **`duration`** — 액션의 `duration:` 에서 파싱된 초 단위 숫자. 읽기 전용;
  `t / duration` 로 progress 계산에 유용합니다.
- **`props`** — 액션 입력 `props:`(선택)에서 설정됩니다. 워크플로우가 전달하는
  어떤 형태든 페이지에서 `window.__renderer.props`로 참조됩니다.

이 예제는 `props`에 `title:`을 전달하며 페이지(`animation.html`)는
이를 움직이는 진행 표시줄 위에 크게 중앙 정렬된 제목으로 렌더링합니다.

## 준비사항

### 필수 요구사항

- model-compose 설치
- `PATH`에 `ffmpeg`
- Playwright Chromium 브라우저: `playwright install chromium`

### 환경

```bash
cd examples/media-processing/html-animation-to-video
```

## 실행 방법

1. **서비스 시작**
   ```bash
   model-compose up
   ```

2. **렌더 트리거**

   http://localhost:8081의 Gradio UI 또는 HTTP로:

   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H 'Content-Type: application/json' \
     -d '{"workflow_id": "render", "input": {"frame_rate": 30}}'
   ```

응답에는 생성된 `.mp4`의 경로가 포함됩니다.

## 병렬 렌더링

렌더러 액션은 `worker_count` 입력(기본 `1`)을 받습니다. 각 워커는 자기
Chromium 페이지를 열어 공유 큐에서 프레임 번호를 꺼내 렌더하고, 결과는
번호순으로 재정렬되어 인코더로 스트리밍됩니다. 이 예제처럼 가벼운 캔버스
애니메이션에서는 효과가 크지 않지만, `render(t)` 가 실제로 시간을 쓰는
페이지(WebGL 씬, 무거운 컴포지팅)에서는 몇 워커까지 거의 선형으로
확장됩니다.

```bash
curl -X POST http://localhost:8080/api/workflows/runs \
  -H 'Content-Type: application/json' \
  -d '{"workflow_id": "render", "input": {"frame_rate": 30, "worker_count": 4}}'
```

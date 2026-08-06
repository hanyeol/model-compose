# HTML → 비디오 (프레임 렌더링) 예제

`html-frame-renderer`와 `video-encoder` 컴포넌트를 연결하여
HTML 애니메이션을 MP4 비디오로 렌더링합니다.

## 개요

`html-frame-renderer`는 헤드리스 Chromium에서 HTML 페이지를 열고
`window.__renderer`의 페이지 측 계약을 통해 프레임을 한 번에 하나씩
그리도록 요청합니다. 엔진은 PNG 바이트를 `video-encoder`로 스트리밍하며,
이는 ffmpeg에 파이프되어 H.264로 인코딩됩니다.

## `window.__renderer` 계약

페이지는 `window.__renderer`에 `duration`과 `seek(t)` 함수를 노출합니다:

```js
window.__renderer = window.__renderer || {};
Object.assign(window.__renderer, {
  duration: 5.0,        // 컴포지션 총 길이(초) — 엔진은 이 값을 읽어
                        // 캡처할 프레임 수를 결정합니다.
  seek(t) {             // 스크린샷 전에 프레임당 한 번씩 호출됨
    // 시각 t의 상태에 맞게 DOM / 캔버스 / 애니메이션 타임라인을 갱신
  },
});
```

엔진은 페이지 스크립트가 실행되기 전에 하나의 필드를 시드합니다:

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
     -d '{"workflow_id": "render", "input": {"fps": 30}}'
   ```

응답에는 생성된 `.mp4`의 경로가 포함됩니다.

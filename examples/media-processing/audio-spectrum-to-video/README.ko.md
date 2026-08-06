# 오디오 스펙트럼 비디오 예제

오디오 파일(mp3, wav 등)을 이퀄라이저 스타일의 MP4 비디오로 변환하고,
**원본 오디오를 다시 먹싱**합니다. 네 개의 컴포넌트를 연결하여 수행합니다:

1. `file-store` (local)이 업로드된 오디오를
   `./output/audio/${context.task_id}/audio`에 저장하여 다운스트림 job들이
   각각 독립적으로 다시 읽을 수 있게 합니다. 업로드는 일회성 스트림으로 도착하므로
   T 분기할 수 없으며; 한 번 영속화하고 URL로 팬아웃하면 이 문제를 피할 수 있습니다.
2. `audio-feature-extractor`가 그 파일을 읽어 프레임별 주파수 스펙트럼을 생성합니다
   (`frames[frame_count][band_count]`, 값은 `[0, 1]`).
3. `html-frame-renderer`가 `window.__renderer.props.spectrum`에서 스펙트럼을 읽는
   작은 HTML 페이지를 열어, 프레임마다 캔버스에 막대를 그립니다.
4. `video-encoder`가 PNG 프레임을 ffmpeg로 파이핑하여 H.264로 인코딩하고
   원본 오디오 파일을 오디오 트랙으로 먹싱합니다.

추출기와 인코더 입력에 있는 `${jobs.save-audio.output.url as audio;url}` 참조는
model-compose에게 파일 저장소의 `file://` URL을 오디오 리소스로 취급하고,
각 소비자 내부에서 지연 로드하도록 지시합니다.

## `window.__renderer` 계약

페이지는 `window.__renderer`에 `duration`과 `seek(t)`를 노출합니다.
엔진은 `duration`을 읽어 캡처할 프레임 수를 결정한 뒤, 프레임마다 `seek(t)`를
한 번씩 호출하고 각 호출 이후 스크린샷을 찍습니다.

```js
window.__renderer = window.__renderer || {};
Object.assign(window.__renderer, {
  duration: totalSeconds,
  seek(t) {
    // 페이지의 캔버스에 시각 t의 프레임을 그림
  },
});
```

엔진은 페이지 스크립트가 실행되기 전에 액션의 `props:` 입력으로부터
`window.__renderer.props`를 시드합니다. 이 예제에서 워크플로우는 전체 스펙트럼 결과를 전달합니다:

```js
window.__renderer.props.spectrum = {
  frames: [[...], [...], ...],  // 프레임별 밴드 진폭, [0, 1] 범위
  fps: 30,
  band_count: 48,
  frame_count: N,
  duration: seconds,
  sample_rate: 22050,
};
```

`animation.html`은 렌더 시각 `t`에 가장 가까운 소스 프레임을 선택하고
밴드마다 색조가 이동된 수직 막대 하나를 그립니다.

## 준비사항

### 필수 요구사항

- model-compose 설치
- `PATH`에 `ffmpeg`
- Playwright Chromium 브라우저: `playwright install chromium`

### 환경

```bash
cd examples/media-processing/audio-spectrum-to-video
```

오디오 파일을 준비하세요 (mp3, wav, flac, ogg, opus 또는 aac).

## 실행 방법

1. **서비스 시작**
   ```bash
   model-compose up
   ```

2. **렌더 트리거**

   http://localhost:8081의 Gradio UI 또는 HTTP로:

   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F 'workflow_id=render' \
     -F 'input.audio=@./song.mp3' \
     -F 'input.fps=30' \
     -F 'input.band_count=48'
   ```

응답에는 생성된 `.mp4`의 경로가 포함됩니다.

# LLM 모션그래픽 → 비디오

로컬 Qwen 코더 모델이 HTML 모션그래픽 페이지를 작성하고, `html-frame-renderer`가 프레임을 캡처하며, `video-encoder`가 MP4로 인코딩합니다. 렌더가 실패하면 페이지가 보고한 에러 메시지를 모델에 되먹여 다시 작성하게 합니다(renderer-in-the-loop).

## 흐름

```
main (loop, 최대 3회)
 └─ attempt (workflow)
     generate  → coder          Qwen3-Coder가 HTML 작성 (직전 HTML·에러를 함께 받음)
     extract   → html-extractor 응답에서 <html> 문서만 추출, 없으면 일부러 throw하는 페이지로 대체
     render    → renderer       Playwright로 프레임 캡처 (streaming)
     encode    → encoder        MP4 인코딩, 실패하면 on_error로 { ok: false, error }
 until: output.ok == true
```

프레임은 lazy하게 흘러가므로 페이지 로드·렌더 에러는 `encode` 잡에서 드러나고, `on_error`가 그 메시지를 다음 반복의 `previous_error`로 넘깁니다. HTML 추출에 실패해도 fallback 페이지가 스스로 에러를 던지므로 같은 재시도 경로를 탑니다.

## 페이지 계약

시스템 프롬프트가 모델에게 강제하는 규칙은 `html-frame-renderer`의 계약 그대로입니다.

- 최상위 `window.render(t)`가 `t`초 시점의 프레임을 처음부터 그린다 (CSS 애니메이션·rAF 루프·벽시계 금지)
- `render(t)` 끝에서 `window.__renderer.rendered(t)` 호출
- 길이는 `window.__renderer.duration`에서 읽는다
- 준비가 끝나면 `window.__renderer.ready = true`
- GSAP를 쓰면 paused 타임라인을 만들고 `render(t)`에서 `seek(t)`

## 실행

```bash
model-compose up
model-compose run main -i '{"prompt": "검은 배경 위로 \"MindrLabs\" 로고 타이포가 글자 단위로 떠오르고, 금색 라인이 밑줄을 긋는 인트로", "duration": 6, "frame_rate": 30}'
```

## 설정 포인트

| 항목 | 기본값 | 비고 |
| --- | --- | --- |
| `coder.model` | `Qwen/Qwen3-Coder-30B-A3B-Instruct` | 24GB GPU면 AWQ/FP8 양자화본이나 llamacpp 드라이버(GGUF)로 교체 |
| `author.max_iteration_count` | 3 | 모두 실패하면 loop가 `exceeded max_iteration_count` 에러로 종료 |
| `renderer.ready_timeout` | 20s | 깨진 스크립트는 `window.render` 미정의로 즉시 실패하므로 길게 잡을 필요 없음 |

## 요구 사항

- `html-frame-renderer`의 inline HTML 처리 수정(4096바이트 초과 inline HTML에서 `ENAMETOOLONG`)과 페이지 에러 수집이 포함된 버전
- vLLM virtualenv(`.venv/vllm`), Chromium(첫 실행 시 자동 설치), ffmpeg

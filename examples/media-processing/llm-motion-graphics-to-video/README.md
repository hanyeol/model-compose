# LLM Motion Graphics to Video

A local Qwen coder model writes an HTML motion-graphics page, `html-frame-renderer` captures its frames, and `video-encoder` writes the MP4. When a render fails, the page's own error message is fed back to the model so it can repair the page (renderer-in-the-loop).

## Flow

```
main (loop, up to 3 attempts)
 └─ attempt (workflow)
     generate  → coder          Qwen3-Coder writes the HTML (sees the previous HTML and error)
     extract   → html-extractor pulls the <html> document out of the reply; falls back to a page that throws
     render    → renderer       Playwright frame capture (streaming)
     encode    → encoder        MP4 encoding; on failure, on_error yields { ok: false, error }
 until: output.ok == true
```

Frames stream lazily, so page-load and render errors surface in the `encode` job, and `on_error` passes the message on as the next iteration's `previous_error`. A reply with no HTML takes the same retry path: the fallback page throws its own error.

## Page contract

The system prompt holds the model to the `html-frame-renderer` contract:

- A top-level `window.render(t)` draws the frame for time `t` from scratch (no CSS animations, rAF loops or wall-clock time)
- `render(t)` ends by calling `window.__renderer.rendered(t)`
- The length comes from `window.__renderer.duration`
- `window.__renderer.ready = true` once setup is done
- With GSAP: build a paused timeline and `seek(t)` inside `render(t)`

## Run

```bash
model-compose up
model-compose run main -i '{"prompt": "An intro where the word \"MindrLabs\" rises letter by letter over black, then a gold line underlines it", "duration": 6, "frame_rate": 30}'
```

## Knobs

| Setting | Default | Notes |
| --- | --- | --- |
| `coder.model` | `Qwen/Qwen3-Coder-30B-A3B-Instruct` | On a 24 GB GPU, swap in an AWQ/FP8 build or the llamacpp driver (GGUF) |
| `author.max_iteration_count` | 3 | If every attempt fails, the loop ends with `exceeded max_iteration_count` |
| `renderer.ready_timeout` | 20s | Crashed scripts fail immediately (no `window.render`), so this can stay short |

## Requirements

- A build that includes the `html-frame-renderer` fixes (inline HTML over 4096 bytes raised `ENAMETOOLONG`) and page-error capture
- A vLLM virtualenv (`.venv/vllm`), Chromium (installed on first start), ffmpeg

# LLM 动态图形 → 视频

本地 Qwen 代码模型编写 HTML 动态图形页面,`html-frame-renderer` 逐帧截取画面,`video-encoder` 输出 MP4。渲染失败时,会把页面自身的错误信息回传给模型,让它修复页面(renderer-in-the-loop)。

## 流程

```
main (loop,最多 3 次)
 └─ attempt (workflow)
     generate  → coder          Qwen3-Coder 编写 HTML(可见上一次的 HTML 与错误)
     extract   → html-extractor 从回复中提取 <html> 文档;无匹配则回落到会抛错的页面
     render    → renderer       Playwright 帧捕获(streaming)
     encode    → encoder        编码 MP4;失败时 on_error 产出 { ok: false, error }
 until: output.ok == true
```

帧是惰性流式产出的,因此页面加载与渲染错误会在 `encode` 作业中浮现,`on_error` 再把错误信息作为下一次迭代的 `previous_error` 传回去。回复中没有 HTML 时也走同一条重试路径:回落页面会主动抛出自己的错误。

## 页面契约

系统提示会强制模型遵循 `html-frame-renderer` 的契约:

- 顶层 `window.render(t)` 从零开始绘制时刻 `t` 的帧(禁止使用 CSS 动画、rAF 循环或墙上时钟)
- `render(t)` 结束时调用 `window.__renderer.rendered(t)`
- 总长度从 `window.__renderer.duration` 读取
- 初始化完成后设置 `window.__renderer.ready = true`
- 使用 GSAP 时:构建暂停的 timeline,并在 `render(t)` 中 `seek(t)`

## 运行

```bash
model-compose up
model-compose run main -i '{"prompt": "黑色背景上,\"MindrLabs\" 字样逐字浮现,随后金色线条在其下方划出下划线", "duration": 6, "frame_rate": 30}'
```

## 可调项

| 设置 | 默认值 | 备注 |
| --- | --- | --- |
| `coder.model` | `Qwen/Qwen3-Coder-30B-A3B-Instruct` | 24 GB 显卡可换成 AWQ/FP8 版本或 llamacpp 驱动(GGUF) |
| `author.max_iteration_count` | 3 | 全部失败时,loop 以 `exceeded max_iteration_count` 结束 |
| `renderer.ready_timeout` | 20s | 脚本崩溃时会立即失败(无 `window.render`),无需调大 |

## 依赖

- 包含 `html-frame-renderer` 修复(超过 4096 字节的内联 HTML 会抛 `ENAMETOOLONG`)与页面错误捕获的构建版本
- vLLM virtualenv(`.venv/vllm`)、Chromium(首次启动时自动安装)、ffmpeg

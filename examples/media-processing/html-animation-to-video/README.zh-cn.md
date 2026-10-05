# HTML 转视频（帧渲染）示例

通过串联 `html-frame-renderer` 和 `video-encoder` 组件，
将 HTML 动画渲染为 MP4 视频。

## 概述

`html-frame-renderer` 在无头 Chromium 中打开一个 HTML 页面，
并通过一个小的页面侧契约（顶层 `window.render(t)` 以及 `window.__renderer`
上的 `duration`）请求它逐帧绘制。引擎将 PNG 字节流式传输到
`video-encoder`，后者将其管道给 ffmpeg 进行 H.264 编码。

## 页面契约

页面定义顶层 `window.render(t)` 并在准备好捕获时翻转 `ready`。
总时长来自动作的 `duration:` 字段（见 `model-compose.yml`），
作为 `window.__renderer.duration` 注入：

```js
const duration = window.__renderer.duration;   // 来自动作的 `duration:`

window.render = (t) => {              // 每帧截图前调用一次
  // 将 DOM / canvas / 动画时间线更新到时间 t 的状态
};
window.__renderer.ready = true;       // 声明"已准备好开始捕获" —— 引擎只有
                                      // 在此标志变为 true 之后才开始渲染。
                                      // 如需异步准备（Web 字体、图片、
                                      // 纹理），请先 await 后再翻转标志。
```

引擎在任何页面脚本运行之前会预设两个字段：

- **`duration`** —— 从动作的 `duration:` 解析出的秒数。只读；可用于
  `t / duration` 的进度计算。
- **`props`** —— 由动作输入 `props:`（可选）设置。工作流传入的任何形状
  都将在页面上以 `window.__renderer.props` 呈现。

此示例在 `props` 中传入 `title:`，页面（`animation.html`）会将其渲染为
移动进度条上方的大居中标题。

## 准备工作

### 前置条件

- 已安装 model-compose
- `PATH` 中有 `ffmpeg`
- Playwright Chromium 浏览器：`playwright install chromium`

### 环境

```bash
cd examples/media-processing/html-animation-to-video
```

## 运行方式

1. **启动服务**
   ```bash
   model-compose up
   ```

2. **触发渲染**

   通过 http://localhost:8081 的 Gradio UI 或 HTTP：

   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H 'Content-Type: application/json' \
     -d '{"workflow_id": "render", "input": {"frame_rate": 30}}'
   ```

响应中包含生成的 `.mp4` 路径。

## 并行渲染

渲染器动作接受 `worker_count` 输入（默认 `1`）。每个 worker 打开自己的
Chromium 页面，从共享队列中拉取帧编号进行渲染；结果按编号重新排序后
以单调顺序流式送入编码器。对于本示例这类轻量级 canvas 动画效果有限，
但对于 `render(t)` 真正耗时的页面（WebGL 场景、复杂合成），
性能可以在几个 worker 范围内接近线性扩展。

```bash
curl -X POST http://localhost:8080/api/workflows/runs \
  -H 'Content-Type: application/json' \
  -d '{"workflow_id": "render", "input": {"frame_rate": 30, "worker_count": 4}}'
```

# HTML 转视频（帧渲染）示例

通过串联 `html-frame-renderer` 和 `video-encoder` 组件，
将 HTML 动画渲染为 MP4 视频。

## 概述

`html-frame-renderer` 在无头 Chromium 中打开一个 HTML 页面，
并通过 `window.__renderer` 上的页面侧契约请求它逐帧绘制。
引擎将 PNG 字节流式传输到 `video-encoder`，后者将其管道给 ffmpeg
进行 H.264 编码。

## `window.__renderer` 契约

页面在 `window.__renderer` 上暴露 `duration` 与 `seek(t)` 函数：

```js
window.__renderer = window.__renderer || {};
Object.assign(window.__renderer, {
  duration: 5.0,        // 合成的总时长（秒）—— 引擎会读取此值
                        // 以决定要捕获多少帧。
  seek(t) {             // 每帧截图前调用一次
    // 将 DOM / canvas / 动画时间线更新到时间 t 的状态
  },
});
```

引擎在任何页面脚本运行之前会预设一个字段：

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
     -d '{"workflow_id": "render", "input": {"fps": 30}}'
   ```

响应中包含生成的 `.mp4` 路径。

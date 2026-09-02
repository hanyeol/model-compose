# 音频频谱视频示例

将音频文件（mp3、wav 等）转换为均衡器风格的 MP4 视频，并将**原始音频重新混入**，
通过串联四个作业实现：

1. `fan-out`（`spool: true`）将一次性音频上传 tee 为两个独立分支 — 一个供
   频谱提取器使用，另一个供最终编码器使用。上传一次性落到 tempfile，两个
   分支各自按自己的节奏打开文件：编码器分支要等频谱 → 帧渲染管道结束
   才开始消费，普通内存 fan-out 队列无法在这段时间里保留它。两个分支都
   关闭后 tempfile 被删除。
2. `audio-feature-extractor` 读取 `for-spectrum` 分支并产出每帧的频率频谱
   （`frames[frame_count][band_count]`，值在 `[0, 1]`）。
3. `html-frame-renderer` 打开一个小 HTML 页面，从
   `window.__renderer.props.spectrum` 读取频谱，并在画布上为每帧绘制柱形。
4. `video-encoder` 将渲染后的帧通过 ffmpeg 管道进行 H.264 编码，
   并将 `for-encode` 音频分支作为音频轨混入。

## `window.__renderer` 契约

页面在 `window.__renderer` 上暴露 `duration` 与 `seek(t)`。
引擎读取 `duration` 以决定要捕获多少帧，然后每帧调用一次 `seek(t)`
并在每次调用后截图。

```js
window.__renderer = window.__renderer || {};
Object.assign(window.__renderer, {
  duration: totalSeconds,
  seek(t) {
    // 在页面画布上绘制时间 t 的帧
  },
});
```

引擎在任何页面脚本运行之前，会根据动作的 `props:` 输入预设
`window.__renderer.props`。此示例中，工作流传入了完整的频谱结果：

```js
window.__renderer.props.spectrum = {
  frames: [[...], [...], ...],  // 每帧的频段振幅，范围 [0, 1]
  fps: 30,
  band_count: 48,
  frame_count: N,
  duration: seconds,
  sample_rate: 22050,
};
```

`animation.html` 为渲染时间 `t` 选取最接近的源帧，
并为每个频段绘制一个色调偏移的竖直柱形。

## 准备工作

### 前置条件

- 已安装 model-compose
- `PATH` 中有 `ffmpeg`
- Playwright Chromium 浏览器：`playwright install chromium`

### 环境

```bash
cd examples/media-processing/audio-spectrum-to-video
```

准备一个音频文件（mp3、wav、flac、ogg、opus 或 aac）。

## 运行方式

1. **启动服务**
   ```bash
   model-compose up
   ```

2. **触发渲染**

   通过 http://localhost:8081 的 Gradio UI 或 HTTP：

   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F 'workflow_id=render' \
     -F 'input.audio=@./song.mp3' \
     -F 'input.fps=30' \
     -F 'input.band_count=48'
   ```

响应中包含生成的 `.mp4` 路径。

# TikTok 下载器（基于已登录会话）

使用本地运行的 Chrome 浏览器的会话 Cookie 下载 TikTok 视频。适用于
地区限制、年龄限制或需要“登录以继续”的视频等 yt-dlp 单独无法访问的
内容；公开视频在 cookies 字段为空时也能正常工作。

## 概览

两个组件协同工作：

1. **`browser` (`web-browser` / `chrome`)** — 附加到用户以
   `--remote-debugging-port=9222` 启动的 Chrome 实例。你只需在该窗口
   中登录一次 TikTok,工作流就能读取到会话 Cookie。
2. **`downloader` (`media-downloader` / `ytdlp`)** — 直接接收 Cookie
   列表并交给 yt-dlp,用已登录的会话下载视频。

`web-browser` 的 `get-cookies` 返回的 Cookie 结构与 `media-downloader`
所期望的完全一致，因此可以直接串联，无需任何转换步骤。

## 准备

### 前置条件

- 已安装 model-compose 并加入 PATH
- 已安装 Google Chrome（或 Chromium）
- `yt-dlp` — 首次运行时通过驱动的 setup requirement 自动安装
- `ffmpeg` 位于 PATH（音频提取以及分离视频/音频流的合并都需要它）

### 以远程调试模式启动 Chrome

使用独立的用户目录，避免与日常浏览器会话冲突：

**macOS**
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chrome-tiktok-profile
```

**Linux**
```bash
google-chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chrome-tiktok-profile
```

**Windows (PowerShell)**
```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-port=9222 `
  --user-data-dir=$env:TEMP\chrome-tiktok-profile
```

保持该窗口打开。一旦在其中登录 TikTok，会话就会在多次工作流运行之间
持续（直到清除该用户目录或 TikTok 让 Cookie 过期）。

## 运行方式

1. **启动控制器：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **通过 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{
       "workflow_id": "download-tiktok-video",
       "input": {
         "url": "https://www.tiktok.com/@scout2015/video/6718335390845095173"
       }
     }'
   ```

   **通过 Web UI：**
   - 打开 http://localhost:8081
   - 输入视频 URL（可选：`format`）
   - 点击 Run

   **通过 CLI：**
   ```bash
   model-compose run download-tiktok-video \
     --input '{"url": "https://www.tiktok.com/@scout2015/video/6718335390845095173"}'
   ```

3. **当工作流暂停时：**
   - `check-signin` 任务检查页面中是否存在个人资料图标。如果不存在
     （未登录），`wait-for-signin` 任务会在执行前触发中断。
   - 切换到 attach 在 localhost:9222 的 Chrome 窗口，登录 TikTok,
     然后在 Web UI 点击 Resume，或通过 API 发送 resume 请求。
   - 之后工作流会等到个人资料图标出现，再收集 Cookie 并交给 yt-dlp。
   - 当 Chrome 已经有有效的 TikTok 会话时（首次运行之后通常如此），
     `check-signin` 返回 true，中断会被完全跳过。

4. **停止控制器：**
   ```bash
   model-compose down
   ```

## 工作流详情

### "Download a TikTok video" 工作流

**描述**：仅在需要时通过 attach 的 Chrome 登录 TikTok,将获得的会话
Cookie 交给 yt-dlp,下载请求的视频。

#### 任务流程

```mermaid
graph TD
    J1((open-tiktok))
    J2((check-signin))
    J3((wait-for-signin))
    J4((collect-cookies))
    J5((download))
    B[browser<br/>component]
    D[downloader<br/>component]

    Input((Input)) --> J1
    J1 -.-> B
    B -.-> J1
    J1 --> J2
    J2 -.-> B
    B -.-> J2
    J2 --> J3
    J3 -. "check-signin == false → interrupt" .-> Human((Human))
    Human -.-> J3
    J3 -.-> B
    B -.-> J3
    J3 --> J4
    J4 -.-> B
    B -.-> J4
    J4 --> J5
    J5 -.-> D
    D -.-> J5
    J5 --> Output((Output))
```

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `url` | string | 是 | — | TikTok 视频 URL |
| `format` | string \| object | 否 | `mp4` | media-downloader 的 `format`：preset（`mp4`、`webm`、`mkv`、`mp3` 等）、原生 yt-dlp 表达式，或结构化 spec。 |

#### 输出格式

| 字段 | 类型 | 说明 |
|-------|------|-------------|
| `video` | video stream | 下载后的视频文件，以流形式返回 |

Web UI 会嵌入播放器直接播放；HTTP API 会以正确的 content type 返回
数据流。

## 组件详情

### `browser` — web-browser（通过 CDP 连接 Chrome）

通过 Chrome DevTools Protocol 附加到 `localhost:9222`。model-compose
不会主动启动浏览器 — 用户拥有该浏览器进程，因此可以手动完成登录、
SMS/邮箱验证和 CAPTCHA。

动作：

| 动作 | 方法 | 说明 |
|--------|--------|-------------|
| `navigate` | `navigate` | 打开 URL 并等待 DOM 解析完成 |
| `check-signin` | `evaluate` | 最多 5 秒轮询页面，若存在个人资料图标则返回 `true` |
| `wait-for-profile-icon` | `wait-for` | 等待 TikTok 个人资料图标可见（最多 5 分钟） |
| `get-tiktok-cookies` | `get-cookies` | 返回作用域为 `tiktok.com` 的 Cookie |

### `downloader` — media-downloader（yt-dlp）

使用从浏览器获取的 Cookie 运行 yt-dlp。yt-dlp 会将这些 Cookie 写入
临时 Netscape 格式的 Cookie 文件，保留每条 Cookie 的 domain、path、
secure 标志和过期时间，从而让对 `tiktok.com` 的已登录请求与浏览器
中完全一致地成功。

## 关于 Cookie 的说明

`web-browser` 的 `get-cookies` 返回的 Cookie 对象 — 包含 `name`、
`value`、`domain`、`path`、`secure`、`expires` 等字段 — 就是
`media-downloader` 的 `cookies` 字段所接受的形状。这与 Chrome
DevTools Protocol 和 Playwright 使用的结构一致，因此其他 Cookie 来源
（存储的固件、通过 `set-cookies` 注入的种子等）也可以用相同方式接入
downloader。

如果不需要认证（公开视频），可以删除前四个任务，并给 `download` 传入
空的 `cookies` 字段 — 或直接使用独立示例
`media-processing/media-downloader`。

## 关于水印的说明

yt-dlp 默认返回带水印的 Web 流 — 即 tiktok.com 上播放的样子，视频
中带有用户账号水印。[model-compose.yml](model-compose.yml) 中的
`downloader` 组件带有一段被注释掉的 `extractor_args` 块：开启后会
通过 TikTok 的移动端 API 主机请求元数据，从而获得无水印 URL。请
仅在你拥有相应内容权利时取消注释：在某些司法辖区，抓取无水印流可能
与 TikTok 服务条款冲突；并且该 API 主机名偶尔会变更（启用后若下载
开始失败，请查阅 yt-dlp TikTok extractor 源码获取当前值）。

## 故障排查

- **`wait-for-profile-icon` 超时**：附加的 Chrome 窗口可能未处于
  TikTok 页面，或未登录。请在该窗口中打开 https://www.tiktok.com/ ，
  登录后重新运行工作流。
- **CDP 连接被拒绝**：Chrome 未以 `--remote-debugging-port=9222` 启动，
  或该端口已被其他进程占用。可用 `lsof -i :9222` 检查。
- **`Unable to find video in feed` / extractor HTTP 403**：TikTok 对
  请求进行了限流或地域封锁。请确认 Chrome 用户目录中登录的账户位于
  支持的地区，或在附加的浏览器中启用 VPN 后重试。
- **下载成功但视频带水印**：这是默认行为。请参阅上文“关于水印的
  说明”。
- **下载完成后 Web UI 播放器很久才出现**：当源视频为 HEVC 或 VP9 时，
  Gradio 会将其转码为浏览器兼容的编码。若无法接受等待时间，可将
  download 动作的 `format` 覆写为结构化 spec 以优先选择 H.264
  （例如 `{ media: video, container: mp4, codec: avc1 }`）。

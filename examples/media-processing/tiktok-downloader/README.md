# TikTok Downloader (Authenticated)

Download a TikTok video (or its audio track) using the session cookies
of a locally-attached Chrome browser. Use this when a video is
region-restricted, age-gated, or hidden behind a "log in to continue"
wall; public clips also work when you leave the cookie field empty.

## Overview

Two components cooperate:

1. **`browser` (`web-browser` / `chrome`)** — attaches to a Chrome you
   launched with `--remote-debugging-port=9222`. You sign into TikTok
   once in that window; the workflow then reads back the cookies
   TikTok set for your session.
2. **`downloader` (`media-downloader` / `ytdlp`)** — receives those
   cookies as a list and hands them to yt-dlp, which downloads the
   video (or audio) using your authenticated session.

The cookie format returned by `web-browser`'s `get-cookies` is the
same shape `media-downloader` expects, so you can wire one directly
into the other without any conversion step.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Google Chrome (or Chromium) installed
- `yt-dlp` — installed automatically on first run via the driver's
  setup requirements
- `ffmpeg` on your PATH (required for audio extraction and for merging
  separate video/audio streams)

### Launch Chrome with remote debugging

Start Chrome in a dedicated profile so it doesn't collide with your
day-to-day browser session:

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

Leave that window open. Once you sign into TikTok in it, the session
persists across workflow runs (until you clear the profile or TikTok
expires the cookies).

## How to Run

1. **Start the controller:**
   ```bash
   model-compose up
   ```

2. **Run a workflow:**

   **Using API:**
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

   **Using Web UI:**
   - Open http://localhost:8081
   - Enter the video URL and (optionally) `format`
   - Click Run

   **Using CLI:**
   ```bash
   model-compose run download-tiktok-video \
     --input '{"url": "https://www.tiktok.com/@scout2015/video/6718335390845095173"}'
   ```

3. **If the workflow pauses:**
   - The `check-signin` job probes the page for the profile icon. If
     it's not there (no signed-in session), `wait-for-signin`
     interrupts before it runs.
   - Switch to the Chrome window at localhost:9222, sign into TikTok,
     then click Resume in the Web UI or send a resume request via
     the API.
   - The workflow then waits for the profile icon to appear before
     collecting cookies and handing off to yt-dlp.
   - When Chrome already has a valid TikTok session (typical after
     the first run), `check-signin` returns true and the interrupt is
     skipped entirely.

4. **Stop the controller:**
   ```bash
   model-compose down
   ```

## Workflow Details

### "Download a TikTok video" Workflow

**Description**: Sign into TikTok in the attached Chrome (only if the
session isn't already warm), hand the resulting session cookies to
yt-dlp, and download the requested video.

#### Job Flow

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

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | Yes | — | TikTok video URL |
| `format` | string \| object | No | `mp4` | Media downloader `format`: preset (`mp4`, `webm`, `mkv`, `mp3`, ...), raw yt-dlp expression, or structured spec. |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `video` | video stream | Downloaded video file, streamed back |

The Web UI renders an inline player; the HTTP API returns the stream
with the correct content type.

## Component Details

### `browser` — web-browser (Chrome via CDP)

Attaches to Chrome over the DevTools Protocol at `localhost:9222`. No
browser is launched by model-compose — you own the browser process,
which is what lets you complete sign-in, SMS/email verification, and
any CAPTCHA challenges manually.

Actions:

| Action | Method | Description |
|--------|--------|-------------|
| `navigate` | `navigate` | Open a URL and wait until the DOM is parsed |
| `check-signin` | `evaluate` | Poll the page for up to 5 seconds and return `true` if the profile icon is present |
| `wait-for-profile-icon` | `wait-for` | Wait until the TikTok profile icon becomes visible (up to 5 minutes) |
| `get-tiktok-cookies` | `get-cookies` | Return cookies scoped to `tiktok.com` |

### `downloader` — media-downloader (yt-dlp)

Runs yt-dlp with the cookies received from the browser. yt-dlp writes
them into a temporary Netscape cookie file, preserving each cookie's
domain, path, secure flag, and expiry, so authenticated requests to
`tiktok.com` succeed exactly as they would from the browser.

## Notes on Cookies

The cookie objects returned by `web-browser`'s `get-cookies` — with
`name`, `value`, `domain`, `path`, `secure`, `expires`, etc. — are
what `media-downloader` accepts directly on its `cookies` field. This
is the same shape the Chrome DevTools Protocol and Playwright use, so
you can chain other cookie sources (a stored fixture, a
`set-cookies`-style seed) into the downloader in the same way.

If you don't need authentication (public videos), you can drop the
first four jobs and call `download` with an empty `cookies` field —
or just use the standalone `media-processing/media-downloader`
example.

## Notes on Watermarks

By default yt-dlp returns the watermarked web stream — the clip you
see on tiktok.com with the user's handle burned in. The
`downloader` component in [model-compose.yml](model-compose.yml) ships
with a commented-out `extractor_args` block that routes the metadata
request through TikTok's mobile API host, which returns a clean
no-watermark URL. Uncomment it only when you have the rights to the
content: scraping the no-watermark stream may conflict with TikTok's
Terms of Service in some jurisdictions, and the API host name
occasionally changes (if downloads start failing after enabling it,
check the yt-dlp TikTok extractor source for the current value).

## Troubleshooting

- **`wait-for-profile-icon` times out**: The Chrome window may not
  actually be at TikTok, or you're not signed in. Navigate to
  https://www.tiktok.com/ in the attached window, sign in, then
  retry the workflow.
- **CDP connection refused**: Chrome wasn't launched with
  `--remote-debugging-port=9222`, or another process is using the
  port. Check with `lsof -i :9222`.
- **`Unable to find video in feed` / HTTP 403 from the extractor**:
  TikTok is rate-limiting or geoblocking the request. Make sure the
  Chrome profile is signed into an account in a supported region, or
  retry with a VPN active in the attached browser.
- **Download succeeds but the clip has a watermark**: Expected
  default. See the "Notes on Watermarks" section above.
- **Web UI player takes a long time to appear after download**: Gradio
  transcodes the file to a browser-compatible codec when the source
  is HEVC or VP9. If the wait is unacceptable, pass a structured
  `format` on the download action to prefer H.264 (e.g. `{ media:
  video, container: mp4, codec: avc1 }`).

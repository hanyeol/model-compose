# Web Browser Component

The web browser component provides full browser automation with pluggable drivers. It supports navigation, clicking, text input, screenshots, JavaScript evaluation, element extraction, cookie management, scrolling, and waiting for elements.

## Basic Configuration

```yaml
component:
  type: web-browser
  driver: chrome
  host: localhost
  port: 9222
  timeout: 30s
  action:
    method: navigate
    url: https://example.com
    wait_until: load
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `web-browser` |
| `driver` | string | `chrome` | Browser driver: `chrome`, `playwright` |
| `timeout` | string | `30s` | Default timeout for all actions |
| `actions` | array | `[]` | List of browser actions |

### Driver Types

#### Chrome Driver

Connects to a running Chrome/Chromium instance via the Chrome DevTools Protocol.

```yaml
component:
  type: web-browser
  driver: chrome
  host: localhost
  port: 9222
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `driver` | string | `chrome` | Must be `chrome` |
| `endpoint` | string | `null` | Full WebSocket debugger URL (e.g. `ws://localhost:9222/devtools/page/<id>`). If set, `host`/`port` are ignored |
| `host` | string | `localhost` | Host where Chrome remote debugging port is exposed |
| `port` | integer | `9222` | Chrome remote debugging port |
| `target_index` | integer | `0` | Index of the browser target to attach to when auto-discovering via `host`/`port` |

#### Playwright Driver

Launches a browser instance using Playwright, or attaches to a browser you already started.

```yaml
component:
  type: web-browser
  driver: playwright
  browser: chromium
  headless: true
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `driver` | string | **required** | Must be `playwright` |
| `browser` | string | `chromium` | Browser engine: `chromium`, `firefox`, `webkit` |
| `channel` | string | `null` | Use a system-installed browser channel instead of the bundled Chromium: `chrome`, `chrome-beta`, `chrome-dev`, `chrome-canary`, `msedge`, `msedge-beta`, `msedge-dev`. Only valid when `browser=chromium` |
| `headless` | boolean | `true` | Whether to run the browser in headless mode. Ignored when `cdp_url` is set |
| `args` | array | `[]` | Additional command-line arguments passed to the browser process |
| `persistent_dir` | string | `null` | Reuse a persistent browser profile at this path (cookies, extensions, settings). Ignored when `cdp_url` is set |
| `cdp_url` | string | `null` | Attach to an already-running Chromium via CDP (e.g. `http://localhost:9222`). When set, `browser`, `channel`, `headless`, `args`, and `persistent_dir` must be left at their defaults |

**Launch modes.** The three fields above select between three launch strategies:

- **Fresh launch (default).** Playwright starts its bundled Chromium (or the system channel if `channel` is set). Each session is isolated.
- **Persistent profile (`persistent_dir`).** Playwright launches a browser that stores cookies, local storage, and extensions in the given directory, so state persists across runs. Useful for sites where you want to keep browser-level settings but not for Google login (see below).
- **Attach over CDP (`cdp_url`).** Playwright connects to a Chromium that you started yourself with `--remote-debugging-port=<n>`. This is the recommended path for sites that block automated logins (notably Google/YouTube), because the login itself happens in an ordinary Chrome session where you sign in by hand; Playwright only takes over afterwards. Since the browser was not launched by Playwright, all `launch`-related options are rejected in this mode.

**Bypassing Google's login block.** Google detects Playwright-launched browsers and shows "This browser or app may not be secure." The reliable workaround is `cdp_url`:

```bash
# 1. Start Chrome yourself with a dedicated profile and remote debugging.
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir=$HOME/.model-compose/chrome-profile

# 2. Sign in to the target site by hand in that Chrome window.
# 3. Leave the window open and run model-compose against it:
```

```yaml
component:
  type: web-browser
  driver: playwright
  cdp_url: http://localhost:9222
```

### Common Action Configuration

All web browser actions share these common settings:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Action method: `navigate`, `click`, `input-text`, `screenshot`, `evaluate`, `wait-for`, `extract`, `get-cookies`, `set-cookies`, `scroll`, `capture-video` |
| `timeout` | string | `null` | Per-action timeout override. Falls back to component-level timeout |
| `output` | string | `null` | Output variable mapping |

## Action Methods

### Navigate

Navigate to a URL and wait for a page lifecycle event:

```yaml
component:
  type: web-browser
  action:
    method: navigate
    url: https://example.com
    wait_until: load
```

**Navigate Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string | **required** | URL to navigate to |
| `wait_until` | string | `load` | Event to wait for: `load`, `domcontentloaded`, `networkidle`, `commit` |

**Returns:** `{ "url": "...", "frameId": "..." }`

### Click

Click an element by CSS selector, XPath, or coordinates:

```yaml
component:
  type: web-browser
  action:
    method: click
    selector: "button#submit"
```

**Click Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `selector` | string | `null` | CSS selector of the element to click |
| `xpath` | string | `null` | XPath of the element to click |
| `x` | integer | `null` | Absolute X coordinate for direct mouse click |
| `y` | integer | `null` | Absolute Y coordinate for direct mouse click |

> Exactly one of `selector`, `xpath`, or `x`+`y` must be provided.

**Returns:** `{ "x": 100, "y": 200 }`

### Input Text

Type text into an input element:

```yaml
component:
  type: web-browser
  action:
    method: input-text
    selector: "input[name='search']"
    text: "hello world"
    clear_first: true
```

**Input Text Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `selector` | string | `null` | CSS selector of the target input |
| `xpath` | string | `null` | XPath of the target input |
| `text` | string | **required** | Text to type into the element |
| `clear_first` | boolean | `true` | Clear existing content before typing |

> Either `selector` or `xpath` must be provided (not both).

**Returns:** `{ "typed": "hello world" }`

### Screenshot

Capture a screenshot of the page or a specific element:

```yaml
component:
  type: web-browser
  action:
    method: screenshot
    full_page: true
    format: png
```

**Screenshot Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `full_page` | boolean | `false` | Capture the full scrollable page |
| `selector` | string | `null` | CSS selector to capture only a specific element |
| `format` | string | `png` | Image format: `png` or `jpeg` |
| `quality` | integer | `null` | JPEG quality (0-100). Only applicable when `format=jpeg` |

**Returns:** base64-encoded image string

### Evaluate

Execute JavaScript in the page context:

```yaml
component:
  type: web-browser
  action:
    method: evaluate
    expression: "document.title"
```

**Evaluate Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `expression` | string | **required** | JavaScript expression to evaluate |

**Returns:** the evaluated JavaScript value

### Wait For

Wait for an element to appear, become visible, or become hidden:

```yaml
component:
  type: web-browser
  action:
    method: wait-for
    selector: ".results-loaded"
    condition: visible
    timeout: 10s
```

**Wait For Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `selector` | string | `null` | CSS selector to wait for |
| `xpath` | string | `null` | XPath to wait for |
| `condition` | string | `present` | Condition: `present`, `visible`, `hidden` |

> Either `selector` or `xpath` must be provided (not both).

**Returns:** `{ "found": true }`

### Extract

Extract text, HTML, or attributes from page elements:

```yaml
component:
  type: web-browser
  action:
    method: extract
    selector: ".article-body"
    extract_mode: text
```

**Extract Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `selector` | string | `null` | CSS selector |
| `xpath` | string | `null` | XPath expression |
| `extract_mode` | string | `text` | Extraction mode: `text`, `html`, `attribute` |
| `attribute` | string | `null` | Attribute name (required when `extract_mode=attribute`) |
| `multiple` | boolean | `false` | Return all matches as a list |

> Either `selector` or `xpath` must be provided (not both).

**Returns:** extracted string (or list of strings when `multiple=true`)

### Get Cookies

Retrieve cookies from the browser:

```yaml
component:
  type: web-browser
  action:
    method: get-cookies
```

**Get Cookies Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `urls` | array | `null` | Restrict returned cookies to these URLs. If omitted, returns all cookies |

**Returns:** list of cookie objects

### Set Cookies

Set cookies in the browser:

```yaml
component:
  type: web-browser
  action:
    method: set-cookies
    cookies:
      - name: session
        value: abc123
        domain: example.com
```

**Set Cookies Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `cookies` | array | **required** | List of cookie dicts (`name`, `value`, `domain`, `path`, ...) |

**Returns:** `{ "set": <count> }`

### Scroll

Scroll the page or a specific element. The behavior depends on the combination of parameters:

- **No selector/xpath**: Scrolls the page by `x` and `y` pixels (`window.scrollBy`)
- **selector/xpath without x/y**: Scrolls the element into view (`scrollIntoView`)
- **selector/xpath with x/y**: Scrolls the element's internal content (`element.scrollBy`)

**Page scroll:**

```yaml
component:
  type: web-browser
  action:
    method: scroll
    y: 500
```

**Scroll element into view:**

```yaml
component:
  type: web-browser
  action:
    method: scroll
    selector: "#target-section"
```

**Scroll element's internal content:**

```yaml
component:
  type: web-browser
  action:
    method: scroll
    selector: ".scrollable-container"
    y: 300
```

**Scroll Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `selector` | string | `null` | CSS selector of the target element |
| `xpath` | string | `null` | XPath of the target element |
| `x` | integer | `null` | Horizontal scroll amount in pixels |
| `y` | integer | `null` | Vertical scroll amount in pixels |

> Only one of `selector` or `xpath` can be provided.

**Returns:** `{ "scrolled_x": 0, "scrolled_y": 500 }`

### Capture Video

Capture video (and audio) from a `<video>` element on the page and stream it out as encoded chunks. Uses `HTMLMediaElement.captureStream()` + `MediaRecorder` inside the browser, so no OS-level screen-recording permission is needed.

```yaml
component:
  type: web-browser
  driver: playwright
  cdp_url: http://localhost:9222
  action:
    method: capture-video
    url: https://www.youtube.com/watch?v=...
    duration: 30s
    encoding:
      format: webm
      video: { codec: vp9, bitrate: 3M }
      audio: { codec: opus, bitrate: 128k }
```

**Capture Video Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string | `null` | URL to navigate to before capturing. If omitted, captures the current page |
| `selector` | string | `null` | CSS selector for the `<video>` element to capture. If omitted, the first `<video>` on the page is used |
| `include_video_track` | boolean | `true` | Include the video track in the capture |
| `include_audio_track` | boolean | `true` | Include the audio track in the capture |
| `encoding` | object | `null` | Video/audio encoding settings (see below). If omitted, the browser picks defaults (typically VP8+Opus in WebM) |
| `duration` | string | `null` | Total capture duration (e.g. `30s`). If omitted, capture runs until the workflow tears the action down |

**Encoding Configuration (`encoding`):**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `format` | string | `null` | Container format: `webm`, `mp4` |
| `video.codec` | string | `null` | Video codec (e.g. `vp9`, `vp8`, `h264`) |
| `video.bitrate` | string | `null` | Video bitrate (e.g. `3M`, `500k`) |
| `audio.codec` | string | `null` | Audio codec (e.g. `opus`) |
| `audio.bitrate` | string | `null` | Audio bitrate (e.g. `128k`) |

The `format` + codecs are combined into a `MediaRecorder` `mimeType` (e.g. `video/webm;codecs=vp9,opus`), and bitrates map to `videoBitsPerSecond` / `audioBitsPerSecond`. If a codec is omitted, the browser's default for that container is used, which typically lets it pick a hardware-accelerated path.

**Returns:** an async stream of encoded chunks (`bytes`). Chunks are self-contained WebM/MP4 fragments in emission order; consume them sequentially and concatenate to reconstruct the media. Downstream jobs can pipe the stream into `video-converter` for remuxing or transcoding.

**Notes and caveats:**

- **Login-gated sources.** For sites that block automated logins (YouTube, Gmail, etc.), use the Playwright `cdp_url` mode described above. Attempting to log in from a Playwright-launched browser will fail.
- **Playback must be running.** Capture starts from the moment `MediaRecorder.start()` is called; the `<video>` element must actually be playing. Sites with autoplay restrictions may need a `click` action first to start playback.
- **Ads and interstitials cause gaps.** Non-logged-in captures often include ad breaks that interrupt the media stream. Capturing while signed in via `cdp_url` avoids most of this.
- **Container/codec pairing.** `MediaRecorder` only accepts combinations the browser knows how to produce (e.g. WebM with VP8/VP9/Opus). Requesting an unsupported combination raises an error inside the page.

## Multiple Actions Configuration

Define multiple browser actions in a single component:

```yaml
component:
  type: web-browser
  driver: chrome
  host: localhost
  port: 9222
  timeout: 30s
  actions:
    - id: navigate
      method: navigate
      url: "${input.url}"
      wait_until: networkidle

    - id: click
      method: click
      selector: "${input.selector}"

    - id: type-text
      method: input-text
      selector: "${input.selector}"
      text: "${input.text}"

    - id: screenshot
      method: screenshot
      full_page: false
      format: png

    - id: extract-text
      method: extract
      selector: "${input.selector}"
      extract_mode: text
```

## Usage Examples

### Simple Page Navigation and Extraction

```yaml
component:
  type: web-browser
  driver: chrome
  host: localhost
  port: 9222
  actions:
    - id: go
      method: navigate
      url: "https://example.com"
      wait_until: load

    - id: get-title
      method: evaluate
      expression: "document.title"
      output:
        title: ${result}
```

### Form Login

```yaml
component:
  type: web-browser
  driver: chrome
  host: localhost
  port: 9222
  timeout: 30s
  actions:
    - id: navigate
      method: navigate
      url: "${input.login_url}"
      wait_until: networkidle

    - id: fill-username
      method: input-text
      selector: "input[name='username']"
      text: "${input.username}"

    - id: fill-password
      method: input-text
      selector: "input[name='password']"
      text: "${input.password}"

    - id: submit
      method: click
      selector: "button[type='submit']"
```

### CAPTCHA Detection with JavaScript

```yaml
component:
  type: web-browser
  driver: chrome
  host: localhost
  port: 9222
  actions:
    - id: check-captcha
      method: evaluate
      expression: >
        !!(document.querySelector('[id*=captcha],[class*=captcha]')
          || document.querySelector('iframe[src*=captcha]')
          || document.querySelector('#cf-challenge-running'))
```

### Element Extraction with XPath

```yaml
component:
  type: web-browser
  driver: chrome
  host: localhost
  port: 9222
  actions:
    - id: extract-links
      method: extract
      xpath: "//a[@class='product-link']"
      extract_mode: attribute
      attribute: href
      multiple: true
      output:
        links: ${result}
```

### Full Page Screenshot

```yaml
component:
  type: web-browser
  driver: chrome
  host: localhost
  port: 9222
  actions:
    - id: capture
      method: screenshot
      full_page: true
      format: jpeg
      quality: 80
      output:
        image: ${result}
```

### Cookie Management

```yaml
component:
  type: web-browser
  driver: chrome
  host: localhost
  port: 9222
  actions:
    - id: inject-cookies
      method: set-cookies
      cookies:
        - name: session_id
          value: "${input.session}"
          domain: example.com
          path: /

    - id: read-cookies
      method: get-cookies
      urls:
        - "https://example.com"
      output:
        cookies: ${result}
```

## Integration with Workflows

### Scrape with CAPTCHA Human Fallback

```yaml
workflows:
  - id: scrape-with-fallback
    jobs:
      - id: navigate
        component: browser
        action: navigate
        input:
          url: ${input.url}

      - id: detect-captcha
        component: browser
        action: check-captcha
        interrupt:
          after:
            condition:
              operator: eq
              input: ${output}
              value: true
            message: >
              CAPTCHA detected! Please solve it via noVNC at:
              http://localhost:6080/vnc.html
        depends_on: [ navigate ]

      - id: extract
        component: browser
        action: extract-text
        input:
          selector: ${input.selector}
        depends_on: [ detect-captcha ]

components:
  - id: browser
    type: web-browser
    driver: chrome
    host: localhost
    port: 9222
    timeout: 30s
    actions:
      - id: navigate
        method: navigate
        url: "${input.url}"
        wait_until: networkidle

      - id: check-captcha
        method: evaluate
        expression: >
          !!(document.querySelector('[id*=captcha],[class*=captcha]')
            || document.querySelector('iframe[src*=captcha]'))

      - id: extract-text
        method: extract
        selector: "${input.selector}"
        extract_mode: text
```

### Login and Scrape Protected Content

```yaml
workflows:
  - id: login-and-scrape
    jobs:
      - id: open-login
        component: browser
        action: navigate
        input:
          url: ${input.login_url}

      - id: fill-username
        component: browser
        action: type-text
        input:
          selector: "input[name='username']"
          text: ${input.username}
        depends_on: [ open-login ]

      - id: fill-password
        component: browser
        action: type-text
        input:
          selector: "input[name='password']"
          text: ${input.password}
        depends_on: [ fill-username ]

      - id: submit
        component: browser
        action: click
        input:
          selector: "button[type='submit']"
        depends_on: [ fill-password ]

      - id: navigate-content
        component: browser
        action: navigate
        input:
          url: ${input.content_url}
        depends_on: [ submit ]

      - id: extract-content
        component: browser
        action: extract-text
        input:
          selector: ${input.selector}
        depends_on: [ navigate-content ]
        output:
          content: ${output as text}

components:
  - id: browser
    type: web-browser
    driver: chrome
    host: localhost
    port: 9222
    timeout: 30s
    actions:
      - id: navigate
        method: navigate
        url: "${input.url}"
        wait_until: networkidle

      - id: type-text
        method: input-text
        selector: "${input.selector}"
        text: "${input.text}"

      - id: click
        method: click
        selector: "${input.selector}"

      - id: extract-text
        method: extract
        selector: "${input.selector}"
        extract_mode: text
```

## Chrome Connection

When using the chrome driver, the component connects to a running Chrome/Chromium instance via the Chrome DevTools Protocol. Chrome must be started with remote debugging enabled:

```bash
# Start Chrome with remote debugging
google-chrome --remote-debugging-port=9222 --headless --no-sandbox

# Or using Docker
docker run -d -p 9222:9222 -p 6080:6080 \
  chromedp/headless-shell:latest
```

### Connection Methods

**Auto-discovery (default):**
The component queries `http://<host>:<port>/json` to discover browser targets and connects via WebSocket.

```yaml
component:
  type: web-browser
  driver: chrome
  host: localhost
  port: 9222
```

**Direct WebSocket URL:**
Skip auto-discovery by providing the full WebSocket URL.

```yaml
component:
  type: web-browser
  driver: chrome
  endpoint: "ws://localhost:9222/devtools/page/ABC123"
```

## Timeout Configuration

### Component-Level Timeout

Apply to all actions:

```yaml
component:
  type: web-browser
  timeout: 30s
  actions:
    - id: navigate
      method: navigate
      url: "https://example.com"

    - id: extract
      method: extract
      selector: ".content"
```

### Action-Level Timeout

Override for specific actions:

```yaml
component:
  type: web-browser
  timeout: 30s
  actions:
    - id: quick-check
      method: evaluate
      expression: "document.readyState"
      timeout: 5s

    - id: slow-navigation
      method: navigate
      url: "https://slow-site.example.com"
      wait_until: networkidle
      timeout: 120s
```

## Human-in-the-Loop with noVNC

For human-in-the-loop workflows (e.g., CAPTCHA resolution), use the workflow `interrupt` feature with `metadata` to provide the noVNC URL. This keeps the VNC connection details in the workflow definition where the interrupt occurs, rather than in the component configuration.

```yaml
jobs:
  - id: detect-captcha
    component: browser
    action: check-captcha
    interrupt:
      after:
        condition:
          operator: eq
          input: ${job.output}
          value: true
        message: "CAPTCHA detected! Please solve it via noVNC."
        metadata:
          novnc_url: "http://localhost:6080/vnc.html"
```

The `metadata` is included in the interrupt response, allowing UIs to show a direct link to the browser session.

## Variable Interpolation

Web browser actions support dynamic configuration:

```yaml
component:
  type: web-browser
  action:
    method: ${input.action_method | "navigate"}
    url: ${input.target_url}
    selector: ${input.css_selector}
    text: ${input.text_to_type}
    wait_until: ${input.wait_event | "load"}
    timeout: ${input.timeout | "30s"}
```

## Best Practices

1. **Use `networkidle` for SPAs**: For single-page applications, use `wait_until: networkidle` to ensure content is fully loaded
2. **Prefer CSS Selectors**: CSS selectors are generally faster than XPath expressions
3. **Set Appropriate Timeouts**: Increase timeout for slow pages, reduce for quick checks
4. **Use `wait-for` Before Extraction**: Wait for dynamic content to render before extracting
5. **Clear Fields Before Typing**: Keep `clear_first: true` (default) to avoid appending to existing input values
6. **Manage Cookies**: Use `get-cookies`/`set-cookies` to preserve login state across sessions
7. **Human Fallback**: Use workflow `interrupt` with `metadata.novnc_url` for CAPTCHA or MFA scenarios
8. **Headless Chrome**: Run Chrome headless in production for better performance

## Common Use Cases

- **Web Scraping**: Navigate and extract content from dynamic JavaScript-heavy sites
- **Form Automation**: Fill and submit web forms programmatically
- **CAPTCHA Handling**: Detect CAPTCHAs and pause for human resolution
- **Login Automation**: Automate login flows to access protected content
- **Visual Testing**: Capture screenshots for visual comparison
- **Cookie Management**: Inject or export cookies for authenticated sessions
- **Page Monitoring**: Periodically check page content for changes
- **Data Extraction**: Extract structured data from web pages using CSS/XPath
- **Media Capture**: Record live video streams (e.g. YouTube live) to WebM/MP4 for downstream transcoding

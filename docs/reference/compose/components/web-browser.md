# Web Browser Component

The web browser component provides full browser automation via the Chrome DevTools Protocol (CDP). It connects to a running Chrome/Chromium instance and supports navigation, clicking, text input, screenshots, JavaScript evaluation, element extraction, cookie management, scrolling, and waiting for elements.

## Basic Configuration

```yaml
component:
  type: web-browser
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
| `host` | string | `localhost` | Host where Chrome remote debugging port is exposed |
| `port` | integer | `9222` | Chrome remote debugging port |
| `cdp_endpoint` | string | `null` | Full WebSocket debugger URL (e.g. `ws://localhost:9222/devtools/page/<id>`). If set, `host`/`port` are ignored |
| `target_index` | integer | `0` | Index of the browser target to attach to when auto-discovering via `host`/`port` |
| `novnc_url` | string | `null` | URL of the noVNC viewer for human-in-the-loop scenarios |
| `timeout` | string | `30s` | Default timeout for all actions |
| `actions` | array | `[]` | List of browser actions |

### Common Action Configuration

All web browser actions share these common settings:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Action method: `navigate`, `click`, `input-text`, `screenshot`, `evaluate`, `wait-for`, `extract`, `get-cookies`, `set-cookies`, `scroll` |
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
| `wait_until` | string | `load` | Event to wait for: `load`, `domcontentloaded`, `networkidle` |

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
| `await_promise` | boolean | `false` | Await the result if the expression returns a Promise |

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

Scroll the page or a specific element:

```yaml
component:
  type: web-browser
  action:
    method: scroll
    y: 500
```

**Scroll Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `selector` | string | `null` | Scroll a specific element into view |
| `x` | integer | `0` | Horizontal scroll amount in pixels |
| `y` | integer | `0` | Vertical scroll amount in pixels |

**Returns:** `{ "scrolled_x": 0, "scrolled_y": 500 }`

## Multiple Actions Configuration

Define multiple browser actions in a single component:

```yaml
component:
  type: web-browser
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
    host: localhost
    port: 9222
    novnc_url: "http://localhost:6080/vnc.html"
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

## CDP Connection

The web browser component connects to a running Chrome/Chromium instance via the Chrome DevTools Protocol. Chrome must be started with remote debugging enabled:

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
  host: localhost
  port: 9222
```

**Direct WebSocket URL:**
Skip auto-discovery by providing the full WebSocket URL.

```yaml
component:
  type: web-browser
  cdp_endpoint: "ws://localhost:9222/devtools/page/ABC123"
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

The `novnc_url` field enables human-in-the-loop workflows. When a workflow encounters something it cannot handle (e.g., CAPTCHA), it can interrupt and display the noVNC URL so a human can interact with the browser directly.

```yaml
component:
  type: web-browser
  host: localhost
  port: 9222
  novnc_url: "http://localhost:6080/vnc.html"
```

This URL is included in workflow interrupt metadata, allowing UIs to show a direct link to the browser session.

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
7. **Human Fallback**: Use `novnc_url` with workflow interrupts for CAPTCHA or MFA scenarios
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

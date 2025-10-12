# Chapter 7: Web UI Configuration

This chapter covers how to configure model-compose's Web UI. Learn how to set up a web interface for testing and running workflows using Gradio and static file drivers.

---

## 7.1 Web UI Overview

model-compose optionally provides a web interface for testing and running workflows. The Web UI works identically regardless of controller type (`http-server` or `mcp-server`) and automatically executes workflows according to the configured controller.

### Controller Only

Running only the controller without Web UI. Suitable for production environments where only API endpoints are needed.

```yaml
controller:
  type: http-server
  port: 8080
  base_path: /api
  # No webui configuration
```

In this case, workflows can only be executed via the HTTP API (`/api/workflows/runs`).

### Controller + Web UI

Run Web UI together to test and execute workflows from a browser.

```yaml
controller:
  type: http-server
  port: 8080       # Controller API port
  base_path: /api
  webui:
    driver: gradio # or static
    port: 8081     # Web UI port (must differ from controller)
```

> **Important**: Web UI must always run on a different port from the controller.

With this configuration, the controller API runs at `http://localhost:8080/api` and the Web UI at `http://localhost:8081`. The Web UI internally calls the controller API to execute workflows.

---

## 7.2 Gradio Driver

Gradio is an interactive web UI automatically generated based on workflow schemas.

### Configuration

```yaml
controller:
  type: http-server
  port: 8080
  base_path: /api
  webui:
    driver: gradio  # Default (can be omitted)
    host: 0.0.0.0   # Default
    port: 8081      # Default
```

Configuration options:
- `driver`: Web UI driver (default: `gradio`)
- `host`: Host address the Web UI server binds to (default: `0.0.0.0`)
- `port`: Web UI server port (default: `8081`, must differ from controller port)

### Automatic UI Generation

Gradio automatically generates UI based on workflow `input` and `output` definitions:

**Input Component Mapping**:
- `string`: Text input (Textbox)
- `text`: Multi-line text input (Textbox, 5-15 lines)
- `integer`: Integer input (Textbox)
- `number`: Number input (Number)
- `boolean`: Checkbox (Checkbox)
- `list`: Comma-separated list (Textbox)
- `image`: Image upload (Image)
- `audio`: Audio upload (Audio)
- `video`: Video upload (Video)
- `file`: File upload (File)
- `select`: Dropdown (Dropdown)

**Output Component Mapping**:
- `string`, `text`: Text display (Textbox, read-only)
- `markdown`: Markdown rendering (Markdown)
- `json`, `objects`: JSON viewer (JSON)
- `image`: Image display (Image)
- `audio`: Audio player (Audio)
- `video`: Video player (Video)

### Streaming Output Support

When workflow output is specified as `as text;sse-text` or `as json;sse-json`, it's displayed in real-time streaming.

```yaml
workflow:
  title: Summarize Text
  input: ${input}
  output: ${output as text;sse-text}  # Streaming output

component:
  type: model
  task: text-generation
  model: facebook/bart-large-cnn
  text: ${input.text}
  streaming: true  # Enable streaming in component
```

- **Text Streaming** (`sse-text`): Accumulates and displays chunks as they arrive (e.g., AI text generation)
- **JSON Streaming** (`sse-json`): Adds each chunk to a list and displays (e.g., sequential generation of multiple results)

In Gradio UI, output updates in real-time so you can see the generation process.

### Multiple Workflows

- When multiple workflows are defined, they're displayed in separate tabs
- Each tab displays the workflow's `title` or `id`

### Accessing Gradio UI

```
http://localhost:8081
```

Each workflow is displayed with the following structure:
1. Workflow title and description
2. Input parameter section
3. "Run Workflow" button
4. Output value section

---

## 7.3 Static File Driver

Serves custom HTML/CSS/JavaScript files. Uses FastAPI's `StaticFiles` to serve static files and automatically serves `index.html` with the `html=True` option.

### Configuration

```yaml
controller:
  type: http-server
  port: 8080
  base_path: /api
  webui:
    driver: static     # Required
    host: 0.0.0.0      # Default
    port: 8081         # Default
    static_dir: webui  # Default
```

Configuration options:
- `driver`: `static` (required, must be specified since gradio is the default)
- `host`: Host address the Web UI server binds to (default: `0.0.0.0`)
- `port`: Web UI server port (default: `8081`)
- `static_dir`: Directory path containing static files (default: `webui`)

### How It Works

- All files in the `static_dir` path are mounted to the `/` path
- Accessing `http://localhost:8081/` automatically serves `index.html`
- All static files (CSS, JS, images, etc.) can be referenced with relative paths
- The controller API runs on a separate port (e.g., 8080), so CORS configuration may be needed

### Directory Structure Example

```
webui/
├── index.html
├── css/
│   └── style.css
├── js/
│   └── app.js
└── assets/
    └── logo.png
```

### Simple Example

**index.html**:
```html
<!DOCTYPE html>
<html>
<head>
    <title>AI Workflow UI</title>
    <link rel="stylesheet" href="/css/style.css">
</head>
<body>
    <h1>Workflow Runner</h1>
    <div id="workflow-container">
        <input id="input" type="text" placeholder="Enter input...">
        <button onclick="runWorkflow()">Run</button>
        <pre id="output"></pre>
    </div>
    <script src="/js/app.js"></script>
</body>
</html>
```

**js/app.js**:
```javascript
async function runWorkflow() {
    const input = document.getElementById('input').value;
    const output = document.getElementById('output');

    try {
        const response = await fetch('http://localhost:8080/api/workflows/runs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                workflow_id: 'my-workflow',
                input: { text: input },
                wait_for_completion: true,
                output_only: true
            })
        });

        const data = await response.json();
        output.textContent = JSON.stringify(data, null, 2);
    } catch (error) {
        output.textContent = `Error: ${error.message}`;
    }
}
```

> **Note**: The static file driver simply serves files; actual workflow execution must be called directly from JavaScript via the controller API.

---

## 7.4 Web UI Deployment via Reverse Proxy

In production environments, you can deploy both the controller API and Web UI together through a reverse proxy like Nginx.

### model-compose Configuration

```yaml
controller:
  type: http-server
  host: 127.0.0.1  # Accessible from proxy only
  port: 8080
  base_path: /api
  webui:
    driver: gradio
    host: 127.0.0.1
    port: 8081
```

### Nginx Configuration Example

```nginx
server {
    listen 80;
    server_name example.com;

    # API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8080/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Web UI proxy
    location / {
        proxy_pass http://127.0.0.1:8081/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

External access:
- **API**: `http://example.com/api/` → `http://127.0.0.1:8080/api/`
- **Web UI**: `http://example.com/` → `http://127.0.0.1:8081/`

Since the Web UI is served from the same domain as the controller, no separate CORS configuration is needed.

---

## Next Steps

Try these:
- Test auto-generated UI with Gradio
- Build custom UI with static file driver
- Display real-time responses with streaming output

---

**Next Chapter**: [8. Using Local AI Models](./08-local-ai-models.md)

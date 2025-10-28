# 第7章：Web UI 配置

本章介绍如何配置 model-compose 的 Web UI。学习如何使用 Gradio 和静态文件驱动来设置测试和运行工作流的 Web 界面。

---

## 7.1 Web UI 概述

model-compose 可选地提供用于测试和运行工作流的 Web 界面。无论控制器类型（`http-server` 或 `mcp-server`）如何，Web UI 的工作方式都相同，并根据配置的控制器自动执行工作流。

### 仅控制器

仅运行控制器而不使用 Web UI。适用于只需要 API 端点的生产环境。

```yaml
controller:
  type: http-server
  port: 8080
  base_path: /api
  # 不配置 webui
```

在这种情况下，工作流只能通过 HTTP API (`/api/workflows/runs`) 执行。

### 控制器 + Web UI

一起运行 Web UI 以从浏览器测试和执行工作流。

```yaml
controller:
  type: http-server
  port: 8080       # 控制器 API 端口
  base_path: /api
  webui:
    driver: gradio # 或 static
    port: 8081     # Web UI 端口（必须与控制器不同）
```

> **重要**：Web UI 必须始终在与控制器不同的端口上运行。

通过此配置，控制器 API 运行在 `http://localhost:8080/api`，Web UI 运行在 `http://localhost:8081`。Web UI 内部调用控制器 API 来执行工作流。

---

## 7.2 Gradio 驱动

Gradio 是根据工作流模式自动生成的交互式 Web UI。

### 配置

```yaml
controller:
  type: http-server
  port: 8080
  base_path: /api
  webui:
    driver: gradio  # 默认（可省略）
    host: 0.0.0.0   # 默认
    port: 8081      # 默认
```

配置选项：
- `driver`：Web UI 驱动（默认：`gradio`）
- `host`：Web UI 服务器绑定的主机地址（默认：`0.0.0.0`）
- `port`：Web UI 服务器端口（默认：`8081`，必须与控制器端口不同）

### 自动 UI 生成

Gradio 根据工作流的 `input` 和 `output` 定义自动生成 UI：

**输入组件映射**：
- `string`：文本输入 (Textbox)
- `text`：多行文本输入 (Textbox, 5-15 行)
- `integer`：整数输入 (Textbox)
- `number`：数字输入 (Number)
- `boolean`：复选框 (Checkbox)
- `list`：逗号分隔列表 (Textbox)
- `image`：图像上传 (Image)
- `audio`：音频上传 (Audio)
- `video`：视频上传 (Video)
- `file`：文件上传 (File)
- `select`：下拉菜单 (Dropdown)

**输出组件映射**：
- `string`、`text`：文本显示 (Textbox, 只读)
- `markdown`：Markdown 渲染 (Markdown)
- `json`、`objects`：JSON 查看器 (JSON)
- `image`：图像显示 (Image)
- `audio`：音频播放器 (Audio)
- `video`：视频播放器 (Video)

### 流式输出支持

当工作流输出指定为 `as text;sse-text` 或 `as json;sse-json` 时，会实时流式显示。

```yaml
workflow:
  title: Summarize Text
  input: ${input}
  output: ${output as text;sse-text}  # 流式输出

component:
  type: model
  task: text-generation
  model: facebook/bart-large-cnn
  text: ${input.text}
  streaming: true  # 在组件中启用流式传输
```

- **文本流式传输** (`sse-text`)：累积并显示到达的块（例如，AI 文本生成）
- **JSON 流式传输** (`sse-json`)：将每个块添加到列表中并显示（例如，多个结果的顺序生成）

在 Gradio UI 中，输出会实时更新，因此您可以看到生成过程。

### 多个工作流

- 当定义多个工作流时，它们会显示在单独的选项卡中
- 每个选项卡显示工作流的 `title` 或 `id`

### 访问 Gradio UI

```
http://localhost:8081
```

每个工作流以以下结构显示：
1. 工作流标题和描述
2. 输入参数部分
3. "运行工作流" 按钮
4. 输出值部分

---

## 7.3 静态文件驱动

提供自定义 HTML/CSS/JavaScript 文件。使用 FastAPI 的 `StaticFiles` 提供静态文件，并使用 `html=True` 选项自动提供 `index.html`。

### 配置

```yaml
controller:
  type: http-server
  port: 8080
  base_path: /api
  webui:
    driver: static     # 必需
    host: 0.0.0.0      # 默认
    port: 8081         # 默认
    static_dir: webui  # 默认
```

配置选项：
- `driver`：`static`（必需，因为 gradio 是默认值，所以必须指定）
- `host`：Web UI 服务器绑定的主机地址（默认：`0.0.0.0`）
- `port`：Web UI 服务器端口（默认：`8081`）
- `static_dir`：包含静态文件的目录路径（默认：`webui`）

### 工作原理

- `static_dir` 路径中的所有文件都挂载到 `/` 路径
- 访问 `http://localhost:8081/` 会自动提供 `index.html`
- 所有静态文件（CSS、JS、图像等）都可以使用相对路径引用
- 控制器 API 在单独的端口上运行（例如 8080），因此可能需要 CORS 配置

### 目录结构示例

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

### 简单示例

**index.html**：
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

**js/app.js**：
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

> **注意**：静态文件驱动只是提供文件；实际的工作流执行必须直接从 JavaScript 通过控制器 API 调用。

---

## 7.4 通过反向代理部署 Web UI

在生产环境中，您可以通过 Nginx 等反向代理将控制器 API 和 Web UI 一起部署。

### model-compose 配置

```yaml
controller:
  type: http-server
  host: 127.0.0.1  # 仅可从代理访问
  port: 8080
  base_path: /api
  webui:
    driver: gradio
    host: 127.0.0.1
    port: 8081
```

### Nginx 配置示例

```nginx
server {
    listen 80;
    server_name example.com;

    # API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8080/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Web UI 代理
    location / {
        proxy_pass http://127.0.0.1:8081/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

外部访问：
- **API**：`http://example.com/api/` → `http://127.0.0.1:8080/api/`
- **Web UI**：`http://example.com/` → `http://127.0.0.1:8081/`

由于 Web UI 与控制器从同一域提供服务，因此不需要单独的 CORS 配置。

---

## 下一步

试试这些：
- 使用 Gradio 测试自动生成的 UI
- 使用静态文件驱动构建自定义 UI
- 使用流式输出显示实时响应

---

**下一章**：[8. 使用本地 AI 模型](./08-local-ai-models.md)

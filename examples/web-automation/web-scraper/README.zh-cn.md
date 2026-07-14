# 网页抓取示例

此示例通过针对不同抓取场景的多个工作流，展示了 `web-scraper` 组件的各种网页抓取能力。

## 概述

此示例提供了 7 个不同的网页抓取工作流，演示：

1. **基本抓取**：使用 CSS 选择器提取文本内容
2. **链接提取**：从网页提取所有超链接
3. **JavaScript 渲染**：使用 Playwright 抓取动态加载的内容
4. **表单提交**：填写并提交表单，然后提取结果
5. **多个元素**：从多个匹配元素提取内容
6. **XPath 提取**：使用 XPath 表达式进行精确的元素定位
7. **HTML 提取**：提取原始 HTML 标记以供进一步处理

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- 网页抓取依赖：
  ```bash
  pip install playwright beautifulsoup4 lxml
  playwright install chromium
  ```

### 设置

导航到此示例目录：
```bash
cd examples/web-scraper
```

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```

   服务将启动：
   - API 端点：http://localhost:8080/api
   - Web UI：http://localhost:8081

2. **运行工作流：**

   **使用 API：**
   ```bash
   # 基本抓取
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{
       "workflow": "basic-scraping",
       "input": {
         "url": "https://example.com",
         "selector": "h1"
       }
     }'

   # 提取链接
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{
       "workflow": "extract-links",
       "input": {
         "url": "https://example.com"
       }
     }'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 从下拉列表中选择工作流
   - 输入参数
   - 点击"运行工作流"

   **使用 CLI：**
   ```bash
   # 基本抓取
   model-compose run basic-scraping --input '{
     "url": "https://example.com",
     "selector": "h1"
   }'

   # JavaScript 渲染
   model-compose run javascript-rendering --input '{
     "url": "https://spa-example.com",
     "selector": ".content",
     "wait_for": ".loaded"
   }'
   ```

## 组件详情

### Web Scraper 组件

- **类型**：Web scraper 组件
- **用途**：从网页提取内容
- **功能**：
  - 支持 CSS 选择器和 XPath
  - 使用 Playwright 进行 JavaScript 渲染
  - 表单填写和提交
  - 多种提取模式（text、HTML、attribute）
  - 自定义标头和超时配置

## 工作流详情

### 1. Basic Scraping 工作流

**ID**：`basic-scraping`
**描述**：使用 CSS 选择器从网页提取文本内容

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `url` | text | 是 | - | 要抓取的网页 URL |
| `selector` | text | 否 | `"body"` | 用于定位元素的 CSS 选择器 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `content` | text | 提取的文本内容 |

---

### 2. Extract Links 工作流

**ID**：`extract-links`
**描述**：使用属性提取从网页提取所有链接

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `url` | text | 是 | - | 要抓取的网页 URL |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `links` | array | 提取的 href 属性列表 |

---

### 3. JavaScript Rendering 工作流

**ID**：`javascript-rendering`
**描述**：使用 Playwright 从 JavaScript 渲染的网页提取内容

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `url` | text | 是 | - | 要抓取的网页 URL |
| `selector` | text | 否 | `".content"` | 用于定位元素的 CSS 选择器 |
| `wait_for` | text | 否 | - | 提取前等待的 CSS 选择器 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `content` | text | 从 JavaScript 渲染页面提取的文本内容 |

**注意**：此工作流使用 Playwright 执行 JavaScript，适用于单页应用（SPA）和动态加载的内容。

---

### 4. Form Submission 工作流

**ID**：`form-submission`
**描述**：填写并提交网页表单，然后提取结果内容

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `url` | text | 是 | - | 包含表单的网页 URL |
| `username` | text | 是 | - | 要填写的用户名值 |
| `password` | text | 是 | - | 要填写的密码值 |
| `form_selector` | text | 否 | `"form"` | 表单的 CSS 选择器 |
| `result_selector` | text | 否 | `".result"` | 提交后等待的 CSS 选择器 |
| `content_selector` | text | 否 | `".result"` | 用于内容提取的 CSS 选择器 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `result` | text | 表单提交后提取的内容 |

---

### 5. Multiple Elements 工作流

**ID**：`multiple-elements`
**描述**：从匹配选择器的多个元素提取文本

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `url` | text | 是 | - | 要抓取的网页 URL |
| `selector` | text | 否 | `"article h2"` | 用于定位元素的 CSS 选择器 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `titles` | array | 从匹配元素提取的文本内容列表 |

**注意**：此工作流自动包含自定义 User-Agent 标头。

---

### 6. XPath Extraction 工作流

**ID**：`xpath-extraction`
**描述**：使用 XPath 表达式从网页提取特定内容

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `url` | text | 是 | - | 要抓取的网页 URL |
| `xpath` | text | 否 | `"//div[@class='content']//p"` | 用于定位元素的 XPath 表达式 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `paragraphs` | array | 从匹配元素提取的文本内容列表 |

---

### 7. HTML Extraction 工作流

**ID**：`html-extraction`
**描述**：提取特定元素的 HTML 标记以供进一步处理

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `url` | text | 是 | - | 要抓取的网页 URL |
| `selector` | text | 否 | `"article"` | 用于定位元素的 CSS 选择器 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `html` | text | 提取的 HTML 标记 |

---

## 自定义

### 修改提取模式

更改 `extract_mode` 以提取不同类型的内容：

```yaml
component:
  type: web-scraper
  action:
    extract_mode: text    # 选项：text、html、attribute
    attribute: href       # 当 extract_mode 为 "attribute" 时需要
```

### 添加自定义标头

包含用于身份验证或识别的自定义 HTTP 标头：

```yaml
component:
  type: web-scraper
  headers:
    Authorization: Bearer ${env.API_TOKEN}
    User-Agent: MyCustomBot/1.0
```

### 调整超时

为加载缓慢的页面配置超时：

```yaml
component:
  type: web-scraper
  timeout: 120s  # 2 分钟
```

### 不输入的表单提交

仅点击提交按钮而不填写表单字段：

```yaml
submit:
  selector: button[type="submit"]
  # 未指定表单字段 - 仅点击按钮
```

## 最佳实践

- **尊重 robots.txt**：始终检查并尊重网站爬取政策
- **速率限制**：抓取多个页面时在请求之间添加延迟
- **User-Agent**：使用描述性的 User-Agent 来标识您的抓取工具
- **错误处理**：处理可能找不到元素的情况
- **JavaScript 渲染**：仅在必要时使用，因为它消耗更多资源
- **身份验证**：切勿硬编码凭据 - 使用环境变量

## 故障排除

### Playwright 安装

如果遇到 Playwright 错误：
```bash
playwright install chromium
```

### 超时错误

对于加载缓慢的页面，增加超时：
```yaml
timeout: 120s
```

### 找不到元素

- 使用浏览器 DevTools 验证选择器
- 检查元素是否动态加载（使用 `enable_javascript: true`）
- 使用 `wait_for` 等待特定元素

## 高级用法

### 多步骤抓取

在工作流中组合多个组件：

```yaml
workflows:
  - id: multi-step-scraping
    jobs:
      - id: get-links
        component: link-extractor
      - id: scrape-each-page
        component: page-scraper
        input:
          url: ${jobs.get-links.output.links[0]}
```

### 动态表单值

使用工作流输入进行动态表单提交：

```yaml
submit:
  form:
    input[name="search"]: ${input.query}
    select[name="category"]: ${input.category}
```

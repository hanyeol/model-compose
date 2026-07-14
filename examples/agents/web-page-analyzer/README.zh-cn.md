# 网页分析代理示例

此示例演示了一个使用 web-scraper 工具抓取和分析网页的自主代理。提供一个 URL 和关于该页面的问题，代理将自行决定调用哪些工具来回答。

## 概述

代理通过 ReAct 循环运行：

1. **接收请求**：用户提供包含网页 URL 的问题
2. **获取**：代理首先使用 `fetch_page` 读取完整页面文本并理解页面结构
3. **提取**：根据需要使用 `extract_elements` 或 `extract_links` 进行针对性提取
4. **回答**：收集到足够上下文后，生成清晰、结构良好的答案

### 可用工具

| 工具 | 描述 |
|------|------|
| `fetch_page` | 从网页 URL 获取主要文本内容 |
| `extract_links` | 从网页提取所有超链接（href URL） |
| `extract_elements` | 使用 CSS 选择器提取特定元素的文本内容 |

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- OpenAI API 密钥

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/agents/web-page-analyzer
   ```

2. 复制示例环境文件：
   ```bash
   cp .env.sample .env
   ```

3. 编辑 `.env` 并添加您的 OpenAI API 密钥：
   ```env
   OPENAI_API_KEY=your-openai-api-key
   ```

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"question": "总结 https://example.com/blog/post 的要点"}'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 输入您的问题，然后点击"运行工作流"按钮

   **使用 CLI：**
   ```bash
   model-compose run --input '{"question": "列出 https://example.com 上的所有 H2 标题"}'
   ```

## 组件详情

### OpenAI GPT-4o 组件 (gpt-4o)
- **类型**：HTTP 客户端组件
- **用途**：用于代理推理和答案生成的 LLM
- **API**：OpenAI GPT-4o Chat Completions（function calling）

### Web Scraper 组件 (page-scraper, link-scraper, element-scraper)
- **类型**：Web scraper 组件
- **用途**：通过 CSS 选择器进行 HTML 抓取
- **提取模式**：`text` 用于内容提取，`attribute` 用于链接提取

### 分析代理组件 (analyzer-agent)
- **类型**：Agent 组件
- **用途**：抓取和分析网页的自主代理
- **最大迭代次数**：10

## 工作流详情

### 工具：fetch_page

**描述**：从网页 URL 获取主要文本内容。

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `url` | string | 是 | - | 要获取的网页 URL |

### 工具：extract_links

**描述**：从网页提取所有超链接（href URL）。返回页面中找到的 URL 的 JSON 列表。

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `url` | string | 是 | - | 要提取链接的网页 URL |

### 工具：extract_elements

**描述**：使用 CSS 选择器从网页提取特定元素的文本内容。返回匹配元素文本的 JSON 列表。

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `url` | string | 是 | - | 网页 URL |
| `selector` | string | 是 | - | 目标元素的 CSS 选择器（例如 "h2"、".title"、"#main p"） |

## 注意事项

- 代理被指示优先使用简单的基于标签的选择器（例如 `h1`、`h2`、`p`、`li`、`a`、`table tr`），而不是猜测类名。
- 如果选择器返回空结果，代理会尝试更简单或更宽泛的选择器，而不是猜测另一个类名。

## 自定义

- 将 `gpt-4o` 替换为其他支持 function calling 的模型
- 添加更多抓取工具（例如图像提取器、表格解析器）
- 调整 `max_iteration_count` 以允许更深入的页面探索
- 为抓取器添加 User-Agent 头或超时设置以应对反爬网站

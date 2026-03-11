# 网络研究代理示例

此示例演示了一个自主代理，它可以搜索网络并获取页面内容来研究主题并提供综合答案。

## 概述

代理通过 ReAct 循环运行：

1. **接收问题**：用户提供研究问题
2. **搜索和获取**：代理自主使用工具搜索网络并阅读相关页面
3. **综合**：收集足够的信息后，生成综合答案

### 可用工具

| 工具 | 描述 |
|------|------|
| `search_web` | 使用 Tavily API 搜索网络 |
| `fetch_page` | 从 URL 中提取文本内容 |

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- OpenAI API 密钥
- Tavily API 密钥 ([tavily.com](https://tavily.com))

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/agents/web-researcher
   ```

2. 复制示例环境文件：
   ```bash
   cp .env.sample .env
   ```

3. 编辑 `.env` 并添加您的 API 密钥：
   ```env
   OPENAI_API_KEY=your-openai-api-key
   TAVILY_API_KEY=your-tavily-api-key
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
     -d '{"question": "量子计算的最新进展是什么？"}'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 输入您的研究问题并点击"运行工作流"按钮

   **使用 CLI：**
   ```bash
   model-compose run --input '{"question": "量子计算的最新进展是什么？"}'
   ```

## 组件详情

### OpenAI GPT-4o 组件 (gpt-4o)
- **类型**：HTTP 客户端组件
- **用途**：用于代理推理和工具使用的 LLM
- **API**：OpenAI GPT-4o Chat Completions（function calling）

### Tavily 搜索组件 (tavily)
- **类型**：HTTP 客户端组件
- **用途**：网络搜索 API
- **API**：Tavily Search API

### 网页抓取组件 (scraper)
- **类型**：Web scraper 组件
- **用途**：从网页中提取文本内容

### 研究代理组件 (research-agent)
- **类型**：Agent 组件
- **用途**：协调工具的自主研究代理
- **最大迭代次数**：10

## 工作流详情

### 工具：search_web

**描述**：搜索网络以获取给定查询的信息。

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `query` | string | 是 | - | 搜索查询字符串 |
| `max_results` | integer | 否 | `5` | 返回的最大搜索结果数 |

### 工具：fetch_page

**描述**：从网页 URL 获取并提取文本内容。

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `url` | string | 是 | - | 要获取的网页 URL |

## 自定义

- 将 `gpt-4o` 替换为其他支持 function calling 的模型（例如 Claude、Llama 3.1+）
- 调整 `max_iteration_count` 以控制代理探索深度
- 通过定义额外的工作流添加更多工具（例如图像分析、翻译）

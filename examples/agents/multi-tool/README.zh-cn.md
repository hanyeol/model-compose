# 多工具助手代理示例

此示例演示了一个多功能助手代理，它结合了网络搜索、天气查询、计算器和时钟等多种工具来回答各类问题。

## 概述

代理通过 ReAct 循环运行：

1. **接收问题**：用户提出问题
2. **选择工具**：代理根据问题决定使用哪些工具
3. **执行和组合**：代理调用工具，组合结果并进行推理
4. **回答**：使用收集的信息生成综合答案

### 可用工具

| 工具 | 描述 |
|------|------|
| `search_web` | 使用 Tavily API 搜索网络 |
| `get_weather` | 获取城市的当前天气 |
| `run_calculation` | 执行 Python 表达式进行数学计算 |
| `get_current_time` | 获取当前日期和时间 |

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- OpenAI API 密钥
- Tavily API 密钥 ([tavily.com](https://tavily.com))
- OpenWeatherMap API 密钥 ([openweathermap.org](https://openweathermap.org/api))

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/agents/multi-tool
   ```

2. 复制示例环境文件：
   ```bash
   cp .env.sample .env
   ```

3. 编辑 `.env` 并添加您的 API 密钥：
   ```env
   OPENAI_API_KEY=your-openai-api-key
   TAVILY_API_KEY=your-tavily-api-key
   OPENWEATHER_API_KEY=your-openweathermap-api-key
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
     -d '{"question": "东京的天气怎么样？现在那里几点了？"}'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 输入您的问题并点击"运行工作流"按钮

   **使用 CLI：**
   ```bash
   model-compose run --input '{"question": "计算 2 的 64 次方并搜索那个数字代表什么"}'
   ```

## 组件详情

### OpenAI GPT-4o 组件 (gpt-4o)
- **类型**：HTTP 客户端组件
- **用途**：用于代理推理和工具选择的 LLM
- **API**：OpenAI GPT-4o Chat Completions（function calling）

### Tavily 搜索组件 (tavily)
- **类型**：HTTP 客户端组件
- **用途**：网络搜索 API
- **API**：Tavily Search API

### 天气 API 组件 (weather-api)
- **类型**：HTTP 客户端组件
- **用途**：当前天气数据
- **API**：OpenWeatherMap API

### 计算器组件 (calculator)
- **类型**：Shell 组件
- **用途**：执行 Python 表达式进行计算

### 时钟组件 (clock)
- **类型**：Shell 组件
- **用途**：获取当前日期和时间

### 助手代理组件 (assistant)
- **类型**：Agent 组件
- **用途**：协调所有工具的多工具助手
- **最大迭代次数**：10

## 工作流详情

### 工具：search_web

**描述**：搜索网络以获取给定查询的信息。

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `query` | string | 是 | - | 搜索查询字符串 |
| `max_results` | integer | 否 | `5` | 最大搜索结果数 |

### 工具：get_weather

**描述**：获取城市的当前天气。

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `city` | string | 是 | - | 城市名称，例如 "Tokyo" 或 "London,UK" |

### 工具：run_calculation

**描述**：执行 Python 表达式进行数学计算。

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `expression` | string | 是 | - | 要计算的 Python 表达式，例如 "print(2 ** 10)" |

### 工具：get_current_time

**描述**：获取包含时区信息的当前日期和时间。

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| - | - | - | - | 此工具不需要输入参数 |

## 自定义

- 将 `gpt-4o` 替换为其他支持 function calling 的模型
- 通过定义额外的工作流添加更多工具（例如翻译、图像生成）
- 为更简单的用例移除不需要的工具
- 调整 `max_iteration_count` 以控制代理探索深度

# Web3 空投猎手代理示例

此示例演示了一个自主代理，它结合 DeFi API 和网页抓取来发现最新的空投机会和 DeFi 收益信息。

## 概述

代理通过 ReAct 循环运行：

1. **接收请求**：用户提出关于空投或 DeFi 收益的问题
2. **查询 API**：代理调用 DeFiLlama 获取可靠的收益和协议数据
3. **抓取数据源**：代理抓取 airdrops.io 上的热门空投名称和详情页
4. **编写报告**：代理将收集到的数据汇总为结构清晰的 markdown 报告，并附上来源

### 可用工具

| 工具 | 描述 |
|------|------|
| `fetch_hottest_airdrops` | 从 airdrops.io 获取热门空投项目名称 |
| `fetch_defi_yields` | 从 DeFiLlama API 获取顶级 DeFi 收益池（APY、TVL、链、协议） |
| `fetch_defi_protocols` | 从 DeFiLlama API 获取顶级 DeFi 协议（TVL、类别、链） |
| `fetch_page` | 从网页 URL 获取主要文本内容 |
| `extract_links` | 从网页提取所有超链接（href URL） |
| `extract_elements` | 使用 CSS 选择器提取特定元素的文本 |

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- OpenAI API 密钥

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/agents/web3-airdrop-hunter
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
     -d '{"question": "现在最热门的空投和最佳 DeFi 收益是什么？"}'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 输入您的问题，然后点击"运行工作流"按钮

   **使用 CLI：**
   ```bash
   model-compose run --input '{"question": "查找 Arbitrum 上的顶级稳定币收益"}'
   ```

## 组件详情

### OpenAI GPT-4o 组件 (gpt-4o)
- **类型**：HTTP 客户端组件
- **用途**：用于代理推理和报告生成的 LLM
- **API**：OpenAI GPT-4o Chat Completions（function calling）

### DeFiLlama API 组件 (defillama-yields, defillama-protocols)
- **类型**：HTTP 客户端组件
- **用途**：DeFi 收益和协议数据的可靠 API 数据源
- **端点**：`https://yields.llama.fi/pools`、`https://api.llama.fi/protocols`

### Web Scraper 组件 (airdrops-io-titles, page-scraper, link-scraper, element-scraper)
- **类型**：Web scraper 组件
- **用途**：使用浏览器 User-Agent 的 HTML 抓取，30 秒超时
- **提取模式**：`text` 或 `attribute`

### 猎手代理组件 (hunter-agent)
- **类型**：Agent 组件
- **用途**：收集加密数据并生成报告的自主代理
- **最大迭代次数**：10

## 工作流详情

### 工具：fetch_hottest_airdrops

**描述**：从 airdrops.io 获取最热门的空投列表。返回热门空投项目名称的 JSON 列表。

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `query` | string | 否 | `all` | 忽略，传入任意值 |

### 工具：fetch_defi_yields

**描述**：从 DeFiLlama API 获取顶级 DeFi 收益耕作池。返回按 TVL 排序的池列表，包含 project、chain、symbol、tvlUsd、apy、apyBase、apyReward 和 pool URL。

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `chain` | string | 否 | `all` | 按区块链名称筛选（例如 "Ethereum"、"Arbitrum"、"Solana"） |

### 工具：fetch_defi_protocols

**描述**：从 DeFiLlama API 获取顶级 DeFi 协议。返回包含 name、chain、tvl、change_1d、change_7d 和 category 的 JSON 列表。

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `category` | string | 否 | `all` | 按类别筛选（例如 "Dexes"、"Lending"、"Bridge"） |

### 工具：fetch_page

**描述**：从网页 URL 获取主要文本内容。

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `url` | string | 是 | - | 要获取的网页 URL |

### 工具：extract_links

**描述**：从网页提取所有超链接（href URL）。

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `url` | string | 是 | - | 要提取链接的网页 URL |

### 工具：extract_elements

**描述**：使用 CSS 选择器提取特定元素的文本。

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `url` | string | 是 | - | 网页 URL |
| `selector` | string | 是 | - | 目标元素的 CSS 选择器（例如 "h2"、"table tr"、"li"） |

## 注意事项

- 代理被指示不要抓取 CoinMarketCap、DappRadar 或 DeFiLlama 网页，因为它们受 Cloudflare 保护。请改用 API 工具。
- 代理始终提醒用户在参与任何空投或 DeFi 协议前进行 DYOR（Do Your Own Research）。

## 自定义

- 将 `gpt-4o` 替换为其他支持 function calling 的模型
- 添加更多数据源（例如 CoinGecko API、Dune Analytics）
- 调整 `max_iteration_count` 以允许更深入的研究
- 更改 DeFiLlama 结果数量（当前为 `[:20]`）以扩大或缩小数据范围

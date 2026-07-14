# Web3 Airdrop Hunter Agent Example

This example demonstrates an autonomous agent that combines DeFi APIs and web scraping to discover the latest airdrop opportunities and DeFi yield information.

## Overview

The agent operates through a ReAct loop:

1. **Receive Request**: The user asks a question about airdrops or DeFi yields
2. **Query APIs**: The agent calls DeFiLlama for reliable yield and protocol data
3. **Scrape Sources**: The agent scrapes airdrops.io for trending airdrop names and detail pages
4. **Compile Report**: The agent aggregates the gathered data into a well-organized markdown report with source attribution

### Available Tools

| Tool | Description |
|------|-------------|
| `fetch_hottest_airdrops` | Fetch trending airdrop project names from airdrops.io |
| `fetch_defi_yields` | Fetch top DeFi yield pools from DeFiLlama API (APY, TVL, chain, protocol) |
| `fetch_defi_protocols` | Fetch top DeFi protocols from DeFiLlama API (TVL, category, chain) |
| `fetch_page` | Fetch main text content from a web page URL |
| `extract_links` | Extract all hyperlinks (href URLs) from a web page |
| `extract_elements` | Extract text from specific elements using a CSS selector |

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- OpenAI API key

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/agents/web3-airdrop-hunter
   ```

2. Copy the sample environment file:
   ```bash
   cp .env.sample .env
   ```

3. Edit `.env` and add your OpenAI API key:
   ```env
   OPENAI_API_KEY=your-openai-api-key
   ```

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflow:**

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"question": "What are the hottest airdrops and best DeFi yields right now?"}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Enter your question and click "Run Workflow"

   **Using CLI:**
   ```bash
   model-compose run --input '{"question": "Find top stablecoin yields on Arbitrum"}'
   ```

## Component Details

### OpenAI GPT-4o Component (gpt-4o)
- **Type**: HTTP client component
- **Purpose**: LLM for agent reasoning and report generation
- **API**: OpenAI GPT-4o Chat Completions with function calling

### DeFiLlama API Components (defillama-yields, defillama-protocols)
- **Type**: HTTP client component
- **Purpose**: Reliable API-based data source for DeFi yields and protocols
- **Endpoints**: `https://yields.llama.fi/pools`, `https://api.llama.fi/protocols`

### Web Scraper Components (airdrops-io-titles, page-scraper, link-scraper, element-scraper)
- **Type**: Web scraper component
- **Purpose**: HTML scraping with a browser User-Agent, 30s timeout
- **Extract modes**: `text` or `attribute`

### Hunter Agent Component (hunter-agent)
- **Type**: Agent component
- **Purpose**: Autonomous agent that gathers crypto data and compiles reports
- **Max Iterations**: 10

## Workflow Details

### Tool: fetch_hottest_airdrops

**Description**: Fetch the hottest airdrops list from airdrops.io. Returns a JSON list of trending airdrop project names.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | No | `all` | Ignored, pass any value |

### Tool: fetch_defi_yields

**Description**: Fetch top DeFi yield farming pools from DeFiLlama API. Returns pools sorted by TVL with project, chain, symbol, tvlUsd, apy, apyBase, apyReward, and pool URL.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `chain` | string | No | `all` | Filter by blockchain chain name (e.g. "Ethereum", "Arbitrum", "Solana") |

### Tool: fetch_defi_protocols

**Description**: Fetch top DeFi protocols from DeFiLlama API. Returns a JSON list with name, chain, tvl, change_1d, change_7d, and category.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `category` | string | No | `all` | Filter by category (e.g. "Dexes", "Lending", "Bridge") |

### Tool: fetch_page

**Description**: Fetch and extract the main text content from a web page URL.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | Yes | - | The URL of the web page to fetch |

### Tool: extract_links

**Description**: Extract all hyperlinks (href URLs) from a web page.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | Yes | - | The URL of the web page to extract links from |

### Tool: extract_elements

**Description**: Extract text content from specific elements using a CSS selector.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | Yes | - | The URL of the web page |
| `selector` | string | Yes | - | CSS selector to target elements (e.g. "h2", "table tr", "li") |

## Notes

- The agent is instructed NOT to scrape CoinMarketCap, DappRadar, or DeFiLlama web pages because they are protected by Cloudflare. Use the API tools instead.
- The agent always reminds users to DYOR (Do Your Own Research) before participating in any airdrop or DeFi protocol.

## Customization

- Replace `gpt-4o` with other models that support function calling
- Add more data sources (e.g. CoinGecko API, Dune Analytics)
- Adjust `max_iteration_count` to allow deeper research
- Change the DeFiLlama result limit (currently `[:20]`) to widen or narrow the data set

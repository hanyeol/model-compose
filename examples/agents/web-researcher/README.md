# Web Researcher Agent Example

This example demonstrates an autonomous agent that searches the web and fetches page content to research a topic and provide a comprehensive answer.

## Overview

The agent operates through a ReAct loop:

1. **Receive Question**: The user provides a research question
2. **Search & Fetch**: The agent autonomously uses tools to search the web and read relevant pages
3. **Synthesize**: After gathering enough information, the agent produces a comprehensive answer

### Available Tools

| Tool | Description |
|------|-------------|
| `search_web` | Search the web using Tavily API |
| `fetch_page` | Fetch and extract text content from a URL |

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- OpenAI API key
- Tavily API key ([tavily.com](https://tavily.com))

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/agents/web-researcher
   ```

2. Copy the sample environment file:
   ```bash
   cp .env.sample .env
   ```

3. Edit `.env` and add your API keys:
   ```env
   OPENAI_API_KEY=your-openai-api-key
   TAVILY_API_KEY=your-tavily-api-key
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
     -d '{"question": "What are the latest advancements in quantum computing?"}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Enter your research question and click "Run Workflow"

   **Using CLI:**
   ```bash
   model-compose run --input '{"question": "What are the latest advancements in quantum computing?"}'
   ```

## Component Details

### OpenAI GPT-4o Component (gpt-4o)
- **Type**: HTTP client component
- **Purpose**: LLM for agent reasoning and tool use
- **API**: OpenAI GPT-4o Chat Completions with function calling

### Tavily Search Component (tavily)
- **Type**: HTTP client component
- **Purpose**: Web search API
- **API**: Tavily Search API

### Web Scraper Component (scraper)
- **Type**: Web scraper component
- **Purpose**: Extract text content from web pages

### Research Agent Component (research-agent)
- **Type**: Agent component
- **Purpose**: Autonomous research agent that orchestrates tools
- **Max Iterations**: 10

## Workflow Details

### Tool: search_web

**Description**: Search the web for information on a given query.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | - | The search query string |
| `max_results` | integer | No | `5` | Maximum number of search results to return |

### Tool: fetch_page

**Description**: Fetch and extract the text content from a web page URL.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | Yes | - | The URL of the web page to fetch |

## Customization

- Replace `gpt-4o` with other models that support function calling (e.g., Claude, Llama 3.1+)
- Adjust `max_iteration_count` to control agent depth
- Add more tools (e.g., image analysis, translation) by defining additional workflows

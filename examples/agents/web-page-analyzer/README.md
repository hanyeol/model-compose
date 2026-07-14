# Web Page Analyzer Agent Example

This example demonstrates an autonomous agent that scrapes and analyzes web pages using web-scraper tools. Give it a URL and a question about the page, and the agent will decide which tools to call to answer it.

## Overview

The agent operates through a ReAct loop:

1. **Receive Request**: The user provides a question that references a web page URL
2. **Fetch**: The agent starts with `fetch_page` to read the full page text and understand its structure
3. **Extract**: The agent optionally uses `extract_elements` or `extract_links` for targeted extraction
4. **Answer**: After gathering enough context, the agent produces a clear, well-organized answer

### Available Tools

| Tool | Description |
|------|-------------|
| `fetch_page` | Fetch and extract the main text content from a web page URL |
| `extract_links` | Extract all hyperlinks (href URLs) from a web page |
| `extract_elements` | Extract text content from specific elements using a CSS selector |

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- OpenAI API key

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/agents/web-page-analyzer
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
     -d '{"question": "Summarize the main points of https://example.com/blog/post"}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Enter your question and click "Run Workflow"

   **Using CLI:**
   ```bash
   model-compose run --input '{"question": "List all H2 headings on https://example.com"}'
   ```

## Component Details

### OpenAI GPT-4o Component (gpt-4o)
- **Type**: HTTP client component
- **Purpose**: LLM for agent reasoning and answer generation
- **API**: OpenAI GPT-4o Chat Completions with function calling

### Web Scraper Components (page-scraper, link-scraper, element-scraper)
- **Type**: Web scraper component
- **Purpose**: HTML scraping via CSS selectors
- **Extract modes**: `text` for content extraction, `attribute` for link extraction

### Analyzer Agent Component (analyzer-agent)
- **Type**: Agent component
- **Purpose**: Autonomous agent that scrapes and analyzes web pages
- **Max Iterations**: 10

## Workflow Details

### Tool: fetch_page

**Description**: Fetch and extract the main text content from a web page URL.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | Yes | - | The URL of the web page to fetch |

### Tool: extract_links

**Description**: Extract all hyperlinks (href URLs) from a web page. Returns a JSON list of URLs found on the page.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | Yes | - | The URL of the web page to extract links from |

### Tool: extract_elements

**Description**: Extract text content from specific elements on a web page using a CSS selector. Returns a JSON list of matched element texts.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | Yes | - | The URL of the web page |
| `selector` | string | Yes | - | CSS selector to target elements (e.g. "h2", ".title", "#main p") |

## Notes

- The agent is instructed to prefer simple tag-based selectors (e.g. `h1`, `h2`, `p`, `li`, `a`, `table tr`) over guessing class names.
- If a selector returns empty results, the agent tries a simpler or broader selector rather than guessing another class name.

## Customization

- Replace `gpt-4o` with other models that support function calling
- Add more scraping tools (e.g. an image extractor, a table parser)
- Adjust `max_iteration_count` to allow deeper page exploration
- Add a User-Agent header or timeout to the scrapers to handle bot-protected sites

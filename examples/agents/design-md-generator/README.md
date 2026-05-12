# DESIGN.md Generator Example

This example demonstrates an AI agent that analyzes a website's visual design system and generates a comprehensive DESIGN.md document, using headless browser automation with the `web-browser` component and an `agent` component powered by GPT-4o.

## Overview

This example runs a Chromium browser inside a Docker container and uses an AI agent to systematically inspect a website's design system:

1. **Navigate** to the target URL using a headless browser
2. **Extract** design tokens — colors, typography, spacing, border radii, and computed styles — through multiple browser tools
3. **Synthesize** a comprehensive DESIGN.md document covering color palette, typography rules, component stylings, layout principles, and more

Key features:

- **Agent-Driven Analysis**: GPT-4o agent with 8 browser tools performs a multi-pass design inspection strategy
- **Docker System Module**: Single container running Chromium, Xvfb, x11vnc, noVNC, and socat via supervisord
- **CDP (Chrome DevTools Protocol)**: Communicates with Chromium for navigation, DOM extraction, and JavaScript evaluation
- **noVNC Remote Desktop**: Provides browser-visible UI at `http://localhost:6080/vnc.html` for monitoring the analysis
- **Gradio Web UI**: Interactive interface at `http://localhost:8081` to submit URLs and view generated DESIGN.md

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Docker installed and running
- OpenAI API key (GPT-4o)

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/design-md-generator
   ```

2. Copy the environment sample file and add your API key:
   ```bash
   cp .env.sample .env
   ```

3. Edit `.env` and set your OpenAI API key:
   ```env
   OPENAI_API_KEY=your-api-key-here
   ```

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   This builds the Docker image (if needed) and starts the browser container.

2. **Run the workflow:**

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Enter a URL (e.g., `https://stripe.com`) and click Run
   - The agent will analyze the site and generate a DESIGN.md document

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/main/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"url": "https://stripe.com"}}'
   ```

   **Using CLI:**
   ```bash
   model-compose run main --input '{"url": "https://stripe.com"}'
   ```

3. **Monitor the browser** (optional):
   - Open noVNC at http://localhost:6080/vnc.html to watch the agent navigate and inspect pages in real-time

4. **Stop the service:**
   ```bash
   model-compose down
   ```

## Workflow Details

### "DESIGN.md Generator" Workflow (Default)

**Description**: Analyze a website's design system and generate a comprehensive DESIGN.md document.

#### Job Flow

```mermaid
graph TD
    Input((Input)) --> Agent

    subgraph Agent["design-md-generator (Agent)"]
        direction TB
        LLM[GPT-4o]
        T1[navigate_to_url]
        T2[extract_page_structure]
        T3[extract_page_html]
        T4[extract_computed_styles]
        T5[extract_color_palette]
        T6[extract_typography]
        T7[extract_spacing_and_radii]
        T8[scroll_page]

        LLM --> T1 & T2 & T3 & T4 & T5 & T6 & T7 & T8
        T1 & T2 & T3 & T4 & T5 & T6 & T7 & T8 --> LLM
    end

    Agent --> Output((Output))
```

The agent follows a multi-pass analysis strategy:
1. **Pass 1 — Structure Overview**: Navigate to URL, extract page structure and font imports
2. **Pass 2 — Data Extraction**: Extract color palette, typography, spacing, and computed styles from key elements
3. **Pass 3 — Detail Inspection**: Inspect brand-specific components (hero, pricing cards, feature grids, etc.)
4. **Pass 4 — Synthesis**: Combine all extracted data into the DESIGN.md document

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | Yes | — | Target website URL to analyze (e.g., `https://stripe.com`) |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `design_md` | text | The generated DESIGN.md document content |
| `messages` | json | Full conversation messages between the agent and GPT-4o |

## Component Details

### Browser Component (`browser`)

- **Type**: `web-browser`
- **Driver**: Chrome (CDP)
- **Host**: `localhost:9222`
- **Timeout**: 60 seconds
- **Concurrency**: 1 (serial execution)

#### Available Actions

| Action | Method | Description |
|--------|--------|-------------|
| `navigate` | `navigate` | Navigate to a URL and wait for page load |
| `extract-html` | `extract` | Extract HTML content by CSS selector |
| `extract-text` | `extract` | Extract text content by CSS selector |
| `evaluate` | `evaluate` | Execute arbitrary JavaScript in the page |
| `scroll` | `scroll` | Scroll the page by pixel offset |

### GPT-4o Component (`gpt-4o`)

- **Type**: `http-client`
- **API**: OpenAI Chat Completions (`/v1/chat/completions`)
- **Model**: `gpt-4o`
- **Max Tokens**: 16,384

### Design MD Generator Component (`design-md-generator`)

- **Type**: `agent`
- **Model**: GPT-4o (via the `gpt-4o` component)
- **Max Iterations**: 20
- **Tools**: 8 browser-based workflows for design inspection

#### Agent Tools

| Tool | Description |
|------|-------------|
| `navigate_to_url` | Open any URL in the browser |
| `extract_page_structure` | Get structural outline of the page (sections, IDs, classes, headings) |
| `extract_page_html` | Get HTML of specific elements via CSS selector |
| `extract_computed_styles` | Get exact computed CSS of elements (colors, fonts, spacing, shadows) |
| `extract_color_palette` | Scan all elements for unique background, text, border, and shadow colors |
| `extract_typography` | Scan all text elements for unique font combinations |
| `extract_spacing_and_radii` | Collect all unique spacing and border-radius values |
| `scroll_page` | Scroll the page to reveal below-the-fold content |

## System Details

### Docker Container Architecture

The `chrome-with-novnc` system runs a single Alpine-based container with the following services managed by supervisord:

| Service | Port | Description |
|---------|------|-------------|
| Xvfb | — | Virtual framebuffer (display `:99`, 1920x1080) |
| Chromium | 9222 | Browser with CDP remote debugging |
| x11vnc | 5900 | VNC server mirroring the virtual display |
| noVNC | 6080 | Web-based VNC client |
| socat | 9223 | TCP proxy for external CDP access |

**Port mapping**: `9222→9223` (CDP), `6080→6080` (noVNC)

## Customization

### Use a Different Model
Replace the `gpt-4o` component with another OpenAI-compatible model:
```yaml
components:
  - id: gpt-4o
    type: http-client
    base_url: https://api.openai.com/v1
    action:
      body:
        model: gpt-4o-mini  # or any other model
        max_tokens: 16384
```

### Adjust Agent Iterations
Increase `max_iteration_count` for more thorough analysis of complex sites:
```yaml
components:
  - id: design-md-generator
    type: agent
    max_iteration_count: 30  # default: 20
```

### Change Screen Resolution
Set environment variables in the `Dockerfile`:
```dockerfile
ENV SCREEN_WIDTH=2560
ENV SCREEN_HEIGHT=1440
```

## Troubleshooting

### Common Issues

1. **Container build fails**: Ensure Docker is running (`docker info`)
2. **CDP connection timeout**: The container may take a few seconds to start. model-compose retries automatically within the configured timeout (60s)
3. **Agent exceeds iteration limit**: Complex sites may require more iterations. Increase `max_iteration_count` in the agent component
4. **noVNC not accessible**: Check that port `6080` is not in use (`lsof -i :6080`)
5. **OpenAI API errors**: Verify your `OPENAI_API_KEY` is valid and has sufficient quota
6. **Shared memory errors**: The container uses `shm_size: 2gb` to prevent Chromium crashes. Increase if needed

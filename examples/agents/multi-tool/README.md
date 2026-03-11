# Multi-Tool Assistant Agent Example

This example demonstrates a versatile assistant agent that combines multiple tools — web search, weather lookup, calculator, and clock — to answer a wide range of questions.

## Overview

The agent operates through a ReAct loop:

1. **Receive Question**: The user asks any question
2. **Select Tools**: The agent decides which tools to use based on the question
3. **Execute & Combine**: The agent calls tools, combines results, and reasons about them
4. **Answer**: Produces a comprehensive answer using gathered information

### Available Tools

| Tool | Description |
|------|-------------|
| `search_web` | Search the web using Tavily API |
| `get_weather` | Get current weather for a city |
| `run_calculation` | Execute Python expressions for math |
| `get_current_time` | Get current date and time |

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- OpenAI API key
- Tavily API key ([tavily.com](https://tavily.com))
- OpenWeatherMap API key ([openweathermap.org](https://openweathermap.org/api))

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/agents/multi-tool
   ```

2. Copy the sample environment file:
   ```bash
   cp .env.sample .env
   ```

3. Edit `.env` and add your API keys:
   ```env
   OPENAI_API_KEY=your-openai-api-key
   TAVILY_API_KEY=your-tavily-api-key
   OPENWEATHER_API_KEY=your-openweathermap-api-key
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
     -d '{"question": "What is the weather in Tokyo and what time is it there?"}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Enter your question and click "Run Workflow"

   **Using CLI:**
   ```bash
   model-compose run --input '{"question": "Calculate 2^64 and search for what that number represents"}'
   ```

## Component Details

### OpenAI GPT-4o Component (gpt-4o)
- **Type**: HTTP client component
- **Purpose**: LLM for agent reasoning and tool selection
- **API**: OpenAI GPT-4o Chat Completions with function calling

### Tavily Search Component (tavily)
- **Type**: HTTP client component
- **Purpose**: Web search API
- **API**: Tavily Search API

### Weather API Component (weather-api)
- **Type**: HTTP client component
- **Purpose**: Current weather data
- **API**: OpenWeatherMap API

### Calculator Component (calculator)
- **Type**: Shell component
- **Purpose**: Execute Python expressions for calculations

### Clock Component (clock)
- **Type**: Shell component
- **Purpose**: Get current date and time

### Assistant Agent Component (assistant)
- **Type**: Agent component
- **Purpose**: Multi-tool assistant that orchestrates all tools
- **Max Iterations**: 10

## Workflow Details

### Tool: search_web

**Description**: Search the web for information on a given query.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | - | The search query string |
| `max_results` | integer | No | `5` | Maximum number of search results |

### Tool: get_weather

**Description**: Get the current weather for a city.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `city` | string | Yes | - | City name, e.g. "Tokyo" or "London,UK" |

### Tool: run_calculation

**Description**: Execute a Python expression to perform mathematical calculations.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `expression` | string | Yes | - | Python expression to evaluate, e.g. "print(2 ** 10)" |

### Tool: get_current_time

**Description**: Get the current date and time with timezone information.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| - | - | - | - | This tool requires no input parameters |

## Customization

- Replace `gpt-4o` with other models that support function calling
- Add more tools by defining additional workflows (e.g., translation, image generation)
- Remove unused tools for simpler use cases
- Adjust `max_iteration_count` to control agent depth

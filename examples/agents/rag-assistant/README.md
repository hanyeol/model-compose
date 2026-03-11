# RAG Assistant Agent Example

This example demonstrates an autonomous agent that uses Retrieval-Augmented Generation (RAG) to answer questions by searching and adding knowledge to a ChromaDB vector store.

## Overview

The agent operates through a ReAct loop:

1. **Receive Question**: The user provides a question
2. **Search Knowledge**: The agent searches the vector store for relevant information
3. **Add Knowledge**: The agent can also add new knowledge to the store
4. **Answer**: After retrieving relevant context, the agent produces an informed answer

### Available Tools

| Tool | Description |
|------|-------------|
| `search_knowledge` | Search the knowledge base for relevant documents |
| `add_knowledge` | Add new knowledge to the knowledge base |

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- OpenAI API key
- ChromaDB (installed automatically as a dependency)

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/agents/rag-assistant
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
     -d '{"question": "What do you know about model-compose?"}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Enter your question and click "Run Workflow"

   **Using CLI:**
   ```bash
   model-compose run --input '{"question": "What do you know about model-compose?"}'
   ```

## Component Details

### OpenAI GPT-4o Component (gpt-4o)
- **Type**: HTTP client component
- **Purpose**: LLM for agent reasoning (chat action) and text embedding (embedding action)
- **API**: OpenAI Chat Completions + Embeddings API

### Vector Store Component (vector-store)
- **Type**: Vector store component
- **Purpose**: Store and search knowledge embeddings
- **Driver**: ChromaDB
- **Collection**: `knowledge`

### RAG Assistant Agent Component (rag-assistant)
- **Type**: Agent component
- **Purpose**: Autonomous RAG agent that searches and manages knowledge
- **Max Iterations**: 5

## Workflow Details

### Tool: search_knowledge

**Description**: Search the knowledge base for relevant information.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | - | The search query to find relevant knowledge |

### Tool: add_knowledge

**Description**: Add a new piece of knowledge to the knowledge base.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `text` | string | Yes | - | The text content to add to the knowledge base |
| `source` | string | No | `user-input` | Source or origin of the knowledge |

## Customization

- Replace `text-embedding-3-small` with other embedding models
- Switch ChromaDB to Milvus or other vector store drivers
- Adjust `max_iteration_count` to control retrieval depth
- Add more tools (e.g., web search) to combine RAG with live data

# Chat Completion Message — Canonical Format

The canonical representation of a chat message inside model-compose. All agent components and chat-completion model tasks operate on this shape. Provider-specific formats (OpenAI, Anthropic, Gemini, …) are translated to and from this canonical form by provider adapters — never by user DSL.

## Rationale

- **One shape, one place to reason.** Message history is passed between components as data. A stable canonical shape means callers do not need to know which provider produced or will consume the message.
- **Adapters absorb provider differences.** Semantic reshuffling (Anthropic's system-as-top-level, tool_result-in-user-role; Gemini's no-tool-call-id; OpenAI's JSON-string arguments; role alternation and adjacent-role merging) belongs in imperative adapter code, not DSL mapping. This mirrors how LangChain, Vercel AI SDK, LiteLLM, and Haystack all solve the same problem.
- **Extensible by design.** Adding new content kinds (image, audio, reasoning, citations) means adding a new block type, not reshaping the message.

## Message

```python
{
    "role": "system" | "user" | "assistant" | "tool",
    "content": [Block, ...]
}
```

| Field | Type | Notes |
|-------|------|-------|
| `role` | string | One of `system`, `user`, `assistant`, `tool`. Role names in provider payloads may differ (e.g. Gemini's `model` for assistant) — adapters handle the rename. |
| `content` | list of Block | Ordered content of the message. Always a list of typed blocks, never a bare string — even for text-only messages. |

Every block has a `type` field that discriminates the union. Unknown types are ignored by the adapter (forward-compatible).

### `text`

```python
{ "type": "text", "text": str }
```

Plain text content. Multiple text blocks in one message are concatenated by the adapter when the provider expects a single string.

### `tool_call`

```python
{
    "type": "tool_call",
    "id": str,          # identifier used to correlate with the matching tool_result
    "name": str,        # tool name
    "arguments": dict   # parsed arguments (never a JSON string, even for OpenAI-origin messages)
}
```

Appears only in `assistant` messages.

### `tool_result`

```python
{
    "type": "tool_result",
    "id": str,          # must match a preceding tool_call.id
    "content": str,     # tool output serialized as a string (JSON-encoded if the tool returned a dict/list)
    "is_error": bool    # optional; present and true only when the tool failed
}
```

Appears only in `tool` messages. Built-in producers (agent components) emit **one `tool_result` per `tool` message** — parallel tool calls produce multiple adjacent `tool` messages, one per result. The shape technically permits multiple `tool_result` blocks in a single `tool` message, but consumers should not rely on it; user code that manufactures messages should follow the one-per-message convention so downstream adapters can perform stateless variable mapping.

### Extension blocks (reserved)

Not yet emitted by any built-in adapter, but the shape is reserved:

- `{"type": "image", "source": {...}}`
- `{"type": "audio", "source": {...}}`
- `{"type": "file", "source": {...}}`
- `{"type": "reasoning", "text": str}` — for Anthropic extended thinking / OpenAI o1-style hidden reasoning

## Rules

1. **`content` is always a list of blocks.** Never elide to a string, even for a single text block. Consumers can rely on the list shape.
2. **`is_error` is present only when true.** Success case omits the field entirely.
3. **`tool_call.arguments` is a dict.** Adapters parse JSON on the way in, serialize on the way out.
4. **`tool_call.id` must be unique within a conversation** and referenced by exactly one `tool_result.id`. For providers without native tool-call IDs (Gemini), the adapter assigns one and maintains the linkage internally.
5. **Adjacent same-role messages should be merged** — assistant+assistant into one message with concatenated blocks, tool+tool likewise. Adapters perform this at the wire boundary if the provider requires strict role alternation (Anthropic).
6. **System messages carry a single text block.** Adapters extract this to top-level fields where the provider requires it (Anthropic `system`, Gemini `systemInstruction`).

## Provider Mapping Summary

The following mappings are performed by adapters. Users do not write these — they are shown here to make the canonical's design decisions traceable.

| Canonical | OpenAI Chat Completions | Anthropic Messages | Google Gemini |
|-----------|-------------------------|--------------------|---------------|
| `role: system` | `{role: system, content: str}` | top-level `system` field | top-level `systemInstruction` |
| `role: user` | `{role: user, content: str \| [parts]}` | `{role: user, content: [blocks]}` | `{role: user, parts: [...]}` |
| `role: assistant` | `{role: assistant, content, tool_calls}` | `{role: assistant, content: [blocks]}` | `{role: model, parts: [...]}` |
| `role: tool` | `{role: tool, tool_call_id, content}` (one per result) | `{role: user, content: [{type: tool_result, ...}]}` | `{role: user, parts: [{functionResponse}, ...]}` |
| `content[type=text]` | `content` (str) or `{type: text, text}` | `{type: text, text}` | `{text}` |
| `content[type=tool_call]` | `tool_calls[].function.{name, arguments: JSON str}` | `{type: tool_use, id, name, input}` | `{functionCall: {name, args}}` |
| `content[type=tool_result]` | `role: tool` message | `{type: tool_result, tool_use_id, content, is_error}` | `{functionResponse: {name, response}}` |
| `tool_call.arguments` (dict) | JSON string (`json.dumps`) | dict (`input`) | dict (`args`) |
| `tool_call.id` | `call_*` string | `toolu_*` string | (none — adapter maintains internal linkage) |

## Examples

### A simple text turn

```python
[
  { "role": "user",      "content": [{"type": "text", "text": "What time is it in Seoul?"}] },
  { "role": "assistant", "content": [{"type": "text", "text": "It is 3:14 PM in Seoul."}] }
]
```

### Assistant calls two tools in parallel; each result comes back as its own tool message

```python
[
  { "role": "user", "content": [{"type": "text", "text": "Compare weather in SF and Tokyo."}] },
  {
    "role": "assistant",
    "content": [
      { "type": "text", "text": "Let me check both cities." },
      { "type": "tool_call", "id": "a", "name": "get_weather", "arguments": {"city": "SF"} },
      { "type": "tool_call", "id": "b", "name": "get_weather", "arguments": {"city": "Tokyo"} }
    ]
  },
  { "role": "tool", "content": [{"type": "tool_result", "id": "a", "content": "{\"temp_c\": 15, \"cond\": \"foggy\"}"}] },
  { "role": "tool", "content": [{"type": "tool_result", "id": "b", "content": "{\"temp_c\": 22, \"cond\": \"clear\"}"}] },
  { "role": "assistant", "content": [{"type": "text", "text": "SF is 15 °C and foggy; Tokyo is 22 °C and clear."}] }
]
```

### A tool that failed

```python
{
  "role": "tool",
  "content": [
    { "type": "tool_result", "id": "a", "content": "TimeoutError: upstream took too long", "is_error": true }
  ]
}
```

## Model Component Contract

The agent component sends canonical messages to its `model.component` and expects a **canonical assistant message** back. The user's `model.output` mapping is responsible for translating each provider's response shape into the canonical form.

Minimum contract for `model.output`:

```yaml
role: assistant
content:
  - { type: text, text: "..." }                                # 0 or 1
  - { type: tool_call, id: ..., name: ..., arguments: {...} }  # 0 or more
```

The agent inspects `content[*].type == "tool_call"` to decide whether to continue the tool loop or return. `text` blocks with no `tool_call` blocks terminate the loop.

### OpenAI Chat Completions → canonical

```yaml
output:
  role: assistant
  content:
    "+":
      - "?":
          input: ${response.choices[0].message.content}
          operator: neq
          value: null
          if_true:
            - type: text
              text: ${response.choices[0].message.content}
      - "*": ${response.choices[0].message.tool_calls}
        type: tool_call
        id: ${item.id}
        name: ${item.function.name}
        arguments: ${item.function.arguments as json}
```

Notes: OpenAI serializes `arguments` as a JSON string; the `as json` cast parses it to a dict as the canonical requires. `content` is `null` when the assistant only calls tools; the `?` branch drops the text block in that case.

### Anthropic Messages → canonical

```yaml
output:
  role: assistant
  content:
    "*": ${response.content}
    "?":
      - input: ${item.type}
        value: text
        if_true: { type: text, text: ${item.text} }
      - input: ${item.type}
        value: tool_use
        if_true:
          type: tool_call
          id: ${item.id}
          name: ${item.name}
          arguments: ${item.input}
```

Anthropic returns content blocks directly under `response.content`; the mapping just relabels `tool_use` → `tool_call` and passes `input` through as `arguments` (already a dict).

### Google Gemini → canonical

```yaml
output:
  role: assistant
  content:
    "*": ${response.candidates[0].content.parts}
    "?":
      - input: ${item.text}
        operator: neq
        value: null
        if_true: { type: text, text: ${item.text} }
      - input: ${item.functionCall}
        operator: neq
        value: null
        if_true:
          type: tool_call
          id: ""
          name: ${item.functionCall.name}
          arguments: ${item.functionCall.args}
```

Gemini has no native tool-call IDs; leave `id` blank and the agent's tool-result linkage stays positional within the turn.

## Provider-Specific Sidecar (reserved)

For provider-specific fields that do not fit the canonical (Anthropic `cache_control`, `thinking`; OpenAI `logprobs` request flags; Gemini `safetySettings` at the block level), the reserved sidecar is:

```python
{
    "type": "text",
    "text": "...",
    "provider_options": {
        "anthropic": { "cache_control": { "type": "ephemeral" } }
    }
}
```

Not yet consumed by any adapter. Documented here so future adoption does not require changing the canonical shape.

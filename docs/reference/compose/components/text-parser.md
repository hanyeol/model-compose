# Text Parser Component

The text parser component extracts structured data (JSON, YAML, XML, tables, lists, regex matches, or raw code blocks) out of noisy free-form text. It is designed for LLM outputs that mix natural language with the payload you actually care about — code fences, trailing commas, `//` comments, and tag-wrapped answers are handled leniently so workflows can consume clean values without brittle post-processing.

## Basic Configuration

```yaml
component:
  type: text-parser
  action:
    text: ${input.llm_output}
    format: json
    strategy: largest
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `text-parser` |
| `actions` | array | `[]` | List of text parsing actions |

### Action Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `text` | string / array / stream | **required** | Input text (or list/stream of texts) to parse |
| `format` | string | `json` | Structured format: `json` \| `yaml` \| `code` \| `xml` \| `list` \| `table` \| `regex` |
| `strategy` | string | `largest` | Which candidate to return when multiple matches are found: `first` \| `last` \| `all` \| `largest` |
| `fallback` | any | `null` | Value returned when no candidate is extracted |
| `batch_size` | integer | `null` | Number of input texts processed per batch |
| `json_schema` | object | `null` | JSON Schema validated against the extracted result (`json` format only). Requires the `jsonschema` package |
| `xml_root` | string | `null` | Extract only the block whose root tag matches (`xml` format only) |
| `xml_output` | string | `text` | Return the raw XML block string (`text`) or a parsed dict (`dict`) — `xml` format only |
| `list_separator` | string | `,` | Item separator for the `list` format |
| `table_column_separator` | string | `,` | Column separator for the `table` format (`\t` for TSV, `;` for European CSV) |
| `table_row_separator` | string | `\n` | Row separator for the `table` format |
| `table_header` | bool | `true` | If true, treat the first row as headers (returns `List[Dict]`); else returns `List[List[str]]` |
| `table_quote` | string | `"` | Quote character for the `table` format |
| `regex_pattern` | string | `null` | Regex pattern (`regex` format only). Required when `format: regex` |
| `regex_flags` | string | `""` | Combination of `i` (IGNORECASE), `s` (DOTALL), `m` (MULTILINE) |

## Format Behavior

| format | Return type | Notes |
|--------|-------------|-------|
| `json` | `dict` / `list` | Tries whole-string parse → fenced code blocks → balanced `{}`/`[]` spans. Cleans `//`/`/* */` comments and trailing commas. Deduplicates candidates by serialized form. |
| `yaml` | `dict` / `list` | Parses fenced code blocks and `---`-separated documents via `yaml.safe_load`. Scalar results (plain strings/numbers) are excluded. |
| `code` | `str` | Returns full fenced code blocks with the ` ```lang ` and closing ` ``` ` lines preserved. |
| `xml` | `str` or `dict` | Matches `<tag>...</tag>` spans that parse as valid XML. `xml_root` filters by root tag. `xml_output: dict` converts to xmltodict-style dict (attributes as `@name`, mixed text as `#text`, leaf collapses to text). |
| `list` | `List[str]` | Splits on `list_separator`, strips whitespace, drops empty items. |
| `table` | `List[Dict]` or `List[List[str]]` | Uses Python's `csv` module (respects quoting/escaping). `table_row_separator` other than `\n` is normalized first. |
| `regex` | `dict` / `List[str]` / `str` | Applies `regex_pattern` with `regex_flags`. Named groups return `dict`; unnamed groups return `List[str]`; no groups returns the full match string. |

## Strategy

When several candidates are extracted (e.g., multiple JSON objects in the same text), `strategy` picks which one to return:

- `first` — first candidate
- `last` — last candidate
- `all` — every candidate as a list
- `largest` (default) — candidate whose serialized form is longest (usually the most informative payload)

The `list` and `table` formats always produce a single candidate, so `strategy` has no effect on them.

## Usage Examples

### Extract JSON from a chatty LLM response

```yaml
components:
  - id: parser
    type: text-parser
    actions:
      - id: extract-answer
        text: ${jobs.ask-llm.output}
        format: json
        strategy: largest
        fallback: { answer: null, confidence: 0 }
```

Handles inputs like:

```
Sure! Here's what I found:
```json
{"answer": 42, "confidence": 0.9}
```
Hope this helps!
```

### Validate the extraction against a schema

```yaml
- id: parse-typed-answer
  text: ${jobs.ask-llm.output}
  format: json
  json_schema:
    type: object
    required: [answer, confidence]
    properties:
      answer:     { type: integer }
      confidence: { type: number, minimum: 0, maximum: 1 }
  fallback: { answer: null, confidence: 0 }
```

If the extracted object fails validation, `fallback` is returned instead — pair this with a conditional retry job for LLM-fixing patterns.

### Parse CSV/TSV output

```yaml
- id: parse-table
  text: ${jobs.tabular-llm.output}
  format: table
  table_header: true
  # → [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}]

- id: parse-tsv
  text: ${jobs.tsv-tool.output}
  format: table
  table_column_separator: "\t"
```

### Extract a specific XML tag

```yaml
# Return the raw <answer>...</answer> block
- id: pick-answer-tag
  text: ${jobs.tagged-output.output}
  format: xml
  xml_root: answer
  xml_output: text

# Parse a <person> block into a dict
- id: parse-person
  text: ${jobs.tagged-output.output}
  format: xml
  xml_root: person
  xml_output: dict
  # → {"name": "Alice", "age": "30"}
```

### Grab values with a regex

```yaml
- id: extract-weather
  text: ${input.report}
  format: regex
  regex_pattern: "temperature is (?P<temp>[\\d.]+)°C, humidity (?P<humidity>\\d+)%"
  strategy: first
  # → {"temp": "23.5", "humidity": "67"}
```

Unnamed groups return a list instead:

```yaml
- id: extract-pairs
  text: "a=1 b=2 c=3"
  format: regex
  regex_pattern: "(\\w+)=(\\d+)"
  strategy: all
  # → [["a", "1"], ["b", "2"], ["c", "3"]]
```

### Extract a comma-separated list

```yaml
- id: parse-tags
  text: ${jobs.tag-suggester.output}
  format: list
  # "python, machine-learning, data-science" → ["python", "machine-learning", "data-science"]
```

### Extract fenced code blocks

```yaml
- id: extract-code
  text: ${jobs.llm.output}
  format: code
  strategy: all
  # → ["```python\ndef foo(): ...\n```", "```sql\nSELECT ...\n```"]
```

## LangChain-style Output Fixing Pattern

Use conditional job execution instead of a special "fixing" parser:

```yaml
workflows:
  - id: parse-with-retry
    jobs:
      - id: ask-llm
        component: llm
        action: generate

      - id: parse
        component: parser
        action: extract-answer
        input: { text: ${jobs.ask-llm.output} }
        depends_on: [ask-llm]

      - id: retry
        component: llm
        action: fix
        if: ${jobs.parse.output.answer == null}
        input:
          prompt: "The previous response was invalid. Fix it: ${jobs.ask-llm.output}"
        depends_on: [parse]
```

## Streaming Input

If `text` resolves to an async iterator (e.g., an upstream streaming component's output), the parser processes each chunk independently and returns a streaming result. Parsing itself is not chunk-oriented — each stream item is treated as a complete input.

## Variable Interpolation

All fields support variable interpolation:

```yaml
- id: dynamic-parse
  text: ${input.text}
  format: ${input.format | 'json'}
  strategy: ${input.strategy | 'largest'}
  regex_pattern: ${input.pattern}
```

## Best Practices

1. **Prefer `largest` for JSON**: LLMs often mix small partial objects with the final answer — `largest` reliably picks the payload.
2. **Always set `fallback`**: A `null` return on parse failure is often a workflow bug amplifier. Set a shape-preserving default so downstream jobs stay type-stable.
3. **Use `json_schema` to catch shape drift**: When the LLM output structure matters, validate. Combine with a conditional retry job for self-healing pipelines.
4. **Reach for `regex` for surgical extractions**: When the payload has no JSON/XML structure but a predictable pattern (numbers in prose, "key: value" lines), `regex` is faster and more robust than post-processing free text.
5. **`xml_output: dict` when consuming**: If the workflow needs to reach into extracted XML fields, ask for `dict` output up front rather than parsing the returned string.

## Common Use Cases

- **Cleaning LLM JSON output**: Recover structured data from chatty completions
- **Schema-checked extraction**: Enforce output contracts with JSON Schema validation
- **Answer-tag extraction**: Pull `<answer>...</answer>` or `<thinking>...</thinking>` blocks out of chain-of-thought responses
- **CSV/TSV parsing**: Convert model-generated tables into workflow-friendly records
- **Regex-based fact extraction**: Pick numbers, dates, or key-value pairs out of natural-language text
- **Code block extraction**: Isolate generated code from surrounding explanations

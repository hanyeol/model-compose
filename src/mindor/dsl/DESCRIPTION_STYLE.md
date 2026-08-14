# Pydantic Field Description Style Guide

This guide standardizes the `description=` values on every `pydantic.Field` in
`src/mindor/dsl/`. Descriptions are the primary user-facing documentation for
the compose DSL — they show up in JSON Schema exports, IDE hover hints, and the
generated reference under `docs/reference/compose/`. Consistency across ~1,800
fields matters more than clever wording in any single field.

Follow this guide when adding a new field or editing an existing one. When a
rule conflicts with a compelling reason to break it, keep the reason in the
description itself; do not invent silent exceptions.

---

## 1. Form and grammar

### 1.1 Shape: noun phrase, not a full sentence

Start with a noun phrase describing *what the value is* or *what it controls*.
Do not start with a verb like "Specifies…", "Defines…", "Sets…" — those add
words without information.

- ✅ `"TCP port the HTTP controller listens on."`
- ✅ `"Maximum number of actions this component runs concurrently."`
- ❌ `"Specifies the TCP port the HTTP controller listens on."`
- ❌ `"This field defines the maximum number of concurrent actions."`

Boolean flags are the one exception: they read more naturally as a
`Whether …` clause, since the value is a yes/no answer.

- ✅ `"Whether to run tasks in separate threads."`
- ✅ `"Whether streaming output is emitted incrementally."`

### 1.2 Case: sentence case

Only the first word and proper nouns are capitalized. Product names
(`HuggingFace`, `Redis`, `Langfuse`, `Docker`, `SSH`, `HTTP`, `MCP`, `TCP`,
`URL`, `TLS`, `JSON`) keep their canonical casing.

### 1.3 Punctuation: end with a period

Every description ends with a period, including one-liners. This matches the
existing 99% pattern in the codebase and lets tooling concatenate descriptions
without stitching punctuation.

### 1.4 Length: one sentence, 40–120 characters

Aim for a single sentence that fits on one line at typical IDE widths. If the
concept genuinely needs more, add **one** second sentence for a constraint or
default, and stop.

- ✅ `"Maximum seconds to wait for the request before failing."`
- ✅ `"HTTP method used to send the request. Defaults to POST when a body is set."`
- ❌ Multi-paragraph descriptions. Move that content to `docs/reference/`.

### 1.5 Voice: user perspective, not implementation

Describe what a compose author sees or controls, not how the runtime is wired.

- ✅ `"Model identifier — a HuggingFace repo ID or a local path."`
- ❌ `"Passed to AutoModel.from_pretrained as the model_name_or_path argument."`

Domain-specific jargon (LoRA, VAE, LLM, embedding, tokenizer, checkpoint) is
fine — users of those fields already know it. Python/framework jargon
(`Dict`, `Optional`, `discriminated union`, `pydantic`) is not.

---

## 2. Content rules

### 2.1 Prefer a short, natural phrase over cleverness

Short forms like `"ID of component."` or `"Type of component."` are fine —
they are unambiguous, they match the shape of the field name, and they read
cleanly in generated docs. Do not rewrite them into longer paraphrases just
to avoid repeating the field name.

- ✅ `id: str = Field(..., description="ID of component.")`
- ✅ `type: ComponentType = Field(..., description="Type of component.")`
- ✅ `name: str = Field(..., description="Name of workflow.")`

Reach for a longer form only when the short one is genuinely ambiguous or
misleading — for example, when the same field name means something different
in a nearby schema, or when a compose author needs to know *where* the value
shows up (`"Name shown in the Web UI and logs."`).

Never inflate a description with filler words (`"Specifies the ID that uniquely
identifies…"`) — that is the antipattern.

### 2.2 State the scope, not just the kind

A word like `port`, `timeout`, `headers`, `driver`, `model`, or `url` appears
in many schemas. The description must anchor it to the surrounding context —
which server, which request, which backend.

- ❌ `port: int = Field(..., description="Port number.")`
- ✅ `port: int = Field(..., description="TCP port the Redis server listens on.")`
- ❌ `timeout: float = Field(..., description="Timeout in seconds.")`
- ✅ `timeout: float = Field(..., description="Maximum seconds to wait for the polling response before failing.")`

### 2.3 Do not restate the default

The default lives in `Field(default=…)` and is already surfaced in generated
docs and IDE hints. Repeating it in prose invites drift.

- ❌ `Field(default=8080, description="Port to bind. Defaults to 8080.")`
- ✅ `Field(default=8080, description="TCP port the HTTP controller binds on.")`

Exception: if the default's *meaning* is non-obvious (e.g., `0` means unlimited,
`""` means auto-detect), name that meaning inline.

- ✅ `Field(default=0, description="Maximum concurrent actions; 0 means unbounded.")`

### 2.4 Do not restate the type

The type annotation is authoritative. Do not say "A list of…", "An integer
representing…", or "String value that…". Just describe the value.

- ❌ `actions: List[Action] = Field(..., description="A list of actions.")`
- ✅ `actions: List[Action] = Field(..., description="Actions this component exposes to workflows.")`

Exception: when the accepted types carry semantic meaning (e.g., duration
strings like `"30s"` alongside numbers), spell it out.

- ✅ `Field(..., description="Delay before shutdown starts, as a duration string (e.g., \"30s\") or seconds.")`

### 2.5 Declare cross-field relationships

If a field is mutually exclusive with, or required alongside, another field,
say so — the type system cannot express this.

- ✅ `"Full URL for the request. Mutually exclusive with `path`."`
- ✅ `"Callback URL. Required when `completion.type` is `callback`."`

Wrap referenced field names in backticks.

### 2.6 Show a hint only for opaque formats

Inline `(e.g., …)` examples are for values whose shape a user cannot guess:
duration strings, URI schemes, reserved keywords, backend-specific identifiers.
Do not add examples for obvious values.

- ✅ `"Base URL for the WebSocket endpoint (e.g., ws://host:port or wss://host:port)."`
- ❌ `"HTTP method (e.g., GET)."`

---

## 3. Canonical templates for cross-cutting fields

These fields appear across many schemas. Match the template unless a
schema-specific nuance requires deviation — then still keep the shape.

| Field         | Template                                                                                       |
| ------------- | ---------------------------------------------------------------------------------------------- |
| `id`          | `ID of <entity>.`                                                                              |
| `name`        | `Name of <entity>.`                                                                            |
| `type`        | `Type of <entity>.`                                                                            |
| `driver`      | `Backend implementation used for <purpose>.`                                                   |
| `port`        | `TCP port <the server> listens on.`                                                            |
| `host`        | `Hostname or IP address of the <server>.`                                                      |
| `url`         | `Full URL of the <endpoint>.` (add `(e.g., …)` only for non-http schemes)                      |
| `path`        | `URL path appended to the base URL.`                                                           |
| `headers`     | `HTTP headers sent with the <request/callback/poll>.`                                          |
| `params`      | `<Query/URL/workflow input> parameters passed to the <target>.`                                |
| `method`      | `HTTP method used for the <request/poll/callback>.`                                            |
| `timeout`     | `Maximum seconds to wait for <operation> before failing.`                                      |
| `retries`     | `Number of times to retry <operation> after a failure.`                                        |
| `batch_size`  | `Number of <items> processed per batch.`                                                       |
| `max_concurrent_count` | `Maximum concurrent <units> this <entity> runs; 0 means unbounded.`                   |
| `enabled`     | `Whether <feature> is active.`                                                                 |
| `default`     | `Whether to use this <entity> when none is explicitly selected.`                               |
| `runtime`     | `Runtime environment in which this <entity> executes.`                                         |
| `model`       | `Model identifier — a HuggingFace repo ID or a local path.`                                    |
| `device`      | `Compute device the model runs on (e.g., cpu, cuda, cuda:0, mps).`                             |
| `dtype`       | `Numeric precision used for model weights and computation (e.g., float16, bfloat16, float32).` |
| `streaming`   | `Whether output is emitted incrementally as it is produced.`                                   |
| `actions`     | `Actions this <entity> exposes to workflows.`                                                  |
| `output`      | `Output mapping that transforms and extracts values from the <entity>'s result.`               |

Do not paraphrase the template into a different shape just to look different.
Repetition across schemas is the point — a user who has read one `port`
description should recognize every other one.

---

## 4. Rules for base classes and inheritance

`CommonComponentConfig`, `CommonActionConfig`, `CommonRuntimeConfig`,
`CommonListenerConfig`, `CommonTracerConfig`, and `CommonLoggerConfig` define
fields inherited by dozens of subclasses. Descriptions on those base fields
propagate everywhere — spend extra care there.

- Write the base description in terms that apply to *every* subclass. If it
  cannot, promote the field to a subclass instead.
- Do **not** override a base description in a subclass unless the subclass
  meaningfully narrows the semantics (e.g., `HttpClientAction.output` extracts
  from an HTTP response specifically).
- When overriding, keep the same shape and templates as the base — only the
  scope words change.

---

## 5. Anti-patterns checklist

Before committing, grep the description for these patterns. Each one is a
smell that usually means the description needs a rewrite.

- Starts with `Specifies`, `Defines`, `Sets`, `Represents`, `Indicates`, `Contains`.
- Ends without a period.
- Contains `Options for` or `Config for` with no further specificity.
- Contains `Defaults to <literal>` where `<literal>` matches `default=`.
- Contains Python type words: `Dict`, `List`, `Optional`, `Union`, `Tuple`,
  `dict`, `list`, `string value`, `boolean flag`, `integer number`.
- Contains a full URL that is not an example (put URLs in docs, not schema).
- Is longer than 200 characters.
- Is missing entirely on a public field.

`scripts/lint_descriptions.py` (planned in Phase 3) will mechanically enforce
the checkable subset of these rules.

---

## 6. Worked examples

### Before

```python
class ControllerConfig(BaseModel):
    name: Optional[str] = Field(default=None, description="Controller identifier name.")
    max_concurrent_count: int = Field(default=0, description="Max tasks executed concurrently.")
    shutdown_pending_period: Union[str, int, float] = Field(default="0s", description="Delay before shutdown starts, allowing traffic to drain.")
    shutdown_timeout: Union[str, int, float] = Field(default="30s", description="Max wait time for in-progress tasks during shutdown.")
    threaded: bool = Field(default=False, description="Whether to run tasks in separate threads.")
```

### After

```python
class ControllerConfig(BaseModel):
    name: Optional[str] = Field(default=None, description="Name of controller.")
    max_concurrent_count: int = Field(default=0, description="Maximum concurrent tasks; 0 means unbounded.")
    shutdown_pending_period: Union[str, int, float] = Field(default="0s", description="Grace period before shutdown begins, allowing traffic to drain.")
    shutdown_timeout: Union[str, int, float] = Field(default="30s", description="Maximum time to wait for in-progress tasks during shutdown.")
    threaded: bool = Field(default=False, description="Whether to run tasks on separate worker threads.")
```

Notes on the "After" version:
- `name`: kept short — the field name is self-explanatory (§2.1).
- `max_concurrent_count`: the default `0` has a non-obvious meaning
  (*unbounded*), so it is spelled out inline (§2.3, exception).
- `shutdown_pending_period` / `shutdown_timeout`: tightened wording, dropped
  the `Max`/`Delay` shorthand, no default value restated (§2.3).
- `threaded`: added *worker* for scope; still a `Whether` boolean.

---

## 7. When you are unsure

- Ask: *"If I only had this description and the field name, could I use this
  field correctly?"* If no, add the missing piece.
- Ask: *"Am I telling the user what the value is, or how the code uses it?"*
  If the latter, rewrite from the user's perspective.
- When two descriptions collide (base vs. subclass, or two similar fields in
  different schemas), copy the shape from the canonical template in §3 rather
  than inventing a third phrasing.

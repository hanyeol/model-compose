# Text Renderer Component

The text renderer component substitutes `${...}` slots in a template string with values from job inputs and prior outputs, returning the rendered text. It replaces the common `shell` + `printf` detour for prompt assembly and other string-building use cases where the only work is slot filling.

Because every component's inputs are already interpolated by model-compose before the action runs, this component's job is to expose that interpolated template as its own output — no processing, no post-formatting.

## Basic Configuration

```yaml
component:
  type: text-renderer
  action:
    template: |-
      Hello, ${input.name}!
      Your role is ${input.role}.
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `text-renderer` |
| `actions` | array | `[]` | List of text rendering actions |

### Action Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `template` | string / array / stream | **required** | Template text (or list/stream of templates) to render into the action output |
| `batch_size` | integer | `null` | Number of input templates processed per batch when `template` is a list or stream |

## Template Syntax

The `template` field uses the same `${...}` variable interpolation that every other field in model-compose supports — see [Variable Binding](../../../user-guide/14-variable-binding.md). This means:

- `${input.field}` — a workflow input
- `${jobs.<id>.output}` — the output of a prior job
- `${jobs.<id>.output.field}` — a field path on a prior output
- `${env.VAR}` — an environment variable
- `${input.field | 'default'}` — fallback when the value is missing

There is no additional template language. Conditionals, loops, and filters are **not** supported — if you need those, build the shape upstream (e.g., with an `agent` or `shell` component) and feed the final text into `text-renderer`.

## Usage Examples

### Assemble an LLM prompt from optional fields

```yaml
workflow:
  jobs:
    - id: build-prompt
      component: prompt-builder
      input:
        subject: ${input.subject as text | 'a serene landscape'}
        style:   ${input.style as text | 'photorealistic, 85mm lens'}

    - id: generate
      component: image-model
      input:
        prompt: ${jobs.build-prompt.output}
      depends_on: [ build-prompt ]

components:
  - id: prompt-builder
    type: text-renderer
    action:
      template: |-
        Generate an image of ${input.subject}.
        Style: ${input.style}.
        Keep framing natural and lighting coherent.
```

### Render multiple variants in one job

Pass a list of templates to render them all in a single call. The output is a list of rendered strings, one per input template.

```yaml
- id: variants
  component: variant-builder
  input:
    topic: ${input.topic}

components:
  - id: variant-builder
    type: text-renderer
    action:
      template:
        - "Write a short tweet about ${input.topic}."
        - "Write a formal LinkedIn post about ${input.topic}."
        - "Write a casual blog intro about ${input.topic}."
```

### Fall back when an optional field is missing

```yaml
- id: build-caption
  component: captioner
  input:
    name:   ${input.name}
    title:  ${input.title}

components:
  - id: captioner
    type: text-renderer
    action:
      template: "${input.name} — ${input.title | 'untitled'}"
```

## Streaming Input

If `template` resolves to an async iterator (e.g., an upstream streaming component's output), each item is rendered and yielded as part of a streaming result. Each stream item is treated as a complete template. Fragmented chunk streams preserve their fragmentation.

## When to Use This vs Other Components

- Pure variable substitution into a string → **`text-renderer`**
- Need conditionals, loops, or filters inside the template → compose upstream with an `agent`, or generate the text with `shell`
- Run a real shell command and capture stdout → `shell`
- Load a template file or reusable prompt from a store → combine a future store component with `text-renderer`

## Best Practices

1. **Use for prompt assembly, not control flow**: `text-renderer` is a slot filler. If branching logic shows up in your template, split that logic into upstream jobs.
2. **Supply defaults inline**: `${input.foo | 'fallback'}` keeps the component declarative — no separate fallback field is needed.
3. **Prefer multi-line block scalars**: YAML `|-` preserves newlines while stripping the trailing newline, which keeps rendered prompts clean.
4. **Share templates across workflows**: Define the renderer once in `components:` and reference it from multiple workflows rather than inlining the template in each.

## Common Use Cases

- **LLM prompt assembly**: Compose multi-line prompts from optional description fields
- **System message templating**: Fill role/tool/context slots in a system message before passing to an LLM
- **Report / log line formatting**: Build consistent summary strings from workflow outputs
- **Prompt variants**: Render several phrasings of the same prompt in one call for A/B testing or ensemble sampling

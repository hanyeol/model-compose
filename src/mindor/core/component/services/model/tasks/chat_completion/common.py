import asyncio, ast, json, ulid
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Union, Any, Tuple
from collections.abc import AsyncIterator
from mindor.dsl.schema.common.model.tool import ModelTool
from mindor.dsl.schema.component.impl.model.tasks.chat_completion.impl.common import (
    ToolCallParserConfig,
    ToolCallBodyFormat,
    ToolCallNameMarker,
    ToolCallArgumentsMarker,
)

class ToolCallParser:
    """Extract tool_call blocks from raw model output using a declarative marker + body-format spec.

    ``parse`` handles the optional batch envelope (``batch_start_tag``/``batch_end_tag``, e.g.,
    DeepSeek's ``<｜tool_calls_begin｜>...<｜tool_calls_end｜>``) and delegates each envelope's inner
    region — or the whole text when no batch tags are configured — to ``_parse``. ``_parse`` scans
    left-to-right for individual ``start_tag`` occurrences. Text outside a matched call is
    preserved as a ``text`` block; anything inside becomes ``tool_call`` blocks. Malformed
    bodies (invalid JSON, wrong keys, unterminated pythonic call) are treated as text so a
    single bad output cannot swallow the rest of the response.

    Batch semantics: text outside every batch envelope is passed through as text blocks
    unchanged. Text *inside* an envelope but not matched by an inner ``start_tag`` is dropped
    (framing tokens between calls are noise from the consumer's perspective). If the envelope
    is opened but not closed, the whole opening tag onward is returned as text so a truncated
    output cannot silently discard partial content.
    """
    def __init__(self, config: ToolCallParserConfig):
        self.config: ToolCallParserConfig = config

    def parse(self, text: str) -> List[Dict[str, Any]]:
        batch_start_tag = self.config.batch_start_tag
        batch_end_tag   = self.config.batch_end_tag

        if batch_start_tag or batch_end_tag:
            blocks: List[Dict[str, Any]] = []
            cursor = 0

            while cursor < len(text):
                start = text.find(batch_start_tag, cursor)

                if start < 0:
                    tail = text[cursor:]
                    if tail:
                        blocks.append({ "type": "text", "text": tail })
                    break

                if start > cursor:
                    blocks.append({ "type": "text", "text": text[cursor:start] })

                inner_start = start + len(batch_start_tag)
                end = text.find(batch_end_tag, inner_start)

                if end < 0:
                    # Unclosed batch: return everything from the opening tag as text so nothing is
                    # silently swallowed. Streaming callers use ToolCallStreamSplitter and never
                    # reach this branch.
                    blocks.append({ "type": "text", "text": text[start:] })
                    break

                inner_blocks = self._parse(text[inner_start:end])
                # Framing between inner calls (whitespace, separators) is noise; only real
                # tool_call blocks propagate outward from within a batch.
                blocks.extend(block for block in inner_blocks if block.get("type") == "tool_call")
                cursor = end + len(batch_end_tag)

            return blocks

        return self._parse(text)

    def _parse(self, text: str) -> List[Dict[str, Any]]:
        blocks: List[Dict[str, Any]] = []
        pending_text, cursor = "", 0

        while cursor < len(text):
            start = text.find(self.config.start_tag, cursor)

            if start < 0:
                pending_text += text[cursor:]
                break

            pending_text += text[cursor:start]
            body_start = start + len(self.config.start_tag)
            calls, body_end = self._read_body(text, body_start)

            if not calls:
                # Malformed body: keep the start_tag as literal text and resume just past it.
                pending_text += text[start:body_start]
                cursor = body_start
                continue

            if pending_text:
                blocks.append({ "type": "text", "text": pending_text })
                pending_text = ""

            blocks.extend(calls)
            cursor = body_end

        if pending_text:
            blocks.append({ "type": "text", "text": pending_text })

        return blocks

    def _read_body(self, text: str, body_start: int) -> Tuple[List[Dict[str, Any]], int]:
        if self.config.end_tag:
            end = text.find(self.config.end_tag, body_start)

            if end < 0:
                return [], body_start

            calls = self._parse_body(text[body_start:end])

            if not calls:
                return [], body_start

            return calls, end + len(self.config.end_tag)

        # end_tag omitted: read exactly one syntactic value starting at body_start.
        body, consumed = self._read_one_value(text, body_start)

        if body is None:
            return [], body_start

        calls = self._parse_body(body)

        if not calls:
            return [], body_start

        return calls, body_start + consumed

    def _read_one_value(self, text: str, offset: int) -> Tuple[Optional[str], int]:
        # Skip whitespace, then delegate to the format-specific length probe.
        head = offset

        while head < len(text) and text[head].isspace():
            head += 1

        if head >= len(text):
            return None, 0

        if self.config.format == ToolCallBodyFormat.JSON:
            end = self._json_value_end(text, head)
        else:
            end = self._pythonic_value_end(text, head)

        if end is None:
            return None, 0

        return text[head:end], end - offset

    def _parse_body(self, body: str) -> List[Dict[str, Any]]:
        if self.config.format == ToolCallBodyFormat.PYTHONIC:
            return self._parse_pythonic_body(body)

        # JSON format. When markers pluck name/arguments from specific locations inside the raw
        # body, the body as a whole may not be valid JSON (e.g., DeepSeek: "function<sep>name\n
        # ```json\n{...}\n```"). Otherwise the body itself is a JSON value.
        if self.config.name_marker or self.config.arguments_marker:
            return self._parse_marker_body(body)

        return self._parse_json_body(body)

    def _parse_json_body(self, body: str) -> List[Dict[str, Any]]:
        try:
            payload = json.loads(body)
        except (ValueError, TypeError):
            return []

        items = payload if isinstance(payload, list) else [ payload ]

        if not items or not all(isinstance(item, dict) for item in items):
            return []

        calls = [ self._build_call_from_json(item) for item in items ]

        if any(call is None for call in calls):
            return []

        return calls  # type: ignore[return-value]

    def _parse_marker_body(self, body: str) -> List[Dict[str, Any]]:
        # Marker path: exactly one call per body. Multi-call batching is done by the outer
        # start_tag/end_tag loop (each call is its own <start_tag>...<end_tag> span).
        name = self._extract_name(body)

        if not name:
            return []

        arguments = self._extract_arguments(body)

        if arguments is None:
            return []

        return [ {
            "type": "tool_call",
            "id": f"call_{ulid.ulid()}",
            "name": name,
            "arguments": arguments,
        } ]

    def _extract_name(self, body: str) -> Optional[str]:
        marker = self.config.name_marker

        if marker is not None:
            start = body.find(marker.prefix)

            if start < 0:
                return None

            name_start = start + len(marker.prefix)
            end = body.find(marker.suffix, name_start)

            if end < 0:
                return None

            name = body[name_start:end].strip()

            return name or None
        else:
            # Fall back to JSON body + name_key. Reached when only arguments_marker is set.
            try:
                payload = json.loads(body)
            except (ValueError, TypeError):
                return None

            if not isinstance(payload, dict):
                return None

            value = payload.get(self.config.name_key)

            return value if isinstance(value, str) and value else None

    def _extract_arguments(self, body: str) -> Optional[Dict[str, Any]]:
        marker = self.config.arguments_marker

        if marker is not None:
            start = body.find(marker.open)

            if start < 0:
                return None

            args_start = start + len(marker.open)
            end = body.find(marker.close, args_start)

            if end < 0:
                return None

            try:
                arguments = json.loads(body[args_start:end])
            except (ValueError, TypeError):
                return None

            return arguments if isinstance(arguments, dict) else None
        else:
            # Fall back to JSON body + arguments_key. Reached when only name_marker is set.
            try:
                payload = json.loads(body)
            except (ValueError, TypeError):
                return None

            if not isinstance(payload, dict):
                return None

            arguments = payload.get(self.config.arguments_key, {})

            return arguments if isinstance(arguments, dict) else None

    def _build_call_from_json(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        name = item.get(self.config.name_key)

        if not isinstance(name, str) or not name:
            return None

        arguments = item.get(self.config.arguments_key, {})

        if not isinstance(arguments, dict):
            return None

        return {
            "type": "tool_call",
            "id": f"call_{ulid.ulid()}",
            "name": name,
            "arguments": arguments,
        }

    def _parse_pythonic_body(self, body: str) -> List[Dict[str, Any]]:
        try:
            tree = ast.parse(body.strip(), mode="eval").body
        except SyntaxError:
            return []

        nodes = tree.elts if isinstance(tree, (ast.List, ast.Tuple)) else [tree]

        if not nodes:
            return []

        calls = [ self._pythonic_call_to_dict(node) for node in nodes ]

        if any(call is None for call in calls):
            return []

        return calls  # type: ignore[return-value]

    def _pythonic_call_to_dict(self, node: ast.AST) -> Optional[Dict[str, Any]]:
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            return None

        if node.args:
            return None

        arguments: Dict[str, Any] = {}

        for keyword in node.keywords:
            if keyword.arg is None:
                return None

            try:
                arguments[keyword.arg] = ast.literal_eval(keyword.value)
            except (ValueError, SyntaxError):
                return None

        return {
            "type": "tool_call",
            "id": f"call_{ulid.ulid()}",
            "name": node.func.id,
            "arguments": arguments,
        }

    def _json_value_end(self, text: str, start: int) -> Optional[int]:
        # Walk a JSON value tracking string state + brace/bracket depth. Sufficient for objects
        # and arrays, which is what tool-call bodies use.
        first = text[start]

        if first not in "{[":
            return None

        stack = [first]
        in_string = False
        escape = False
        cursor = start + 1

        while cursor < len(text) and stack:
            ch = text[cursor]

            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch in "{[":
                    stack.append(ch)
                elif ch in "}]":
                    opener = stack.pop()
                    if (opener, ch) not in (("{", "}"), ("[", "]")):
                        return None

            cursor += 1

        return cursor if not stack else None

    def _pythonic_value_end(self, text: str, start: int) -> Optional[int]:
        # Grow the window one char at a time and try to parse; first success wins.
        for end in range(start + 1, len(text) + 1):
            snippet = text[start:end]

            try:
                ast.parse(snippet, mode="eval")
            except SyntaxError:
                continue

            return end

        return None

class ToolCallStreamSplitter:
    """Chunk-at-a-time splitter used by ``ChatChoicesBuilder.stream``.

    Maintains a rolling buffer and a cursor. On each ``feed``:
      * text before the next ``start_tag`` is flushed once the tag boundary is unambiguous
        (i.e., the buffer is long enough that a partial prefix can no longer be an incomplete
        tag), so we never emit a byte we'd have to retract;
      * a ``start_tag`` is held until its body closes (end_tag or complete JSON/pythonic value),
        at which point every extracted tool_call is flushed in one shot;
      * any buffer still open when the stream ends is discarded silently.
    """
    def __init__(self, parser: ToolCallParser):
        self.parser: ToolCallParser = parser
        self.buffer: str = ""
        self.cursor: int = 0
        self.inside_call: bool = False
        self.call_start: int = 0

    def feed(self, chunk: str) -> List[Dict[str, Any]]:
        self.buffer += chunk
        emitted: List[Dict[str, Any]] = []

        while True:
            if not self.inside_call:
                start = self.buffer.find(self.parser.config.start_tag, self.cursor)

                if start < 0:
                    # Nothing tag-like committed yet. Flush text up to the point where a partial
                    # start_tag prefix could still form, keep the tail in the buffer.
                    safe = len(self.buffer) - (len(self.parser.config.start_tag) - 1)

                    if safe > self.cursor:
                        emitted.append({ "type": "text", "text": self.buffer[self.cursor:safe] })
                        self.cursor = safe

                    return emitted

                if start > self.cursor:
                    emitted.append({ "type": "text", "text": self.buffer[self.cursor:start] })

                self.inside_call = True
                self.call_start = start
                self.cursor = start + len(self.parser.config.start_tag)

                continue

            # We're inside a tag; try to close it.
            body_start = self.call_start + len(self.parser.config.start_tag)
            if self.parser.config.end_tag:
                end_at = self.buffer.find(self.parser.config.end_tag, body_start)

                if end_at < 0:
                    return emitted

                span_end = end_at + len(self.parser.config.end_tag)
            else:
                _, consumed = self.parser._read_one_value(self.buffer, body_start)

                if consumed == 0:
                    return emitted

                span_end = body_start + consumed

            calls, _ = self.parser._read_body(self.buffer, body_start)
            emitted.extend(calls)  # empty list if body was malformed -> drop the span silently
            self.inside_call = False
            self.cursor = span_end

    def flush(self) -> List[Dict[str, Any]]:
        # End-of-stream: flush any trailing text sitting outside a call. Text held back only
        # because it could be a partial start_tag is now known to not be one, so emit it. An
        # open, unclosed call is discarded per the "silently drop malformed" policy.
        if self.inside_call:
            return []

        tail = self.buffer[self.cursor:]
        self.cursor = len(self.buffer)

        return [ { "type": "text", "text": tail } ] if tail else []

class ChatToolBuilder(ABC):
    def __init__(self, tools: List[ModelTool]):
        self.tools: List[ModelTool] = tools

    def build(self, tools: Optional[Union[List[str], List[ModelTool]]]) -> List[Dict[str, Any]]:
        if tools is None or all(isinstance(tool, str) for tool in tools):
            tools = self._select_tools(tools)
        return [ self._build_tool(tool) for tool in tools ]

    def _select_tools(self, names: Optional[List[str]]) -> List[ModelTool]:
        tools: List[ModelTool] = []

        if names is not None:
            for name in names:
                tool = next((tool for tool in self.tools if tool.name == name), None)
                if not tool:
                    raise LookupError(f"Tool '{name}' is not defined in the component's tool catalog.")
                tools.append(tool)
        else:
            tools.extend(self.tools)

        return tools

    @abstractmethod
    def _build_tool(self, tool: ModelTool) -> Dict[str, Any]:
        pass

class ChatChoicesBuilder:
    """Assemble n chat-completion sequences into a choices envelope (project-internal schema).

    Both ``build`` and ``stream`` emit the same shape:
    ``{ choices: [ { index, content: [block, ...], finish_reason } ] }``.
    In ``build`` the content array holds every block for a completed sequence and
    ``finish_reason`` is ``"stop"``. In ``stream`` each event carries the blocks added since the
    last event (typically one) with ``finish_reason: None``; when a sequence ends we emit a
    terminator with ``content: []`` and ``finish_reason: "stop"`` so consumers can detect
    per-sequence completion without a sentinel.

    Blocks are ``{type:'text', text}`` or ``{type:'tool_call', id, name, arguments}``. When no
    ``ToolCallParser`` is supplied, only text blocks are emitted. Otherwise streaming holds
    partial output in a per-sequence buffer and only emits a ``tool_call`` block once the
    enclosing marker closes; any buffer still open at end-of-stream is discarded.
    """

    def __init__(self, parser: Optional[ToolCallParser] = None):
        self.parser: Optional[ToolCallParser] = parser

    def build(self, sequences: List[str]) -> Dict[str, Any]:
        return {
            "choices": [
                {
                    "index": index,
                    "content": self._split_content(text),
                    "finish_reason": "stop",
                }
                for index, text in enumerate(sequences)
            ],
        }

    async def stream(self, sequences: List[AsyncIterator[str]]) -> AsyncIterator[Dict[str, Any]]:
        queue: asyncio.Queue = asyncio.Queue()
        end = object()

        async def _stream(index: int, source: AsyncIterator[str]) -> None:
            # The splitter only needs the single-call scanner (start_tag/end_tag). Batch
            # envelope tokens leak out as harmless text deltas.
            splitter = ToolCallStreamSplitter(self.parser) if self.parser is not None else None
            try:
                async for chunk in source:
                    if not chunk:
                        continue

                    if splitter is None:
                        await queue.put(self._choice_chunk(index, [ { "type": "text", "text": chunk } ]))
                        continue

                    blocks = splitter.feed(chunk)
                    if blocks:
                        await queue.put(self._choice_chunk(index, blocks))

                if splitter is not None:
                    blocks = splitter.flush()
                    if blocks:
                        await queue.put(self._choice_chunk(index, blocks))

                await queue.put(self._choice_chunk(index, [], finish_reason="stop"))
            finally:
                await queue.put(end)

        stream_tasks = [ asyncio.create_task(_stream(index, source)) for index, source in enumerate(sequences) ]
        active_stream_count = len(sequences)

        try:
            while active_stream_count > 0:
                chunk = await queue.get()
                if chunk is end:
                    active_stream_count -= 1
                    continue
                yield chunk
        finally:
            for task in stream_tasks:
                if not task.done():
                    task.cancel()

    def _split_content(self, text: str) -> List[Dict[str, Any]]:
        if self.parser is None:
            return [ { "type": "text", "text": text } ]

        blocks = self.parser.parse(text)

        return blocks or [ { "type": "text", "text": text } ]

    def _choice_chunk(self, index: int, blocks: List[Dict[str, Any]], finish_reason: Optional[str] = None) -> Dict[str, Any]:
        return {
            "choices": [ {
                "index": index,
                "content": blocks,
                "finish_reason": finish_reason,
            } ],
        }

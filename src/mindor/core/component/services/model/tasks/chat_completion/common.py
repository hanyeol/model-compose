import asyncio, ast, io, json, tokenize, ulid
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Union, Any, Tuple
from collections.abc import AsyncIterator
from mindor.dsl.schema.common.model.tool import ModelTool
from mindor.dsl.schema.component.impl.model.tasks.chat_completion.impl.common import (
    ToolCallParserConfig,
    ToolCallBodyFormat,
    ReasoningParserConfig,
)

class ToolCallParser:
    """Extract tool_call blocks from raw model output using a declarative marker + body-format spec.

    ``parse`` handles the optional batch envelope (``batch_start_tag``/``batch_end_tag``, e.g.,
    DeepSeek's ``<｜tool_calls_begin｜>...<｜tool_calls_end｜>``) and delegates each envelope's body
    — or the whole text when no batch tags are configured — to ``_parse``. ``_parse`` scans
    left-to-right for individual ``start_tag`` occurrences. Text outside a matched call is
    preserved as a ``text`` block; anything inside becomes ``tool_call`` blocks. Malformed
    bodies (invalid JSON, wrong keys, unterminated pythonic call) are treated as text so a
    single bad output cannot swallow the rest of the response.

    Batch semantics: text outside every batch envelope is passed through as text blocks
    unchanged. Bytes inside an envelope that do not belong to a matched call are dropped
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

                batch_body_start = start + len(batch_start_tag)
                batch_end = text.find(batch_end_tag, batch_body_start)

                if batch_end < 0:
                    # Unclosed batch: return everything from the opening tag as text so nothing is
                    # silently swallowed. Streaming callers use ToolCallStreamSplitter and never
                    # reach this branch.
                    blocks.append({ "type": "text", "text": text[start:] })
                    break

                call_blocks = self._parse(text[batch_body_start:batch_end])
                # Framing between calls in a batch (whitespace, separators) is noise; only real
                # tool_call blocks propagate outward from within a batch.
                blocks.extend(block for block in call_blocks if block.get("type") == "tool_call")
                cursor = batch_end + len(batch_end_tag)

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
        # Marker path: exactly one call per body. Multi-call batching is done by the enclosing
        # start_tag/end_tag loop in ``_parse`` (each call is its own <start_tag>...<end_tag>
        # span).
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
        # Find the shortest prefix that parses as a *tool call shape* — Call, or List/Tuple
        # of Call. First-parses-wins is wrong because ``get_weather(...)`` already parses as
        # a bare Name at length 1; we'd stop before consuming the arguments. Char-by-char
        # ``ast.parse`` is also O(n^2). Instead, tokenize once to walk top-level bracket
        # boundaries and probe candidate end offsets in order.
        candidates: List[int] = []

        try:
            token_stream = tokenize.generate_tokens(io.StringIO(text[start:]).readline)
            depth = 0

            for token in token_stream:
                token_type = token.type

                if token_type in (tokenize.ENCODING, tokenize.NEWLINE, tokenize.NL, tokenize.COMMENT, tokenize.INDENT, tokenize.DEDENT):
                    continue

                if token_type == tokenize.ENDMARKER:
                    break

                if token_type == tokenize.OP:
                    string = token.string

                    if string in "([{":
                        depth += 1
                        continue

                    if string in ")]}":
                        depth -= 1

                        if depth < 0:
                            break

                        if depth == 0:
                            # Position just past this closer, in absolute text coords.
                            offset = self._token_end_to_offset(text, start, token.end)

                            if offset is not None:
                                candidates.append(offset)

                        continue

                # Bare name/literal at top level (depth==0) with no trailing bracket forms a
                # complete value at the token's end. Record it as a low-priority candidate;
                # the semantic filter below will reject non-Call shapes.
                if depth == 0:
                    offset = self._token_end_to_offset(text, start, token.end)

                    if offset is not None:
                        candidates.append(offset)
        except (tokenize.TokenError, IndentationError):
            # tokenize raises TokenError on unbalanced brackets or unterminated strings — that
            # is exactly the "value not yet complete" case that the streaming splitter probes
            # every chunk; treat it as "no candidates yet" and fall through.
            pass

        # Probe candidates shortest-to-longest, but a valid *longer* match beats a shorter one
        # only when the shorter one is not a proper tool-call shape. Since ``_parse_body`` will
        # reject non-Call ASTs anyway, we simply return the first candidate whose parse yields
        # a Call/List[Call]/Tuple[Call]. Deduplicate while preserving order.
        seen = set()

        for end in candidates:
            if end in seen or end <= start:
                continue

            seen.add(end)

            snippet = text[start:end].strip()

            if not snippet:
                continue

            try:
                node = ast.parse(snippet, mode="eval").body
            except SyntaxError:
                continue

            if isinstance(node, ast.Call):
                return end

            if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
                if all(isinstance(elt, ast.Call) for elt in node.elts):
                    return end

        return None

    @staticmethod
    def _token_end_to_offset(text: str, base_offset: int, token_end: Tuple[int, int]) -> Optional[int]:
        # ``tokenize`` reports ``token.end`` as (row, col) into the substring passed to
        # generate_tokens (which started at ``base_offset`` inside ``text``); convert it back
        # to an absolute offset in ``text``. Row is 1-indexed.
        end_row, end_col = token_end
        cursor, row = base_offset, 1

        while row < end_row and cursor < len(text):
            newline = text.find("\n", cursor)

            if newline < 0:
                return None

            cursor = newline + 1
            row += 1

        offset = cursor + end_col

        return offset if offset <= len(text) else None

class ToolCallStreamSplitter:
    """Chunk-at-a-time splitter used by ``ChatChoicesBuilder.stream``.

    Maintains a rolling buffer and a cursor. On each ``feed``:
      * text before the next ``start_tag`` is flushed once the tag boundary is unambiguous
        (i.e., the buffer is long enough that a partial prefix can no longer be an incomplete
        tag), so we never emit a byte we'd have to retract;
      * a ``start_tag`` is held until its body closes (end_tag or complete JSON/pythonic value),
        at which point every extracted tool_call is flushed in one shot;
      * any buffer still open when the stream ends is discarded silently.

    When ``batch_start_tag``/``batch_end_tag`` are configured the splitter mirrors
    :meth:`ToolCallParser.parse`: text between (but not inside) batch envelopes passes through
    as text blocks; ``batch_start_tag``/``batch_end_tag`` themselves are consumed; text inside
    the envelope that is not part of a matched call is dropped as framing noise. An unclosed
    batch at end-of-stream is discarded silently — the already-emitted tool_calls stay, but
    (unlike the non-streaming parser) the raw prefix cannot be resurrected because the
    envelope's opening tag was already consumed live.
    """
    # Trim the rolling buffer once its slack (bytes before the earliest live index) exceeds
    # this threshold. Chosen so short interactive streams never allocate an extra string, but
    # long multi-MB generations don't grow the buffer unboundedly or make `find` O(n) per feed.
    _TRIM_THRESHOLD: int = 64 * 1024

    def __init__(self, parser: ToolCallParser):
        self.parser: ToolCallParser = parser
        self.config: ToolCallParserConfig = parser.config

        # Outer state (feed): batch envelope tracking. Mirrors ToolCallParser.parse.
        self._batch_buffer: str = ""
        self._batch_cursor: int = 0
        self._inside_batch: bool = False

        # Inner state (_feed): single-call tracking. Mirrors ToolCallParser._parse; reset on
        # every envelope entry/exit so the two modes stay independent.
        self._call_buffer: str = ""
        self._call_cursor: int = 0
        self._inside_call: bool = False
        self._call_start: int = 0

    def feed(self, chunk: str) -> List[Dict[str, Any]]:
        # Outer layer mirrors ToolCallParser.parse (lines 32-72): envelope-external text passes
        # through as text blocks, envelope-internal bytes are delegated to _feed, and non-
        # tool_call blocks _feed emits inside an envelope are filtered out (line 67 policy).
        batch_start_tag = self.config.batch_start_tag
        batch_end_tag   = self.config.batch_end_tag

        if batch_start_tag or batch_end_tag:
            blocks: List[Dict[str, Any]] = []
            self._batch_buffer += chunk

            while True:
                if not self._inside_batch:
                    start = self._batch_buffer.find(batch_start_tag, self._batch_cursor)

                    if start < 0:
                        # Emit batch-external text up to the partial-batch-tag safety zone.
                        stable_end = len(self._batch_buffer) - (len(batch_start_tag) - 1)

                        if stable_end > self._batch_cursor:
                            blocks.append({ "type": "text", "text": self._batch_buffer[self._batch_cursor:stable_end] })
                            self._batch_cursor = stable_end

                        break

                    if start > self._batch_cursor:
                        blocks.append({ "type": "text", "text": self._batch_buffer[self._batch_cursor:start] })

                    self._inside_batch = True
                    self._batch_cursor = start + len(batch_start_tag)
                    self._reset_call()

                    continue

                end_of_batch = self._batch_buffer.find(batch_end_tag, self._batch_cursor)

                if end_of_batch < 0:
                    # Envelope still open — feed everything up to a safety zone into the call
                    # scanner and keep only its tool_call blocks (framing bytes are noise).
                    stable_end = len(self._batch_buffer) - (len(batch_end_tag) - 1)

                    if stable_end > self._batch_cursor:
                        call_blocks = self._feed(self._batch_buffer[self._batch_cursor:stable_end])
                        blocks.extend(block for block in call_blocks if block.get("type") == "tool_call")
                        self._batch_cursor = stable_end

                    break

                # Envelope closes: feed the remaining envelope-internal bytes, drop the call
                # scanner's flush (an unclosed call inside a closing envelope is framing per
                # the parser's batch policy), then skip past the closing tag and reset for the
                # next envelope.
                if end_of_batch > self._batch_cursor:
                    call_blocks = self._feed(self._batch_buffer[self._batch_cursor:end_of_batch])
                    blocks.extend(block for block in call_blocks if block.get("type") == "tool_call")

                self._inside_batch = False
                self._batch_cursor = end_of_batch + len(batch_end_tag)
                self._reset_call()

            self._trim_batch()
            self._trim_buffer()

            return blocks

        blocks = self._feed(chunk)
        self._trim_buffer()

        return blocks

    def flush(self) -> List[Dict[str, Any]]:
        # End-of-stream. When batching is configured any unclosed envelope is silently
        # discarded — the opening tag was already consumed live and there is no clean way to
        # resurrect it (unlike ToolCallParser.parse, which can inspect the full string). Any
        # bytes buffered inside that envelope are framing noise → drop.
        if self._inside_batch:
            return []

        # No open envelope: flush any settled batch-external text (only meaningful when
        # batching is configured but never entered), then flush the call scanner's tail.
        blocks: List[Dict[str, Any]] = []

        if self.config.batch_start_tag or self.config.batch_end_tag:
            batch_tail = self._batch_buffer[self._batch_cursor:]
            self._batch_cursor = len(self._batch_buffer)

            if batch_tail:
                blocks.append({ "type": "text", "text": batch_tail })

        if self._inside_call:
            return blocks

        call_tail = self._call_buffer[self._call_cursor:]
        self._call_cursor = len(self._call_buffer)

        if call_tail:
            blocks.append({ "type": "text", "text": call_tail })

        return blocks

    def _feed(self, chunk: str) -> List[Dict[str, Any]]:
        # Single-call scanner. Mirrors ToolCallParser._parse (lines 74-105): scan for start_tag,
        # buffer the body until it closes, emit tool_call blocks; malformed bodies fall back to
        # start_tag..span_end as literal text so a broken call cannot swallow surrounding output.
        self._call_buffer += chunk
        blocks: List[Dict[str, Any]] = []

        while True:
            if not self._inside_call:
                start = self._call_buffer.find(self.config.start_tag, self._call_cursor)

                if start < 0:
                    # No start_tag committed yet. Flush text up to the point where a partial
                    # start_tag prefix could still form; keep the tail in the buffer.
                    stable_end = len(self._call_buffer) - (len(self.config.start_tag) - 1)

                    if stable_end > self._call_cursor:
                        blocks.append({ "type": "text", "text": self._call_buffer[self._call_cursor:stable_end] })
                        self._call_cursor = stable_end

                    return blocks

                if start > self._call_cursor:
                    blocks.append({ "type": "text", "text": self._call_buffer[self._call_cursor:start] })

                self._inside_call = True
                self._call_start = start
                self._call_cursor = start + len(self.config.start_tag)

                continue

            body_start = self._call_start + len(self.config.start_tag)
            if self.config.end_tag:
                end_at = self._call_buffer.find(self.config.end_tag, body_start)

                if end_at < 0:
                    return blocks

                span_end = end_at + len(self.config.end_tag)
            else:
                _, consumed = self.parser._read_one_value(self._call_buffer, body_start)

                if consumed == 0:
                    return blocks

                span_end = body_start + consumed

            calls, _ = self.parser._read_body(self._call_buffer, body_start)

            if calls:
                blocks.extend(calls)
            else:
                # Mirror ToolCallParser._parse's malformed-body policy (line 91): keep the
                # entire start_tag..span_end run as literal text. When invoked from inside a
                # batch envelope ``feed`` filters this text block out, matching the batch
                # parser's "only tool_call blocks survive" rule (line 67).
                blocks.append({ "type": "text", "text": self._call_buffer[self._call_start:span_end] })

            self._inside_call = False
            self._call_cursor = span_end

    def _reset_call(self) -> None:
        # Envelope entry/exit is a hard boundary for the call scanner — mid-call state from a
        # previous region must not leak across it.
        self._call_buffer = ""
        self._call_cursor = 0
        self._inside_call = False
        self._call_start = 0

    def _trim_batch(self) -> None:
        if self._batch_cursor < self._TRIM_THRESHOLD:
            return

        self._batch_buffer = self._batch_buffer[self._batch_cursor:]
        self._batch_cursor = 0

    def _trim_buffer(self) -> None:
        # Inner buffer: keep only bytes past the earliest live index. When inside a call the
        # call's start marker must survive (we emit start_tag..span_end on malformed bodies);
        # otherwise everything before the cursor is settled.
        earliest = self._call_start if self._inside_call else self._call_cursor

        if earliest < self._TRIM_THRESHOLD:
            return

        self._call_buffer = self._call_buffer[earliest:]
        self._call_cursor -= earliest
        self._call_start -= earliest

class ReasoningParser:
    """Extract ``reasoning`` blocks from raw model output.

    Two modes based on ``start_tag``:
      * **tagged** (start_tag set, e.g. DeepSeek-R1 ``<think>...</think>``): scan for
        ``start_tag``, emit a reasoning block from ``start_tag`` to ``end_tag``, everything
        else stays as text.
      * **prefix** (start_tag omitted, e.g. Qwen3 thinking mode): the output *begins* with
        reasoning; everything up to the first ``end_tag`` is a reasoning block, and the
        remainder becomes text.

    Malformed spans (start_tag with no closing end_tag) are dropped silently — the opening
    tag is discarded and everything after it up to end-of-stream vanishes. This matches the
    "reasoning is transient, don't leak partials" policy.

    Streaming lives in :class:`ReasoningStreamSplitter`; this class is stateless and only
    handles complete-buffer parsing.
    """
    def __init__(self, config: ReasoningParserConfig):
        self.config: ReasoningParserConfig = config

    def parse(self, text: str) -> List[Dict[str, Any]]:
        # Non-streaming path: no partial-tag safety zone. Split reasoning spans in one pass
        # so downstream consumers (e.g. the tool_call parser) see complete text runs.
        blocks: List[Dict[str, Any]] = []
        cursor = 0

        if self.config.start_tag is None:
            # "Prefix" mode: text begins inside a reasoning span. Everything up to end_tag is
            # reasoning; the remainder is text. An unclosed span means the whole output is
            # reasoning and there is no trailing text.
            close = text.find(self.config.end_tag)

            if close < 0:
                if text:
                    blocks.append({ "type": "reasoning", "text": text })

                return blocks

            if close > 0:
                blocks.append({ "type": "reasoning", "text": text[:close] })

            cursor = close + len(self.config.end_tag)
            tail = text[cursor:]

            if tail:
                blocks.append({ "type": "text", "text": tail })

            return blocks

        while cursor < len(text):
            open_at = text.find(self.config.start_tag, cursor)

            if open_at < 0:
                tail = text[cursor:]

                if tail:
                    blocks.append({ "type": "text", "text": tail })

                break

            if open_at > cursor:
                blocks.append({ "type": "text", "text": text[cursor:open_at] })

            body_start = open_at + len(self.config.start_tag)
            close = text.find(self.config.end_tag, body_start)

            if close < 0:
                # Unclosed span: drop the opening tag and everything after silently.
                break

            if close > body_start:
                blocks.append({ "type": "reasoning", "text": text[body_start:close] })

            cursor = close + len(self.config.end_tag)

        return blocks

class ReasoningStreamSplitter:
    """Chunk-at-a-time counterpart to :class:`ReasoningParser`.

    Maintains a rolling buffer and a cursor. On each ``feed``:
      * bytes clearly outside a reasoning span are flushed as ``text`` blocks up to a safe
        boundary (leaving room for a possible partial ``start_tag`` prefix);
      * bytes inside a span are flushed as ``reasoning`` blocks up to a safe boundary before a
        possible partial ``end_tag`` prefix — reasoning streams incrementally like text;
      * on ``flush`` any trailing bytes buffered inside an unclosed reasoning span are
        discarded silently (the "reasoning is transient, don't leak partials" policy).

    Prefix mode (``config.start_tag is None``) starts already inside a reasoning span; there is
    no way to re-enter one after ``end_tag``.
    """
    _TRIM_THRESHOLD: int = 64 * 1024  # see ToolCallStreamSplitter for rationale

    def __init__(self, parser: ReasoningParser):
        self.parser: ReasoningParser = parser
        self.config: ReasoningParserConfig = parser.config

        self._buffer: str = ""
        self._cursor: int = 0
        # In "prefix" mode we're implicitly inside a reasoning span from the very first byte.
        self._inside_reasoning: bool = self.config.start_tag is None

    def feed(self, chunk: str) -> List[Dict[str, Any]]:
        blocks = self._feed(chunk)
        self._trim_buffer()

        return blocks

    def flush(self) -> List[Dict[str, Any]]:
        # End-of-stream. Prefix mode (start_tag is None) mirrors ReasoningParser.parse: an
        # output that never emits end_tag is entirely reasoning, so any buffered tail flushes
        # as a reasoning block. Tagged mode keeps the "drop unclosed <think>" policy.
        if self._inside_reasoning:
            if self.config.start_tag is not None:
                return []

            tail = self._buffer[self._cursor:]
            self._cursor = len(self._buffer)

            return [ { "type": "reasoning", "text": tail } ] if tail else []

        tail = self._buffer[self._cursor:]
        self._cursor = len(self._buffer)

        return [ { "type": "text", "text": tail } ] if tail else []

    def _feed(self, chunk: str) -> List[Dict[str, Any]]:
        blocks: List[Dict[str, Any]] = []
        self._buffer += chunk

        while True:
            if self._inside_reasoning:
                end_at = self._buffer.find(self.config.end_tag, self._cursor)

                if end_at < 0:
                    # Emit reasoning text up to a point where a partial end_tag prefix could
                    # still form; keep the tail buffered.
                    stable_end = len(self._buffer) - (len(self.config.end_tag) - 1)

                    if stable_end > self._cursor:
                        blocks.append({ "type": "reasoning", "text": self._buffer[self._cursor:stable_end] })
                        self._cursor = stable_end

                    return blocks

                if end_at > self._cursor:
                    blocks.append({ "type": "reasoning", "text": self._buffer[self._cursor:end_at] })

                self._cursor = end_at + len(self.config.end_tag)
                self._inside_reasoning = False

                continue

            # Outside a reasoning span. In "tagged" mode we may re-enter one via start_tag;
            # in "prefix" mode we never re-enter (only one reasoning span at the very start).
            if self.config.start_tag is None:
                stable_end = len(self._buffer)

                if stable_end > self._cursor:
                    blocks.append({ "type": "text", "text": self._buffer[self._cursor:stable_end] })
                    self._cursor = stable_end

                return blocks

            start = self._buffer.find(self.config.start_tag, self._cursor)

            if start < 0:
                # No start_tag committed yet. Flush text up to a safe boundary where a partial
                # start_tag prefix could still form; keep the tail buffered.
                stable_end = len(self._buffer) - (len(self.config.start_tag) - 1)

                if stable_end > self._cursor:
                    blocks.append({ "type": "text", "text": self._buffer[self._cursor:stable_end] })
                    self._cursor = stable_end

                return blocks

            if start > self._cursor:
                blocks.append({ "type": "text", "text": self._buffer[self._cursor:start] })

            self._cursor = start + len(self.config.start_tag)
            self._inside_reasoning = True

    def _trim_buffer(self) -> None:
        # Reasoning has no analogue to ToolCallStreamSplitter's ``_call_start`` — nothing
        # before ``_cursor`` needs to survive; drop it once the slack grows past threshold.
        if self._cursor < self._TRIM_THRESHOLD:
            return

        self._buffer = self._buffer[self._cursor:]
        self._cursor = 0

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
    last event with ``finish_reason: None``; a per-sequence terminator with ``content: []`` and
    ``finish_reason: "stop"`` marks end-of-sequence.

    Blocks are ``{type:'text', text}``, ``{type:'reasoning', text}``, or
    ``{type:'tool_call', id, name, arguments}``. When both a reasoning and a tool-call parser
    are supplied the pipeline runs reasoning first: reasoning spans are extracted, then any
    surviving text runs are passed through the tool-call parser. Reasoning streams like text
    (incremental deltas); tool_call spans buffer until their closing marker; malformed or
    unclosed spans in either parser are discarded silently.
    """
    def __init__(
        self,
        tool_call_parser: Optional[ToolCallParser] = None,
        reasoning_parser: Optional[ReasoningParser] = None,
    ):
        self.tool_call_parser: Optional[ToolCallParser] = tool_call_parser
        self.reasoning_parser: Optional[ReasoningParser] = reasoning_parser

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
            reasoning_splitter = ReasoningStreamSplitter(self.reasoning_parser) if self.reasoning_parser is not None else None
            tool_call_splitter = ToolCallStreamSplitter(self.tool_call_parser) if self.tool_call_parser is not None else None

            def _route(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
                # Text blocks feed the tool-call splitter; reasoning/tool_call blocks pass
                # through. When no tool-call parser is configured everything passes as-is.
                if tool_call_splitter is None:
                    return chunks

                blocks: List[Dict[str, Any]] = []

                for block in chunks:
                    if block.get("type") == "text":
                        blocks.extend(tool_call_splitter.feed(block["text"]))
                    else:
                        blocks.append(block)

                return blocks

            try:
                async for chunk in source:
                    if not chunk:
                        continue

                    if reasoning_splitter is not None:
                        blocks = _route(reasoning_splitter.feed(chunk))
                    elif tool_call_splitter is not None:
                        blocks = tool_call_splitter.feed(chunk)
                    else:
                        blocks = [ { "type": "text", "text": chunk } ]

                    if blocks:
                        await queue.put(self._choice_chunk(index, blocks))

                # Flush order matches the pipeline: reasoning tail → tool-call tail.
                tail: List[Dict[str, Any]] = []

                if reasoning_splitter is not None:
                    tail.extend(_route(reasoning_splitter.flush()))

                if tool_call_splitter is not None:
                    tail.extend(tool_call_splitter.flush())

                if tail:
                    await queue.put(self._choice_chunk(index, tail))

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
        # First pass: peel reasoning spans, leaving a mix of reasoning + text blocks (or a
        # single text block when no reasoning parser is configured).
        if self.reasoning_parser is not None:
            blocks = self.reasoning_parser.parse(text)
        else:
            blocks = [ { "type": "text", "text": text } ]

        # Second pass: run the tool_call parser over each surviving text block; reasoning
        # blocks pass through unchanged.
        if self.tool_call_parser is not None:
            source, blocks = blocks, []

            for block in source:
                if block.get("type") == "text":
                    blocks.extend(self.tool_call_parser.parse(block["text"]))
                else:
                    blocks.append(block)

        return blocks or [ { "type": "text", "text": text } ]

    def _choice_chunk(self, index: int, blocks: List[Dict[str, Any]], finish_reason: Optional[str] = None) -> Dict[str, Any]:
        return {
            "choices": [ {
                "index": index,
                "content": blocks,
                "finish_reason": finish_reason,
            } ],
        }

from typing import Union, Literal, Optional, Dict, List, Tuple, Set, Any
from collections.abc import AsyncIterator
import csv
import io
import json
import re
import xml.etree.ElementTree as ET
from mindor.dsl.schema.component import TextParserComponentConfig
from mindor.dsl.schema.action import (
    ActionConfig,
    TextParserActionConfig,
    TextParserFormat,
    TextParserStrategy,
    TextParserXmlOutput,
)
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.logger import logging
from ...action.base import ComponentAction
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext

class TextParserAction(ComponentAction):
    def __init__(self, config: TextParserActionConfig):
        self.config: TextParserActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        text       = await context.render_text(self.config.text, collect=False)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(text, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(text, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_texts in BatchSourceIterator(text, batch_size=batch_size or 1):
                    batch_results = await self._process_batch(batch_texts, params, context.cancellation_token)
                    for result in batch_results:
                        scope = f"stream:{id(result)}"
                        context.register_source("result", result, scope=scope)
                        yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else result

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_texts in BatchSourceIterator(text, batch_size=batch_size or 1):
                batch_results = await self._process_batch(batch_texts, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        format                 = await context.render_variable(self.config.format)
        strategy               = await context.render_variable(self.config.strategy)
        fallback               = await context.render_variable(self.config.fallback)
        json_schema            = await context.render_variable(self.config.json_schema) if self.config.json_schema is not None else None
        xml_root               = await context.render_variable(self.config.xml_root) if self.config.xml_root is not None else None
        xml_output             = await context.render_variable(self.config.xml_output)
        list_separator         = await context.render_variable(self.config.list_separator)
        table_column_separator = await context.render_variable(self.config.table_column_separator)
        table_row_separator    = await context.render_variable(self.config.table_row_separator)
        table_header           = await context.render_variable(self.config.table_header)
        table_quote            = await context.render_variable(self.config.table_quote)
        regex_pattern          = await context.render_variable(self.config.regex_pattern) if self.config.regex_pattern is not None else None
        regex_flags            = await context.render_variable(self.config.regex_flags)

        try:
            format = TextParserFormat(format)
        except ValueError:
            raise ValueError(f"Unsupported format for text-parser: {format!r}")

        try:
            strategy = TextParserStrategy(strategy)
        except ValueError:
            raise ValueError(f"Unsupported strategy for text-parser: {strategy!r}")

        try:
            xml_output = TextParserXmlOutput(xml_output)
        except ValueError:
            raise ValueError(f"Unsupported xml_output for text-parser: {xml_output!r}")

        if format == TextParserFormat.REGEX and not regex_pattern:
            raise ValueError("'regex_pattern' must be specified for regex format.")

        return {
            "format":                 format,
            "strategy":               strategy,
            "fallback":               fallback,
            "json_schema":            json_schema,
            "xml_root":               xml_root,
            "xml_output":             xml_output,
            "list_separator":         list_separator,
            "table_column_separator": table_column_separator,
            "table_row_separator":    table_row_separator,
            "table_header":           table_header,
            "table_quote":            table_quote,
            "regex_pattern":          regex_pattern,
            "regex_flags":            regex_flags,
        }

    async def _process_batch(
        self,
        texts: List[Any],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        results: List[Any] = []

        for text in texts:
            results.append(await self._process(text, params, cancellation_token))

        return results

    async def _process(
        self,
        text: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Any:
        if text is None:
            logging.debug("Text parser skipped because no text was provided.")
            return None

        if not isinstance(text, str):
            text = str(text)

        def _parse() -> Any:
            candidates = self._extract(text, params)

            if params["format"] in (TextParserFormat.LIST, TextParserFormat.TABLE):
                result = candidates[0] if candidates else None
            else:
                result = self._apply_strategy(candidates, params["strategy"])

            if result is None:
                return params["fallback"]

            if params["format"] == TextParserFormat.JSON and params["json_schema"] is not None:
                result = self._validate_json_schema(result, params)
                if result is None:
                    return params["fallback"]

            return result

        return await self._run_in_executor(_parse)

    def _extract(self, text: str, params: Dict[str, Any]) -> List[Any]:
        if params["format"] == TextParserFormat.JSON:
            return self._dedupe_candidates(self._extract_json(text))

        if params["format"] == TextParserFormat.YAML:
            return self._dedupe_candidates(self._extract_yaml(text))

        if params["format"] == TextParserFormat.CODE:
            return self._extract_code_blocks(text, include_language=True)

        if params["format"] == TextParserFormat.XML:
            return self._extract_xml(text, params)

        if params["format"] == TextParserFormat.LIST:
            return [ self._extract_list(text, params) ]

        if params["format"] == TextParserFormat.TABLE:
            return [ self._extract_table(text, params) ]

        if params["format"] == TextParserFormat.REGEX:
            return self._extract_regex(text, params)

        raise ValueError(f"Unsupported format: {params['format']}")

    def _extract_json(self, text: str) -> List[Any]:
        candidates: List[Any] = []

        self._try_parse_json(text, candidates)

        for block in self._extract_code_blocks(text, include_language=False):
            self._try_parse_json(block, candidates)

        for span in self._extract_balanced(text, "{", "}") + self._extract_balanced(text, "[", "]"):
            self._try_parse_json(span, candidates)

        return candidates

    def _try_parse_json(self, text: str, candidates: List[Any]) -> None:
        for source in (text, self._clean_json(text)):
            try:
                parsed = json.loads(source)
            except (json.JSONDecodeError, TypeError):
                continue

            if isinstance(parsed, (dict, list)):
                candidates.append(parsed)
                return

    def _clean_json(self, text: str) -> str:
        text = self._remove_comments(text)
        text = self._remove_trailing_commas(text)

        return text

    def _remove_comments(self, text: str) -> str:
        out: List[str] = []
        index = 0
        in_string = False
        escape = False

        while index < len(text):
            ch = text[index]
            next_ch = text[index + 1] if index + 1 < len(text) else ""

            if in_string:
                out.append(ch)
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                index += 1
                continue

            if ch == '"':
                in_string = True
                out.append(ch)
                index += 1
                continue

            if ch == "/" and next_ch == "/":
                while index < len(text) and text[index] != "\n":
                    index += 1
                continue

            if ch == "/" and next_ch == "*":
                index += 2
                while index < len(text) - 1 and not (text[index] == "*" and text[index + 1] == "/"):
                    index += 1
                index += 2
                continue

            out.append(ch)
            index += 1

        return "".join(out)

    def _remove_trailing_commas(self, text: str) -> str:
        return re.sub(r",(\s*[\]}])", r"\1", text)

    def _validate_json_schema(self, result: Any, params: Dict[str, Any]) -> Any:
        try:
            import jsonschema
        except ImportError as e:
            raise RuntimeError("JSON schema validation requires the 'jsonschema' package.") from e

        try:
            jsonschema.validate(instance=result, schema=params["json_schema"])
        except jsonschema.ValidationError as e:
            logging.debug("JSON schema validation failed: %s", e.message)
            return None

        return result

    def _extract_yaml(self, text: str) -> List[Any]:
        import yaml

        candidates: List[Any] = []

        for block in self._extract_code_blocks(text, include_language=False):
            try:
                parsed = yaml.safe_load(block)
            except yaml.YAMLError:
                continue

            if isinstance(parsed, (dict, list)):
                candidates.append(parsed)

        for part in re.split(r"^---\s*$", text, flags=re.MULTILINE):
            part = part.strip()

            if not part:
                continue

            try:
                parsed = yaml.safe_load(part)
            except yaml.YAMLError:
                continue

            if isinstance(parsed, (dict, list)):
                candidates.append(parsed)

        return candidates

    def _extract_xml(self, text: str, params: Dict[str, Any]) -> List[Any]:
        candidates: List[str] = []
        root_tag = params["xml_root"]

        for block in self._extract_code_blocks(text, include_language=False):
            self._collect_xml_block(block, root_tag, candidates)

        for match in re.finditer(r"<([a-zA-Z][a-zA-Z0-9_:-]*)(?:\s[^>]*)?>[\s\S]*?</\1>", text):
            self._collect_xml_block(match.group(0), root_tag, candidates)

        if params["xml_output"] == TextParserXmlOutput.DICT:
            return [ self._xml_to_dict(ET.fromstring(block)) for block in candidates ]

        return candidates

    def _collect_xml_block(self, fragment: str, root_tag: Optional[str], candidates: List[str]) -> None:
        try:
            element = ET.fromstring(fragment)
        except ET.ParseError:
            return

        if root_tag is not None and element.tag != root_tag:
            return

        if fragment not in candidates:
            candidates.append(fragment)

    def _xml_to_dict(self, element: ET.Element) -> Any:
        node: Dict[str, Any] = {}

        for key, value in element.attrib.items():
            node[f"@{key}"] = value

        children_by_tag: Dict[str, List[Any]] = {}

        for child in element:
            children_by_tag.setdefault(child.tag, []).append(self._xml_to_dict(child))

        for tag, values in children_by_tag.items():
            node[tag] = values[0] if len(values) == 1 else values

        text = (element.text or "").strip()

        if text:
            if node:
                node["#text"] = text
            else:
                return text

        return node

    def _extract_list(self, text: str, params: Dict[str, Any]) -> List[str]:
        separator = params["list_separator"]

        return [ item.strip() for item in text.split(separator) if item.strip() ]

    def _extract_table(self, text: str, params: Dict[str, Any]) -> Any:
        column_separator = params["table_column_separator"]
        row_separator    = params["table_row_separator"]
        header           = bool(params["table_header"])
        quote            = params["table_quote"]

        if row_separator != "\n":
            text = text.replace(row_separator, "\n")

        reader = csv.reader(
            io.StringIO(text),
            delimiter=column_separator,
            quotechar=quote or '"',
        )
        rows = [ row for row in reader if row ]

        if not rows:
            return []

        if header:
            headers = rows[0]
            return [ dict(zip(headers, row)) for row in rows[1:] ]

        return rows

    def _extract_regex(self, text: str, params: Dict[str, Any]) -> List[Any]:
        pattern = params["regex_pattern"]

        flag_bits = 0
        flag_map = { "i": re.IGNORECASE, "s": re.DOTALL, "m": re.MULTILINE }

        for ch in params["regex_flags"] or "":
            if ch not in flag_map:
                raise ValueError(
                    f"Unsupported regex flag: {ch!r} (expected any of 'i', 's', 'm')."
                )

            flag_bits |= flag_map[ch]

        compiled = re.compile(pattern, flag_bits)
        candidates: List[Any] = []

        for match in compiled.finditer(text):
            if compiled.groupindex:
                candidates.append(match.groupdict())
            elif compiled.groups > 0:
                candidates.append(list(match.groups()))
            else:
                candidates.append(match.group(0))

        return candidates

    def _extract_balanced(self, text: str, open_ch: str, close_ch: str) -> List[str]:
        results: List[str] = []
        index = 0

        while index < len(text):
            start = text.find(open_ch, index)

            if start == -1:
                break

            balance = 1
            pos = start + 1
            in_string = False
            escape = False

            while pos < len(text) and balance > 0:
                ch = text[pos]

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
                    elif ch == open_ch:
                        balance += 1
                    elif ch == close_ch:
                        balance -= 1

                pos += 1

            if balance == 0:
                results.append(text[start:pos])
                index = pos
            else:
                index = start + 1

        return results

    def _extract_code_blocks(self, text: str, include_language: bool) -> List[str]:
        pattern = r"```(\w*)\s*\n?([\s\S]*?)\s*```"
        blocks: List[str] = []

        for match in re.finditer(pattern, text):
            inner = match.group(2).strip()

            if not inner:
                continue

            if include_language:
                blocks.append(match.group(0))
            else:
                blocks.append(inner)

        return blocks

    def _apply_strategy(self, candidates: List[Any], strategy: TextParserStrategy) -> Any:
        if not candidates:
            return None

        if strategy == TextParserStrategy.FIRST:
            return candidates[0]

        if strategy == TextParserStrategy.LAST:
            return candidates[-1]

        if strategy == TextParserStrategy.ALL:
            return candidates

        if strategy == TextParserStrategy.LARGEST:
            return max(candidates, key=self._candidate_size)

        raise ValueError(f"Unsupported strategy: {strategy}")

    def _candidate_size(self, candidate: Any) -> int:
        if isinstance(candidate, (dict, list)):
            return len(json.dumps(candidate, default=str))

        return len(str(candidate))

    def _dedupe_candidates(self, candidates: List[Any]) -> List[Any]:
        result: List[Any] = []
        seen: Set[Any] = set()

        for candidate in candidates:
            if isinstance(candidate, (dict, list)):
                key = json.dumps(candidate, sort_keys=True, default=str)
            else:
                key = candidate

            if key in seen:
                continue

            seen.add(key)
            result.append(candidate)

        return result

@register_component(ComponentType.TEXT_PARSER)
class TextParserComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: TextParserComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await TextParserAction(action).run(context)

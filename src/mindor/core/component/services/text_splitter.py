from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import TextSplitterComponentConfig
from mindor.dsl.schema.action import ActionConfig, TextSplitterActionConfig
from ..base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ..context import ComponentActionContext

class TextSplitterAction:
    def __init__(self, config: TextSplitterActionConfig):
        self.config: TextSplitterActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        text           = await context.render_variable(self.config.text)
        separators     = await context.render_variable(self.config.separators)
        chunk_size     = await context.render_variable(self.config.chunk_size)
        chunk_overlap  = await context.render_variable(self.config.chunk_overlap)
        maximize_chunk = await context.render_variable(self.config.maximize_chunk)
        stream         = await context.render_variable(self.config.stream)

        chunks = self._recursive_split(text, separators or [ "\n\n", "\n", " ", "" ], chunk_size, maximize_chunk)

        if chunk_overlap > 0 and len(chunks) > 1:
            return self._overlap_chunks(chunks, chunk_overlap)

        return chunks

    def _recursive_split(self, text: str, separators: List[str], chunk_size: int, maximize_chunk: bool) -> List[str]:
        if len(text) <= chunk_size:
            return [ text ]

        separator = separators[0] if separators else ""
        if separator == "":
            return self._character_split(text, chunk_size)

        chunks, current = [], ""
        for part in text.split(separator):
            candidate = current + separator + part if current else part

            if len(candidate) > chunk_size:
                if current:
                    chunks.append(current)
                    current = part
                else:
                    if len(separators) > 1:
                        sub_chunks = self._recursive_split(part, separators[1:], chunk_size, maximize_chunk)
                    else:
                        sub_chunks = self._character_split(part, chunk_size)
                    chunks.extend(sub_chunks)
                    current = ""
            else:
                if maximize_chunk:
                    current = candidate
                else:
                    if current:
                        chunks.append(current)
                    current = part

        if current:
            chunks.append(current)

        return chunks

    def _character_split(self, text: str, chunk_size: int) -> List[str]:
        return [ text[i:i + chunk_size] for i in range(0, len(text), chunk_size) ]
    
    def _overlap_chunks(self, chunks: List[str], chunk_overlap: int) -> List[str]:
        overlapped = [ chunks[0] ]

        for i in range(1, len(chunks)):
            prev = chunks[i - 1]
            current = chunks[i]
            overlap = prev[-chunk_overlap:] if len(prev) >= chunk_overlap else prev
            overlapped.append(overlap + current)

        return overlapped

@register_component(ComponentType.TEXT_SPLITTER)
class TextSplitterComponent(ComponentService):
    def __init__(self, id: str, config: TextSplitterComponentConfig, global_configs: ComponentGlobalConfigs, daemon: bool):
        super().__init__(id, config, global_configs, daemon)

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await TextSplitterAction(action).run(context)

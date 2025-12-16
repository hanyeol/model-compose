from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
import re
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

        return self._split_text(text, separators or ["\n\n", "\n", " ", ""], chunk_size, chunk_overlap)

    def _split_text(self, text: str, separators: List[str], chunk_size: int, chunk_overlap: int) -> List[str]:
        """Split text using recursive character text splitting."""
        if not text:
            return []

        if chunk_overlap > chunk_size:
            raise ValueError(f"Got a larger chunk overlap ({chunk_overlap}) than chunk size ({chunk_size}), should be smaller.")

        return self._split_text_recursive(text, separators, chunk_size, chunk_overlap)

    def _split_text_recursive(self, text: str, separators: List[str], chunk_size: int, chunk_overlap: int) -> List[str]:
        """Recursively split text by separators."""
        final_chunks = []

        # Find the first separator that exists in the text
        separator = separators[-1] if separators else ""
        remaining_separators = []

        for i, sep in enumerate(separators):
            if not sep:
                separator = sep
                break
            if sep in text:
                separator = sep
                remaining_separators = separators[i + 1:]
                break

        # Split using the separator with keep_separator=True logic
        splits = self._split_text_with_separator(text, separator, keep_separator=True)

        # Now go merging things, recursively splitting longer texts.
        good_splits = []
        # Use empty separator when merging because separator is already in splits
        merge_separator = ""

        for s in splits:
            if len(s) < chunk_size:
                good_splits.append(s)
            else:
                if good_splits:
                    merged_text = self._merge_splits(good_splits, chunk_size, chunk_overlap, merge_separator)
                    final_chunks.extend(merged_text)
                    good_splits = []
                if not remaining_separators:
                    final_chunks.append(s)
                else:
                    other_info = self._split_text_recursive(s, remaining_separators, chunk_size, chunk_overlap)
                    final_chunks.extend(other_info)

        if good_splits:
            merged_text = self._merge_splits(good_splits, chunk_size, chunk_overlap, merge_separator)
            final_chunks.extend(merged_text)

        return final_chunks

    def _split_text_with_separator(self, text: str, separator: str, keep_separator: bool) -> List[str]:
        """Split text with regex and optionally keep separator."""
        if separator:
            if keep_separator:
                # The parentheses in the pattern keep the delimiters in the result.
                # keep_separator=True means "start" mode: attach separator to the start of next chunk
                separator_pattern = re.escape(separator)
                splits_ = re.split(f"({separator_pattern})", text)

                # Combine separator with following chunk (start mode)
                # For splits_ = ['First', '. ', 'Second', '. ', 'Third.']
                # We want: ['First', '. Second', '. Third.']
                splits = [splits_[i] + splits_[i + 1] for i in range(1, len(splits_), 2)]

                # Handle even number of elements (last chunk has separator)
                if len(splits_) % 2 == 0:
                    splits += splits_[-1:]

                # Add first element at the beginning
                splits = [splits_[0], *splits]
            else:
                splits = re.split(re.escape(separator), text)
        else:
            # Empty separator means split into characters
            splits = list(text)

        # Filter out empty strings
        return [s for s in splits if s]

    def _merge_splits(self, splits: List[str], chunk_size: int, chunk_overlap: int, separator: str) -> List[str]:
        """Merge splits into chunks with overlap, matching langchain's algorithm exactly."""
        separator_len = len(separator)
        chunks = []
        current_chunk_parts: List[str] = []
        current_chunk_length = 0

        def _calculate_separator_contribution(num_parts: int) -> int:
            """Calculate the total length added by separators between parts."""
            return separator_len if num_parts > 0 else 0

        def _would_exceed_chunk_size(new_part_length: int) -> bool:
            """Check if adding a new part would exceed the chunk size."""
            separator_contribution = _calculate_separator_contribution(len(current_chunk_parts))
            return current_chunk_length + new_part_length + separator_contribution > chunk_size

        def _save_current_chunk() -> None:
            """Save the current chunk to the result list."""
            if current_chunk_parts:
                chunk_text = self._join_docs(current_chunk_parts, separator)
                if chunk_text is not None:
                    chunks.append(chunk_text)

        def _should_remove_oldest_part(new_part_length: int) -> bool:
            """Determine if we should remove the oldest part to make room for overlap."""
            # Remove if current chunk exceeds the overlap limit
            if current_chunk_length > chunk_overlap:
                return True

            # Or if adding the new part would still exceed chunk size and we have content
            if current_chunk_length > 0:
                separator_contribution = _calculate_separator_contribution(len(current_chunk_parts))
                return current_chunk_length + new_part_length + separator_contribution > chunk_size

            return False

        def _remove_oldest_part() -> None:
            """Remove the oldest part from the current chunk and update the length."""
            nonlocal current_chunk_length
            oldest_part_length = len(current_chunk_parts[0])
            separator_contribution = separator_len if len(current_chunk_parts) > 1 else 0
            current_chunk_length -= oldest_part_length + separator_contribution
            current_chunk_parts.pop(0)

        def _add_part(part: str) -> None:
            """Add a new part to the current chunk and update the length."""
            nonlocal current_chunk_length
            part_length = len(part)
            separator_contribution = separator_len if len(current_chunk_parts) > 1 else 0
            current_chunk_parts.append(part)
            current_chunk_length += part_length + separator_contribution

        # Process each split
        for split in splits:
            split_length = len(split)

            # If adding this split would exceed chunk size, finalize current chunk
            if _would_exceed_chunk_size(split_length):
                _save_current_chunk()

                # Trim the current chunk to fit within overlap constraints
                while _should_remove_oldest_part(split_length):
                    _remove_oldest_part()

            # Add the split to the current chunk
            _add_part(split)

        # Save any remaining chunk
        _save_current_chunk()

        return chunks

    def _join_docs(self, docs: List[str], separator: str) -> Optional[str]:
        """Join documents with separator and strip whitespace."""
        text = separator.join(docs)
        text = text.strip()
        return text or None

@register_component(ComponentType.TEXT_SPLITTER)
class TextSplitterComponent(ComponentService):
    def __init__(self, id: str, config: TextSplitterComponentConfig, global_configs: ComponentGlobalConfigs, daemon: bool):
        super().__init__(id, config, global_configs, daemon)

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await TextSplitterAction(action).run(context)
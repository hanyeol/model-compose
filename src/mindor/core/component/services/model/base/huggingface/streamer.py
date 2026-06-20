from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, List

if TYPE_CHECKING:
    from transformers import PreTrainedTokenizer, TextIteratorStreamer
    from torch import Tensor

class BatchTextIteratorStreamer:
    """Fan-out wrapper around N TextIteratorStreamer instances, one per batch row.

    `model.generate()` calls `put(value)` once with the prompt (shape:
    ``(batch_size, prompt_len)``) and then once per generation step with the
    newly produced tokens (shape: ``(batch_size,)``). For each call this
    splits the rows and forwards a batch-size-1 slice to the matching inner
    streamer, so each row can be consumed as an independent token iterator.

    The standard ``TextIteratorStreamer`` rejects ``batch_size > 1`` outright,
    which makes it incompatible with batched ``generate()``. Use this instead
    when you need per-row streaming from a single batched generation call.
    """

    def __init__(
        self,
        tokenizer: PreTrainedTokenizer,
        batch_size: int,
        skip_prompt: bool = False,
        timeout: Optional[float] = None,
        **decode_kwargs,
    ):
        from transformers import TextIteratorStreamer

        self.batch_size: int = batch_size
        self.streamers: List[TextIteratorStreamer] = [
            TextIteratorStreamer(tokenizer, skip_prompt=skip_prompt, timeout=timeout, **decode_kwargs)
            for _ in range(batch_size)
        ]

    def put(self, value: Tensor) -> None:
        if value.ndim == 1:
            for index, streamer in enumerate(self.streamers):
                streamer.put(value[index:index + 1])
            return

        if value.shape[0] != self.batch_size:
            raise ValueError(
                f"BatchTextIteratorStreamer received value with batch dim {value.shape[0]} "
                f"but was configured for batch_size={self.batch_size}"
            )

        for index, streamer in enumerate(self.streamers):
            streamer.put(value[index:index + 1])

    def end(self) -> None:
        for streamer in self.streamers:
            streamer.end()

    def __getitem__(self, index: int) -> TextIteratorStreamer:
        return self.streamers[index]

    def __len__(self) -> int:
        return self.batch_size

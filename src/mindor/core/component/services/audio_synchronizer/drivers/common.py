from __future__ import annotations

from typing import TYPE_CHECKING, Optional, List, Tuple, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import AudioSynchronizerActionConfig
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.variable.media import MediaArrayValue
from mindor.core.foundation.variable.atomic import AtomicDict
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ..base import ComponentActionContext
import asyncio

if TYPE_CHECKING:
    import numpy as np

# Downsampled mono rate used for cross-correlation. 8 kHz keeps enough
# bandwidth for speech/music transients while shrinking FFT cost by ~5–6x
# versus 44.1 kHz. Sub-sample precision comes from parabolic interpolation
# around the peak, so lag resolution is not limited by 1/8000 s.
_ANALYSIS_SAMPLE_RATE = 8000

class AudioSyncOffset(AtomicDict):
    def __log__(self) -> str:
        return (
            f"<AudioSyncOffset offset={self.get('offset', 0.0):.4f}s "
            f"confidence={self.get('confidence', 0.0):.3f}>"
        )

class AudioSynchronizerAction(ComponentAction):
    def __init__(self, config: AudioSynchronizerActionConfig):
        self.config: AudioSynchronizerActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        sources    = await context.render_media_array(self.config.sources, single_as_array=True)
        batch_size = await context.render_variable(self.config.batch_size)

        is_single_input  = isinstance(sources, MediaArrayValue) and sources.is_single
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(sources, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_sources in BatchSourceIterator(sources, batch_size=batch_size or 1):
                    batch_results = await self._synchronize_batch(batch_sources, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[List[AudioSyncOffset]] = []
            async for batch_sources in BatchSourceIterator(sources, batch_size=batch_size or 1):
                batch_results = await self._synchronize_batch(batch_sources, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _synchronize_batch(
        self,
        sources: List[MediaArrayValue],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[List[AudioSyncOffset]]:
        return await asyncio.gather(*[
            self._synchronize(source, cancellation_token) for source in sources
        ])

    async def _synchronize(
        self,
        sources: MediaArrayValue,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[AudioSyncOffset]:
        sources: List[MediaSource] = await sources.collect()

        if len(sources) == 0:
            return []

        # A single source is trivially aligned to itself.
        if len(sources) < 2:
            return [ AudioSyncOffset({ "offset": 0.0, "confidence": 1.0 }) ]

        samples = await asyncio.gather(*[ self._decode_pcm(source, _ANALYSIS_SAMPLE_RATE) for source in sources ])
        reference = samples[0]

        # Offsets against the first source: each entry is how much later the
        # source starts relative to sources[0] (positive => later).
        offsets: List[Tuple[float, float]] = [ (0.0, 1.0) ]

        for target in samples[1:]:
            offsets.append(self._compute_offset(reference, target, _ANALYSIS_SAMPLE_RATE))

        # Re-anchor on the latest-starting source so every reported offset is
        # the amount to trim from the head of that source to reach the common
        # start. The anchor itself lands at 0; all others are non-negative.
        latest_start = max(offset for offset, _ in offsets)

        return [
            AudioSyncOffset({ "offset": latest_start - offset, "confidence": confidence })
            for offset, confidence in offsets
        ]

    @staticmethod
    def _compute_offset(reference: np.ndarray, target: np.ndarray, sample_rate: int) -> Tuple[float, float]:
        """Return (offset_seconds, confidence) so that shifting ``target`` by
        ``offset`` aligns it with ``reference``.

        Positive offset means ``target`` starts later than ``reference``.
        Confidence is the normalized peak correlation coefficient in [0, 1].
        """
        import numpy as np

        if reference.size == 0 or target.size == 0:
            return 0.0, 0.0

        reference = reference - reference.mean()
        target    = target - target.mean()

        # Full-lag cross-correlation via FFT: convolving `reference` with the
        # time-reversed `target` is equivalent to `np.correlate(ref, tgt, "full")`
        # and places lag `k - (M-1)` at index `k`.
        M = target.size
        size = reference.size + M - 1
        fft_size = 1 << (size - 1).bit_length()

        correlation = np.fft.irfft(
            np.fft.rfft(reference, fft_size) * np.fft.rfft(target[::-1], fft_size),
            fft_size,
        )[:size]

        peak_index = int(np.argmax(np.abs(correlation)))
        # `np.correlate` counts positive lag when the reference is shifted right
        # relative to the target; we invert the sign so a positive offset means
        # the target starts later than the reference.
        lag_samples = float((M - 1) - peak_index)

        # Parabolic interpolation around the peak for sub-sample precision.
        if 0 < peak_index < correlation.size - 1:
            y0, y1, y2 = correlation[peak_index - 1], correlation[peak_index], correlation[peak_index + 1]
            denom = (y0 - 2 * y1 + y2)
            if denom != 0:
                lag_samples -= 0.5 * (y0 - y2) / denom

        offset = lag_samples / sample_rate

        # Normalized peak: divide by product of L2 norms to bound in [0, 1].
        norm = float(np.linalg.norm(reference)) * float(np.linalg.norm(target))
        confidence = float(abs(correlation[peak_index]) / norm) if norm > 0 else 0.0
        confidence = max(0.0, min(1.0, confidence))

        return float(offset), confidence

    @abstractmethod
    async def _decode_pcm(self, source: MediaSource, sample_rate: int) -> np.ndarray:
        """Decode any audio/video source into mono float32 PCM in [-1, 1]."""
        pass

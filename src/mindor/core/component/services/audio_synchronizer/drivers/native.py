from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import AudioSynchronizerComponentConfig
from mindor.dsl.schema.action import AudioSynchronizerActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.variable.media import MediaArrayValue
from mindor.core.utils.soundfile.audio import load_pcm_samples
from ....action.media import MediaInputPathResolver
from ..base import AudioSynchronizerService, AudioSynchronizerDriver, register_audio_synchronizer_service
from ..base import ComponentActionContext
from .common import AudioSynchronizerAction
import asyncio, os

if TYPE_CHECKING:
    import numpy as np

# Downsampled mono rate used for cross-correlation. 8 kHz keeps enough
# bandwidth for speech/music transients while shrinking FFT cost by ~5–6x
# versus 44.1 kHz. Sub-sample precision comes from parabolic interpolation
# around the peak, so lag resolution is not limited by 1/8000 s.
_ANALYSIS_SAMPLE_RATE = 8000

class NativeAudioSynchronizerAction(AudioSynchronizerAction):
    async def _synchronize_batch(
        self,
        sources: List[MediaArrayValue],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[List[Dict[str, Any]]]:
        return await asyncio.gather(*[
            self._synchronize(source, cancellation_token) for source in sources
        ])

    async def _synchronize(
        self,
        sources: MediaArrayValue,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        sources: List[MediaSource] = await sources.collect()

        if len(sources) == 0:
            return []

        # A single source is trivially aligned to itself.
        if len(sources) < 2:
            return [ { "offset": 0.0, "confidence": 1.0 } ]

        samples = await asyncio.gather(*[ self._load_pcm_samples(source, _ANALYSIS_SAMPLE_RATE) for source in sources ])
        reference = samples[0]

        # Offsets against the first source: each entry is how much later the
        # source starts relative to sources[0] (positive => later). Each pair
        # is computed in a thread so the FFT does not block the event loop.
        offsets: List[Tuple[float, float]] = [ (0.0, 1.0) ]

        for target in samples[1:]:
            if cancellation_token is not None and cancellation_token.is_cancelled():
                raise asyncio.CancelledError()
            offsets.append(await asyncio.to_thread(self._compute_offset, reference, target, _ANALYSIS_SAMPLE_RATE))

        # Re-anchor on the latest-starting source so every reported offset is
        # the amount to trim from the head of that source to reach the common
        # start. The anchor itself lands at 0; all others are non-negative.
        latest_start = max(offset for offset, _ in offsets)

        return [
            { "offset": latest_start - offset, "confidence": confidence }
            for offset, confidence in offsets
        ]

    async def _load_pcm_samples(self, source: MediaSource, sample_rate: int) -> np.ndarray:
        input_path, spooled = await MediaInputPathResolver().resolve(source, streamable_media=[ "audio" ])

        if input_path is None:
            raise ValueError("Native audio synchronizer requires a file-based audio source.")

        try:
            return await self._run_in_executor(load_pcm_samples, input_path, sample_rate)
        finally:
            if spooled:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass
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

@register_audio_synchronizer_service(AudioSynchronizerDriver.NATIVE)
class NativeAudioSynchronizerService(AudioSynchronizerService):
    def __init__(self, id: str, config: AudioSynchronizerComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "numpy", "soundfile", "librosa" ]

    async def _run(
        self,
        action: AudioSynchronizerActionConfig,
        context: ComponentActionContext,
    ) -> Any:
        return await NativeAudioSynchronizerAction(action).run(context)

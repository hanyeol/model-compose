from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import AudioFeatureExtractorActionConfig
from mindor.dsl.schema.action.impl.audio_feature_extractor.impl.common import AudioFeature
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.variable.time import parse_duration
from mindor.core.logger import logging
from ..base import ComponentActionContext
import asyncio

if TYPE_CHECKING:
    import numpy as np

class AudioFeatureExtractorAction:
    def __init__(self, config: AudioFeatureExtractorActionConfig):
        self.config: AudioFeatureExtractorActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        audio      = await context.render_audio(self.config.audio)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(self.config.feature, context)

        is_single_input  = not isinstance(audio, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(audio, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                    batch_results = await self._process_batch(batch_audios, self.config.feature, params, loop)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results = []
            async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                batch_results = await self._process_batch(batch_audios, self.config.feature, params, loop)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, feature: AudioFeature, context: ComponentActionContext) -> Dict[str, Any]:
        sample_rate = int(await context.render_variable(self.config.sample_rate))
        fps         = int(await context.render_variable(self.config.fps))

        if feature == AudioFeature.SPECTRUM:
            max_frequency = await context.render_variable(self.config.max_frequency) if self.config.max_frequency is not None else None

            return {
                "sample_rate":     sample_rate,
                "fps":             fps,
                "band_count":      int(await context.render_variable(self.config.band_count)),
                "min_frequency":   float(await context.render_variable(self.config.min_frequency)),
                "max_frequency":   float(max_frequency) if max_frequency is not None else sample_rate / 2,
                "window_size":     int(await context.render_variable(self.config.window_size)),
                "window_type":     await context.render_variable(self.config.window_type),
                "frequency_scale": await context.render_variable(self.config.frequency_scale),
                "normalize_mode":  await context.render_variable(self.config.normalize_mode),
                "percentile":      float(await context.render_variable(self.config.percentile)),
            }

        if feature == AudioFeature.WAVEFORM:
            return {
                "sample_rate":     sample_rate,
                "fps":             fps,
                "point_count":     int(await context.render_variable(self.config.point_count)),
                "window_duration": parse_duration(await context.render_variable(self.config.window_duration)),
                "summary_mode":    await context.render_variable(self.config.summary_mode),
                "rectify":         bool(await context.render_variable(self.config.rectify)),
            }

        raise ValueError(f"Unsupported audio feature: {feature}")

    async def _process_batch(
        self,
        audios: List[MediaSource],
        feature: AudioFeature,
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
    ) -> List[Optional[dict]]:
        return await asyncio.gather(*[
            self._process(audio, feature, params, loop) for audio in audios
        ])

    async def _process(
        self,
        audio: MediaSource,
        feature: AudioFeature,
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
    ) -> Optional[dict]:
        if audio is None:
            logging.debug("Audio feature extractor (%s) skipped because no audio was provided.", feature)
            return None

        return await self._extract(feature, audio, params, loop)

    async def _extract(
        self,
        feature: AudioFeature,
        source: MediaSource,
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
    ) -> dict:
        if feature == AudioFeature.SPECTRUM:
            return await self._extract_spectrum(source, params, loop)

        if feature == AudioFeature.WAVEFORM:
            return await self._extract_waveform(source, params, loop)

        raise ValueError(f"Unsupported audio feature: {feature}")

    async def _extract_spectrum(self, source: MediaSource, params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> dict:
        samples = await self._decode_pcm(source, params["sample_rate"])
        return await loop.run_in_executor(None, self._compute_spectrum, samples, params)

    async def _extract_waveform(self, source: MediaSource, params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> dict:
        samples = await self._decode_pcm(source, params["sample_rate"])
        return await loop.run_in_executor(None, self._compute_waveform, samples, params)

    def _compute_spectrum(self, samples: np.ndarray, params: Dict[str, Any]) -> dict:
        import numpy as np

        sample_rate = params["sample_rate"]
        fps         = params["fps"]
        band_count  = params["band_count"]
        window_size = params["window_size"]

        hop = max(1, sample_rate // fps)
        frame_count = max(0, (len(samples) - window_size) // hop)

        frequencies = np.fft.rfftfreq(window_size, 1.0 / sample_rate)
        band_indices = self._compute_band_indices(
            frequencies,
            band_count,
            params["min_frequency"],
            params["max_frequency"],
            params["frequency_scale"]
        )
        
        window = self._get_fft_window(params["window_type"], window_size)

        bands = np.zeros((frame_count, band_count), dtype=np.float32)
        for i in range(frame_count):
            start = i * hop
            segment = samples[start:start + window_size] * window
            magnitude = np.abs(np.fft.rfft(segment, n=window_size))
            for j, index in enumerate(band_indices):
                if index.size:
                    bands[i, j] = magnitude[index].mean()

        frames = self._normalize_spectrum(bands, params["normalize_mode"], params["percentile"])

        return {
            "frames": frames.tolist(),
            "fps": fps,
            "band_count": band_count,
            "frame_count": frame_count,
            "duration": frame_count / fps if fps else 0.0,
            "sample_rate": sample_rate,
        }

    def _compute_waveform(self, samples: np.ndarray, params: Dict[str, Any]) -> dict:
        import numpy as np

        sample_rate  = params["sample_rate"]
        fps          = params["fps"]
        point_count  = params["point_count"]
        summary_mode = params["summary_mode"]
        rectify      = params["rectify"]

        win = max(point_count, int(sample_rate * params["window_duration"]))
        hop = max(1, sample_rate // fps)
        bucket = win // point_count
        usable = point_count * bucket

        frame_count = max(0, (len(samples) - win) // hop)
        frames = np.zeros((frame_count, point_count), dtype=np.float32)

        for i in range(frame_count):
            start = i * hop
            segment = samples[start:start + usable].reshape(point_count, bucket)
            if summary_mode == "peak":
                if rectify:
                    frames[i] = np.abs(segment).max(axis=1)
                else:
                    peak_pos = segment.max(axis=1)
                    peak_neg = segment.min(axis=1)
                    frames[i] = np.where(np.abs(peak_pos) >= np.abs(peak_neg), peak_pos, peak_neg)
            else:  # rms
                rms = np.sqrt((segment ** 2).mean(axis=1))
                frames[i] = rms if rectify else rms * np.sign(segment.mean(axis=1))

        return {
            "frames": frames.tolist(),
            "fps": fps,
            "point_count": point_count,
            "frame_count": frame_count,
            "duration": frame_count / fps if fps else 0.0,
            "sample_rate": sample_rate,
        }

    @staticmethod
    def _compute_band_indices(frequencies: np.ndarray, band_count: int, min_frequency: float, max_frequency: float, frequency_scale: str) -> List[np.ndarray]:
        import numpy as np

        if frequency_scale == "log":
            min_frequency_safe = max(min_frequency, 1e-3)
            edges = np.logspace(np.log10(min_frequency_safe), np.log10(max_frequency), band_count + 1)
        else:
            edges = np.linspace(min_frequency, max_frequency, band_count + 1)

        return [ np.where((frequencies >= edges[i]) & (frequencies < edges[i + 1]))[0] for i in range(band_count) ]

    @staticmethod
    def _get_fft_window(name: str, size: int) -> np.ndarray:
        import numpy as np

        return {
            "hann":     np.hanning,
            "hamming":  np.hamming,
            "blackman": np.blackman,
        }[name](size).astype(np.float32)

    @staticmethod
    def _normalize_spectrum(bands: np.ndarray, mode: str, percentile: float) -> np.ndarray:
        import numpy as np

        if bands.size == 0 or mode == "none":
            return bands

        if mode == "peak-percentile":
            scale = np.percentile(bands, percentile) or 1.0
            return np.clip(np.sqrt(bands / scale), 0.0, 1.0)

        return bands

    @abstractmethod
    async def _decode_pcm(self, source: MediaSource, sample_rate: int) -> np.ndarray:
        """Decode any audio source into mono float32 PCM in [-1, 1]."""
        pass

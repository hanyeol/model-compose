from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import MusicSynthesizerActionConfig, MusicSynthesizerActionMethod
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.audio import PcmStreamResource
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.variable.time import parse_time
from mindor.core.foundation.variable.array import ArrayValue
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ..base import ComponentActionContext
import asyncio

class MusicSynthesizerAction(ComponentAction):
    def __init__(self, config: MusicSynthesizerActionConfig):
        self.config: MusicSynthesizerActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        input, is_single_input, is_streaming_input = await self._prepare_input(self.config.method, context)
        streaming = await context.render_scalar(self.config.streaming, bool, False)

        params = await self._resolve_params(self.config.method, context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        if is_streaming_input:
            async def _stream_output_generator():
                async for batch_inputs in BatchSourceIterator(input, batch_size=1):
                    batch_results = await self._process_batch(self.config.method, batch_inputs, params, streaming, context.cancellation_token)
                    for result in batch_results:
                        context.register_source("result[]", result)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            return _stream_output_generator()
        else:
            results: List[PcmStreamResource] = []
            async for batch_inputs in BatchSourceIterator(input, batch_size=1):
                batch_results = await self._process_batch(self.config.method, batch_inputs, params, streaming, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _prepare_input(
        self,
        method: MusicSynthesizerActionMethod,
        context: ComponentActionContext,
    ) -> Tuple[Any, bool, bool]:
        if method == MusicSynthesizerActionMethod.SEQUENCE:
            tracks = await context.render_array(self.config.tracks, single_as_array=True)
            beats  = await context.render_variable(self.config.beats)

            is_single_input    = isinstance(tracks, ArrayValue)
            is_streaming_input = isinstance(tracks, (StreamIterator, AsyncIterator))

            return (tracks, beats), is_single_input, is_streaming_input

        raise ValueError(f"Unsupported music synthesizer action method: {method}")

    async def _resolve_params(
        self,
        method: MusicSynthesizerActionMethod,
        context: ComponentActionContext,
    ) -> Dict[str, Any]:
        if method == MusicSynthesizerActionMethod.SEQUENCE:
            bpm         = await context.render_scalar(self.config.bpm, float)
            sample_rate = await context.render_scalar(self.config.sample_rate, int)
            channels    = await context.render_scalar(self.config.channels, int)
            seed        = await context.render_scalar(self.config.seed, int, None)
            master      = await context.render_variable(self.config.master) or {}
            sidechain   = await context.render_variable(self.config.sidechain)

            if bpm <= 0:
                raise ValueError(f"bpm must be positive, got {bpm}.")

            if channels not in (1, 2):
                raise ValueError(f"channels must be 1 or 2, got {channels}.")

            master    = self._build_master(master)
            sidechain = self._build_sidechain(sidechain) if sidechain else None

            return {
                "bpm":         bpm,
                "sample_rate": sample_rate,
                "channels":    channels,
                "seed":        seed,
                "master":      master,
                "sidechain":   sidechain,
            }

        raise ValueError(f"Unsupported music synthesizer action method: {method}")

    async def _process_batch(
        self,
        method: MusicSynthesizerActionMethod,
        inputs: Any,
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[PcmStreamResource]:
        if method in (MusicSynthesizerActionMethod.SEQUENCE, ):
            inputs = list(zip(*inputs))

        return await asyncio.gather(*[
            self._synthesize(method, input, params, streaming, cancellation_token) for input in inputs
        ])

    async def _synthesize(
        self,
        method: MusicSynthesizerActionMethod,
        input: Any,
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> PcmStreamResource:
        if method == MusicSynthesizerActionMethod.SEQUENCE:
            tracks, beats = input
            tracks = self._build_tracks(await tracks.collect())
            beats  = float(beats)

            if beats <= 0:
                raise ValueError(f"beats must be positive, got {beats}.")

            return await self._sequence(tracks, beats, params, streaming, cancellation_token)

        raise ValueError(f"Unsupported music synthesizer action method: {method}")

    def _build_tracks(self, tracks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "id":     track["id"],
                "gain":   float(track.get("gain", 1.0)),
                "pan":    float(track.get("pan", 0.0)),
                "events": self._build_events(track.get("events") or []),
            }
            for track in tracks
        ]

    def _build_master(self, master: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "soft_clip":       float(master.get("soft_clip", 0.0)),
            "normalize_level": float(master.get("normalize_level")) if master.get("normalize_level") is not None else None,
            "silences":        self._build_silences(master.get("silences") or []),
            "fades":           self._build_fades(master.get("fades") or []),
        }

    def _build_sidechain(self, sidechain: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "trigger":      sidechain["trigger"],
            "targets":      list(sidechain.get("targets") or []),
            "depth":        float(sidechain.get("depth", 0.78)),
            "attack_time":  parse_time(sidechain.get("attack_time", "2ms")),
            "release_time": parse_time(sidechain.get("release_time", "70ms")),
        }

    def _build_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "beat":       self._build_beat_positions(event["beat"]),
                "instrument": event["instrument"],
                "length":     float(event["length"]) if event.get("length") is not None else None,
                "gain":       float(event.get("gain", 1.0)),
                "pan":        float(event.get("pan", 0.0)),
                "params":     event.get("params") or {},
            }
            for event in events
        ]

    def _build_silences(self, silences: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "start_beat":        float(silence["start_beat"]),
                "end_beat":          float(silence["end_beat"]),
                "pre_fade_duration": parse_time(silence.get("pre_fade_duration", "3ms")),
            }
            for silence in silences
        ]

    def _build_fades(self, fades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "start_beat": float(fade["start_beat"]),
                "end_beat":   float(fade["end_beat"]),
                "curve":      fade.get("curve", "quadratic"),
            }
            for fade in fades
        ]

    def _build_beat_positions(self, beat: Any) -> List[float]:
        if isinstance(beat, dict):
            start = float(beat["start"])
            end   = float(beat["end"])
            step  = float(beat.get("step", 1.0))
            phase = float(beat.get("phase", 0.0))

            if step <= 0.0:
                raise ValueError(f"Beat-pattern step must be positive, got {step}.")

            positions: List[float] = []
            index = 0

            while True:
                position = start + index * step

                if position >= end:
                    break

                positions.append(position + phase)
                index += 1

            return positions

        if isinstance(beat, list):
            return [ float(value) for value in beat ]

        return [ float(beat) ]

    @abstractmethod
    async def _sequence(
        self,
        tracks: List[Dict[str, Any]],
        beats: float,
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> PcmStreamResource:
        pass

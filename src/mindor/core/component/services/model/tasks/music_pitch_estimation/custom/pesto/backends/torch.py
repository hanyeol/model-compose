from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Tuple, List, Dict, Any, Callable
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from mindor.dsl.schema.component import ModelComponentConfig, PestoMusicPitchEstimationModelComponentConfig, ModelPrecision, ModelProvider
from mindor.dsl.schema.action import ModelActionConfig, PestoMusicPitchEstimationModelActionConfig, PitchUnit
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import AudioBufferStreamer
from mindor.core.foundation.streaming.media import MediaSource
from ........base import ComponentActionContext
from ......base import ModelTaskDriver
from ....common import MusicPitchEstimationTaskAction, PitchContour
import asyncio

if TYPE_CHECKING:
    from pesto import PESTO
    import numpy as np
    import torch

class StreamingModelPool:
    """One PESTO streaming model per slot — the model holds a per-batch circular
    buffer that must not be shared across concurrent streams.
    """
    _ACQUIRE_TIMEOUT = 1.0

    def __init__(
        self,
        loader: Callable[[], Any],
        size: int,
        run_in_executor: Callable[..., Any],
    ):
        self._loader = loader
        self._size = max(1, size)
        self._run_in_executor = run_in_executor
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=self._size)
        self._all: List[Any] = []
        self._populate_lock = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self):
        await self._ensure_populated()

        try:
            model = await asyncio.wait_for(self._queue.get(), timeout=self._ACQUIRE_TIMEOUT)
        except asyncio.TimeoutError as exc:
            raise ValueError(
                f"PESTO streaming pool exhausted (max_batch_size={self._size}); increase it or reduce concurrency."
            ) from exc

        try:
            yield model
        finally:
            self._reset_streaming_cache(model)
            await self._queue.put(model)

    async def close(self) -> None:
        async with self._populate_lock:
            self._all.clear()

            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

    async def _ensure_populated(self) -> None:
        if len(self._all) >= self._size:
            return

        async with self._populate_lock:
            while len(self._all) < self._size:
                model = await self._run_in_executor(self._loader)
                self._all.append(model)
                await self._queue.put(model)

    @staticmethod
    def _reset_streaming_cache(model: Any) -> None:
        # PESTO's streaming mode wires CachedConv1d modules that stash a persistent
        # padding tensor per batch slot. Zero it so the next stream starts clean.
        for module in model.modules():
            cache = getattr(module, "cache", None)
            pad = getattr(cache, "pad", None) if cache is not None else None

            if pad is not None and hasattr(pad, "zero_"):
                pad.zero_()

class PestoTorchMusicPitchEstimationTaskAction(MusicPitchEstimationTaskAction):
    def __init__(
        self,
        config: PestoMusicPitchEstimationModelActionConfig,
        offline_model: Optional[PESTO],
        streaming_pool: Optional[StreamingModelPool],
        component_config: PestoMusicPitchEstimationModelComponentConfig,
        device: Optional[torch.device],
    ):
        super().__init__(config, device)

        self.config: PestoMusicPitchEstimationModelActionConfig = config
        self.offline_model: Optional[PESTO] = offline_model
        self.streaming_pool: Optional[StreamingModelPool] = streaming_pool
        self.component_config: PestoMusicPitchEstimationModelComponentConfig = component_config

    async def _estimate_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[List[PitchContour], List[AsyncIterator[Dict[str, Any]]]]:
        if streaming:
            return [ self._stream_frames(audio, params, cancellation_token) for audio in audios ]

        if self.streaming_pool is not None:
            return [ await self._collect_streamed_frames(audio, params, cancellation_token) for audio in audios ]

        return await self._collect_frames(audios, params)

    async def _collect_frames(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
    ) -> List[PitchContour]:
        import numpy as np

        waveforms: List[Tuple[np.ndarray, int]] = []

        for audio in audios:
            buffer = await AudioBufferStreamer(
                audio,
                sample_rate=self.component_config.sample_rate,
                channel="mono"
            ).collect()
            waveforms.append((buffer.waveform, buffer.sample_rate))

        model = self.offline_model
        model.reduction = params["reduction"]

        def _infer() -> List[PitchContour]:
            import numpy as np
            import torch

            results: List[PitchContour] = []

            with torch.inference_mode():
                for waveform, sample_rate in waveforms:
                    waveform_tensor = torch.from_numpy(np.ascontiguousarray(waveform, dtype=np.float32)).to(self.device)

                    if self.component_config.precision == ModelPrecision.FLOAT16:
                        waveform_tensor = waveform_tensor.half()

                    prediction_chunks: List[torch.Tensor] = []
                    confidence_chunks: List[torch.Tensor] = []
                    volume_chunks: List[torch.Tensor] = []
                    activation_chunks: List[torch.Tensor] = []

                    for chunk in waveform_tensor.chunk(chunks=max(1, params["num_chunks"])):
                        predictions, confidence, volume, *activations = model(
                            chunk,
                            sr=sample_rate,
                            convert_to_freq=params["pitch_unit"] == PitchUnit.HZ,
                            return_activations=params["return_activations"],
                        )
                        prediction_chunks.append(predictions)
                        confidence_chunks.append(confidence)
                        volume_chunks.append(volume)
                        activation_chunks.extend(activations)

                    predictions = torch.cat(prediction_chunks, dim=-1)
                    confidence  = torch.cat(confidence_chunks, dim=-1)
                    volume      = torch.cat(volume_chunks, dim=-1)
                    activations = torch.cat(activation_chunks, dim=-2) if params["return_activations"] else None

                    frame_rate = 1000.0 / model.hop_size
                    timesteps = torch.arange(predictions.size(-1), dtype=torch.float32) / frame_rate

                    results.append(self._build_pitch_contour(timesteps, predictions, confidence, volume, activations, sample_rate, frame_rate, params))

            return results

        return await self._run_in_executor(_infer)

    async def _stream_frames(
        self,
        audio: MediaSource,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> AsyncIterator[Dict[str, Any]]:
        import torch

        async with self.streaming_pool.acquire() as model:
            streamer = AudioBufferStreamer(
                audio,
                frame_size=self.component_config.streaming.chunk_size,
                hop_size=self.component_config.streaming.chunk_size,
                channel="mono",
                sample_rate=self.component_config.sample_rate,
                pad_final=True,
            )

            frame_rate = 1000.0 / model.hop_size
            time_offset = 0.0
            frame_count = 0

            model.reduction = params["reduction"]

            async for buffer in streamer:
                if cancellation_token is not None and cancellation_token.is_cancelled():
                    break

                def _infer(waveform=buffer.waveform):
                    import numpy as np
                    import torch

                    waveform_tensor = torch.from_numpy(np.ascontiguousarray(waveform, dtype=np.float32)).unsqueeze(0).to(self.device)

                    if self.component_config.precision == ModelPrecision.FLOAT16:
                        waveform_tensor = waveform_tensor.half()

                    with torch.inference_mode():
                        return model(
                            waveform_tensor,
                            convert_to_freq=params["pitch_unit"] == PitchUnit.HZ,
                            return_activations=params["return_activations"],
                        )

                predictions, confidence, volume, *activations = await self._run_in_executor(_infer)
                chunk_frame_count = predictions.size(-1)

                for index in range(chunk_frame_count):
                    frame: Dict[str, Any] = {
                        "type":       "frame",
                        "time":       time_offset + index / frame_rate,
                        "pitch":      float(predictions[0, index].cpu()),
                        "confidence": float(confidence[0, index].cpu()),
                        "volume":     float(volume[0, index].cpu()),
                    }

                    if activations:
                        frame["activations"] = activations[0][0, index].cpu().tolist()

                    yield frame

                time_offset += chunk_frame_count / frame_rate
                frame_count += chunk_frame_count

        if params["return_metadata"]:
            yield {
                "type":        "metadata",
                "sample_rate": self.component_config.sample_rate,
                "frame_rate":  frame_rate,
                "duration":    time_offset,
                "frame_count": frame_count,
            }

    async def _collect_streamed_frames(
        self,
        audio: MediaSource,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> PitchContour:
        frames: List[Dict[str, Any]] = []

        async for event in self._stream_frames(audio, params, cancellation_token):
            if event["type"] == "frame":
                frames.append({ key: value for key, value in event.items() if key != "type" })

        contour: Dict[str, Any] = { "frames": frames }

        if params["return_metadata"]:
            frame_rate = self.component_config.sample_rate / self.component_config.streaming.chunk_size
            contour["sample_rate"] = self.component_config.sample_rate
            contour["frame_rate"]  = frame_rate
            contour["duration"]    = len(frames) / frame_rate

        return PitchContour(contour)

    def _build_pitch_contour(
        self,
        timesteps: torch.Tensor,
        predictions: torch.Tensor,
        confidence: torch.Tensor,
        volume: torch.Tensor,
        activations: Optional[torch.Tensor],
        sample_rate: int,
        frame_rate: float,
        params: Dict[str, Any],
    ) -> PitchContour:
        frames: List[Dict[str, Any]] = []
        frame_count = predictions.size(-1)

        predictions_cpu = predictions.detach().cpu()
        confidence_cpu  = confidence.detach().cpu()
        volume_cpu      = volume.detach().cpu()
        timesteps_cpu   = timesteps.detach().cpu()
        activations_cpu = activations.detach().cpu() if activations is not None else None

        for index in range(frame_count):
            frame: Dict[str, Any] = {
                "time":       float(timesteps_cpu[index]),
                "pitch":      float(predictions_cpu[..., index].reshape(-1)[0]),
                "confidence": float(confidence_cpu[..., index].reshape(-1)[0]),
                "volume":     float(volume_cpu[..., index].reshape(-1)[0]),
            }

            if activations_cpu is not None:
                frame["activations"] = activations_cpu[..., index, :].reshape(-1).tolist()

            frames.append(frame)

        contour: Dict[str, Any] = { "frames": frames }

        if params["return_metadata"]:
            contour["sample_rate"] = sample_rate
            contour["frame_rate"]  = frame_rate
            contour["duration"]    = frame_count / frame_rate

        return PitchContour(contour)

class PestoTorchMusicPitchEstimationTaskDriver(ModelTaskDriver):
    config: PestoMusicPitchEstimationModelComponentConfig

    def __init__(self, id: str, config: PestoMusicPitchEstimationModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.offline_model: Optional[PESTO] = None
        self.streaming_pool: Optional[StreamingModelPool] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            *torch_requirements("torch", "torchaudio"),
            "pesto-pitch",
            "numpy",
            "soxr"
        ]

    async def _load_model(self) -> None:
        from pesto import load_model

        # pesto.load_model dispatches on the string: a bundled name resolves
        # against its weights/ directory, anything else is treated as a path.
        model_path = self.config.model.path if self.config.model.provider == ModelProvider.LOCAL else self.config.model.name
        device = self._resolve_device(self.config.device)

        step_size = self._resolve_step_size()

        if self.config.streaming is not None:
            # Streaming-enabled component routes both streaming and batch
            # requests through the pool; the offline model is redundant.
            def _load_streaming_model() -> PESTO:
                model = load_model(
                    model_path,
                    step_size=step_size,
                    sampling_rate=self.config.sample_rate,
                    streaming=True,
                    max_batch_size=1,
                )

                if self.config.precision == ModelPrecision.FLOAT16:
                    model = model.half()

                return model.to(device).eval()

            self.streaming_pool = StreamingModelPool(
                loader=_load_streaming_model,
                size=self.config.streaming.max_batch_size,
                run_in_executor=self._run_in_executor,
            )
        else:
            def _load_offline_model() -> PESTO:
                model = load_model(
                    model_path,
                    step_size=step_size,
                    sampling_rate=self.config.sample_rate,
                    streaming=False
                )

                if self.config.precision == ModelPrecision.FLOAT16:
                    model = model.half()

                return model.to(device).eval()

            self.offline_model = await self._run_in_executor(_load_offline_model)

        self.device = device

    async def _unload_model(self) -> None:
        if self.streaming_pool is not None:
            await self.streaming_pool.close()
            self.streaming_pool = None

        self.offline_model = None
        self.device = None

    def _resolve_step_size(self) -> float:
        # pesto.load_model requires a step_size (hop in ms). When only
        # streaming.chunk_size is set, derive the equivalent hop so the offline
        # and streaming models share frame alignment.
        if self.config.step_size is not None:
            return self.config.step_size

        if self.config.streaming is not None and self.config.sample_rate:
            return 1000.0 * self.config.streaming.chunk_size / self.config.sample_rate

        # apply_default_step_size validator fills this in for offline-only configs.
        raise ValueError("Could not resolve step_size for PESTO torch backend.")

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await PestoTorchMusicPitchEstimationTaskAction(
            action,
            self.offline_model,
            self.streaming_pool,
            self.config,
            self.device,
        ).run(context)

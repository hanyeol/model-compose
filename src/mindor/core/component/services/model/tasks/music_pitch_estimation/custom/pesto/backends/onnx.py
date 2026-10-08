from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Tuple, List, Dict, Any, Callable
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from mindor.dsl.schema.component import ModelComponentConfig, PestoMusicPitchEstimationModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, PestoMusicPitchEstimationModelActionConfig, PitchUnit
from mindor.core.foundation.package.onnxruntime import get_onnxruntime_distributions
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import AudioBufferStreamer
from mindor.core.foundation.streaming.media import MediaSource
from ........base import ComponentActionContext
from ......base import ModelTaskDriver
from ....common import MusicPitchEstimationTaskAction, PitchContour
import asyncio

if TYPE_CHECKING:
    import numpy as np
    import onnxruntime as ort
    import torch

class OnnxSessionPool:
    """One onnxruntime session per concurrent stream — the PESTO ONNX graph is
    stateless, but each stream owns its cache tensor and running sessions in
    parallel from a single thread can serialise under GIL/op locks.
    """
    _ACQUIRE_TIMEOUT = 1.0

    def __init__(
        self,
        factory: Callable[[], Any],
        size: int,
        run_in_executor: Callable[..., Any],
        seed: Optional[Any] = None,
    ):
        self._factory = factory
        self._size = max(1, size)
        self._run_in_executor = run_in_executor
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=self._size)
        self._all: List[Any] = []
        self._seed = seed
        self._populate_lock = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self):
        await self._ensure_populated()

        try:
            session = await asyncio.wait_for(self._queue.get(), timeout=self._ACQUIRE_TIMEOUT)
        except asyncio.TimeoutError as exc:
            raise ValueError(
                f"PESTO ONNX session pool exhausted (max_batch_size={self._size}); increase it or reduce concurrency."
            ) from exc

        try:
            yield session
        finally:
            await self._queue.put(session)

    async def close(self) -> None:
        async with self._populate_lock:
            self._all.clear()
            self._seed = None

            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

    async def _ensure_populated(self) -> None:
        if len(self._all) >= self._size:
            return

        async with self._populate_lock:
            if self._seed is not None:
                self._all.append(self._seed)
                await self._queue.put(self._seed)
                self._seed = None

            while len(self._all) < self._size:
                session = await self._run_in_executor(self._factory)
                self._all.append(session)
                await self._queue.put(session)

class PestoOnnxMusicPitchEstimationTaskAction(MusicPitchEstimationTaskAction):
    def __init__(
        self,
        config: PestoMusicPitchEstimationModelActionConfig,
        session_pool: OnnxSessionPool,
        input_names: Tuple[str, str],
        cache_size: int,
        component_config: PestoMusicPitchEstimationModelComponentConfig,
        device: Optional[torch.device],
    ):
        super().__init__(config, device)

        self.config: PestoMusicPitchEstimationModelActionConfig = config
        self.session_pool: OnnxSessionPool = session_pool
        self.input_names: Tuple[str, str] = input_names
        self.cache_size: int = cache_size
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

        return [ await self._collect_frames(audio, params, cancellation_token) for audio in audios ]

    async def _collect_frames(
        self,
        audio: MediaSource,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> PitchContour:
        frames: List[Dict[str, Any]] = []

        async for event in self._stream_frames(audio, params, cancellation_token):
            if event["type"] == "frame":
                frames.append({ k: v for k, v in event.items() if k != "type" })

        contour: Dict[str, Any] = { "frames": frames }

        if params["return_metadata"]:
            frame_rate = self.component_config.sample_rate / self.component_config.streaming.chunk_size
            contour["sample_rate"] = self.component_config.sample_rate
            contour["frame_rate"]  = frame_rate
            contour["duration"]    = len(frames) / frame_rate

        return PitchContour(contour)

    async def _stream_frames(
        self,
        audio: MediaSource,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> AsyncIterator[Dict[str, Any]]:
        import numpy as np

        sample_rate = self.component_config.sample_rate
        chunk_size = self.component_config.streaming.chunk_size
        frame_rate = sample_rate / chunk_size
        audio_name, cache_name = self.input_names

        async with self.session_pool.acquire() as session:
            cache = np.zeros((1, self.cache_size), dtype=np.float32)
            streamer = AudioBufferStreamer(
                audio,
                frame_size=chunk_size,
                hop_size=chunk_size,
                channel="mono",
                sample_rate=sample_rate,
                pad_final=True,
            )
            time_offset = 0.0
            frame_count = 0

            async for buffer in streamer:
                if cancellation_token is not None and cancellation_token.is_cancelled():
                    break

                def _infer(waveform=buffer.waveform, cache_in=cache):
                    import numpy as np

                    x = np.ascontiguousarray(waveform, dtype=np.float32).reshape(1, -1)
                    return session.run(None, { audio_name: x, cache_name: cache_in })

                outputs = await self._run_in_executor(_infer)
                preds, conf, vol, _, cache = outputs
                n = preds.shape[1]

                for index in range(n):
                    pitch = float(preds[ 0, index ])

                    if params["pitch_unit"] == PitchUnit.HZ:
                        pitch = 440.0 * (2.0 ** ((pitch - 69.0) / 12.0))

                    yield {
                        "type":       "frame",
                        "time":       time_offset + index / frame_rate,
                        "pitch":      pitch,
                        "confidence": float(conf[0, index]),
                        "volume":     float(vol[0, index]),
                    }

                time_offset += n / frame_rate
                frame_count += n

        if params["return_metadata"]:
            yield {
                "type":        "metadata",
                "sample_rate": sample_rate,
                "frame_rate":  frame_rate,
                "duration":    time_offset,
                "frame_count": frame_count,
            }

class PestoOnnxMusicPitchEstimationTaskDriver(ModelTaskDriver):
    config: PestoMusicPitchEstimationModelComponentConfig

    def __init__(self, id: str, config: PestoMusicPitchEstimationModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.session_pool: Optional[OnnxSessionPool] = None
        self.input_names: Tuple[str, str] = ("", "")
        self.cache_size: int = 0
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            ("onnxruntime", get_onnxruntime_distributions()),
            "numpy",
            "soxr",
        ]

    async def _load_model(self) -> None:
        import onnxruntime as ort

        model_path = await self._provision_model(self.config.model, prefetch=True)
        device = self._resolve_device(self.config.device)
        providers = self._resolve_providers(device)

        def _load_onnx_session() -> Tuple[Any, Tuple[str, str], int]:
            session = ort.InferenceSession(model_path, providers=providers)
            inputs = session.get_inputs()

            # PESTO ONNX export signature: inputs=[audio, cache], outputs=[pred, conf, vol, act, cache_out]
            if len(inputs) < 2:
                raise ValueError(f"PESTO ONNX graph expects 2 inputs (audio, cache); got {len(inputs)}.")

            audio_name = inputs[0].name
            cache_name = inputs[1].name
            cache_shape = inputs[1].shape
            cache_size = int(cache_shape[1]) if len(cache_shape) >= 2 and isinstance(cache_shape[1], int) else 0

            return session, (audio_name, cache_name), cache_size

        seed_session, input_names, cache_size = await self._run_in_executor(_load_onnx_session)

        self.input_names = input_names
        self.cache_size = cache_size
        self.device = device
        self.session_pool = OnnxSessionPool(
            factory=lambda: ort.InferenceSession(model_path, providers=providers),
            size=self.config.streaming.max_batch_size,
            run_in_executor=self._run_in_executor,
            seed=seed_session,
        )

    async def _unload_model(self) -> None:
        if self.session_pool is not None:
            await self.session_pool.close()
            self.session_pool = None

        self.input_names = ("", "")
        self.cache_size = 0
        self.device = None

    def _resolve_providers(self, device: torch.device) -> List[str]:
        providers: List[str] = self.config.providers or []

        if not providers:
            if device.type == "cuda":
                providers.append("CUDAExecutionProvider")
            
            if device.type == "mps":
                providers.append("CoreMLExecutionProvider")

            providers.append("CPUExecutionProvider")

        return providers

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await PestoOnnxMusicPitchEstimationTaskAction(
            action,
            self.session_pool,
            self.input_names,
            self.cache_size,
            self.config,
            self.device,
        ).run(context)

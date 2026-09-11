from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, Optional, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig, PyannoteVoiceEmbeddingModelComponentConfig, HuggingfaceModelConfig
from mindor.dsl.schema.action import ModelActionConfig, VoiceEmbeddingModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import AudioBufferStreamer
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.package.torch import torch_requirements
from ......base import ComponentActionContext
from ....base import ModelTaskService
from ..common import VoiceEmbeddingTaskAction

if TYPE_CHECKING:
    import numpy as np
    import torch

class PyannoteVoiceEmbeddingTaskAction(VoiceEmbeddingTaskAction):
    def __init__(
        self,
        config: VoiceEmbeddingModelActionConfig,
        inference: Any,
        device: Optional[torch.device],
    ):
        super().__init__(config)

        self.inference: Any = inference
        self.device: Optional[torch.device] = device

    async def _embed_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[List[float]]:
        waveforms = await self._preprocess_audio(audios, params["sample_rate"])

        def _embed() -> List[List[float]]:
            import numpy as np
            import torch
            import torch.nn.functional as F

            embeddings: List[List[float]] = []

            for waveform, sample_rate in waveforms:
                tensor = torch.from_numpy(waveform).unsqueeze(0)

                if self.device is not None:
                    tensor = tensor.to(self.device)

                with torch.no_grad():
                    output = self.inference({ "waveform": tensor, "sample_rate": sample_rate })

                vector = torch.as_tensor(np.asarray(output)).float().flatten()

                if params["normalize"]:
                    vector = F.normalize(vector, p=2, dim=-1, eps=1e-12)

                embeddings.append(vector.cpu().tolist())

            return embeddings

        return await self._run_in_executor(_embed)

    async def _preprocess_audio(self, audios: List[MediaSource], sample_rate: Optional[int]) -> List[Tuple[np.ndarray, int]]:
        waveforms: List[Tuple[np.ndarray, int]] = []

        for audio in audios:
            buffer = await AudioBufferStreamer(audio, sample_rate=sample_rate, channel="mono").collect()
            waveforms.append((buffer.waveform, buffer.sample_rate))

        return waveforms

class PyannoteVoiceEmbeddingTaskService(ModelTaskService):
    config: PyannoteVoiceEmbeddingModelComponentConfig

    def __init__(self, id: str, config: PyannoteVoiceEmbeddingModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.inference: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [ *torch_requirements("torch", "torchaudio"), "pyannote.audio", "numpy", "soxr" ]

    async def _load_model(self) -> None:
        self.inference, self.device = await self._load_pretrained_inference()

    async def _unload_model(self) -> None:
        self.inference = None
        self.device = None

    async def _load_pretrained_inference(self) -> Tuple[Any, torch.device]:
        from pyannote.audio import Model, Inference

        model_path = await self._provision_model(self.config.model)
        device = self._resolve_device(self.config.device)

        token = self.config.model.token if isinstance(self.config.model, HuggingfaceModelConfig) else None
        model = Model.from_pretrained(model_path, token=token)

        if model is None:
            raise RuntimeError(f"Failed to load pyannote embedding model '{model_path}'. Verify the HuggingFace token has access to the gated model.")

        inference = Inference(model, window="whole")
        inference.to(device)

        return inference, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await PyannoteVoiceEmbeddingTaskAction(action, self.inference, self.device).run(context)

from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, Optional, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig, SampleidMusicEmbeddingModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, MusicEmbeddingModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import AudioBufferStreamer
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.package.torch import torch_requirements
from ......base import ComponentActionContext
from ....base import ModelTaskService
from ..common import MusicEmbeddingTaskAction
import os

if TYPE_CHECKING:
    from sampleid import SampleID
    import numpy as np
    import torch

# sampleid ships a 16 kHz mono encoder; the checkpoint's time-axis pooling
# makes the output shape independent of input duration, so callers should
# pre-chunk with an audio-splitter component if per-segment vectors are needed.
_SAMPLEID_SAMPLE_RATE = 16000

class SampleidMusicEmbeddingTaskAction(MusicEmbeddingTaskAction):
    def __init__(
        self,
        config: MusicEmbeddingModelActionConfig,
        model: SampleID,
        device: Optional[torch.device],
    ):
        super().__init__(config)

        self.model: SampleID = model
        self.device: Optional[torch.device] = device

    async def _embed_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[List[float]]:
        waveforms = await self._preprocess_audio(audios)

        def _embed() -> List[List[float]]:
            import numpy as np
            import torch
            import torch.nn.functional as F

            # sampleid expects (batch, samples). Waveforms may differ in length
            # across the batch — pad on the right with zeros so we can stack.
            max_len = max(waveform.shape[-1] for waveform in waveforms)
            padded = np.stack([
                np.pad(waveform, (0, max_len - waveform.shape[-1])) if waveform.shape[-1] < max_len else waveform
                for waveform in waveforms
            ])

            x = torch.from_numpy(padded).float()
            if self.device is not None:
                x = x.to(self.device)

            with torch.inference_mode():
                embeddings = self.model(x, audio=True)  # (B, 1, D)

            embeddings = embeddings.squeeze(1)

            if params["normalize"]:
                embeddings = F.normalize(embeddings, p=2, dim=-1, eps=1e-12)

            return embeddings.cpu().tolist()

        return await self._run_in_executor(_embed)

    async def _preprocess_audio(self, audios: List[MediaSource]) -> List[np.ndarray]:
        import numpy as np

        waveforms: List[np.ndarray] = []

        for audio in audios:
            buffer = await AudioBufferStreamer(audio, sample_rate=_SAMPLEID_SAMPLE_RATE, channel="mono").collect()
            mono = np.ascontiguousarray(buffer.waveform, dtype=np.float32)

            if mono.ndim == 2:
                mono = mono.mean(axis=0)

            waveforms.append(mono)

        return waveforms

class SampleidMusicEmbeddingTaskService(ModelTaskService):
    config: SampleidMusicEmbeddingModelComponentConfig

    def __init__(self, id: str, config: SampleidMusicEmbeddingModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[SampleID] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [
            *torch_requirements("torch", "torchaudio"),
            "sampleid@git+https://github.com/sony/sampleid.git",
            "soxr",
        ]

    async def _load_model(self) -> None:
        self.model, self.device = await self._load_sampleid()

    async def _unload_model(self) -> None:
        self.model = None
        self.device = None

    async def _load_sampleid(self) -> Tuple[SampleID, torch.device]:
        from sampleid import SampleID

        device = self._resolve_device(self.config.device)

        # sampleid.SampleID.load_checkpoint auto-downloads the Zenodo weights
        # when ckpt_path is None. The schema stamps a sentinel name for the
        # discriminator, so we only forward the name as a checkpoint path when
        # it points at an existing local file.
        checkpoint_path = self.config.model.name

        if not checkpoint_path or not os.path.isfile(checkpoint_path):
            checkpoint_path = None

        model = SampleID.load_checkpoint(ckpt_path=checkpoint_path, device=device)

        return model, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await SampleidMusicEmbeddingTaskAction(
            action,
            self.model,
            self.device,
        ).run(context)

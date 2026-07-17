from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, Optional, List, Iterator, Tuple, Union, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import ModelComponentConfig, SepformerSpeechSeparationModelComponentConfig, HuggingfaceModelConfig
from mindor.dsl.schema.action import ModelActionConfig, SpeechSeparationModelActionConfig
from mindor.core.foundation.streaming.audio import PcmStreamResource, load_audio_array
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.utils.audio import encode_waveform_to_pcm16
from ......base import ComponentActionContext
from ..common import SpeechSeparationTaskService, SpeechSeparationTaskAction
import asyncio

if TYPE_CHECKING:
    import numpy as np
    import torch

_DEFAULT_SEPFORMER_REPO = "speechbrain/sepformer-wsj02mix"

class SepformerSpeechSeparationTaskAction(SpeechSeparationTaskAction):
    def __init__(
        self,
        config: SpeechSeparationModelActionConfig,
        model: Any,
        device: Optional[torch.device],
    ):
        super().__init__(config, device)

        self.model: Any = model

    async def _separate(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
    ) -> Union[List[List[Dict[str, Any]]], List[Union[Iterator[Dict[str, Any]], AsyncIterator[Dict[str, Any]]]]]:
        sample_rate = int(params["sample_rate"])
        waveforms = await self._preprocess_audio(audios, sample_rate)
        results = []

        for waveform in waveforms:
            tracks = self._collect_tracks(waveform, sample_rate)
            if streaming:
                async def _stream_chunk_generator(tracks=tracks):
                    for track in tracks:
                        yield track
                results.append(_stream_chunk_generator())
            else:
                results.append(tracks)

        return results

    async def _preprocess_audio(self, audios: List[MediaSource], sample_rate: int) -> List[np.ndarray]:
        waveforms: List[np.ndarray] = []

        for audio in audios:
            waveform, _ = await load_audio_array(audio, sample_rate=sample_rate)
            waveforms.append(waveform)

        return waveforms

    def _collect_tracks(self, waveform: np.ndarray, sample_rate: int) -> List[Dict[str, Any]]:
        import numpy as np
        import torch

        tensor = torch.from_numpy(waveform).unsqueeze(0)
        if self.device is not None:
            tensor = tensor.to(self.device)

        with torch.no_grad():
            estimates = self.model.separate_batch(tensor)

        # estimates shape: (batch=1, samples, sources)
        estimates = estimates.squeeze(0).detach().cpu().numpy()
        num_sources = estimates.shape[-1]

        return [ self._build_track(estimates[:, index], index, sample_rate) for index in range(num_sources) ]

    def _build_track(self, samples: np.ndarray, index: int, sample_rate: int) -> Dict[str, Any]:
        frames, channels = encode_waveform_to_pcm16(samples)

        return {
            "index":       index,
            "sample_rate": sample_rate,
            "audio":       PcmStreamResource(frames, {
                "sample_rate": str(sample_rate),
                "channels":    str(channels),
                "bit_depth":   "16",
            }),
        }

class SepformerSpeechSeparationTaskService(SpeechSeparationTaskService):
    config: SepformerSpeechSeparationModelComponentConfig

    def __init__(self, id: str, config: SepformerSpeechSeparationModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "speechbrain", "torch", "torchaudio", "numpy", "soxr" ]

    async def _load_model(self) -> None:
        self.model, self.device = self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None
        self.device = None

    def _load_pretrained_model(self) -> Tuple[Any, torch.device]:
        from speechbrain.inference.separation import SepformerSeparation

        device = self._resolve_device(self.config.device)
        source, savedir = self._resolve_source_and_savedir()
        model = SepformerSeparation.from_hparams(source=source, savedir=savedir, run_opts={"device": str(device)})

        return model, device

    def _resolve_source_and_savedir(self) -> Tuple[str, Optional[str]]:
        model = self.config.model

        if isinstance(model, HuggingfaceModelConfig):
            return model.repository, model.cache_dir

        if isinstance(model, str):
            return model, None

        return _DEFAULT_SEPFORMER_REPO, None

    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop,
    ) -> Any:
        return await SepformerSpeechSeparationTaskAction(action, self.model, self.device).run(context, loop)

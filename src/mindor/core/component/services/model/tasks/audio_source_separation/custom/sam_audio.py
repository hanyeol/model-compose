from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Dict, Optional, List, Any
from collections.abc import AsyncIterator
from dataclasses import dataclass
from mindor.dsl.schema.component import ModelComponentConfig, SamAudioAudioSourceSeparationModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, SamAudioAudioSourceSeparationModelActionConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import PcmStreamResource, AudioBufferStreamer
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.utils.audio import encode_waveform_to_pcm
from ......base import ComponentActionContext
from ......action.media import MediaInputPathResolver
from ....base import ModelTaskDriver
from ..common import AudioSourceSeparationTaskAction
import os

if TYPE_CHECKING:
    from sam_audio.model.model import SAMAudio
    from sam_audio.processor import SAMAudioProcessor
    import numpy as np
    import torch

# SAM-Audio processor anchor tokens: `+` marks "target is here", `-` actively
# suppresses a span. Regions the user does not cover stay as <null> inside the
# processor (not `-`), so we do not auto-fill the gaps.
_POLARITY_TOKEN: Dict[str, str] = {
    "positive": "+",
    "negative": "-",
}

@dataclass
class SamAudioVisualPrompt:
    video: MediaSource
    mask: MediaSource

class SamAudioAudioSourceSeparationTaskAction(AudioSourceSeparationTaskAction):
    config: SamAudioAudioSourceSeparationModelActionConfig

    def __init__(
        self,
        config: SamAudioAudioSourceSeparationModelActionConfig,
        model: SAMAudio,
        processor: SAMAudioProcessor,
        sample_rate: int,
        device: Optional[torch.device],
        precision: Optional[Any] = None,
    ):
        super().__init__(config, device, precision)

        self.model: SAMAudio = model
        self.processor: SAMAudioProcessor = processor
        self.sample_rate: int = sample_rate

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, Any, bool, bool]:
        (audio, prompt), primary_input, is_single_input, is_streaming_input = await super()._prepare_input(context)

        if self.config.visual is not None:
            video  = await context.render_video(self.config.visual.video)
            mask   = await context.render_video(self.config.visual.mask)
            visual = SamAudioVisualPrompt(video=video, mask=mask)
        else:
            visual = None

        if prompt is None and visual is None and self.config.spans is None:
            raise ValueError("SAM-Audio requires at least one of 'prompt', 'visual', or 'spans'.")

        return (audio, prompt, visual), primary_input, is_single_input, is_streaming_input

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        predict_spans        = await context.render_scalar(self.config.params.predict_spans, bool)
        reranking_candidates = await context.render_scalar(self.config.params.reranking_candidates, int)

        params.update({
            "predict_spans":        predict_spans,
            "reranking_candidates": reranking_candidates,
        })

        return params

    async def _separate_batch(
        self,
        inputs: Tuple[List[MediaSource], List[Any], List[Optional[SamAudioVisualPrompt]]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        audios, prompts, visuals = inputs

        # SAM-Audio processor expects torch tensors or file paths; we feed
        # waveform tensors decoded at the model's native sample rate.
        waveforms = await self._preprocess_audio(audios)

        # SAM-Audio requires one description per audio; an empty string is the
        # neutral prompt used alongside visual or span prompting.
        prompts = [ prompt if prompt is not None else "" for prompt in prompts ]
        anchors = self._broadcast_anchors(params["spans"], len(waveforms)) if params["spans"] else None

        # SAM-Audio does not accept a partial batch for `masked_videos` — only
        # feed it when every audio in the batch supplies a visual.
        visual_paths = await self._resolve_visual_paths(visuals) if all(visual is not None for visual in visuals) else None

        try:
            def _separate() -> List[Any]:
                masked_videos = self._mask_videos(visual_paths) if visual_paths else None

                return self._separate(waveforms, prompts, anchors, masked_videos, params)

            return await self._run_in_executor(_separate)
        finally:
            for video_path, video_spooled, mask_path, mask_spooled in visual_paths or []:
                if video_spooled and video_path and os.path.exists(video_path):
                    os.unlink(video_path)

                if mask_spooled and mask_path and os.path.exists(mask_path):
                    os.unlink(mask_path)

    async def _preprocess_audio(self, audios: List[MediaSource]) -> List[np.ndarray]:
        waveforms: List[np.ndarray] = []

        for audio in audios:
            # channel=None keeps the original layout; SAM-Audio processor
            # handles mono/stereo internally.
            audio = await AudioBufferStreamer(audio, sample_rate=self.sample_rate).collect()
            waveforms.append(audio.waveform)

        return waveforms

    async def _resolve_visual_paths(
        self,
        visuals: List[SamAudioVisualPrompt],
    ) -> List[Tuple[Optional[str], bool, Optional[str], bool]]:
        # Materialize each visual's video + mask to on-disk paths so SAM-Audio's
        # `mask_videos` can hand them to torchcodec's VideoDecoder.
        resolver = MediaInputPathResolver()
        visual_paths: List[Tuple[Optional[str], bool, Optional[str], bool]] = []

        for visual in visuals:
            video_path, video_spooled = await resolver.resolve(visual.video)
            mask_path,  mask_spooled  = await resolver.resolve(visual.mask)
            visual_paths.append((video_path, video_spooled, mask_path, mask_spooled))

        return visual_paths

    def _mask_videos(
        self,
        visual_paths: List[Tuple[Optional[str], bool, Optional[str], bool]],
    ) -> List[Any]:
        return [
            self.processor.mask_videos([ video_path ], [ mask_path ])[0]
            for video_path, _, mask_path, _ in visual_paths
        ]

    @staticmethod
    def _broadcast_anchors(spans: List[Dict[str, Any]], count: int) -> List[List[List[Any]]]:
        # SAM-Audio anchor format: list[list[[token, start, end]]] — outer list
        # is per-audio, inner list is per-span. Unspecified regions stay as
        # <null> inside the processor, so we only emit the spans the user gave.
        anchors: List[List[Any]] = []

        for index, span in enumerate(spans):
            polarity = span.get("polarity", "positive")
            token = _POLARITY_TOKEN.get(polarity)

            if token is None:
                raise ValueError(f"'spans[{index}].polarity' must be one of {list(_POLARITY_TOKEN)}, got {polarity!r}.")

            anchors.append([ token, span["start"], span["end"] ])

        return [ anchors for _ in range(count) ]

    def _separate(
        self,
        waveforms: List[np.ndarray],
        prompts: List[str],
        anchors: Optional[List[List[List[Any]]]],
        masked_videos: Optional[List[Any]],
        params: Dict[str, Any],
    ) -> List[Any]:
        import torch

        audios = [ self._waveform_to_tensor(waveform) for waveform in waveforms ]

        processor_params: Dict[str, Any] = {
            "audios":       audios,
            "descriptions": prompts,
        }

        if anchors is not None:
            processor_params["anchors"] = anchors

        if masked_videos is not None:
            processor_params["masked_videos"] = masked_videos

        batch = self.processor(**processor_params)

        if self.device is not None:
            batch = batch.to(self.device)

        with torch.inference_mode(), self._autocast_context(self.device, self.precision):
            output = self.model.separate(
                batch,
                predict_spans=params["predict_spans"],
                reranking_candidates=params["reranking_candidates"],
            )

        targets   = self._split_batched_tensor(output.target)
        residuals = self._split_batched_tensor(output.residual)

        sample_rate = params["sample_rate"] or self.sample_rate

        return [
            self._build_separation_result(target, residual, sample_rate)
            for target, residual in zip(targets, residuals)
        ]

    def _waveform_to_tensor(self, waveform: np.ndarray) -> torch.Tensor:
        import numpy as np
        import torch

        # AudioBufferStreamer.collect() returns (samples,) for mono and
        # (channels, samples) otherwise. SAM-Audio expects (channels, samples).
        tensor = torch.from_numpy(np.ascontiguousarray(waveform, dtype=np.float32))

        if tensor.dim() == 1:
            tensor = tensor.unsqueeze(0)

        return tensor

    def _split_batched_tensor(self, tensor: torch.Tensor) -> List[torch.Tensor]:
        # SAM-Audio returns stacked (batch, channels, samples) tensors; peel
        # the batch dim so each result is (channels, samples).
        tensor = tensor.detach().float().cpu()

        if tensor.dim() == 2:
            return [ tensor ]

        return [ tensor[index] for index in range(tensor.shape[0]) ]

    def _build_separation_result(self, target: torch.Tensor, residual: torch.Tensor, sample_rate: int) -> Dict[str, PcmStreamResource]:
        return {
            "target":   self._tensor_to_pcm(target, sample_rate),
            "residual": self._tensor_to_pcm(residual, sample_rate),
        }

    def _tensor_to_pcm(self, tensor: torch.Tensor, sample_rate: int) -> PcmStreamResource:
        waveform = tensor.numpy()
        frames, channels = encode_waveform_to_pcm(waveform)

        return PcmStreamResource(frames, {
            "sample_rate": str(sample_rate),
            "channels":    str(channels),
            "bit_depth":   "16",
        })

class SamAudioAudioSourceSeparationTaskDriver(ModelTaskDriver):
    config: SamAudioAudioSourceSeparationModelComponentConfig

    def __init__(self, id: str, config: SamAudioAudioSourceSeparationModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[SAMAudio] = None
        self.processor: Optional[SAMAudioProcessor] = None
        self.sample_rate: int = 16000
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        # SAM-Audio pulls several git-only dependencies (dacvae, imagebind,
        # perception-models, laion-clap fork); we install the top-level
        # `sam-audio` wheel which cascades those git installs via its pyproject.
        return [
            *torch_requirements("torch", "torchaudio", "torchvision"),
            "sam-audio@git+https://github.com/facebookresearch/sam-audio.git",
        ]

    async def _load_model(self) -> None:
        self.model, self.processor, self.sample_rate, self.device = await self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None
        self.processor = None
        self.device = None

    async def _load_pretrained_model(self) -> Tuple[Any, Any, int, torch.device]:
        model_path = await self._provision_model(self.config.model, prefetch=True)

        device = self._resolve_device(self.config.device)

        def _load() -> Tuple[Any, Any, int]:
            from sam_audio import SAMAudio, SAMAudioProcessor

            model = SAMAudio.from_pretrained(model_path)
            processor = SAMAudioProcessor.from_pretrained(model_path)

            model = model.eval().to(device)

            sample_rate = int(getattr(processor, "audio_sampling_rate", getattr(model, "sample_rate", 16000)))

            return model, processor, sample_rate

        model, processor, sample_rate = await self._run_in_executor(_load)

        return model, processor, sample_rate, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await SamAudioAudioSourceSeparationTaskAction(
            action,
            self.model,
            self.processor,
            self.sample_rate,
            self.device,
            self.config.precision,
        ).run(context)

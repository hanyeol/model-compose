from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Optional, Dict, List, Any
from mindor.dsl.schema.action import ModelActionConfig, VideoEmbeddingModelActionConfig
from mindor.dsl.schema.component import HuggingfaceVideoEmbeddingModelArchitecture
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.cancellation import CancellationToken
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import ComponentActionContext
from ...base.huggingface.multimodal import HuggingfaceMultimodalModelTaskService
from .common import VideoEmbeddingTaskAction
from PIL import Image as PILImage

if TYPE_CHECKING:
    from transformers import PreTrainedModel, ProcessorMixin
    from torch import Tensor
    import torch

class HuggingfaceVideoEmbeddingTaskAction(VideoEmbeddingTaskAction):
    def __init__(
        self,
        config: VideoEmbeddingModelActionConfig,
        architecture: HuggingfaceVideoEmbeddingModelArchitecture,
        model: PreTrainedModel,
        processor: ProcessorMixin,
        device: torch.device,
    ):
        super().__init__(config)

        self.architecture: HuggingfaceVideoEmbeddingModelArchitecture = architecture
        self.model: PreTrainedModel = model
        self.processor: ProcessorMixin = processor
        self.device: torch.device = device

    async def _embed_batch(
        self,
        videos: List[ImageArrayValue],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[List[float]]:
        expected_frames = self._get_expected_frame_count()
        sampled_videos: List[List[PILImage.Image]] = []

        for video in videos:
            frames = await video.collect()
            sampled_videos.append(self._sample_frames(frames, expected_frames))

        def _embed() -> List[List[float]]:
            import torch, torch.nn.functional as F

            if self.architecture == HuggingfaceVideoEmbeddingModelArchitecture.XCLIP:
                # Work around an upstream issue in transformers 4.55+ where
                # XCLIPModel.get_video_features() calls the internal MIT
                # without return_dict, then fails to read pooler_output from
                # the returned tuple. Route through forward() instead; dummy
                # text is required but video_embeds is independent of it.
                inputs: Dict[str, Tensor] = self.processor(
                    images=sampled_videos,
                    text=[ "" ] * len(sampled_videos),
                    return_tensors="pt",
                    padding=True,
                )
                inputs = { key: value.to(self.device) for key, value in inputs.items() }

                with torch.inference_mode():
                    outputs = self.model(**inputs, return_dict=True)

                embeddings = outputs.video_embeds
            else:
                inputs: Dict[str, Tensor] = self.processor(
                    images=sampled_videos,
                    return_tensors="pt"
                )
                inputs = { key: value.to(self.device) for key, value in inputs.items() }

                with torch.inference_mode():
                    if hasattr(self.model, "get_video_features"):
                        embeddings = self.model.get_video_features(**inputs)
                    else:
                        embeddings = self._get_video_features(inputs)

            if params["normalize"]:
                embeddings = F.normalize(embeddings, p=2, dim=1, eps=1e-12)

            return embeddings.cpu().tolist()

        return await self._run_in_executor(_embed)

    def _get_video_features(self, inputs: Dict[str, Tensor]) -> Tensor:
        outputs = self.model(**inputs, return_dict=True)

        if hasattr(outputs, "video_embeds"):
            return outputs.video_embeds

        if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
            return outputs.pooler_output

        if hasattr(outputs, "last_hidden_state"):
            # Pure video encoders (VideoMAE, etc.) return per-token hidden
            # states; collapse to a single vector by mean-pooling.
            return outputs.last_hidden_state.mean(dim=1)

        raise ValueError(f"Model does not expose video embeddings: {type(self.model).__name__}")

    def _get_expected_frame_count(self) -> int:
        # X-CLIP nests num_frames under vision_config; pure video encoders
        # (VideoMAE, etc.) expose it at the top level. Fall back to 8 when
        # neither is set.
        vision_config = getattr(self.model.config, "vision_config", None)
        num_frames = getattr(vision_config, "num_frames", None) if vision_config else None

        if not num_frames:
            num_frames = getattr(self.model.config, "num_frames", None)

        return int(num_frames) if num_frames else 8

    def _sample_frames(self, frames: List[PILImage.Image], target: int) -> List[PILImage.Image]:
        count = len(frames)

        if count == 0:
            raise ValueError("Cannot embed an empty frame sequence.")

        if count == target:
            return frames

        # Uniformly sample `target` frames, duplicating the last frame when the
        # source is shorter than the model expects.
        indices = [ min(int(round(i * (count - 1) / max(target - 1, 1))), count - 1) for i in range(target) ]

        return [ frames[index] for index in indices ]

@register_model_task_service(ModelTaskType.VIDEO_EMBEDDING, ModelDriver.HUGGINGFACE)
class HuggingfaceVideoEmbeddingTaskService(HuggingfaceMultimodalModelTaskService):
    def _get_model_class(self) -> Type[PreTrainedModel]:
        if self.config.architecture == HuggingfaceVideoEmbeddingModelArchitecture.AUTO:
            from transformers import AutoModel
            return AutoModel

        if self.config.architecture == HuggingfaceVideoEmbeddingModelArchitecture.XCLIP:
            from transformers import XCLIPModel
            return XCLIPModel

        if self.config.architecture == HuggingfaceVideoEmbeddingModelArchitecture.VIDEOMAE:
            from transformers import VideoMAEModel
            return VideoMAEModel

        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    def _get_processor_class(self) -> Type[ProcessorMixin]:
        if self.config.architecture == HuggingfaceVideoEmbeddingModelArchitecture.AUTO:
            from transformers import AutoProcessor
            return AutoProcessor

        if self.config.architecture == HuggingfaceVideoEmbeddingModelArchitecture.XCLIP:
            from transformers import XCLIPProcessor
            return XCLIPProcessor

        if self.config.architecture == HuggingfaceVideoEmbeddingModelArchitecture.VIDEOMAE:
            from transformers import VideoMAEImageProcessor
            return VideoMAEImageProcessor

        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await HuggingfaceVideoEmbeddingTaskAction(action, self.config.architecture, self.model, self.processor, self.device).run(context)

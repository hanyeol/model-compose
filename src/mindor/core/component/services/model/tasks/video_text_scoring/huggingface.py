from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Optional, Union, Dict, List, Any
from mindor.dsl.schema.action import ModelActionConfig, VideoTextScoringModelActionConfig
from mindor.dsl.schema.component import HuggingfaceVideoTextScoringModelArchitecture
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.variable.text import TextArrayValue
from mindor.core.foundation.variable.array import ArrayValue
from mindor.core.foundation.cancellation import CancellationToken
from ...base import ModelTaskType, ModelDriverType, register_model_task_driver
from ...base import ComponentActionContext
from ...base.huggingface.multimodal import HuggingfaceMultimodalModelTaskDriver
from .common import VideoTextScoringTaskAction
from PIL import Image as PILImage

if TYPE_CHECKING:
    from transformers import PreTrainedModel, ProcessorMixin
    from torch import Tensor
    import torch

class HuggingfaceVideoTextScoringTaskAction(VideoTextScoringTaskAction):
    def __init__(
        self,
        config: VideoTextScoringModelActionConfig,
        model: PreTrainedModel,
        processor: ProcessorMixin,
        device: torch.device,
    ):
        super().__init__(config)

        self.model: PreTrainedModel = model
        self.processor: ProcessorMixin = processor
        self.device: torch.device = device

    async def _score_batch(
        self,
        frames: List[Union[ArrayValue, ImageArrayValue]],
        texts: List[TextArrayValue],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        # Collect lazy containers; each job's `frames` is either an ArrayValue
        # (collect-mode: N videos packed into one job) or a single
        # ImageArrayValue (stream-mode: one video per tick).
        videos: List[List[List[PILImage.Image]]] = []

        for frames in frames:
            videos.append(await frames.collect() if isinstance(frames, ArrayValue) else [ frames ])

        videos = [ [ await video.collect() for video in videos ] for videos in videos ]
        texts  = [ await texts.collect() for texts in texts ]
        modes  = [ self._resolve_scoring_mode(len(videos), len(texts)) for videos, texts in zip(videos, texts) ]

        # X-CLIP scores one (videos, texts) matrix per forward pass; jobs are
        # independent scoring contexts and cannot be concatenated into one call.
        videos = [ [ self._sample_frames(frames, frame_count) for frames in videos ] for videos in videos ]
        frame_count = self._get_expected_frame_count()

        def _score() -> List[Dict[str, Any]]:
            results: List[Dict[str, Any]] = []

            for videos, texts, mode in zip(videos, texts, modes):
                cosines, logits = self._forward(videos, texts)

                if mode == "pairwise":
                    results.append(self._build_pairwise_result(cosines, logits, params))
                else:
                    results.append(self._build_cross_result(cosines, logits, mode, params))

            return results

        return await self._run_in_executor(_score)

    def _forward(self, videos: List[List[PILImage.Image]], texts: List[str]) -> tuple[Tensor, Optional[Tensor]]:
        """Return (cosines, logits) as N_video × N_text tensors. logits is None if the model has no logit_scale."""
        import torch

        # XCLIPProcessor expects `images` to be a list of per-video frame lists.
        inputs = self.processor(images=videos, text=texts, return_tensors="pt", padding=True, truncation=True)
        inputs = { key: value.to(self.device) for key, value in inputs.items() }

        with torch.inference_mode():
            outputs = self.model(**inputs, return_dict=True)
            logits = getattr(outputs, "logits_per_video", None)
            logit_scale = getattr(self.model, "logit_scale", None)

            if logits is not None and logit_scale is not None:
                cosines = logits / logit_scale.exp()
                return cosines.detach().cpu(), logits.detach().cpu()

            raise ValueError(f"Model does not expose logits_per_video: {type(self.model).__name__}")

    def _resolve_scoring_mode(self, num_videos: int, num_texts: int) -> str:
        if num_videos == 0 or num_texts == 0:
            raise ValueError(f"Video-text scoring input cannot be empty: videos={num_videos}, texts={num_texts}")

        if num_videos == num_texts:
            return "pairwise"

        if num_videos == 1:
            return "texts_to_video"

        if num_texts == 1:
            return "videos_to_text"

        raise ValueError(
            f"Incompatible video/text lengths for scoring: videos={num_videos}, texts={num_texts}. "
            "Lengths must match, or one side must have length 1."
        )

    def _build_pairwise_result(self, cosines: Tensor, logits: Optional[Tensor], params: Dict[str, Any]) -> Dict[str, Any]:
        # Diagonal: (video[index], text[index]) scores.
        length = cosines.shape[0]
        cosine_values = [ float(cosines[index][index]) for index in range(length) ]
        logit_values = [ float(logits[index][index]) for index in range(length) ] if logits is not None else None

        if length == 1:
            result: Dict[str, Any] = { "cosine": cosine_values[0] }

            if params["return_logit"] and logit_values is not None:
                result["logit"] = logit_values[0]

            return result
        else:
            result = { "cosine": cosine_values }

            if params["return_logit"] and logit_values is not None:
                result["logit"] = logit_values

            return result

    def _build_cross_result(self, cosines: Tensor, logits: Optional[Tensor], mode: str, params: Dict[str, Any]) -> Dict[str, Any]:
        import torch

        # Softmax is always normalized along the many-axis — the row/column with
        # more than one element. The one-length axis would collapse to [1.0, ...].
        if mode == "texts_to_video":
            # 1 video × N texts → row across the text axis.
            cosine_row = cosines[0]
            logit_row = logits[0] if logits is not None else None
            softmax_row = torch.softmax(logit_row, dim=-1) if logit_row is not None and params["return_softmax"] else None
        else:
            # N videos × 1 text → column across the video axis.
            cosine_row = cosines[:, 0]
            logit_row = logits[:, 0] if logits is not None else None
            softmax_row = torch.softmax(logit_row, dim=-1) if logit_row is not None and params["return_softmax"] else None

        result: Dict[str, Any] = { "cosine": [ float(cosine) for cosine in cosine_row.tolist() ] }

        if params["return_logit"] and logit_row is not None:
            result["logit"] = [ float(logit) for logit in logit_row.tolist() ]

        if softmax_row is not None:
            result["softmax"] = [ float(prob) for prob in softmax_row.tolist() ]

        return result

    def _get_expected_frame_count(self) -> int:
        # X-CLIP nests num_frames under vision_config. Fall back to 8 when unset.
        vision_config = getattr(self.model.config, "vision_config", None)
        num_frames = getattr(vision_config, "num_frames", None) if vision_config else None

        if not num_frames:
            num_frames = getattr(self.model.config, "num_frames", None)

        return int(num_frames) if num_frames else 8

    def _sample_frames(self, frames: List[PILImage.Image], target: int) -> List[PILImage.Image]:
        count = len(frames)

        if count == 0:
            raise ValueError("Cannot score an empty frame sequence.")

        if count == target:
            return frames

        # Uniformly sample `target` frames, duplicating the last frame when the
        # source is shorter than the model expects.
        indices = [ min(int(round(i * (count - 1) / max(target - 1, 1))), count - 1) for i in range(target) ]

        return [ frames[index] for index in indices ]

@register_model_task_driver(ModelTaskType.VIDEO_TEXT_SCORING, ModelDriverType.HUGGINGFACE)
class HuggingfaceVideoTextScoringTaskDriver(HuggingfaceMultimodalModelTaskDriver):
    def _get_model_class(self) -> Type[PreTrainedModel]:
        if self.config.architecture == HuggingfaceVideoTextScoringModelArchitecture.XCLIP:
            from transformers import XCLIPModel
            return XCLIPModel

        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    def _get_processor_class(self) -> Type[ProcessorMixin]:
        if self.config.architecture == HuggingfaceVideoTextScoringModelArchitecture.XCLIP:
            from transformers import XCLIPProcessor
            return XCLIPProcessor

        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await HuggingfaceVideoTextScoringTaskAction(
            action,
            self.model,
            self.processor,
            self.device,
        ).run(context)

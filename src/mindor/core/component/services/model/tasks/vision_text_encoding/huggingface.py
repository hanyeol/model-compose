from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Any, Dict, List, Optional, Protocol, Type, Union
from mindor.dsl.schema.action import ModelActionConfig, VisionTextEncodingModelActionConfig
from mindor.dsl.schema.component import HuggingfaceVisionTextEncodingModelComponentConfig
from mindor.core.foundation.cancellation import CancellationToken
from ...base import ModelTaskType, ModelDriverType, register_model_task_driver
from ...base import ComponentActionContext
from ...base.huggingface.multimodal import HuggingfaceMultimodalModelTaskDriver
from .common import VisionTextEncodingTaskAction
from PIL import Image as PILImage

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizer, ProcessorMixin
    from torch import Tensor
    import torch

class WithTokenizer(Protocol):
    tokenizer: PreTrainedTokenizer

class HuggingfaceVisionTextEncodingTaskAction(VisionTextEncodingTaskAction):
    def __init__(
        self,
        config: VisionTextEncodingModelActionConfig,
        model: PreTrainedModel,
        processor: ProcessorMixin,
        device: torch.device,
        chat_template: Optional[str] = None,
    ):
        super().__init__(config)

        self.model: PreTrainedModel = model
        self.processor: Union[ProcessorMixin, WithTokenizer] = processor
        self.device: torch.device = device
        self.chat_template: Optional[str] = chat_template

    async def _encode(
        self,
        text: str,
        images: List[PILImage.Image],
        frames: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        import torch

        def _encode() -> Dict[str, Any]:
            prompt = self._build_prompt(text, len(images), len(frames))

            processor_params: Dict[str, Any] = {
                "text": prompt,
                "return_tensors": "pt",
                "padding": True,
                "add_special_tokens": params["add_special_tokens"],
            }

            if params["max_length"] is not None:
                processor_params["max_length"] = params["max_length"]
                processor_params["truncation"] = True

            if images:
                processor_params["images"] = images

            if frames:
                processor_params["videos"] = frames

            inputs = self.processor(**processor_params)
            inputs = inputs.to(self.device)

            with torch.inference_mode():
                outputs = self.model(
                    **inputs,
                    output_hidden_states=True,
                    return_dict=True,
                )

            hidden_states = outputs.hidden_states[params["layer"]][0]
            token_types   = inputs.get("token_type_ids")

            return {
                "hidden_states": hidden_states.cpu().contiguous(),
                "token_types":   token_types[0].cpu().contiguous() if token_types is not None else None,
                "spec": {
                    "hidden_size":        hidden_states.shape[-1],
                    "dtype":              str(hidden_states.dtype).removeprefix("torch."),
                    "layer":              params["layer"],
                    "add_special_tokens": params["add_special_tokens"],
                    "max_length":         params["max_length"],
                },
            }

        return await self._run_in_executor(_encode)

    def _build_prompt(self, text: str, image_count: int, frame_count: int) -> str:
        content: List[Dict[str, Any]] = []
        content.extend({ "type": "image" } for _ in range(image_count))
        content.extend({ "type": "video" } for _ in range(frame_count))
        content.append({ "type": "text", "text": text })

        return self.processor.apply_chat_template(
            [ { "role": "user", "content": content } ],
            tokenize=False,
            add_generation_prompt=False,
            **({ "chat_template": self.chat_template } if self.chat_template else {}),
        )

@register_model_task_driver(ModelTaskType.VISION_TEXT_ENCODING, ModelDriverType.HUGGINGFACE)
class HuggingfaceVisionTextEncodingTaskDriver(HuggingfaceMultimodalModelTaskDriver):
    config: HuggingfaceVisionTextEncodingModelComponentConfig

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await HuggingfaceVisionTextEncodingTaskAction(
            action, self.model, self.processor, self.device, self.config.chat_template,
        ).run(context)

    def _get_model_class(self) -> Type[PreTrainedModel]:
        from transformers import AutoModel
        return AutoModel

    def _get_processor_class(self) -> Type[ProcessorMixin]:
        from transformers import AutoProcessor
        return AutoProcessor

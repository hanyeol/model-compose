from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Any, Dict, List, Optional, Type
from mindor.dsl.schema.action import ModelActionConfig, TextEncodingModelActionConfig
from mindor.dsl.schema.component import HuggingfaceTextEncodingModelComponentConfig
from mindor.core.foundation.cancellation import CancellationToken
from ...base import ModelTaskType, ModelDriverType, register_model_task_driver
from ...base import ComponentActionContext
from ...base.huggingface.language import HuggingfaceLanguageModelTaskDriver
from .common import TextEncodingTaskAction

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizer
    from torch import Tensor
    import torch

class HuggingfaceTextEncodingTaskAction(TextEncodingTaskAction):
    def __init__(
        self,
        config: TextEncodingModelActionConfig,
        model: PreTrainedModel,
        tokenizer: PreTrainedTokenizer,
        device: torch.device,
        chat_template: Optional[str] = None,
    ):
        super().__init__(config)

        self.model: PreTrainedModel = model
        self.tokenizer: PreTrainedTokenizer = tokenizer
        self.device: torch.device = device
        self.chat_template: Optional[str] = chat_template

    async def _encode_batch(
        self,
        texts: List[str],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        import torch

        def _encode() -> List[Dict[str, Any]]:
            prompts = [ self._apply_chat_template(text) for text in texts ]

            inputs: Dict[str, Tensor] = self.tokenizer(
                prompts,
                return_tensors="pt",
                padding=True,
                truncation=params["max_length"] is not None,
                max_length=params["max_length"] or self.tokenizer.model_max_length,
                add_special_tokens=params["add_special_tokens"],
                return_token_type_ids=True,
            )
            inputs = { key: value.to(self.device) for key, value in inputs.items() }

            with torch.inference_mode():
                outputs = self.model(
                    input_ids=inputs["input_ids"],
                    attention_mask=inputs.get("attention_mask"),
                    output_hidden_states=True,
                )

            hidden_states = outputs.hidden_states[params["layer"]]
            token_types   = inputs.get("token_type_ids")

            spec = {
                "hidden_size":        hidden_states.shape[-1],
                "dtype":              str(hidden_states.dtype).removeprefix("torch."),
                "layer":              params["layer"],
                "add_special_tokens": params["add_special_tokens"],
                "max_length":         params["max_length"],
            }

            results: List[Dict[str, Any]] = []

            for index in range(hidden_states.shape[0]):
                results.append({
                    "hidden_states": hidden_states[index].cpu().contiguous(),
                    "token_types":   token_types[index].cpu().contiguous() if token_types is not None else None,
                    "spec":          spec,
                })

            return results

        return await self._run_in_executor(_encode)

    def _apply_chat_template(self, text: str) -> str:
        if self.chat_template is None and getattr(self.tokenizer, "chat_template", None) is None:
            return text

        return self.tokenizer.apply_chat_template(
            [ { "role": "user", "content": text } ],
            tokenize=False,
            add_generation_prompt=False,
            **({ "chat_template": self.chat_template } if self.chat_template else {}),
        )

@register_model_task_driver(ModelTaskType.TEXT_ENCODING, ModelDriverType.HUGGINGFACE)
class HuggingfaceTextEncodingTaskDriver(HuggingfaceLanguageModelTaskDriver):
    config: HuggingfaceTextEncodingModelComponentConfig

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await HuggingfaceTextEncodingTaskAction(
            action, self.model, self.tokenizer, self.device, self.config.chat_template,
        ).run(context)

    def _get_model_class(self) -> Type[PreTrainedModel]:
        from transformers import AutoModel
        return AutoModel

    def _get_tokenizer_class(self) -> Type[PreTrainedTokenizer]:
        from transformers import AutoTokenizer
        return AutoTokenizer

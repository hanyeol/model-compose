from __future__ import annotations
from typing import TYPE_CHECKING, Union, Tuple

from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelTrainerTaskType, ModelTrainerDriverType, ModelQuantizationType, ModelPrecision
from mindor.dsl.schema.action import SftModelTrainerActionConfig
from .....context import ComponentActionContext
from ...base import UnslothModelTrainerTaskDriver, register_model_trainer_task_driver
from .common import SftModelTrainerTaskAction

if TYPE_CHECKING:
    from transformers.trainer_utils import TrainOutput

class UnslothSftModelTrainerTaskAction(SftModelTrainerTaskAction):
    def _train(
        self,
        training_arguments: Dict[str, Any],
        train_dataset: Any,
        eval_dataset: Any,
        dataset_text_field: str,
        max_seq_length: Optional[int],
        packing: bool,
        completion_only_loss: bool,
        output_dir: str,
    ) -> TrainOutput:
        from unsloth import FastLanguageModel
        from trl import SFTTrainer, SFTConfig

        # Unsloth handles 4-/8-bit loading via boolean flags rather than a
        # BitsAndBytesConfig. Fall through to a plain 16-bit LoRA load when
        # quantization is unset.
        load_in_4bit = False
        load_in_8bit = False

        if self.trainer_config.quantization is not None:
            if self.trainer_config.quantization.type == ModelQuantizationType.INT8:
                load_in_8bit = True
            else:
                load_in_4bit = True

        # `dtype=None` lets unsloth pick bf16 on Ampere+ and fp16 otherwise;
        # only override when the user explicitly set precision.
        dtype = self._get_model_dtype()

        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=self.model_path,
            max_seq_length=self.trainer_config.max_seq_length,
            dtype=dtype,
            load_in_4bit=load_in_4bit,
            load_in_8bit=load_in_8bit,
        )

        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        # Mirror the tokenizer's pad id onto the model config. Some architectures
        # (e.g. Qwen3) ship with pad_token_id=None; without this sync SFTTrainer's
        # causal forward pass raises when a batch has padding.
        if model.config.pad_token_id is None:
            model.config.pad_token_id = tokenizer.pad_token_id

        # Unsloth requires get_peft_model to be called via FastLanguageModel so
        # its custom kernels are patched into the LoRA layers. Standard peft
        # get_peft_model would bypass those kernels and lose the speedup.
        lora = self.trainer_config.lora
        model = FastLanguageModel.get_peft_model(
            model,
            r=lora.rank,
            lora_alpha=lora.alpha,
            lora_dropout=lora.dropout,
            target_modules=lora.target_modules,
            bias=lora.bias,
            use_gradient_checkpointing=training_arguments.get("gradient_checkpointing", False),
        )

        # When the dataset carries a `messages` column (either supplied by the
        # user or rewritten from prompt/response), route through the tokenizer's
        # chat template explicitly. Matches the huggingface driver's rationale.
        formatting_func = None

        if dataset_text_field == "messages":
            if getattr(tokenizer, "chat_template", None) is None:
                raise ValueError(
                    f"Tokenizer for {self.model_path!r} has no chat_template; conversational "
                    f"SFT (messages column) requires a chat template. Set one on the tokenizer "
                    f"before training, or use `text_column` for a pre-flattened text field."
                )

            def _format_messages(example: Dict[str, Any]) -> str:
                return tokenizer.apply_chat_template(example["messages"], tokenize=False)

            formatting_func = _format_messages

        sft_config_params: Dict[str, Any] = {
            "dataset_text_field":   dataset_text_field if formatting_func is None else None,
            "max_seq_length":       max_seq_length,
            "packing":              packing,
            "completion_only_loss": completion_only_loss,
        }

        if formatting_func is not None:
            sft_config_params["dataset_kwargs"] = { "add_special_tokens": False }

        sft_config = SFTConfig(**sft_config_params, **training_arguments)

        trainer = SFTTrainer(
            model=model,
            args=sft_config,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            processing_class=tokenizer,
            formatting_func=formatting_func,
        )

        result = trainer.train()

        trainer.save_model(output_dir)
        tokenizer.save_pretrained(output_dir)

        return result

@register_model_trainer_task_driver(ModelTrainerTaskType.SFT, ModelTrainerDriverType.UNSLOTH)
class UnslothSftTrainerTaskDriver(UnslothModelTrainerTaskDriver):
    def _get_setup_requirements(self) -> List[Union[str, Tuple[str, List[str]]]]:
        return [
            *super()._get_setup_requirements(),
            "trl>=0.12,<0.14",
        ]

    async def _run(self, action: SftModelTrainerActionConfig, context: ComponentActionContext) -> Dict[str, Any]:
        return await UnslothSftModelTrainerTaskAction(action, self.config, self.model_path).run(context)

from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, List, Any
from mindor.dsl.schema.component import ModelTrainerTaskType, ModelTrainerDriverType
from mindor.dsl.schema.action import SftModelTrainerActionConfig
from .....context import ComponentActionContext
from ...base import HuggingfaceModelTrainerTaskDriver, register_model_trainer_task_driver
from .common import SftModelTrainerTaskAction

if TYPE_CHECKING:
    from transformers.trainer_utils import TrainOutput

class HuggingfaceSftModelTrainerTaskAction(SftModelTrainerTaskAction):
    def _train(
        self,
        training_arguments: Dict[str, Any],
        train_dataset: Any,
        evaluation_dataset: Any,
        dataset_text_field: str,
        max_seq_length: int,
        packing: bool,
        completion_only_loss: bool,
        output_dir: str,
    ) -> TrainOutput:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from trl import SFTTrainer, SFTConfig

        if self.trainer_config.quantization is not None:
            quantization_config = self._build_quantization_config(self.trainer_config.quantization)
        else:
            quantization_config = None

        if self.trainer_config.lora is not None:
            lora_config = self._build_lora_config(self.trainer_config.lora, task_type_hint="CAUSAL_LM")
        else:
            lora_config = None

        model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            quantization_config=quantization_config,
            device_map=self.trainer_config.device,
            torch_dtype=self._get_model_dtype(),
        )
        tokenizer = AutoTokenizer.from_pretrained(self.model_path)

        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        # Mirror the tokenizer's pad id onto the model config. Some architectures
        # (e.g. Qwen3) ship with pad_token_id=None; without this sync the
        # classification/causal forward pass raises when a batch has padding.
        if model.config.pad_token_id is None:
            model.config.pad_token_id = tokenizer.pad_token_id

        # Order matters for QLoRA: prepare_model_for_kbit_training() re-enables
        # input gradients and disables the base model's use_cache before LoRA
        # wraps the modules. See PEFT/QLoRA guide.
        if quantization_config is not None:
            from peft import prepare_model_for_kbit_training

            model = prepare_model_for_kbit_training(
                model,
                use_gradient_checkpointing=training_arguments.get("gradient_checkpointing", False),
            )

        if lora_config is not None:
            from peft import get_peft_model

            model = get_peft_model(model, lora_config)

        # When the dataset carries a `messages` column (either supplied by the
        # user or rewritten from prompt/response), route through the tokenizer's
        # chat template explicitly. TRL's conversational auto-detection compares
        # Feature objects and breaks across datasets versions; an explicit
        # formatting_func is the stable path.
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

        # apply_chat_template(tokenize=False) already emits BOS/EOS in the
        # formatted string. If the subsequent tokenization step also prepends
        # special tokens (the default) the model sees duplicated BOS/EOS, which
        # degrades loss and generation. TRL suppresses this on its auto-detection
        # path but not when a formatting_func is supplied — we opt out explicitly.
        sft_config_params: Dict[str, Any] = {
            "dataset_text_field":   dataset_text_field if formatting_func is None else None,
            "max_seq_length":       max_seq_length,
            "packing":              packing,
            "completion_only_loss": completion_only_loss,
        }

        if formatting_func is not None:
            sft_config_params["dataset_kwargs"] = { "add_special_tokens": False }

        sft_config = SFTConfig(
            **sft_config_params,
            **training_arguments,
        )

        trainer = SFTTrainer(
            model=model,
            args=sft_config,
            train_dataset=train_dataset,
            eval_dataset=evaluation_dataset,
            processing_class=tokenizer,  # replaces `tokenizer=` in TRL 0.12+
            formatting_func=formatting_func,
        )

        result = trainer.train()

        trainer.save_model(output_dir)
        tokenizer.save_pretrained(output_dir)

        return result

@register_model_trainer_task_driver(ModelTrainerTaskType.SFT, ModelTrainerDriverType.HUGGINGFACE)
class HuggingfaceSftTrainerTaskDriver(HuggingfaceModelTrainerTaskDriver):
    def _get_setup_requirements(self) -> List[str]:
        return [
            *super()._get_setup_requirements(),
            "trl>=0.12,<0.14",
        ]

    async def _run(self, action: SftModelTrainerActionConfig, context: ComponentActionContext) -> Dict[str, Any]:
        return await HuggingfaceSftModelTrainerTaskAction(action, self.config, self.model_path).run(context)

from __future__ import annotations
from typing import TYPE_CHECKING, Union, Tuple

from typing import Any, Dict, List, Optional
import sys, platform
from mindor.dsl.schema.component import ModelTrainerTaskType, ModelTrainerDriverType, LayaTypedDecisionModelTrainerComponentConfig
from mindor.dsl.schema.action import TypedDecisionModelTrainerActionConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.package.installer import install_package_from_github, is_package_installed
from .....context import ComponentActionContext
from ...base import ModelTrainerTaskDriver, register_model_trainer_task_driver
from .common import TypedDecisionModelTrainerTaskAction

if TYPE_CHECKING:
    pass


class LayaTypedDecisionModelTrainerTaskAction(TypedDecisionModelTrainerTaskAction):
    config: TypedDecisionModelTrainerActionConfig
    trainer_config: LayaTypedDecisionModelTrainerComponentConfig

    def _train(
        self,
        training_arguments: Dict[str, Any],
        train_dataset: Any,
        evaluation_dataset: Optional[Any],
        columns: Dict[str, Any],
        output_dir: str,
    ) -> Dict[str, Any]:
        from laya_trainer import LayaTrainerConfig, train

        # Laya's recipe owns its own LR schedule (cosine) and uses encoder/head
        # LR splits; map the trainer's global learning_rate onto the head LR so
        # the user still has a single DSL-level knob, and keep the encoder LR
        # at its upstream default unless `freeze_encoder=True` zeroes it out.
        config = LayaTrainerConfig(
            model_dir=self.model_path,
            output_dir=output_dir,
            state_column=columns["state_column"],
            schema_column=columns["schema_column"],
            answers_column=columns["answers_column"],
            num_train_epochs=training_arguments["num_train_epochs"],
            micro_batch_size=training_arguments["per_device_train_batch_size"],
            gradient_accumulation_steps=training_arguments["gradient_accumulation_steps"],
            head_learning_rate=training_arguments["learning_rate"],
            weight_decay=training_arguments["weight_decay"],
            max_grad_norm=training_arguments["max_grad_norm"],
            freeze_encoder=self.trainer_config.freeze_encoder,
            gradient_checkpointing=training_arguments["gradient_checkpointing"],
            seed=training_arguments["seed"],
            device=self.trainer_config.device,
            logging_steps=training_arguments["logging_steps"],
        )

        return train(train_dataset, config, eval_dataset=evaluation_dataset)


@register_model_trainer_task_driver(ModelTrainerTaskType.TYPED_DECISION, ModelTrainerDriverType.LAYA)
class LayaTypedDecisionModelTrainerTaskDriver(ModelTrainerTaskDriver):
    config: LayaTypedDecisionModelTrainerComponentConfig

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            *torch_requirements("torch>=2.0.0"),
            "transformers>=4.48.0",
            "safetensors>=0.4.0",
            "numpy>=1.20.0",
            "laya>=0.3.20",
            "huggingface_hub>=0.20.0",
        ]

    async def _setup(self) -> None:
        if not is_package_installed("laya_trainer"):
            await install_package_from_github(
                "laya_trainer",
                "https://github.com/hanyeol/mindor-laya-trainer.git",
                revision="v1.0.0",
                source_path=".",
            )

    async def _run(self, action: TypedDecisionModelTrainerActionConfig, context: ComponentActionContext) -> Dict[str, Any]:
        return await LayaTypedDecisionModelTrainerTaskAction(action, self.config, self.model_path).run(context)

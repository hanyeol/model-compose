from __future__ import annotations
from typing import TYPE_CHECKING, Union, Tuple

from typing import Any, Dict, List, Optional
from mindor.dsl.schema.component import ModelTrainerTaskType, ModelTrainerDriverType, KevTypedDecisionModelTrainerComponentConfig
from mindor.dsl.schema.action import TypedDecisionModelTrainerActionConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.package.installer import install_package_from_github, is_package_installed
from .....context import ComponentActionContext
from ...base import ModelTrainerTaskDriver, register_model_trainer_task_driver
from .common import TypedDecisionModelTrainerTaskAction
import sys, platform

if TYPE_CHECKING:
    pass

class KevTypedDecisionModelTrainerTaskAction(TypedDecisionModelTrainerTaskAction):
    config: TypedDecisionModelTrainerActionConfig
    trainer_config: KevTypedDecisionModelTrainerComponentConfig

    def _train(
        self,
        training_arguments: Dict[str, Any],
        train_dataset: Any,
        eval_dataset: Optional[Any],
        columns: Dict[str, Any],
        output_dir: str,
    ) -> Dict[str, Any]:
        from kev_trainer import KevTrainerConfig, train

        model_repository = getattr(self.trainer_config.model, "repository", None)
        model_local_path = getattr(self.trainer_config.model, "path", None)
        model_id = model_repository or model_local_path or self.model_path

        lora_rank = self.trainer_config.lora.rank if self.trainer_config.lora is not None else 8

        config = KevTrainerConfig(
            model_id=model_id,
            output_dir=output_dir,
            state_column=columns["state_column"],
            schema_column=columns["schema_column"],
            answers_column=columns["answers_column"],
            num_train_epochs=training_arguments["num_train_epochs"],
            per_device_train_batch_size=training_arguments["per_device_train_batch_size"],
            gradient_accumulation_steps=training_arguments["gradient_accumulation_steps"],
            learning_rate=training_arguments["learning_rate"],
            weight_decay=training_arguments["weight_decay"],
            max_grad_norm=training_arguments["max_grad_norm"],
            warmup_steps=training_arguments["warmup_steps"],
            seed=training_arguments["seed"],
            lora_rank=lora_rank,
            max_state_length=self.trainer_config.max_state_length,
            max_branch_length=self.trainer_config.max_branch_length,
            bf16=training_arguments["bf16"],
            fp16=training_arguments["fp16"],
            gradient_checkpointing=training_arguments["gradient_checkpointing"],
            logging_steps=training_arguments["logging_steps"],
            device=self.trainer_config.device,
        )

        return train(train_dataset, config, eval_dataset=eval_dataset)


@register_model_trainer_task_driver(ModelTrainerTaskType.TYPED_DECISION, ModelTrainerDriverType.KEV)
class KevTypedDecisionModelTrainerTaskDriver(ModelTrainerTaskDriver):
    config: KevTypedDecisionModelTrainerComponentConfig

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        requirements: List[str] = [
            *torch_requirements("torch>=2.6,<2.9"),
            "accelerate>=1.15",
            "peft>=0.21",
            "pydantic>=2.9",
            "transformers>=5.17,<6",
            "numpy>=2.5.3",
            "scikit-learn>=1.9.1",
            "huggingface_hub",
        ]

        if sys.platform == "darwin" and platform.machine() == "arm64":
            requirements.append("mlx-lm>=0.31.3,<0.32")

        return requirements

    async def _setup(self) -> None:
        if not is_package_installed("kev"):
            await install_package_from_github(
                "kev",
                "https://github.com/jaredpalmer/kev.git",
                revision="c9c1f8555053",
                source_path=".",
            )

        if not is_package_installed("kev_trainer"):
            await install_package_from_github(
                "kev_trainer",
                "https://github.com/hanyeol/mindor-kev-trainer.git",
                revision="v1.0.0",
                source_path=".",
            )

    async def _run(self, action: TypedDecisionModelTrainerActionConfig, context: ComponentActionContext) -> Dict[str, Any]:
        return await KevTypedDecisionModelTrainerTaskAction(action, self.config, self.model_path).run(context)

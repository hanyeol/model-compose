from __future__ import annotations
from typing import TYPE_CHECKING, Union, Tuple

from typing import Any, Dict, List, Optional
from mindor.dsl.schema.component import ModelTrainerTaskType, ModelTrainerDriverType, ClefTypedDecisionModelTrainerComponentConfig
from mindor.dsl.schema.action import TypedDecisionModelTrainerActionConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.package.installer import install_package_from_github, is_package_installed
from .....context import ComponentActionContext
from ...base import ModelTrainerTaskDriver, register_model_trainer_task_driver
from .common import TypedDecisionModelTrainerTaskAction

if TYPE_CHECKING:
    pass

class ClefTypedDecisionModelTrainerTaskAction(TypedDecisionModelTrainerTaskAction):
    config: TypedDecisionModelTrainerActionConfig
    trainer_config: ClefTypedDecisionModelTrainerComponentConfig

    def _train(
        self,
        training_arguments: Dict[str, Any],
        train_dataset: Any,
        eval_dataset: Optional[Any],
        columns: Dict[str, Any],
        output_dir: str,
    ) -> Dict[str, Any]:
        from clef_trainer import ClefTrainerConfig, train

        config = ClefTrainerConfig(
            model_path=self.model_path,
            output_dir=output_dir,
            state_column=columns["state_column"],
            schema_column=columns["schema_column"],
            answers_column=columns["answers_column"],
            learning_rate=training_arguments["learning_rate"],
            per_device_train_batch_size=training_arguments["per_device_train_batch_size"],
            per_device_eval_batch_size=training_arguments["per_device_eval_batch_size"],
            num_train_epochs=training_arguments["num_train_epochs"],
            weight_decay=training_arguments["weight_decay"],
            warmup_steps=training_arguments["warmup_steps"],
            max_grad_norm=training_arguments["max_grad_norm"],
            gradient_accumulation_steps=training_arguments["gradient_accumulation_steps"],
            optim=training_arguments["optim"],
            lr_scheduler_type=training_arguments["lr_scheduler_type"],
            seed=training_arguments["seed"],
            fp16=training_arguments["fp16"],
            bf16=training_arguments["bf16"],
            gradient_checkpointing=training_arguments["gradient_checkpointing"],
            logging_steps=training_arguments["logging_steps"],
            eval_steps=training_arguments["eval_steps"],
            save_steps=training_arguments["save_steps"],
            choice_loss_weight=self.trainer_config.choice_loss_weight,
            noul_loss_weight=self.trainer_config.noul_loss_weight,
            score_loss_weight=self.trainer_config.score_loss_weight,
            device=self.trainer_config.device,
        )

        return train(train_dataset, config, eval_dataset=eval_dataset)

@register_model_trainer_task_driver(ModelTrainerTaskType.TYPED_DECISION, ModelTrainerDriverType.CLEF)
class ClefTypedDecisionModelTrainerTaskDriver(ModelTrainerTaskDriver):
    config: ClefTypedDecisionModelTrainerComponentConfig

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        # Clef trainer brings its own transformers / datasets / safetensors pins
        # via its pyproject; here we only guarantee torch (installed through the
        # project's shared torch pin logic) and huggingface_hub for the
        # provisioner that fetches the Cloudflare/clef snapshot.
        return [
            *torch_requirements("torch>=2.11"),
            "transformers>=5.10.2",
            "huggingface_hub",
        ]

    async def _setup(self) -> None:
        if not is_package_installed("clef_trainer"):
            await install_package_from_github(
                "clef_trainer",
                "https://github.com/hanyeol/mindor-clef-trainer.git",
                revision="v1.0.0",
                source_path=".",
            )

    async def _run(self, action: TypedDecisionModelTrainerActionConfig, context: ComponentActionContext) -> Dict[str, Any]:
        return await ClefTypedDecisionModelTrainerTaskAction(action, self.config, self.model_path).run(context)

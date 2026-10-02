from __future__ import annotations
from typing import TYPE_CHECKING, Union, Tuple

from typing import Any, Dict, List, Optional
import sys, platform
from mindor.dsl.schema.component import ModelTrainerTaskType, ModelTrainerDriverType, NimbleTypedDecisionModelTrainerComponentConfig
from mindor.dsl.schema.action import TypedDecisionModelTrainerActionConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.package.installer import install_package_from_github, is_package_installed
from .....context import ComponentActionContext
from ...base import ModelTrainerTaskDriver, register_model_trainer_task_driver
from .common import TypedDecisionModelTrainerTaskAction

if TYPE_CHECKING:
    pass

class NimbleTypedDecisionModelTrainerTaskAction(TypedDecisionModelTrainerTaskAction):
    config: TypedDecisionModelTrainerActionConfig
    trainer_config: NimbleTypedDecisionModelTrainerComponentConfig

    def _train(
        self,
        training_arguments: Dict[str, Any],
        train_dataset: Any,
        evaluation_dataset: Optional[Any],
        columns: Dict[str, Any],
        output_dir: str,
    ) -> Dict[str, Any]:
        from nimble_trainer import NimbleTrainerConfig, train

        # Translate the generic trainer schedule into Nimble's step-based CLI
        # vocabulary.  Upstream uses --max_steps; map epochs onto a step count
        # by rounding to the dataset's size at training time.  Users who want
        # a step-based run can set num_epochs=1 and override max_steps via a
        # downstream patch.
        base_model_repository = getattr(self.trainer_config.base_model, "repository", None)
        base_model_path = getattr(self.trainer_config.base_model, "path", None)
        model_id = base_model_repository or base_model_path

        if model_id is None:
            raise ValueError("nimble trainer requires `base_model` with either `repository` or `path`")

        # Nimble's trainer expects max_steps, learning_rate etc.  Derive a
        # step budget: one epoch of a dataset is len(train_dataset) /
        # (batch * grad_accum) steps.  Multiply by num_epochs.
        try:
            dataset_rows = len(train_dataset)
        except TypeError:
            dataset_rows = 0

        epochs = training_arguments["num_train_epochs"]
        batch = training_arguments["per_device_train_batch_size"]
        accum = training_arguments["gradient_accumulation_steps"]
        max_steps = max(1, int(round(dataset_rows * epochs / max(1, batch * accum)))) if dataset_rows > 0 else 2000

        lora_rank = self.trainer_config.lora.rank if self.trainer_config.lora is not None else 8
        lora_alpha = self.trainer_config.lora.alpha if self.trainer_config.lora is not None else None
        lora_dropout = self.trainer_config.lora.dropout if self.trainer_config.lora is not None else 0.05

        config = NimbleTrainerConfig(
            model_id=model_id,
            revision=getattr(self.trainer_config.base_model, "revision", None),
            output_dir=output_dir,
            state_column=columns["state_column"],
            schema_column=columns["schema_column"],
            answers_column=columns["answers_column"],
            max_steps=max_steps,
            learning_rate=training_arguments["learning_rate"],
            per_device_train_batch_size=batch,
            gradient_accumulation_steps=accum,
            warmup_steps=training_arguments["warmup_steps"],
            weight_decay=training_arguments["weight_decay"],
            max_grad_norm=training_arguments["max_grad_norm"],
            seed=training_arguments["seed"],
            max_length=self.trainer_config.max_seq_length,
            lora_rank=lora_rank,
            lora_alpha=lora_alpha,
            lora_dropout=lora_dropout,
            bf16=training_arguments["bf16"],
            gradient_checkpointing=training_arguments["gradient_checkpointing"],
            save_steps=training_arguments["save_steps"],
            logging_steps=training_arguments["logging_steps"],
            device=self.trainer_config.device,
        )

        return train(train_dataset, config, eval_dataset=evaluation_dataset)

@register_model_trainer_task_driver(ModelTrainerTaskType.TYPED_DECISION, ModelTrainerDriverType.NIMBLE)
class NimbleTypedDecisionModelTrainerTaskDriver(ModelTrainerTaskDriver):
    config: NimbleTypedDecisionModelTrainerComponentConfig

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        # Mirror the inference-side driver's platform-conditioned pins so the
        # trainer resolves against the same wheels the scorer uses on this host.
        requirements: List[str] = []

        if sys.platform == "linux" and platform.machine() in ("x86_64", "aarch64"):
            requirements.extend([
                *torch_requirements("torch>=2.8,<3"),
                "accelerate==1.15.0",
                "sentencepiece==0.2.2",
            ])

        if sys.platform == "darwin" and platform.machine() == "arm64":
            requirements.extend([
                "mlx==0.32.2",
                "mlx-lm==0.31.3",
            ])

        requirements.extend([
            "transformers==5.17.0",
            "peft==0.21.0",
            "huggingface_hub",
        ])

        return requirements

    async def _setup(self) -> None:
        # Nimble upstream has no PyPI release and no pyproject at the repo root
        # (the trainer-relevant code sits under the `nimble/` subdir); drop that
        # subdir onto sys.path alongside mindor the same way the inference driver
        # does.
        if not is_package_installed("nimble"):
            await install_package_from_github(
                "nimble",
                "https://github.com/bespokelabsai/nimble.git",
                revision="f136b3f75721",
                subdirs=[ "nimble" ],
            )

        if not is_package_installed("nimble_trainer"):
            await install_package_from_github(
                "nimble_trainer",
                "https://github.com/hanyeol/mindor-nimble-trainer.git",
                revision="v1.0.0",
                source_path=".",
            )

    async def _run(self, action: TypedDecisionModelTrainerActionConfig, context: ComponentActionContext) -> Dict[str, Any]:
        return await NimbleTypedDecisionModelTrainerTaskAction(action, self.config, self.model_path).run(context)

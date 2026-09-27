from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from abc import abstractmethod
from mindor.dsl.schema.component import ModelTrainerComponentConfig
from mindor.dsl.schema.action import SftModelTrainerActionConfig
from .....context import ComponentActionContext
from ...base import ModelTrainerTaskAction

if TYPE_CHECKING:
    from transformers.trainer_utils import TrainOutput

class SftModelTrainerTaskAction(ModelTrainerTaskAction):
    config: SftModelTrainerActionConfig

    def __init__(self, config: SftModelTrainerActionConfig, trainer_config: ModelTrainerComponentConfig, model_path: str):
        super().__init__(config, trainer_config, model_path)

    async def run(self, context: ComponentActionContext) -> Dict[str, Any]:
        # Render every templated field OUTSIDE the executor — async can't run inside.
        dataset            = await context.render_variable(self.config.dataset)
        evaluation_dataset = await context.render_variable(self.config.evaluation_dataset) if self.config.evaluation_dataset is not None else None
        output_dir         = await context.render_text(self.config.output_dir)

        # Dataset loading, split resolution, and building the messages column all
        # touch disk / network and can block for a long time — keep them off the
        # event loop. eval_strategy reflects what _load_datasets actually surfaces
        # (either action.evaluation_dataset OR a DatasetDict split), so training
        # arguments must be built AFTER split resolution.
        train_dataset, evaluation_dataset = await self._run_in_executor(
            self._prepare_datasets,
            dataset,
            evaluation_dataset,
        )
        training_arguments = await self._build_training_arguments(context, output_dir, has_evaluation=evaluation_dataset is not None)

        # SFTTrainer routes on dataset_text_field. When the user supplied
        # (prompt, response) we built a canonical `messages` column, so the
        # driver-side field name aligns with that column.
        dataset_text_field = self.config.text_column if self.config.text_column is not None else "messages"

        result = await self._run_in_executor(
            self._train,
            training_arguments,
            train_dataset,
            evaluation_dataset,
            dataset_text_field,
            output_dir,
        )

        return {
            "output_dir": output_dir,
            "train_loss": result.training_loss,
            "metrics":    dict(result.metrics),
        }

    def _prepare_datasets(self, dataset: Any, evaluation_dataset: Any) -> Tuple[Any, Optional[Any]]:
        train_dataset, evaluation_dataset = self._load_datasets(dataset, evaluation_dataset)

        # Only build the messages column when the user supplied (prompt, response);
        # text_column mode passes through untouched.
        if self.config.text_column is None and self.config.prompt_column is not None and self.config.response_column is not None:
            train_dataset = self._build_messages_column(train_dataset)

            if evaluation_dataset is not None:
                evaluation_dataset = self._build_messages_column(evaluation_dataset)

        return train_dataset, evaluation_dataset

    def _build_messages_column(self, dataset: Any) -> Any:
        prompt_column   = self.config.prompt_column
        response_column = self.config.response_column
        system_column   = self.config.system_column

        def _to_messages(example: Dict[str, Any]) -> Dict[str, Any]:
            messages: List[Dict[str, str]] = []

            if system_column is not None and example.get(system_column):
                messages.append({ "role": "system", "content": example[system_column] })

            messages.append({ "role": "user",      "content": example[prompt_column] })
            messages.append({ "role": "assistant", "content": example[response_column] })

            return { "messages": messages }

        drop_columns = [ column for column in (prompt_column, response_column, system_column) if column is not None ]

        return dataset.map(_to_messages, remove_columns=drop_columns)

    @abstractmethod
    def _train(
        self,
        training_arguments: Dict[str, Any],
        train_dataset: Any,
        evaluation_dataset: Any,
        dataset_text_field: str,
        output_dir: str,
    ) -> TrainOutput:
        pass

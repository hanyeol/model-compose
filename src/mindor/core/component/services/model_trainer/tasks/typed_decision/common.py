from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Any, Dict, Optional, Tuple
from abc import abstractmethod
from mindor.dsl.schema.component import ModelTrainerComponentConfig
from mindor.dsl.schema.action import TypedDecisionModelTrainerActionConfig
from .....context import ComponentActionContext
from ...base import ModelTrainerTaskAction

if TYPE_CHECKING:
    pass

class TypedDecisionModelTrainerTaskAction(ModelTrainerTaskAction):
    config: TypedDecisionModelTrainerActionConfig

    def __init__(self, config: TypedDecisionModelTrainerActionConfig, trainer_config: ModelTrainerComponentConfig, model_path: str):
        super().__init__(config, trainer_config, model_path)

    async def run(self, context: ComponentActionContext) -> Dict[str, Any]:
        dataset            = await context.render_variable(self.config.dataset)
        evaluation_dataset = await context.render_variable(self.config.evaluation_dataset) if self.config.evaluation_dataset is not None else None
        state_column       = await context.render_text(self.config.state_column)
        schema_column      = await context.render_text(self.config.schema_column)
        answers_column     = await context.render_text(self.config.answers_column)
        max_seq_length     = await context.render_scalar(self.config.max_seq_length, int)
        output_dir         = await context.render_text(self.config.output_dir)

        # Loading HuggingFace datasets touches disk; keep it off the event loop.
        train_dataset, evaluation_dataset = await self._run_in_executor(
            self._load_datasets, dataset, evaluation_dataset,
        )

        self._validate_columns(train_dataset, state_column, schema_column, answers_column)

        if evaluation_dataset is not None:
            self._validate_columns(evaluation_dataset, state_column, schema_column, answers_column)

        training_arguments = await self._build_training_arguments(
            context, output_dir, has_evaluation=evaluation_dataset is not None,
        )

        columns = {
            "state_column":    state_column,
            "schema_column":   schema_column,
            "answers_column":  answers_column,
            "max_seq_length":  max_seq_length,
        }

        result = await self._run_in_executor(
            self._train,
            training_arguments,
            train_dataset,
            evaluation_dataset,
            columns,
            output_dir,
        )

        return {
            "output_dir": output_dir,
            **result,
        }

    def _validate_columns(self, dataset: Any, state_column: str, schema_column: str, answers_column: str) -> None:
        column_names = getattr(dataset, "column_names", None)
        if column_names is None:
            # Streaming / plain-dict iterables don't expose column_names — defer
            # validation to the family-specific trainer which iterates rows.
            return

        missing = [ name for name in (state_column, schema_column, answers_column) if name not in column_names ]

        if missing:
            raise ValueError(
                f"dataset is missing required typed-decision column(s): {missing!r}; "
                f"available columns: {list(column_names)!r}"
            )

    @abstractmethod
    def _train(
        self,
        training_arguments: Dict[str, Any],
        train_dataset: Any,
        evaluation_dataset: Optional[Any],
        columns: Dict[str, Any],
        output_dir: str,
    ) -> Dict[str, Any]:
        pass

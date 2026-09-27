from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Set, Any
from abc import abstractmethod
from mindor.dsl.schema.component import ModelTrainerComponentConfig
from mindor.dsl.schema.action import TextClassificationModelTrainerActionConfig
from .....context import ComponentActionContext
from ...base import ModelTrainerTaskAction

if TYPE_CHECKING:
    from transformers.trainer_utils import TrainOutput

class TextClassificationModelTrainerTaskAction(ModelTrainerTaskAction):
    config: TextClassificationModelTrainerActionConfig

    def __init__(self, config: TextClassificationModelTrainerActionConfig, trainer_config: ModelTrainerComponentConfig, model_path: str):
        super().__init__(config, trainer_config, model_path)

    async def run(self, context: ComponentActionContext) -> Dict[str, Any]:
        dataset            = await context.render_variable(self.config.dataset)
        evaluation_dataset = await context.render_variable(self.config.evaluation_dataset) if self.config.evaluation_dataset is not None else None
        text_column        = await context.render_text(self.config.text_column)
        label_column       = await context.render_text(self.config.label_column)
        label_names        = await context.render_variable(self.config.label_names) if self.config.label_names is not None else None
        num_labels         = await context.render_scalar(self.config.num_labels, int)
        output_dir         = await context.render_text(self.config.output_dir)

        # Dataset load, split resolution, and label scanning all touch disk and
        # can iterate multi-million rows — keep them off the event loop.
        train_dataset, evaluation_dataset, label_names, num_labels, label_remap = await self._run_in_executor(
            self._prepare_datasets,
            dataset,
            evaluation_dataset,
            label_column,
            label_names,
            num_labels,
        )
        training_arguments = await self._build_training_arguments(
            context,
            output_dir,
            has_evaluation=evaluation_dataset is not None
        )

        result = await self._run_in_executor(
            self._train,
            training_arguments,
            train_dataset,
            evaluation_dataset,
            text_column,
            label_column,
            label_names,
            num_labels,
            label_remap,
            output_dir,
        )

        return {
            "output_dir": output_dir,
            "train_loss": result.training_loss,
            "metrics":    dict(result.metrics),
        }

    def _prepare_datasets(
        self,
        dataset: Any,
        evaluation_dataset: Any,
        label_column: str,
        label_names: Optional[List[str]],
        num_labels: Optional[int],
    ) -> Tuple[Any, Optional[Any], Optional[List[str]], int, Optional[Dict[int, int]]]:
        train_dataset, evaluation_dataset = self._load_datasets(dataset, evaluation_dataset)
        label_names, num_labels, label_remap = self._resolve_labels(
            train_dataset,
            label_column,
            label_names,
            num_labels
        )

        return train_dataset, evaluation_dataset, label_names, num_labels, label_remap

    def _resolve_labels(
        self,
        train_dataset: Any,
        label_column: str,
        label_names: Optional[List[str]],
        num_labels: Optional[int],
    ) -> Tuple[Optional[List[str]], int, Optional[Dict[int, int]]]:
        """Return (label_names, num_labels, label_remap).

        Resolution order for the label list:
            1. explicit action.label_names
            2. ClassLabel.names on the training feature
            3. distinct label values scanned from the split (no names)

        `label_remap` is None when the observed label domain is already the
        contiguous {0, ..., num_labels-1}. Otherwise it maps observed values to
        contiguous indices so the classifier head's output range is valid —
        e.g. labels {1, 2} become {0, 1}. When action.label_names or
        ClassLabel.names is present its ordering fixes the remap; when only
        the observed values are known they are sorted.

        Fails explicitly on inconsistencies (num_labels vs label_names length,
        observed values vs declared num_labels).
        """
        from datasets import ClassLabel

        label_values = self._collect_label_values(train_dataset, label_column)
        label_index_order: Optional[List[int]] = None

        if label_names is not None:
            # When label_names is given, observed values must be integer indices into it.
            if label_values - set(range(len(label_names))):
                raise ValueError(
                    f"label_column {label_column!r} contains values outside "
                    f"range(len(label_names)={len(label_names)}); got {sorted(label_values)!r}."
                )

            label_index_order = list(range(len(label_names)))
        else:
            feature = train_dataset.features.get(label_column)

            if isinstance(feature, ClassLabel):
                label_names = list(feature.names)

                if label_values - set(range(feature.num_classes)):
                    raise ValueError(
                        f"label_column {label_column!r} contains values outside "
                        f"ClassLabel.num_classes={feature.num_classes}; got {sorted(label_values)!r}."
                    )

                label_index_order = list(range(feature.num_classes))
            else:
                # No names available — sort observed values to get a stable index mapping.
                label_index_order = sorted(label_values)

        if num_labels is not None and num_labels != len(label_index_order):
            raise ValueError(
                f"num_labels={num_labels} does not match the resolved label count "
                f"({len(label_index_order)} from {'label_names' if label_names else 'dataset scan'})."
            )

        num_labels = len(label_index_order)

        # Build remap only when the label domain is not already contiguous {0..N-1}.
        if label_index_order == list(range(num_labels)):
            label_remap = None
        else:
            label_remap = { label: index for index, label in enumerate(label_index_order) }

        return label_names, num_labels, label_remap

    def _collect_label_values(self, dataset: Any, label_column: str) -> Set[int]:
        # Cheap for GLUE-sized datasets, expensive for multi-million-row corpora.
        # Users can avoid the scan on huge datasets by declaring `label_names`
        # (the resolver only uses this scan for validation, not enumeration).
        #
        # Reject non-integer labels explicitly. A bare `int(value)` would silently
        # collapse [0.2, 0.8] to {0} and let training proceed with a single-class
        # head over floating-point targets. Booleans are also excluded — they are
        # a subclass of int in Python but almost always indicate schema confusion
        # in a classification dataset.
        label_values: Set[int] = set()

        for value in dataset[label_column]:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(
                    f"label_column {label_column!r} contains a non-integer value {value!r} "
                    f"(type {type(value).__name__}). Classification requires integer class "
                    f"indices; convert or bucket the column before training."
                )

            label_values.add(value)

        return label_values

    @abstractmethod
    def _train(
        self,
        training_arguments: Dict[str, Any],
        train_dataset: Any,
        evaluation_dataset: Any,
        text_column: str,
        label_column: str,
        label_names: Optional[List[str]],
        num_labels: int,
        label_remap: Optional[Dict[int, int]],
        output_dir: str,
    ) -> TrainOutput:
        pass

from __future__ import annotations
from typing import TYPE_CHECKING, Union, Tuple

from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelTrainerTaskType, ModelTrainerDriverType
from mindor.dsl.schema.action import TextClassificationModelTrainerActionConfig
from .....context import ComponentActionContext
from ...base import HuggingfaceModelTrainerTaskDriver, register_model_trainer_task_driver
from .common import TextClassificationModelTrainerTaskAction

if TYPE_CHECKING:
    from transformers.trainer_utils import TrainOutput

class HuggingfaceTextClassificationModelTrainerTaskAction(TextClassificationModelTrainerTaskAction):
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
        max_seq_length: Optional[int],
        output_dir: str,
    ) -> TrainOutput:
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
            DataCollatorWithPadding,
            Trainer,
            TrainingArguments,
        )

        if self.trainer_config.quantization is not None:
            quantization_config = self._build_quantization_config(self.trainer_config.quantization)
        else:
            quantization_config = None

        if self.trainer_config.lora is not None:
            lora_config = self._build_lora_config(self.trainer_config.lora, task_type_hint="SEQ_CLS")
        else:
            lora_config = None

        tokenizer = AutoTokenizer.from_pretrained(self.model_path)

        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        model_params: Dict[str, Any] = {
            "num_labels":          num_labels,
            "quantization_config": quantization_config,
            "device_map":          self.trainer_config.device,
            "torch_dtype":         self._get_model_dtype(),
        }

        if label_names is not None:
            model_params["id2label"] = { index: name for index, name in enumerate(label_names) }
            model_params["label2id"] = { name: index for index, name in enumerate(label_names) }

        model = AutoModelForSequenceClassification.from_pretrained(self.model_path, **model_params)

        # Mirror the tokenizer's pad id onto the model config. Some architectures
        # (e.g. Qwen3) ship with pad_token_id=None; the sequence-classification
        # forward pass raises when a batch has padding without this sync.
        if model.config.pad_token_id is None:
            model.config.pad_token_id = tokenizer.pad_token_id

        if quantization_config is not None:
            from peft import prepare_model_for_kbit_training

            model = prepare_model_for_kbit_training(
                model,
                use_gradient_checkpointing=training_arguments.get("gradient_checkpointing", False),
            )

        if lora_config is not None:
            from peft import get_peft_model

            model = get_peft_model(model, lora_config)

        def _tokenize(examples: Dict[str, Any]) -> Dict[str, Any]:
            # Dynamic padding via DataCollatorWithPadding at batch time — padding
            # to max_seq_length here would inflate short-input datasets (e.g.
            # sentence-level classification) with mostly-pad tokens.
            return tokenizer(
                examples[text_column],
                truncation=True,
                max_length=max_seq_length,
            )

        train_dataset = train_dataset.map(_tokenize, batched=True)

        if evaluation_dataset is not None:
            evaluation_dataset = evaluation_dataset.map(_tokenize, batched=True)

        # Remap observed label values to contiguous 0..N-1 indices when the label
        # domain is non-contiguous (e.g. {1, 2}). Without this the classifier head,
        # which outputs indices 0..num_labels-1, would compute loss against
        # out-of-range targets.
        if label_remap is not None:
            def _remap(example: Dict[str, Any]) -> Dict[str, Any]:
                return { label_column: label_remap[int(example[label_column])] }

            train_dataset = train_dataset.map(_remap)

            if evaluation_dataset is not None:
                evaluation_dataset = evaluation_dataset.map(_remap)

        # Rename the label column to `labels` — the canonical name expected by
        # transformers' data collators and loss computation.
        if label_column != "labels":
            train_dataset = train_dataset.rename_column(label_column, "labels")

            if evaluation_dataset is not None:
                evaluation_dataset = evaluation_dataset.rename_column(label_column, "labels")

        trainer_arguments = TrainingArguments(**training_arguments)

        trainer = Trainer(
            model=model,
            args=trainer_arguments,
            train_dataset=train_dataset,
            eval_dataset=evaluation_dataset,
            processing_class=tokenizer,
            data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
            compute_metrics=self._compute_metrics if evaluation_dataset is not None else None,
        )

        result = trainer.train()

        trainer.save_model(output_dir)
        tokenizer.save_pretrained(output_dir)

        return result

    @staticmethod
    def _compute_metrics(eval_prediction: Any) -> Dict[str, float]:
        # Report accuracy plus macro-averaged precision/recall/F1. Macro is the
        # right default for classification: it weights all classes equally, so
        # a minority class collapsing does not get hidden behind a majority-class
        # score. Callers who want a different average can subclass and override.
        from sklearn.metrics import accuracy_score, precision_recall_fscore_support
        import numpy as np

        predictions = np.argmax(eval_prediction.predictions, axis=-1)
        labels = eval_prediction.label_ids

        precision, recall, f1, _ = precision_recall_fscore_support(
            labels, predictions, average="macro", zero_division=0
        )

        return {
            "accuracy":  accuracy_score(labels, predictions),
            "precision": precision,
            "recall":    recall,
            "f1":        f1,
        }

@register_model_trainer_task_driver(ModelTrainerTaskType.TEXT_CLASSIFICATION, ModelTrainerDriverType.HUGGINGFACE)
class HuggingfaceTextClassificationTrainerTaskDriver(HuggingfaceModelTrainerTaskDriver):
    def _get_setup_requirements(self) -> List[Union[str, Tuple[str, List[str]]]]:
        return [
            *super()._get_setup_requirements(),
            "scikit-learn",
        ]

    async def _run(self, action: TextClassificationModelTrainerActionConfig, context: ComponentActionContext) -> Dict[str, Any]:
        return await HuggingfaceTextClassificationModelTrainerTaskAction(action, self.config, self.model_path).run(context)

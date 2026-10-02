from __future__ import annotations
from typing import TYPE_CHECKING, Union, Tuple

from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import ClefTypedDecisionModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, TypedDecisionModelActionConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.cancellation import CancellationToken
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import TypedDecisionTaskAction
import sys

class ClefTypedDecisionTaskAction(TypedDecisionTaskAction):
    def __init__(
        self,
        config: TypedDecisionModelActionConfig,
        model: Any,
        processor: Any,
        device: str,
        model_path: str,
    ):
        super().__init__(config)

        self.model: Any = model
        self.processor: Any = processor
        self.device: str = device
        self.model_path: str = model_path

    async def _score_batch(
        self,
        texts: List[str],
        schema: Dict[str, Any],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        def _score() -> List[Dict[str, Any]]:
            import torch
            from joint_schema_model import collate_records, encode_record

            device = torch.device(self.device) if self.device not in (None, "auto") else next(self.model.parameters()).device

            results: List[Dict[str, Any]] = []

            for text in texts:
                record = { "state": text, "questions": schema }
                record = encode_record(self.processor.tokenizer, record, processor=self.processor)
                records = collate_records([ record ], self.processor.tokenizer.pad_token_id, device)

                with torch.inference_mode():
                    logits = self.model(records)[0]

                results.append(self._build_decision_result(record, logits, schema, params))

            return results

        return await self._run_in_executor(_score)

    def _build_decision_result(self, record: Any, logits: Any, schema: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        # Clef's joint schema head returns one logit vector per question; apply per-question softmax
        # for probabilities, then flatten to the typed-decision task's { decision, fields } contract.
        decision: Dict[str, Any] = {}
        fields: Dict[str, Any] = {}

        for question, question_logits in zip(record.questions, logits):
            question_id = question.question_id
            option_ids = list(question.option_ids)
            probabilities = question_logits.float().softmax(-1).tolist()
            scores = dict(zip(option_ids, probabilities))

            question_type = (schema.get(question_id) or {}).get("type")

            if question_type == "noul":
                probability_true = scores.get("true", scores.get("yes", 0.0))
                decision[question_id] = probability_true >= 0.5
            elif question_type in ("choice", "score"):
                decision[question_id] = max(scores, key=scores.get)
            else:
                decision[question_id] = max(scores, key=scores.get)

            field: Dict[str, Any] = {}

            if params["return_probabilities"]:
                field["scores"] = scores

            if params["return_logits"]:
                field["logits"] = dict(zip(option_ids, question_logits.float().tolist()))

            if field:
                fields[question_id] = field

        result: Dict[str, Any] = { "decision": decision }

        if fields:
            result["fields"] = fields

        return result

class ClefTypedDecisionTaskDriver(ModelTaskDriver):
    config: ClefTypedDecisionModelComponentConfig

    def __init__(self, id: str, config: ClefTypedDecisionModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Any] = None
        self.processor: Optional[Any] = None
        self.model_path: Optional[str] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        # Clef ships the `joint_schema_model` module inside its HF repo (no pip package),
        # so we only need the runtime deps the module imports.
        return [
            *torch_requirements("torch>=2.11"),
            "transformers>=5.10.2",
            "accelerate",
            "huggingface_hub",
        ]

    async def _load_model(self) -> None:
        model_path = await self._provision_model(self.config.model, prefetch=True)
        device = self._resolve_device(self.config.device)

        def _load() -> Tuple[Any, Any, str]:
            # joint_schema_model lives at the snapshot root rather than as an installable package,
            # so put the snapshot on sys.path before importing it.
            if model_path not in sys.path:
                sys.path.insert(0, model_path)

            from joint_schema_model import load_release_model

            loaded_model, loaded_processor = load_release_model(model_path, device=device)
            return loaded_model, loaded_processor, model_path

        self.model, self.processor, self.model_path = await self._run_in_executor(_load)

    async def _unload_model(self) -> None:
        self.model = None
        self.processor = None
        self.model_path = None

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await ClefTypedDecisionTaskAction(
            action,
            self.model,
            self.processor,
            self.config.device,
            self.model_path,
        ).run(context)

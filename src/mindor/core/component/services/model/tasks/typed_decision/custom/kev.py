from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from mindor.dsl.schema.action import ModelActionConfig, TypedDecisionModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.package.installer import install_package_from_github
from mindor.core.foundation.package.torch import torch_requirements
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import TypedDecisionTaskAction
import importlib.util
import os, sys, platform

if TYPE_CHECKING:
    from mindor.dsl.schema.component import KevTypedDecisionModelComponentConfig

class KevTypedDecisionTaskAction(TypedDecisionTaskAction):
    def __init__(
        self,
        config: TypedDecisionModelActionConfig,
        tokenizer: Any,
        model: Any,
        max_state: int,
        max_branch: int,
    ):
        super().__init__(config)

        self.tokenizer: Any = tokenizer
        self.model: Any = model
        self.max_state: int = max_state
        self.max_branch: int = max_branch

    async def _score_batch(
        self,
        texts: List[str],
        schema: Dict[str, Any],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        from kev.api import SystemOneRequest, to_record, to_answers

        def _score() -> List[Dict[str, Any]]:
            results: List[Dict[str, Any]] = []

            for text in texts:
                request = SystemOneRequest(state=text, model="kev", questions=schema)
                record, meta = to_record(request)
                encoding = self.model.encode(self.tokenizer, record, max_state=self.max_state, max_branch=self.max_branch)
                probabilities = self.model.probs(encoding)
                answers = to_answers([ probability.tolist() for probability in probabilities ], meta)
                results.append(self._build_decision_result(answers, params))

            return results

        return await self._run_in_executor(_score)

    def _build_decision_result(self, answers: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        # kev.api.to_answers already returns per-question dicts shaped like
        # { "type": "noul", "noul": p } / { "type": "choice", "choice": name, "probabilities": {...}, "confidence": c }
        # / { "type": "score", "score": expected, "probabilities": {...}, "legend": {...}, "confidence": c }.
        # Flatten to the typed-decision task's common { decision, fields } contract.
        decision: Dict[str, Any] = {}
        fields: Dict[str, Any] = {}

        for question_id, answer in answers.items():
            question_type = answer.get("type")

            if question_type == "noul":
                probability_true = answer["noul"]
                decision[question_id] = probability_true >= 0.5

                if params["return_probabilities"]:
                    fields[question_id] = {
                        "scores": {
                            "true": probability_true,
                            "false": 1.0 - probability_true
                        }
                    }
            elif question_type == "choice":
                decision[question_id] = answer["choice"]

                if params["return_probabilities"]:
                    fields[question_id] = {
                        "scores": answer.get("probabilities", {})
                    }
            elif question_type == "score":
                decision[question_id] = answer["score"]

                if params["return_probabilities"]:
                    fields[question_id] = {
                        "scores": answer.get("probabilities", {})
                    }
            else:
                decision[question_id] = answer

        result: Dict[str, Any] = { "decision": decision }

        if fields:
            result["fields"] = fields

        return result

class KevTypedDecisionTaskDriver(ModelTaskDriver):
    config: KevTypedDecisionModelComponentConfig

    def __init__(self, id: str, config: KevTypedDecisionModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.tokenizer: Optional[Any] = None
        self.model: Optional[Any] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        # Mirror kev's own inference-only pins from pyproject.toml.
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

        # kev's MLX fast path is Apple Silicon only.
        if sys.platform == "darwin" and platform.machine() == "arm64":
            requirements.append("mlx-lm>=0.31.3,<0.32")

        return requirements

    async def _setup(self) -> None:
        # kev ships a proper pyproject.toml; install it as a normal package.
        # Revision pinned to jaredpalmer/kev@main as of 2026-09-24.
        if importlib.util.find_spec("kev") is None:
            await install_package_from_github(
                "kev",
                "https://github.com/jaredpalmer/kev.git",
                revision="c9c1f855505336ac32092a5f68305d397f7fcc3e",
                source_path=".",
            )

    async def _load_model(self) -> None:
        self.tokenizer, self.model = await self._load_checkpoint()

    async def _unload_model(self) -> None:
        self.tokenizer = None
        self.model = None

    async def _load_checkpoint(self) -> Any:
        model_path = await self._provision_model(self.config.model, prefetch=True)
        backend = self.config.backend.value

        def _load():
            from kev.checkpoint import Checkpoint, LoadOptions
            from kev.device import default_device

            options = LoadOptions.from_env()

            if backend != "auto" and hasattr(options, "model_copy"):
                options = options.model_copy(update={ "backend": backend })

            return Checkpoint(model_path).load(default_device(), options)

        return await self._run_in_executor(_load)

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await KevTypedDecisionTaskAction(
            action,
            self.tokenizer,
            self.model,
            self.config.max_state,
            self.config.max_branch,
        ).run(context)

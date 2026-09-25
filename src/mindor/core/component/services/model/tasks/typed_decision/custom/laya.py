from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from mindor.dsl.schema.action import ModelActionConfig, TypedDecisionModelActionConfig
from mindor.dsl.schema.component import LayaTypedDecisionModelComponentConfig, LayaPreset
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.package.torch import torch_requirements
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import TypedDecisionTaskAction
import sys, platform

if TYPE_CHECKING:
    from laya import Agent as LayaAgent

class LayaTypedDecisionTaskAction(TypedDecisionTaskAction):
    def __init__(
        self,
        config: TypedDecisionModelActionConfig,
        agent: LayaAgent,
        max_seq_length: Optional[int],
        max_head_length: Optional[int],
    ):
        super().__init__(config)

        self.agent: LayaAgent = agent
        self.max_seq_length: Optional[int] = max_seq_length
        self.max_head_length: Optional[int] = max_head_length

    async def _score_batch(
        self,
        texts: List[str],
        schema: Dict[str, Any],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        def _score() -> List[Dict[str, Any]]:
            # Map to laya's own kwargs; upstream still names them max_len / head_max_len.
            predict_params: Dict[str, Any] = {}

            if self.max_seq_length is not None:
                predict_params["max_len"] = self.max_seq_length

            if self.max_head_length is not None:
                predict_params["head_max_len"] = self.max_head_length

            results = self.agent.predict_batch(texts, schema, **predict_params)

            return [ self._build_decision_result(result, params) for result in results ]

        return await self._run_in_executor(_score)

    def _build_decision_result(self, result: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        # laya.Agent.predict_batch returns { "answers": { qid: { "type": "noul|choice|score", ... } }, ... }.
        # Flatten to the typed-decision task's common { decision, fields } contract.
        answers = result.get("answers", {})
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
                            "false": 1.0 - probability_true,
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

        payload: Dict[str, Any] = { "decision": decision }

        if fields:
            payload["fields"] = fields

        return payload

class LayaTypedDecisionTaskDriver(ModelTaskDriver):
    config: LayaTypedDecisionModelComponentConfig

    def __init__(self, id: str, config: LayaTypedDecisionModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.agent: Optional[LayaAgent] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        # Mirror laya's own pyproject pins.
        requirements: List[str] = [
            *torch_requirements("torch>=2.0.0"),
            "transformers>=4.48.0",
            "safetensors>=0.4.0",
            "numpy>=1.20.0",
            "laya>=0.3.20",
            "huggingface_hub>=0.20.0",
        ]

        # laya[fast] adds the TileLang CUDA fast path; only meaningful on Linux+x86_64 with CUDA.
        if self.config.fast:
            if sys.platform == "linux" and platform.machine() == "x86_64":
                requirements.append("tilelang>=0.1.14")

        return requirements

    async def _load_model(self) -> None:
        self.agent = await self._run_in_executor(self._load_agent)

    async def _unload_model(self) -> None:
        self.agent = None

    def _load_agent(self) -> LayaAgent:
        from laya import Agent

        # 'english' is the bundle's root checkpoint (no subfolder); every other preset is
        # both the folder name inside the bundle and the standalone-repo suffix, so
        # forwarding the preset value directly to laya.Agent works either way.
        preset = self.config.preset
        subfolder = None if preset == LayaPreset.ENGLISH else preset.value

        return Agent(
            model_id_or_path=self._resolve_model_id(),
            subfolder=subfolder,
            fast=self.config.fast,
        )

    def _resolve_model_id(self) -> str:
        # laya.Agent knows how to snapshot-download its own checkpoint, and it filters the
        # download to just the files the bundle repo needs for the requested subfolder. Passing
        # a local dir the model provisioner produced would defeat that filter for bundle repos,
        # so hand Agent the repository id when we have one and let it manage the fetch.
        repository = getattr(self.config.model, "repository", None)

        if repository:
            return repository

        path = getattr(self.config.model, "path", None)

        if path:
            return path

        raise ValueError(
            f"Component '{self.id}': laya driver needs either a HuggingFace repository or a local path in `model`."
        )

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await LayaTypedDecisionTaskAction(
            action,
            self.agent,
            self.config.max_seq_length,
            self.config.max_head_length,
        ).run(context)

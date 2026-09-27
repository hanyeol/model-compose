from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Union, Dict, List, Any
from mindor.dsl.schema.action import ModelActionConfig, TypedDecisionModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.package.installer import install_package_from_github
from mindor.core.foundation.package.torch import torch_requirements
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import TypedDecisionTaskAction
import importlib.util
import os, sys, platform

if TYPE_CHECKING:
    from mindor.dsl.schema.component import NimbleTypedDecisionModelComponentConfig
    from nimble.scoring.parallel_scorer import ParallelScorer
    from nimble.scoring.cuda_scorer import CudaCandidateScorer

    NimbleScorer = Union[ParallelScorer, CudaCandidateScorer]

class NimbleTypedDecisionTaskAction(TypedDecisionTaskAction):
    def __init__(self, config: TypedDecisionModelActionConfig, scorer: NimbleScorer):
        super().__init__(config)

        self.scorer: NimbleScorer = scorer

    async def _score_batch(
        self,
        texts: List[str],
        schema: Dict[str, Any],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        def _score() -> List[Dict[str, Any]]:
            results: List[Dict[str, Any]] = []

            for text in texts:
                scoring = self.scorer.score(text, schema)
                results.append(self._build_decision_result(scoring, params))

            return results

        return await self._run_in_executor(_score)

    def _build_decision_result(self, scoring: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        # Nimble returns { "output": {...}, "fields": { name: { "scores": {...}, "logits": {...} } } }.
        # Map to the typed-decision task's common { decision, fields } contract and trim
        # per-field payloads according to the action's return_probabilities / return_logits flags.
        result: Dict[str, Any] = { "decision": scoring.get("output", {}) }
        fields: Dict[str, Any] = {}

        for name, value in scoring.get("fields", {}).items():
            field: Dict[str, Any] = {}

            if params["return_probabilities"]:
                field["scores"] = value.get("scores")

            if params["return_logits"]:
                field["logits"] = value.get("logits")

            if field:
                fields[name] = field

        if fields:
            result["fields"] = fields

        return result

class NimbleTypedDecisionTaskDriver(ModelTaskDriver):
    config: NimbleTypedDecisionModelComponentConfig

    def __init__(self, id: str, config: NimbleTypedDecisionModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.scorer: Optional[NimbleScorer] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        # Versions mirror the pins Nimble ships in requirements/{mlx,cuda-eval,training}.txt.
        # Nimble itself has no pyproject/setup.py, so it is fetched via `_setup` (see below).
        requirements: List[str] = []

        # Nimble's CUDA scorer requires torch>=2.8 and a BF16-capable GPU.
        if sys.platform == "linux" and platform.machine() in ("x86_64", "aarch64"):
            requirements.extend([
                *torch_requirements("torch>=2.8,<3"),
                "accelerate==1.15.0",
                "sentencepiece==0.2.2",
            ])

        # ParallelScorer runs on MLX; the LoRA merge itself is done via peft on CPU.
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
        # bespokelabsai/nimble is a research repo without pyproject/setup.py, so
        # `pip install git+...` fails. Drop the `nimble/` package next to `mindor`
        # via install_package_from_github's subdirs mechanism.
        if importlib.util.find_spec("nimble") is None:
            await install_package_from_github(
                "nimble",
                "https://github.com/bespokelabsai/nimble.git",
                revision="f136b3f75721",
                subdirs=[ "nimble" ],
            )

    async def _load_model(self) -> None:
        adapter_path = await self._provision_model(self.config.model, prefetch=True)
        base_path = await self._provision_model(self.config.base_model, prefetch=True)
        merged_path = await self._merge_adapter(adapter_path, base_path)

        self.scorer = await self._run_in_executor(self._load_scorer, merged_path)

    async def _unload_model(self) -> None:
        self.scorer = None

    async def _merge_adapter(self, adapter_path: str, base_path: str) -> str:
        merged_root = os.path.join(self._get_model_cache_dir(), "nimble-merged")
        merged_path = os.path.join(merged_root, os.path.basename(adapter_path.rstrip(os.sep)))

        if os.path.isdir(merged_path) and os.path.isfile(os.path.join(merged_path, "config.json")):
            return merged_path

        def _merge() -> str:
            from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration
            from peft import PeftModel
            import torch

            os.makedirs(os.path.dirname(merged_path), exist_ok=True)

            base_model = Qwen3_5ForConditionalGeneration.from_pretrained(
                base_path,
                dtype=torch.bfloat16,
                device_map="cpu",
            )
            adapter = PeftModel.from_pretrained(base_model, adapter_path)
            merged = adapter.merge_and_unload(safe_merge=True)
            merged.save_pretrained(merged_path)
            AutoTokenizer.from_pretrained(adapter_path).save_pretrained(merged_path)

            return merged_path

        return await self._run_in_executor(_merge)

    def _load_scorer(self, merged_path: str) -> NimbleScorer:
        if sys.platform == "linux" and platform.machine() in ("x86_64", "aarch64"):
            from nimble.scoring.cuda_scorer import CudaCandidateScorer
            return CudaCandidateScorer(
                model_path=merged_path,
                model_id=getattr(self.config.model, "repository", None) or self.id,
                revision=getattr(self.config.model, "revision", None) or "main",
                max_input_tokens=self.config.max_seq_length,
            )

        if sys.platform == "darwin" and platform.machine() == "arm64":
            from nimble.scoring.parallel_scorer import ParallelScorer
            return ParallelScorer(model_path=merged_path, max_input_tokens=self.config.max_seq_length)

        raise RuntimeError(
            "Nimble supports only Darwin+arm64 (MLX) or Linux (x86_64 / aarch64) with CUDA; "
            f"got platform={sys.platform}, machine={platform.machine()}."
        )

    def _get_model_cache_dir(self) -> str:
        return os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "models")

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await NimbleTypedDecisionTaskAction(action, self.scorer).run(context)

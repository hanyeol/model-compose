from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, List, Any
from mindor.dsl.schema.action import ModelActionConfig, TextEmbeddingModelActionConfig
from mindor.dsl.schema.component import DeviceMode
from mindor.core.foundation.cancellation import CancellationToken
from .....base import ComponentActionContext
from .....base.huggingface.language import HuggingfaceLanguageModelTaskDriver
from ..base import HuggingfaceTextEmbeddingTaskAction
from ...common import TextEmbedding

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer
    import torch

class SbertHuggingfaceTextEmbeddingTaskAction(HuggingfaceTextEmbeddingTaskAction):
    def __init__(
        self,
        config: TextEmbeddingModelActionConfig,
        model: SentenceTransformer,
        device: torch.device,
    ):
        super().__init__(config, device)

        self.model: SentenceTransformer = model

    async def _embed_batch(
        self,
        texts: List[str],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[TextEmbedding]:
        def _embed() -> List[TextEmbedding]:
            vectors = self.model.encode(
                texts,
                normalize_embeddings=bool(params.get("normalize", True))
            )
            
            return [ TextEmbedding(vector) for vector in vectors.tolist() ]

        return await self._run_in_executor(_embed)

class SbertHuggingfaceTextEmbeddingTaskDriver(HuggingfaceLanguageModelTaskDriver):
    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            *super()._get_setup_requirements(),
            "sentence-transformers"
        ]

    async def _load_model(self) -> None:
        from sentence_transformers import SentenceTransformer

        model_path = await self._provision_model(self.config.model)
        device = self._resolve_device(self.config.device) if self.config.device_mode == DeviceMode.SINGLE else None
        dtype = self._get_model_dtype()
        quantization_config = self._resolve_model_quantization_config(self.config, device, dtype)

        def _load() -> SentenceTransformer:
            params: Dict[str, Any] = {}
            model_kwargs: Dict[str, Any] = {}

            if quantization_config is not None:
                # SentenceTransformer forwards model_kwargs to the underlying
                # AutoModel.from_pretrained; passing quantization_config here is
                # the only way to route bitsandbytes through SBERT's loader.
                model_kwargs["quantization_config"] = quantization_config

                if device is not None:
                    model_kwargs["device_map"] = { "": device }
                else:
                    model_kwargs["device_map"] = self.config.device_mode.value

            if model_kwargs:
                params["model_kwargs"] = model_kwargs

            # SentenceTransformer warns if both `device` and `device_map` are
            # passed; skip its `device` arg when we've already pinned via device_map.
            if "device_map" not in model_kwargs and device is not None:
                params["device"] = str(device.type)

            return SentenceTransformer(model_path, **params)

        self.model = await self._run_in_executor(_load)
        self.device = device if device is not None else self._resolve_device(self.config.device)

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await SbertHuggingfaceTextEmbeddingTaskAction(
            action,
            self.model,
            self.device,
        ).run(context)

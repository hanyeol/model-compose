from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.component import ModelComponentConfig, PeftAdapterConfig, HuggingfaceModelConfig, DeviceMode
from mindor.core.logger import logging
from .common import ModelTaskService

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizer, ProcessorMixin, TextIteratorStreamer
    from torch import Tensor
    import torch

class BatchTextIteratorStreamer:
    """Fan-out wrapper around N TextIteratorStreamer instances, one per batch row.

    `model.generate()` calls `put(value)` once with the prompt (shape:
    ``(batch_size, prompt_len)``) and then once per generation step with the
    newly produced tokens (shape: ``(batch_size,)``). For each call this
    splits the rows and forwards a batch-size-1 slice to the matching inner
    streamer, so each row can be consumed as an independent token iterator.

    The standard ``TextIteratorStreamer`` rejects ``batch_size > 1`` outright,
    which makes it incompatible with batched ``generate()``. Use this instead
    when you need per-row streaming from a single batched generation call.
    """

    def __init__(
        self,
        tokenizer: PreTrainedTokenizer,
        batch_size: int,
        skip_prompt: bool = False,
        timeout: Optional[float] = None,
        **decode_kwargs,
    ):
        from transformers import TextIteratorStreamer

        self.batch_size: int = batch_size
        self.streamers: List[TextIteratorStreamer] = [
            TextIteratorStreamer(tokenizer, skip_prompt=skip_prompt, timeout=timeout, **decode_kwargs)
            for _ in range(batch_size)
        ]

    def put(self, value: Tensor) -> None:
        if value.ndim == 1:
            for index, streamer in enumerate(self.streamers):
                streamer.put(value[index:index + 1])
            return

        if value.shape[0] != self.batch_size:
            raise ValueError(
                f"BatchTextIteratorStreamer received value with batch dim {value.shape[0]} "
                f"but was configured for batch_size={self.batch_size}"
            )

        for index, streamer in enumerate(self.streamers):
            streamer.put(value[index:index + 1])

    def end(self) -> None:
        for streamer in self.streamers:
            streamer.end()

    def __getitem__(self, index: int) -> TextIteratorStreamer:
        return self.streamers[index]

    def __len__(self) -> int:
        return self.batch_size

class HuggingfaceModelTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _load_pretrained_model(self) -> PreTrainedModel:
        model_cls = self._get_model_class()
        model = model_cls.from_pretrained(self._get_model_path(self.config), **self._get_model_params(self.config))

        if len(self.config.peft_adapters or []) > 0:
            model = self._load_peft_adapters(model, self.config.peft_adapters)

        if self.config.device_mode == DeviceMode.SINGLE:
            model = model.to(torch.device(self.config.device))

        return model

    def _load_peft_adapters(self, base_model: PreTrainedModel, adapter_configs: List[PeftAdapterConfig]) -> PreTrainedModel:
        from peft import PeftModel

        names, weights = self._build_peft_adapter_lists(adapter_configs)
        peft_model = PeftModel.from_pretrained(
            base_model,
            self._get_model_path(adapter_configs[0]),
            adapter_name=names[0],
            **self._get_model_params(adapter_configs[0])
        )

        for index in range(1, len(adapter_configs)):
            peft_model.load_adapter(
                self._get_model_path(adapter_configs[index]),
                adapter_name=names[index],
                **self._get_model_params(adapter_configs[index])
            )

        multiple_adapters = len(adapter_configs) > 1
        has_non_unit_weight = any(abs(weight - 1.0) > 1e-12 for weight in weights)

        if multiple_adapters or has_non_unit_weight:
            # Use add_weighted_adapter for merging multiple PEFT adapters with weights
            # Note: This operation can be slow for large models (e.g., 7B+)
            logging.info(f"Merging {len(names)} PEFT adapters with weights {weights}. This may take a while...")
            peft_model.add_weighted_adapter(names, weights=weights, adapter_name="blended_adapter")
            peft_model.set_adapter("blended_adapter")
            logging.info("PEFT adapters merging completed.")
        else:
            peft_model.set_adapter(names[0])

        return peft_model

    def _build_peft_adapter_lists(self, adapter_configs: List[PeftAdapterConfig]) -> Tuple[List[str], List[float]]:
        names: List[str] = []
        weights: List[float] = []

        for index, config in enumerate(adapter_configs):
            names.append(config.name or f"peft_adapter_{index}")
            weights.append(config.weight)

        return names, weights

    def _get_model_class(self) -> Type[PreTrainedModel]:
        raise NotImplementedError("Model class loader not implemented.")

    def _get_model_path(self, config: Union[ModelComponentConfig, PeftAdapterConfig]) -> str:
        if isinstance(config.model, HuggingfaceModelConfig):
            return config.model.repository

        return config.model.path

    def _get_model_params(self, config: Union[ModelComponentConfig, PeftAdapterConfig]) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        if isinstance(config.model, HuggingfaceModelConfig):
            if config.model.filename:
                params["filename"] = config.model.filename

            if config.model.revision:
                params["revision"] = config.model.revision
            
            if config.model.cache_dir:
                params["cache_dir"] = config.model.cache_dir

            if config.model.local_files_only:
                params["local_files_only"] = True
            
            if config.model.token:
                params["token"] = config.model.token

        if not isinstance(config, PeftAdapterConfig):
            if config.device_mode != DeviceMode.SINGLE:
                params["device_map"] = config.device_mode.value
    
        if config.precision is not None:
            params["torch_dtype"] = getattr(torch, config.precision.value)
    
        if config.low_cpu_mem_usage:
            params["low_cpu_mem_usage"] = True

        return params

    def _get_model_device(self, model: PreTrainedModel) -> torch.device:
        return next(model.parameters()).device

class HuggingfaceLanguageModelTaskService(HuggingfaceModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[PreTrainedModel] = None
        self.tokenizer: Optional[PreTrainedTokenizer] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [
            "transformers>=4.21.0",
            "peft>=0.5.0",
            "torch",
            "sentencepiece",
            "accelerate"
        ]

    async def _load_model(self) -> None:
        self.model = self._load_pretrained_model()
        self.tokenizer = self._load_pretrained_tokenizer()
        self.device = self._get_model_device(self.model)

    async def _unload_model(self) -> None:
        self.model = None
        self.tokenizer = None
        self.device = None

    def _load_pretrained_tokenizer(self) -> Optional[PreTrainedTokenizer]:
        tokenizer_cls = self._get_tokenizer_class()
        tokenizer = tokenizer_cls.from_pretrained(self._get_model_path(self.config), **self._get_tokenizer_params())

        if tokenizer.pad_token is None:
            logging.info("Tokenizer does not have a pad_token defined. Configuring pad_token automatically.")
            self._configure_missing_pad_token(tokenizer)

        return tokenizer

    def _configure_missing_pad_token(self, tokenizer: PreTrainedTokenizer) -> None:
        if tokenizer.eos_token is not None:
            tokenizer.pad_token = tokenizer.eos_token
            logging.info(f"Set pad_token to eos_token: {tokenizer.eos_token}")
        else:
            tokenizer.add_special_tokens({ "pad_token": "[PAD]" })
            logging.info("Added new pad_token: [PAD]")

    def _get_tokenizer_class(self) -> Optional[Type[PreTrainedTokenizer]]:
        return None

    def _get_tokenizer_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        if isinstance(self.config.model, HuggingfaceModelConfig):
            if self.config.model.revision:
                params["revision"] = self.config.model.revision

            if self.config.model.cache_dir:
                params["cache_dir"] = self.config.model.cache_dir

            if self.config.model.local_files_only:
                params["local_files_only"] = True

            if self.config.model.token:
                params["token"] = self.config.model.token

        if not self.config.fast_tokenizer:
            params["use_fast"] = False

        return params

class HuggingfaceMultimodalModelTaskService(HuggingfaceModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[PreTrainedModel] = None
        self.processor: Optional[ProcessorMixin] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ 
            "transformers>=4.21.0",
            "torch",
            "sentencepiece",
            "accelerate"
        ]

    async def _load_model(self) -> None:
        self.model = self._load_pretrained_model()
        self.processor = self._load_pretrained_processor()
        self.device = self._get_model_device(self.model)

    async def _unload_model(self) -> None:
        self.model = None
        self.processor = None
        self.device = None

    def _load_pretrained_processor(self) -> Optional[ProcessorMixin]:
        processor_cls = self._get_processor_class()

        if not processor_cls:
            return None

        return processor_cls.from_pretrained(self._get_model_path(self.config), **self._get_processor_params())

    def _get_processor_class(self) -> Optional[Type[ProcessorMixin]]:
        return None

    def _get_processor_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        if isinstance(self.config.model, HuggingfaceModelConfig):
            if self.config.model.revision:
                params["revision"] = self.config.model.revision

            if self.config.model.cache_dir:
                params["cache_dir"] = self.config.model.cache_dir

            if self.config.model.local_files_only:
                params["local_files_only"] = True

            if self.config.model.token:
                params["token"] = self.config.model.token

        return params

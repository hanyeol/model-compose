from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.component import ModelComponentConfig, HuggingfaceModelConfig, LocalModelConfig
from mindor.dsl.schema.action import ModelActionConfig
from mindor.core.logger import logging
from .common import ModelTaskService
from ....context import ComponentActionContext
import asyncio

if TYPE_CHECKING:
    from vllm import AsyncLLMEngine
    from transformers.tokenization_utils_base import PreTrainedTokenizerBase

class VllmModelTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.engine: Optional[AsyncLLMEngine] = None
        self.tokenizer: Optional[PreTrainedTokenizerBase] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "vllm" ]

    async def run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

        if not self._model_loaded:
            async with self._model_load_lock:
                if not self._model_loaded:
                    self._load_model_on_demand()

        return await self._run(action, context, loop)

    def _load_model(self) -> None:
        from vllm import AsyncEngineArgs, AsyncLLMEngine

        model_path = self._get_model_path()
        params = self._get_model_params()

        logging.info(f"Component '{self.id}': loading vLLM model from '{model_path}'")

        engine_args = AsyncEngineArgs(model=model_path, **params)
        self.engine = AsyncLLMEngine.from_engine_args(engine_args)

        self._load_tokenizer(model_path, params)

    def _load_tokenizer(self, model_path: str, params: Dict[str, Any]) -> None:
        from transformers import AutoTokenizer

        tokenizer_path = params.get("tokenizer") or model_path
        tokenizer_kwargs: Dict[str, Any] = {}

        if params.get("trust_remote_code"):
            tokenizer_kwargs["trust_remote_code"] = True
        if params.get("tokenizer_revision"):
            tokenizer_kwargs["revision"] = params["tokenizer_revision"]
        elif params.get("revision"):
            tokenizer_kwargs["revision"] = params["revision"]

        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, **tokenizer_kwargs)

    def _unload_model(self) -> None:
        if self.engine is not None:
            try:
                shutdown = getattr(self.engine, "shutdown_background_loop", None)
                if callable(shutdown):
                    shutdown()
            except Exception:
                pass
            self.engine = None

        self.tokenizer = None

        try:
            import gc
            gc.collect()
        except Exception:
            pass

        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    def _get_model_path(self) -> str:
        if isinstance(self.config.model, HuggingfaceModelConfig):
            return self.config.model.repository

        if isinstance(self.config.model, LocalModelConfig):
            return self.config.model.path

        if isinstance(self.config.model, str):
            return self.config.model

        raise ValueError(f"Unknown model config type: {type(self.config.model)}")

    def _get_model_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        if isinstance(self.config.model, HuggingfaceModelConfig):
            if self.config.model.revision is not None:
                params["revision"] = self.config.model.revision
            if self.config.model.cache_dir is not None:
                params["download_dir"] = self.config.model.cache_dir
            if self.config.model.token is not None:
                params["hf_token"] = self.config.model.token

        for field in [
            "tokenizer", "tokenizer_mode", "skip_tokenizer_init",
            "trust_remote_code", "allowed_local_media_path",
            "tensor_parallel_size", "pipeline_parallel_size",
            "data_parallel_size", "enable_expert_parallel",
            "dtype", "kv_cache_dtype", "seed",
            "max_model_len", "max_seq_len_to_capture",
            "quantization", "rope_scaling", "rope_theta", "hf_overrides",
            "tokenizer_revision", "tokenizer_pool_size", "tokenizer_pool_type",
            "load_format", "config_format",
            "gpu_memory_utilization", "swap_space", "cpu_offload_gb",
            "block_size", "enable_prefix_caching", "prefix_caching_hash_algo",
            "disable_sliding_window", "use_v2_block_manager",
            "num_lookahead_slots",
            "max_num_batched_tokens", "max_num_seqs", "max_num_partial_prefills",
            "max_long_partial_prefills", "long_prefill_token_threshold",
            "enable_chunked_prefill", "scheduler_delay_factor",
            "preemption_mode", "scheduling_policy",
            "speculative_config", "speculative_model",
            "num_speculative_tokens", "speculative_draft_tensor_parallel_size",
            "speculative_max_model_len", "speculative_disable_by_batch_size",
            "ngram_prompt_lookup_max", "ngram_prompt_lookup_min",
            "spec_decoding_acceptance_method",
            "typical_acceptance_sampler_posterior_threshold",
            "typical_acceptance_sampler_posterior_alpha",
            "disable_logprobs_during_spec_decoding",
            "model_loader_extra_config", "ignore_patterns",
            "preemption_check_period", "num_gpu_blocks_override",
            "disable_log_stats", "disable_async_output_proc",
            "worker_cls", "worker_extension_cls",
            "compilation_config", "kv_transfer_config",
            "additional_config", "use_tqdm_on_load",
            "enable_lora", "max_loras", "max_lora_rank",
            "lora_extra_vocab_size", "lora_dtype", "long_lora_scaling_factors",
            "max_cpu_loras", "fully_sharded_loras",
            "enable_prompt_adapter", "max_prompt_adapters",
            "max_prompt_adapter_token",
            "device", "distributed_executor_backend",
            "max_parallel_loading_workers", "ray_workers_use_nsight",
            "disable_custom_all_reduce",
            "limit_mm_per_prompt", "mm_processor_kwargs",
            "disable_mm_preprocessor_cache", "mm_encoder_attn_backend",
            "guided_decoding_backend", "guided_decoding_disable_fallback",
            "guided_decoding_disable_any_whitespace",
            "guided_decoding_disable_additional_properties",
            "logits_processor_pattern", "logits_processors",
            "override_neuron_config", "override_pooler_config",
            "override_generation_config", "model_impl",
            "task", "runner",
            "enforce_eager", "enable_sleep_mode",
            "served_model_name",
            "qlora_adapter_name_or_path",
            "otlp_traces_endpoint", "collect_detailed_traces",
            "disable_log_requests",
            "tokenizer_init_kwargs", "calculate_kv_scales",
            "enable_chunked_mm_input", "chunked_mm_input_size",
            "structured_outputs_config",
        ]:
            value = getattr(self.config, field, None)
            if value is not None:
                params[field] = value

        precision = getattr(self.config, "precision", None)
        if precision is not None and "dtype" not in params:
            params["dtype"] = self._map_precision(precision)

        quantization = getattr(self.config, "quantization", None)
        if quantization is not None and "quantization" not in params:
            if hasattr(quantization, "type"):
                params["quantization"] = self._map_quantization(quantization.type)
            elif isinstance(quantization, str):
                params["quantization"] = quantization

        device = getattr(self.config, "device", None)
        if device and device != "cpu" and "device" not in params:
            params["device"] = device
        elif device == "cpu" and "device" not in params:
            params["device"] = "cpu"

        return params

    def _map_precision(self, precision: Any) -> str:
        from mindor.dsl.schema.component import ModelPrecision

        mapping = {
            ModelPrecision.AUTO: "auto",
            ModelPrecision.FLOAT32: "float32",
            ModelPrecision.FLOAT16: "float16",
            ModelPrecision.BFLOAT16: "bfloat16",
        }
        return mapping.get(precision, "auto")

    def _map_quantization(self, q_type: Any) -> Optional[str]:
        from mindor.dsl.schema.component import ModelQuantizationType

        mapping = {
            ModelQuantizationType.INT8: "bitsandbytes",
            ModelQuantizationType.INT4: "bitsandbytes",
            ModelQuantizationType.FP4: "bitsandbytes",
            ModelQuantizationType.NF4: "bitsandbytes",
        }
        return mapping.get(q_type)

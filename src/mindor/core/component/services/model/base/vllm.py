from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.component import ModelComponentConfig, HuggingfaceModelConfig, LocalModelConfig
from mindor.core.logger import logging
from .common import ModelTaskService

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

    async def _load_model(self) -> None:
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

    async def _unload_model(self) -> None:
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
            # Model & tokenizer
            "tokenizer", "tokenizer_mode", "skip_tokenizer_init",
            "enable_prompt_embeds", "trust_remote_code",
            "allowed_local_media_path", "allowed_media_domains",
            "revision", "code_revision", "tokenizer_revision",
            "hf_config_path", "hf_token", "hf_overrides",
            "runner", "convert", "model_impl", "served_model_name",
            # Loading
            "download_dir", "load_format", "config_format",
            "model_loader_extra_config", "ignore_patterns", "use_tqdm_on_load",
            "safetensors_load_strategy", "safetensors_prefetch_num_threads",
            "safetensors_prefetch_block_size", "pt_load_map_location",
            # Numerical types & limits
            "dtype", "seed", "max_model_len",
            "max_logprobs", "logprobs_mode",
            # Quantization
            "quantization", "quantization_config", "allow_deprecated_quantization",
            # RoPE / attention
            "rope_scaling", "rope_theta",
            "attention_backend", "attention_config",
            "disable_sliding_window", "disable_cascade_attn",
            "override_attention_dtype",
            # Mamba / SSM
            "mamba_backend", "mamba_cache_dtype", "mamba_ssm_cache_dtype",
            "mamba_block_size", "mamba_cache_mode",
            # Compilation & CUDA graphs
            "enforce_eager",
            "cudagraph_capture_sizes", "max_cudagraph_capture_size",
            "compilation_config",
            # Memory / KV cache
            "gpu_memory_utilization", "kv_cache_memory_bytes",
            "swap_space", "cpu_offload_gb", "cpu_offload_params",
            "offload_backend", "offload_group_size",
            "offload_num_in_group", "offload_prefetch_step", "offload_params",
            "block_size", "enable_prefix_caching", "prefix_caching_hash_algo",
            "num_gpu_blocks_override",
            "kv_cache_dtype", "kv_cache_dtype_skip_layers",
            "kv_sharing_fast_prefill",
            "kv_offloading_size", "kv_offloading_backend",
            "kv_transfer_config", "kv_events_config", "ec_transfer_config",
            # Distributed execution
            "distributed_executor_backend",
            "pipeline_parallel_size", "tensor_parallel_size",
            "data_parallel_size", "data_parallel_rank",
            "data_parallel_size_local", "data_parallel_address",
            "data_parallel_rpc_port", "data_parallel_backend",
            "data_parallel_hybrid_lb", "data_parallel_external_lb",
            "prefill_context_parallel_size", "decode_context_parallel_size",
            "dcp_comm_backend",
            "master_addr", "master_port", "nnodes", "node_rank",
            "distributed_timeout_seconds", "cpu_distributed_timeout_seconds",
            "device_ids", "numa_bind",
            "max_parallel_loading_workers", "ray_workers_use_nsight",
            "disable_custom_all_reduce",
            "worker_cls", "worker_extension_cls",
            # Expert / MoE
            "enable_expert_parallel", "enable_ep_weight_filter",
            "moe_backend", "linear_backend", "all2all_backend",
            "enable_eplb", "eplb_config", "expert_placement_strategy",
            "enable_dbo", "ubatch_size",
            # Scheduling
            "max_num_batched_tokens", "max_num_seqs",
            "max_num_partial_prefills", "max_long_partial_prefills",
            "long_prefill_token_threshold",
            "enable_chunked_prefill", "disable_chunked_mm_input",
            "scheduling_policy", "scheduler_cls",
            "scheduler_reserve_full_isl", "watermark",
            "prefill_schedule_interval", "disable_hybrid_kv_cache_manager",
            "async_scheduling", "stream_interval",
            # Multimodal
            "language_model_only", "limit_mm_per_prompt",
            "enable_mm_embeds", "media_io_kwargs", "mm_processor_kwargs",
            "mm_processor_cache_gb", "mm_processor_cache_type",
            "mm_shm_cache_max_object_size_mb",
            "mm_encoder_only", "mm_encoder_tp_mode",
            "mm_encoder_attn_backend", "mm_encoder_attn_dtype",
            "interleave_mm_strings", "skip_mm_profiling", "video_pruning_rate",
            # LoRA
            "enable_lora", "max_loras", "max_lora_rank", "lora_dtype",
            "max_cpu_loras", "fully_sharded_loras",
            "lora_target_modules", "default_mm_loras",
            # Speculative decoding
            "speculative_config",
            # Structured outputs / pooling / generation
            "structured_outputs_config",
            "pooler_config",
            "generation_config", "override_generation_config",
            "override_pooler_config", "override_neuron_config",
            # Logits processors
            "logits_processors", "io_processor_plugin",
            # Runtime modes
            "enable_sleep_mode", "enable_cumem_allocator", "enable_log_requests",
            # Observability
            "disable_log_stats", "show_hidden_metrics_for_version",
            "otlp_traces_endpoint", "collect_detailed_traces",
            "enable_layerwise_nvtx_tracing",
            # Misc
            "additional_config", "kernel_config", "reasoning_config",
            "reasoning_parser",
            "optimization_level", "performance_mode",
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

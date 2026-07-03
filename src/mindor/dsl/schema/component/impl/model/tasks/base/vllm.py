from typing import Union, Literal, Optional, Dict, List, Any
from pydantic import BaseModel, Field

class VllmEngineOptionsConfig(BaseModel):
    # Model & tokenizer
    tokenizer: Optional[str] = Field(default=None, description="Name or path of the HuggingFace tokenizer to use.")
    tokenizer_mode: Optional[Literal[ "auto", "slow", "mistral", "custom" ]] = Field(default=None, description="Tokenizer mode.")
    skip_tokenizer_init: Optional[bool] = Field(default=None, description="Skip initialization of tokenizer and detokenizer; expects pre-tokenized inputs.")
    enable_prompt_embeds: Optional[bool] = Field(default=None, description="Accept prompt embeddings as inputs in addition to text.")
    trust_remote_code: Optional[bool] = Field(default=None, description="Trust remote code from HuggingFace.")
    allowed_local_media_path: Optional[str] = Field(default=None, description="Allowed local media path for multimodal inputs.")
    allowed_media_domains: Optional[List[str]] = Field(default=None, description="Restrict multimodal media downloads to specific domains.")
    revision: Optional[str] = Field(default=None, description="Model version (branch, tag, or commit).")
    code_revision: Optional[str] = Field(default=None, description="Revision for model code.")
    tokenizer_revision: Optional[str] = Field(default=None, description="Tokenizer revision.")
    hf_config_path: Optional[str] = Field(default=None, description="Custom HuggingFace config path.")
    hf_token: Optional[Union[bool, str]] = Field(default=None, description="HuggingFace authentication token. True uses the cached login.")
    hf_overrides: Optional[Dict[str, Any]] = Field(default=None, description="Overrides for HuggingFace config.")
    runner: Optional[Literal[ "auto", "draft", "generate", "pooling" ]] = Field(default=None, description="Model runner type.")
    convert: Optional[Literal[ "auto", "classify", "embed", "none" ]] = Field(default=None, description="Model adapter conversion.")
    model_impl: Optional[Literal[ "auto", "vllm", "transformers" ]] = Field(default=None, description="Model implementation to use.")
    served_model_name: Optional[Union[str, List[str]]] = Field(default=None, description="Model name(s) exposed by the API.")

    # Loading
    download_dir: Optional[str] = Field(default=None, description="Directory to download and cache model weights.")
    load_format: Optional[str] = Field(default=None, description="Format of the model weights to load.")
    config_format: Optional[Literal[ "auto", "hf", "mistral" ]] = Field(default=None, description="Format of the model config.")
    model_loader_extra_config: Optional[Dict[str, Any]] = Field(default=None, description="Extra config for model loader.")
    ignore_patterns: Optional[List[str]] = Field(default=None, description="Patterns to ignore when loading the model.")
    use_tqdm_on_load: Optional[bool] = Field(default=None, description="Show tqdm progress bar during weight load.")
    safetensors_load_strategy: Optional[str] = Field(default=None, description="Loading behavior for safetensors files.")
    safetensors_prefetch_num_threads: Optional[int] = Field(default=None, description="Number of prefetch workers for safetensors.")
    safetensors_prefetch_block_size: Optional[int] = Field(default=None, description="Read size per safetensors prefetch operation.")
    pt_load_map_location: Optional[str] = Field(default=None, description="Device mapping for PyTorch checkpoint loading.")

    # Numerical types & limits
    dtype: Optional[Literal[ "auto", "half", "float16", "bfloat16", "float", "float32" ]] = Field(default=None, description="Data type for model weights and activations.")
    seed: Optional[int] = Field(default=None, description="Random seed.")
    max_model_len: Optional[Union[int, Literal["auto"]]] = Field(default=None, description="Model context length.")
    max_logprobs: Optional[int] = Field(default=None, description="Maximum number of returned log probabilities per token.")
    logprobs_mode: Optional[str] = Field(default=None, description="Log probability output mode (raw or processed).")

    # Quantization
    quantization: Optional[str] = Field(default=None, description="Quantization method (e.g., 'awq', 'gptq', 'fp8', 'bitsandbytes', 'marlin').")
    quantization_config: Optional[Dict[str, Any]] = Field(default=None, description="Detailed quantization configuration.")
    allow_deprecated_quantization: Optional[bool] = Field(default=None, description="Allow legacy quantization methods.")

    # RoPE / attention
    rope_scaling: Optional[Dict[str, Any]] = Field(default=None, description="RoPE scaling configuration.")
    rope_theta: Optional[float] = Field(default=None, description="RoPE theta override.")
    attention_backend: Optional[str] = Field(default=None, description="Attention implementation selection.")
    attention_config: Optional[Dict[str, Any]] = Field(default=None, description="Attention mechanism tuning configuration.")
    disable_sliding_window: Optional[bool] = Field(default=None, description="Disable sliding window attention.")
    disable_cascade_attn: Optional[bool] = Field(default=None, description="Disable cascade attention in V1.")
    override_attention_dtype: Optional[str] = Field(default=None, description="Force a specific attention precision.")

    # Mamba / SSM
    mamba_backend: Optional[str] = Field(default=None, description="State space model backend.")
    mamba_cache_dtype: Optional[str] = Field(default=None, description="Mamba cache precision.")
    mamba_ssm_cache_dtype: Optional[str] = Field(default=None, description="Mamba SSM state precision.")
    mamba_block_size: Optional[int] = Field(default=None, description="Mamba cache block size.")
    mamba_cache_mode: Optional[str] = Field(default=None, description="Mamba caching strategy.")

    # Compilation & CUDA graphs
    enforce_eager: Optional[bool] = Field(default=None, description="Disable CUDA graph and use eager mode.")
    cudagraph_capture_sizes: Optional[List[int]] = Field(default=None, description="Sizes for CUDA graph capture.")
    max_cudagraph_capture_size: Optional[int] = Field(default=None, description="Maximum CUDA graph capture size.")
    compilation_config: Optional[Union[int, Dict[str, Any]]] = Field(default=None, description="torch.compile configuration.")

    # Memory / KV cache
    gpu_memory_utilization: Optional[float] = Field(default=None, description="Fraction of GPU memory to use (0.0-1.0).")
    kv_cache_memory_bytes: Optional[int] = Field(default=None, description="Manual KV cache size in bytes.")
    swap_space: Optional[float] = Field(default=None, description="CPU swap space size in GiB per GPU.")
    cpu_offload_gb: Optional[float] = Field(default=None, description="CPU offload size in GiB per GPU.")
    cpu_offload_params: Optional[List[str]] = Field(default=None, description="Parameter name patterns to offload to CPU.")
    offload_backend: Optional[str] = Field(default=None, description="Weight offload strategy.")
    offload_group_size: Optional[int] = Field(default=None, description="Layers per offload group.")
    offload_num_in_group: Optional[int] = Field(default=None, description="Number of offloaded layers per group.")
    offload_prefetch_step: Optional[int] = Field(default=None, description="Prefetch lookahead distance.")
    offload_params: Optional[List[str]] = Field(default=None, description="Prefetch target parameter patterns.")

    block_size: Optional[int] = Field(default=None, description="Token block size for paged attention.")
    enable_prefix_caching: Optional[bool] = Field(default=None, description="Enable automatic prefix caching.")
    prefix_caching_hash_algo: Optional[str] = Field(default=None, description="Hash algorithm for prefix caching.")
    num_gpu_blocks_override: Optional[int] = Field(default=None, description="Override the number of GPU blocks.")
    kv_cache_dtype: Optional[Literal[ "auto", "fp8", "fp8_e5m2", "fp8_e4m3", "bfloat16", "float16" ]] = Field(default=None, description="Data type for KV cache.")
    kv_cache_dtype_skip_layers: Optional[List[str]] = Field(default=None, description="Skip KV cache quantization for specific layers.")
    kv_sharing_fast_prefill: Optional[bool] = Field(default=None, description="Enable KV sharing fast-prefill optimization.")
    kv_offloading_size: Optional[int] = Field(default=None, description="CPU offload buffer size for KV cache.")
    kv_offloading_backend: Optional[str] = Field(default=None, description="KV offload implementation (e.g., 'native', 'lmcache').")
    kv_transfer_config: Optional[Dict[str, Any]] = Field(default=None, description="KV transfer configuration for disaggregated serving.")
    kv_events_config: Optional[Dict[str, Any]] = Field(default=None, description="KV cache event publishing configuration.")
    ec_transfer_config: Optional[Dict[str, Any]] = Field(default=None, description="Distributed EC cache transfer configuration.")

    # Distributed execution
    distributed_executor_backend: Optional[Literal[ "ray", "mp", "uni", "external_launcher" ]] = Field(default=None, description="Distributed executor backend.")
    pipeline_parallel_size: Optional[int] = Field(default=None, description="Number of pipeline stages.")
    tensor_parallel_size: Optional[int] = Field(default=None, description="Number of GPUs for tensor parallelism.")
    data_parallel_size: Optional[int] = Field(default=None, description="Number of data parallel replicas.")
    data_parallel_rank: Optional[int] = Field(default=None, description="Replica identifier for this instance.")
    data_parallel_size_local: Optional[int] = Field(default=None, description="Local replicas per node.")
    data_parallel_address: Optional[str] = Field(default=None, description="Cluster head node address.")
    data_parallel_rpc_port: Optional[int] = Field(default=None, description="Inter-rank communication port.")
    data_parallel_backend: Optional[Literal[ "mp", "ray" ]] = Field(default=None, description="Data parallel coordination method.")
    data_parallel_hybrid_lb: Optional[bool] = Field(default=None, description="Enable per-node load balancing for data parallel.")
    data_parallel_external_lb: Optional[bool] = Field(default=None, description="Use external load balancer mode.")
    prefill_context_parallel_size: Optional[int] = Field(default=None, description="Prefill context parallelism groups.")
    decode_context_parallel_size: Optional[int] = Field(default=None, description="Decode context parallelism groups.")
    dcp_comm_backend: Optional[str] = Field(default=None, description="DCP communication backend.")
    master_addr: Optional[str] = Field(default=None, description="Multi-node master address.")
    master_port: Optional[int] = Field(default=None, description="Multi-node master port.")
    nnodes: Optional[int] = Field(default=None, description="Total number of nodes.")
    node_rank: Optional[int] = Field(default=None, description="Current node identifier.")
    distributed_timeout_seconds: Optional[int] = Field(default=None, description="Distributed operation timeout.")
    cpu_distributed_timeout_seconds: Optional[int] = Field(default=None, description="CPU communication timeout.")
    device_ids: Optional[List[Union[int, str]]] = Field(default=None, description="Physical GPU device IDs to use.")
    numa_bind: Optional[bool] = Field(default=None, description="Pin workers to NUMA nodes.")
    max_parallel_loading_workers: Optional[int] = Field(default=None, description="Maximum parallel loading workers.")
    ray_workers_use_nsight: Optional[bool] = Field(default=None, description="Profile Ray workers with nsight.")
    disable_custom_all_reduce: Optional[bool] = Field(default=None, description="Disable custom all-reduce kernel.")
    worker_cls: Optional[str] = Field(default=None, description="Custom worker class path.")
    worker_extension_cls: Optional[str] = Field(default=None, description="Custom worker extension class path.")

    # Expert / MoE
    enable_expert_parallel: Optional[bool] = Field(default=None, description="Enable expert parallelism for MoE models.")
    enable_ep_weight_filter: Optional[bool] = Field(default=None, description="Skip non-local expert weights during loading.")
    moe_backend: Optional[str] = Field(default=None, description="MoE kernel backend.")
    linear_backend: Optional[str] = Field(default=None, description="Quantized linear kernel backend.")
    all2all_backend: Optional[str] = Field(default=None, description="MoE all-to-all communication backend.")
    enable_eplb: Optional[bool] = Field(default=None, description="Enable MoE expert load balancing.")
    eplb_config: Optional[Dict[str, Any]] = Field(default=None, description="Expert load balancer configuration.")
    expert_placement_strategy: Optional[str] = Field(default=None, description="Expert distribution pattern.")
    enable_dbo: Optional[bool] = Field(default=None, description="Enable dual batch overlap.")
    ubatch_size: Optional[int] = Field(default=None, description="Micro-batch size for DBO.")

    # Scheduling
    max_num_batched_tokens: Optional[int] = Field(default=None, description="Maximum number of batched tokens per iteration.")
    max_num_seqs: Optional[int] = Field(default=None, description="Maximum number of sequences per iteration.")
    max_num_partial_prefills: Optional[int] = Field(default=None, description="Maximum number of partial prefills per step.")
    max_long_partial_prefills: Optional[int] = Field(default=None, description="Maximum number of long partial prefills per step.")
    long_prefill_token_threshold: Optional[int] = Field(default=None, description="Token threshold for long prefill classification.")
    enable_chunked_prefill: Optional[bool] = Field(default=None, description="Enable chunked prefill scheduling.")
    disable_chunked_mm_input: Optional[bool] = Field(default=None, description="Disable chunked multimodal input scheduling.")
    scheduling_policy: Optional[Literal[ "fcfs", "priority" ]] = Field(default=None, description="Scheduling policy.")
    scheduler_cls: Optional[str] = Field(default=None, description="Custom scheduler class path.")
    scheduler_reserve_full_isl: Optional[bool] = Field(default=None, description="Reserve memory for full input sequence length when scheduling.")
    watermark: Optional[float] = Field(default=None, description="KV cache reservation fraction.")
    prefill_schedule_interval: Optional[int] = Field(default=None, description="DP prefill admission cadence.")
    disable_hybrid_kv_cache_manager: Optional[bool] = Field(default=None, description="Disable hybrid KV cache manager and use uniform allocation.")
    async_scheduling: Optional[bool] = Field(default=None, description="Enable background scheduling.")
    stream_interval: Optional[int] = Field(default=None, description="Token buffering interval for streaming.")

    # Multimodal
    language_model_only: Optional[bool] = Field(default=None, description="Disable all multimodal inputs.")
    limit_mm_per_prompt: Optional[Dict[str, int]] = Field(default=None, description="Per-modality input limits.")
    enable_mm_embeds: Optional[bool] = Field(default=None, description="Accept multimodal embedding inputs.")
    media_io_kwargs: Optional[Dict[str, Any]] = Field(default=None, description="Media I/O processing parameters.")
    mm_processor_kwargs: Optional[Dict[str, Any]] = Field(default=None, description="Kwargs for the multimodal processor.")
    mm_processor_cache_gb: Optional[float] = Field(default=None, description="Multimodal processor cache size in GiB. 0 disables the cache.")
    mm_processor_cache_type: Optional[Literal[ "lru", "shm" ]] = Field(default=None, description="Multimodal cache strategy.")
    mm_shm_cache_max_object_size_mb: Optional[int] = Field(default=None, description="Shared-memory object size limit for multimodal cache (MiB).")
    mm_encoder_only: Optional[bool] = Field(default=None, description="Skip language model component (encoder-only).")
    mm_encoder_tp_mode: Optional[str] = Field(default=None, description="Multimodal encoder TP optimization strategy.")
    mm_encoder_attn_backend: Optional[str] = Field(default=None, description="Attention backend for the multimodal encoder.")
    mm_encoder_attn_dtype: Optional[str] = Field(default=None, description="Multimodal encoder attention precision.")
    interleave_mm_strings: Optional[bool] = Field(default=None, description="Support interleaved text/media prompts.")
    skip_mm_profiling: Optional[bool] = Field(default=None, description="Skip multimodal encoder memory profiling.")
    video_pruning_rate: Optional[float] = Field(default=None, description="Video frame reduction rate.")

    # LoRA
    enable_lora: Optional[bool] = Field(default=None, description="Enable LoRA adapters.")
    max_loras: Optional[int] = Field(default=None, description="Maximum number of LoRA adapters in a single batch.")
    max_lora_rank: Optional[int] = Field(default=None, description="Maximum LoRA rank.")
    lora_dtype: Optional[Literal[ "auto", "float16", "bfloat16", "float32" ]] = Field(default=None, description="Data type for LoRA weights.")
    max_cpu_loras: Optional[int] = Field(default=None, description="Maximum number of LoRA adapters stored in CPU memory.")
    fully_sharded_loras: Optional[bool] = Field(default=None, description="Use fully sharded LoRA layers.")
    lora_target_modules: Optional[List[str]] = Field(default=None, description="Module-level adapter restrictions.")
    default_mm_loras: Optional[Dict[str, str]] = Field(default=None, description="Default LoRA adapters per modality.")

    # Speculative decoding
    speculative_config: Optional[Dict[str, Any]] = Field(default=None, description="Speculative decoding configuration.")

    # Structured outputs / pooling / generation
    structured_outputs_config: Optional[Dict[str, Any]] = Field(default=None, description="Structured outputs configuration.")
    pooler_config: Optional[Dict[str, Any]] = Field(default=None, description="Output pooling behavior settings.")
    generation_config: Optional[str] = Field(default=None, description="Generation config source ('auto', 'vllm', or path).")
    override_generation_config: Optional[Dict[str, Any]] = Field(default=None, description="Override default generation parameters.")
    override_pooler_config: Optional[Dict[str, Any]] = Field(default=None, description="Override pooler config.")
    override_neuron_config: Optional[Dict[str, Any]] = Field(default=None, description="Override Neuron config.")

    # Logits processors
    logits_processors: Optional[List[str]] = Field(default=None, description="Custom logits processor class paths.")
    io_processor_plugin: Optional[str] = Field(default=None, description="Custom I/O processor plugin.")

    # Runtime modes
    enable_sleep_mode: Optional[bool] = Field(default=None, description="Enable sleep mode for the engine.")
    enable_cumem_allocator: Optional[bool] = Field(default=None, description="Enable advanced GPU memory allocator.")
    enable_log_requests: Optional[bool] = Field(default=None, description="Log request information and parameters (AsyncEngine).")

    # Observability
    disable_log_stats: Optional[bool] = Field(default=None, description="Disable logging of stats.")
    show_hidden_metrics_for_version: Optional[str] = Field(default=None, description="Show metrics deprecated since a given version.")
    otlp_traces_endpoint: Optional[str] = Field(default=None, description="OpenTelemetry traces endpoint.")
    collect_detailed_traces: Optional[Union[str, List[str]]] = Field(default=None, description="Collect detailed traces for the given module(s).")
    enable_layerwise_nvtx_tracing: Optional[bool] = Field(default=None, description="Enable per-layer NVTX tracing.")

    # Misc
    additional_config: Optional[Dict[str, Any]] = Field(default=None, description="Additional platform-specific configuration.")
    kernel_config: Optional[Dict[str, Any]] = Field(default=None, description="Kernel selection parameters.")
    reasoning_config: Optional[Dict[str, Any]] = Field(default=None, description="Reasoning model settings.")
    reasoning_parser: Optional[str] = Field(default=None, description="Parser for reasoning model outputs.")
    optimization_level: Optional[str] = Field(default=None, description="Startup vs performance tradeoff level.")
    performance_mode: Optional[str] = Field(default=None, description="Runtime optimization strategy.")

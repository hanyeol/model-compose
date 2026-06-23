from typing import Union, Literal, Optional, Dict, List, Any
from pydantic import BaseModel, Field

class VllmEngineOptions(BaseModel):
    tokenizer: Optional[str] = Field(default=None, description="Name or path of the HuggingFace tokenizer to use.")
    tokenizer_mode: Optional[Literal["auto", "slow", "mistral", "custom"]] = Field(default=None, description="Tokenizer mode.")
    skip_tokenizer_init: Optional[bool] = Field(default=None, description="Skip initialization of tokenizer and detokenizer.")
    trust_remote_code: Optional[bool] = Field(default=None, description="Trust remote code from HuggingFace.")
    allowed_local_media_path: Optional[str] = Field(default=None, description="Allowed local media path for multimodal inputs.")

    tensor_parallel_size: Optional[int] = Field(default=None, description="Number of GPUs for tensor parallelism.")
    pipeline_parallel_size: Optional[int] = Field(default=None, description="Number of pipeline stages.")
    data_parallel_size: Optional[int] = Field(default=None, description="Number of data parallel replicas.")
    enable_expert_parallel: Optional[bool] = Field(default=None, description="Enable expert parallelism for MoE models.")

    dtype: Optional[Literal["auto", "half", "float16", "bfloat16", "float", "float32"]] = Field(default=None, description="Data type for model weights and activations.")
    kv_cache_dtype: Optional[Literal["auto", "fp8", "fp8_e5m2", "fp8_e4m3"]] = Field(default=None, description="Data type for KV cache.")
    seed: Optional[int] = Field(default=None, description="Random seed.")

    max_model_len: Optional[Union[int, Literal["auto"]]] = Field(default=None, description="Model context length.")
    max_seq_len_to_capture: Optional[int] = Field(default=None, description="Maximum sequence length covered by CUDA graphs.")

    quantization: Optional[str] = Field(default=None, description="Quantization method (e.g., 'awq', 'gptq', 'fp8', 'bitsandbytes', 'marlin').")
    rope_scaling: Optional[Dict[str, Any]] = Field(default=None, description="RoPE scaling configuration.")
    rope_theta: Optional[float] = Field(default=None, description="RoPE theta override.")
    hf_overrides: Optional[Dict[str, Any]] = Field(default=None, description="Overrides for HuggingFace config.")

    tokenizer_revision: Optional[str] = Field(default=None, description="Tokenizer revision.")
    tokenizer_pool_size: Optional[int] = Field(default=None, description="Size of the tokenizer pool.")
    tokenizer_pool_type: Optional[str] = Field(default=None, description="Type of the tokenizer pool.")

    load_format: Optional[str] = Field(default=None, description="Format of the model weights to load.")
    config_format: Optional[str] = Field(default=None, description="Format of the model config.")

    gpu_memory_utilization: Optional[float] = Field(default=None, description="Fraction of GPU memory to use (0.0-1.0).")
    swap_space: Optional[float] = Field(default=None, description="CPU swap space size in GiB per GPU.")
    cpu_offload_gb: Optional[float] = Field(default=None, description="CPU offload size in GiB per GPU.")

    block_size: Optional[int] = Field(default=None, description="Token block size for paged attention.")
    enable_prefix_caching: Optional[bool] = Field(default=None, description="Enable automatic prefix caching.")
    prefix_caching_hash_algo: Optional[str] = Field(default=None, description="Hash algorithm for prefix caching.")
    disable_sliding_window: Optional[bool] = Field(default=None, description="Disable sliding window attention.")
    use_v2_block_manager: Optional[bool] = Field(default=None, description="Use BlockSpaceMangerV2.")
    num_lookahead_slots: Optional[int] = Field(default=None, description="Number of speculative lookahead slots.")

    max_num_batched_tokens: Optional[int] = Field(default=None, description="Maximum number of batched tokens per iteration.")
    max_num_seqs: Optional[int] = Field(default=None, description="Maximum number of sequences per iteration.")
    max_num_partial_prefills: Optional[int] = Field(default=None, description="Maximum number of partial prefills per step.")
    max_long_partial_prefills: Optional[int] = Field(default=None, description="Maximum number of long partial prefills per step.")
    long_prefill_token_threshold: Optional[int] = Field(default=None, description="Token threshold for long prefill classification.")

    enable_chunked_prefill: Optional[bool] = Field(default=None, description="Enable chunked prefill scheduling.")
    scheduler_delay_factor: Optional[float] = Field(default=None, description="Delay factor used by the scheduler.")
    preemption_mode: Optional[Literal["recompute", "swap"]] = Field(default=None, description="Preemption mode.")
    scheduling_policy: Optional[Literal["fcfs", "priority"]] = Field(default=None, description="Scheduling policy.")

    speculative_config: Optional[Dict[str, Any]] = Field(default=None, description="Speculative decoding configuration.")
    speculative_model: Optional[str] = Field(default=None, description="Draft model for speculative decoding.")
    num_speculative_tokens: Optional[int] = Field(default=None, description="Number of speculative tokens per step.")
    speculative_draft_tensor_parallel_size: Optional[int] = Field(default=None, description="Tensor parallel size for the draft model.")
    speculative_max_model_len: Optional[int] = Field(default=None, description="Maximum model length for speculative decoding.")
    speculative_disable_by_batch_size: Optional[int] = Field(default=None, description="Disable speculative decoding above this batch size.")
    ngram_prompt_lookup_max: Optional[int] = Field(default=None, description="Maximum n-gram size for prompt lookup.")
    ngram_prompt_lookup_min: Optional[int] = Field(default=None, description="Minimum n-gram size for prompt lookup.")
    spec_decoding_acceptance_method: Optional[str] = Field(default=None, description="Speculative decoding acceptance method.")
    typical_acceptance_sampler_posterior_threshold: Optional[float] = Field(default=None, description="Posterior threshold for typical acceptance sampler.")
    typical_acceptance_sampler_posterior_alpha: Optional[float] = Field(default=None, description="Posterior alpha for typical acceptance sampler.")
    disable_logprobs_during_spec_decoding: Optional[bool] = Field(default=None, description="Disable logprobs during speculative decoding.")

    model_loader_extra_config: Optional[Dict[str, Any]] = Field(default=None, description="Extra config for model loader.")
    ignore_patterns: Optional[List[str]] = Field(default=None, description="Patterns to ignore when loading the model.")
    preemption_check_period: Optional[float] = Field(default=None, description="Period for preemption checks in seconds.")
    num_gpu_blocks_override: Optional[int] = Field(default=None, description="Override the number of GPU blocks.")

    disable_log_stats: Optional[bool] = Field(default=None, description="Disable logging of stats.")
    disable_async_output_proc: Optional[bool] = Field(default=None, description="Disable async output processing.")
    worker_cls: Optional[str] = Field(default=None, description="Custom worker class path.")
    worker_extension_cls: Optional[str] = Field(default=None, description="Custom worker extension class path.")

    compilation_config: Optional[Union[int, Dict[str, Any]]] = Field(default=None, description="torch.compile configuration.")
    kv_transfer_config: Optional[Dict[str, Any]] = Field(default=None, description="KV transfer configuration for disaggregated serving.")
    additional_config: Optional[Dict[str, Any]] = Field(default=None, description="Additional engine configuration.")
    use_tqdm_on_load: Optional[bool] = Field(default=None, description="Show tqdm progress bar during weight load.")

    enable_lora: Optional[bool] = Field(default=None, description="Enable LoRA adapters.")
    max_loras: Optional[int] = Field(default=None, description="Maximum number of LoRA adapters in a single batch.")
    max_lora_rank: Optional[int] = Field(default=None, description="Maximum LoRA rank.")
    lora_extra_vocab_size: Optional[int] = Field(default=None, description="Maximum LoRA extra vocab size.")
    lora_dtype: Optional[Literal["auto", "float16", "bfloat16", "float32"]] = Field(default=None, description="Data type for LoRA weights.")
    long_lora_scaling_factors: Optional[List[float]] = Field(default=None, description="Scaling factors for long LoRA.")
    max_cpu_loras: Optional[int] = Field(default=None, description="Maximum number of LoRA adapters stored in CPU memory.")
    fully_sharded_loras: Optional[bool] = Field(default=None, description="Use fully sharded LoRA layers.")

    enable_prompt_adapter: Optional[bool] = Field(default=None, description="Enable prompt adapters.")
    max_prompt_adapters: Optional[int] = Field(default=None, description="Maximum number of prompt adapters in a single batch.")
    max_prompt_adapter_token: Optional[int] = Field(default=None, description="Maximum number of prompt adapter tokens.")

    distributed_executor_backend: Optional[Literal["ray", "mp", "uni", "external_launcher"]] = Field(default=None, description="Distributed executor backend.")
    max_parallel_loading_workers: Optional[int] = Field(default=None, description="Maximum parallel loading workers.")
    ray_workers_use_nsight: Optional[bool] = Field(default=None, description="Profile Ray workers with nsight.")
    disable_custom_all_reduce: Optional[bool] = Field(default=None, description="Disable custom all-reduce kernel.")

    limit_mm_per_prompt: Optional[Dict[str, int]] = Field(default=None, description="Per-modality input limits.")
    mm_processor_kwargs: Optional[Dict[str, Any]] = Field(default=None, description="Kwargs for the multimodal processor.")
    disable_mm_preprocessor_cache: Optional[bool] = Field(default=None, description="Disable multimodal preprocessor cache.")
    mm_encoder_attn_backend: Optional[str] = Field(default=None, description="Attention backend for the multimodal encoder.")

    guided_decoding_backend: Optional[str] = Field(default=None, description="Guided decoding backend.")
    guided_decoding_disable_fallback: Optional[bool] = Field(default=None, description="Disable guided decoding fallback.")
    guided_decoding_disable_any_whitespace: Optional[bool] = Field(default=None, description="Disable any-whitespace in guided decoding.")
    guided_decoding_disable_additional_properties: Optional[bool] = Field(default=None, description="Disable additionalProperties in guided decoding.")
    logits_processor_pattern: Optional[str] = Field(default=None, description="Regex for allowed logits processors.")
    logits_processors: Optional[List[str]] = Field(default=None, description="Logits processor class paths.")

    override_neuron_config: Optional[Dict[str, Any]] = Field(default=None, description="Override Neuron config.")
    override_pooler_config: Optional[Dict[str, Any]] = Field(default=None, description="Override pooler config.")
    override_generation_config: Optional[Dict[str, Any]] = Field(default=None, description="Override generation config.")
    model_impl: Optional[Literal["auto", "vllm", "transformers"]] = Field(default=None, description="Model implementation to use.")

    task: Optional[str] = Field(default=None, description="vLLM task type (e.g., 'generate', 'embed', 'classify').")
    runner: Optional[str] = Field(default=None, description="vLLM runner type.")

    enforce_eager: Optional[bool] = Field(default=None, description="Disable CUDA graph and use eager mode.")
    enable_sleep_mode: Optional[bool] = Field(default=None, description="Enable sleep mode for the engine.")

    served_model_name: Optional[Union[str, List[str]]] = Field(default=None, description="Model name(s) exposed by the API.")
    qlora_adapter_name_or_path: Optional[str] = Field(default=None, description="Path or name of the QLoRA adapter.")

    otlp_traces_endpoint: Optional[str] = Field(default=None, description="OpenTelemetry traces endpoint.")
    collect_detailed_traces: Optional[str] = Field(default=None, description="Collect detailed traces for the given module.")
    disable_log_requests: Optional[bool] = Field(default=None, description="Disable logging of requests.")

    tokenizer_init_kwargs: Optional[Dict[str, Any]] = Field(default=None, description="Extra kwargs passed to tokenizer init.")
    calculate_kv_scales: Optional[bool] = Field(default=None, description="Calculate KV cache scales at runtime.")
    enable_chunked_mm_input: Optional[bool] = Field(default=None, description="Enable chunked multimodal input.")
    chunked_mm_input_size: Optional[int] = Field(default=None, description="Chunk size for multimodal input.")
    structured_outputs_config: Optional[Dict[str, Any]] = Field(default=None, description="Structured outputs configuration.")

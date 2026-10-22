from typing import Union, Literal, Optional, Dict, List, Any
from pydantic import BaseModel, Field

class SglangEngineOptionsConfig(BaseModel):
    # Model & tokenizer
    tokenizer_path: Optional[str] = Field(default=None, description="Name or path of the HuggingFace tokenizer to use.")
    tokenizer_mode: Optional[Literal[ "auto", "slow" ]] = Field(default=None, description="Tokenizer mode.")
    skip_tokenizer_init: Optional[bool] = Field(default=None, description="Whether to skip tokenizer and detokenizer initialization and expect pre-tokenized inputs.")
    trust_remote_code: Optional[bool] = Field(default=None, description="Whether to execute custom model code shipped in the HuggingFace repository.")
    revision: Optional[str] = Field(default=None, description="Model version (branch, tag, or commit).")
    hf_config_path: Optional[str] = Field(default=None, description="Custom HuggingFace config path.")
    served_model_name: Optional[str] = Field(default=None, description="Model name exposed by the API.")
    is_embedding: Optional[bool] = Field(default=None, description="Whether to run the model as an embedding model.")

    # Loading
    download_dir: Optional[str] = Field(default=None, description="Directory to download and cache model weights.")
    load_format: Optional[Literal[ "auto", "pt", "safetensors", "npcache", "dummy", "sharded_state", "gguf", "bitsandbytes", "layered" ]] = Field(default=None, description="Format of the model weights to load.")
    model_loader_extra_config: Optional[Dict[str, Any]] = Field(default=None, description="Extra config for model loader.")

    # Numerical types & limits
    dtype: Optional[Literal[ "auto", "half", "float16", "bfloat16", "float", "float32" ]] = Field(default=None, description="Data type for model weights and activations.")
    random_seed: Optional[int] = Field(default=None, description="Random seed.")
    context_length: Optional[int] = Field(default=None, description="Model context length.")
    device: Optional[Literal[ "cuda", "rocm", "cpu", "hpu", "xpu" ]] = Field(default=None, description="Device to run the model on.")

    # Quantization
    quantization: Optional[str] = Field(default=None, description="Quantization method (e.g., 'awq', 'gptq', 'fp8', 'bitsandbytes', 'marlin').")
    quantization_param_path: Optional[str] = Field(default=None, description="Path to the quantization parameter file.")
    kv_cache_dtype: Optional[Literal[ "auto", "fp8_e5m2", "fp8_e4m3" ]] = Field(default=None, description="Data type for KV cache.")

    # Attention / compilation
    attention_backend: Optional[Literal[ "flashinfer", "triton", "torch_native", "flashmla", "fa3", "fa4", "cutlass_mla", "ascend", "wave", "intel_amx", "intel_xpu", "aiter", "trtllm_mla", "trtllm_mha" ]] = Field(default=None, description="Attention implementation selection.")
    sampling_backend: Optional[Literal[ "flashinfer", "pytorch" ]] = Field(default=None, description="Sampling kernel backend.")
    disable_cuda_graph: Optional[bool] = Field(default=None, description="Whether to disable CUDA graph capture and run in eager mode.")
    disable_cuda_graph_padding: Optional[bool] = Field(default=None, description="Whether to disable CUDA graph padding.")
    cuda_graph_max_bs: Optional[int] = Field(default=None, description="Maximum batch size for CUDA graph capture.")
    cuda_graph_bs: Optional[List[int]] = Field(default=None, description="Batch sizes for CUDA graph capture.")
    enable_torch_compile: Optional[bool] = Field(default=None, description="Whether to enable torch.compile for the model.")
    torch_compile_max_bs: Optional[int] = Field(default=None, description="Maximum batch size eligible for torch.compile.")
    triton_attention_reduce_in_fp32: Optional[bool] = Field(default=None, description="Whether to reduce the Triton attention output in fp32.")
    triton_attention_num_kv_splits: Optional[int] = Field(default=None, description="Number of KV splits used by the Triton attention kernel.")

    # Memory / KV cache
    mem_fraction_static: Optional[float] = Field(default=None, description="Fraction of GPU memory reserved for static allocations (0.0-1.0).")
    max_total_tokens: Optional[int] = Field(default=None, description="Maximum number of tokens held in the KV cache pool.")
    chunked_prefill_size: Optional[int] = Field(default=None, description="Chunk size for prefill scheduling; -1 disables chunking.")
    max_prefill_tokens: Optional[int] = Field(default=None, description="Maximum number of tokens prefilled per batch.")
    schedule_policy: Optional[Literal[ "lpm", "random", "fcfs", "dfs-weight" ]] = Field(default=None, description="Request scheduling policy.")
    schedule_conservativeness: Optional[float] = Field(default=None, description="Scheduler admission conservativeness factor.")
    page_size: Optional[int] = Field(default=None, description="Token block size for paged attention.")
    disable_radix_cache: Optional[bool] = Field(default=None, description="Whether to disable the radix (prefix) cache.")
    enable_hierarchical_cache: Optional[bool] = Field(default=None, description="Whether to enable the hierarchical KV cache.")
    hicache_ratio: Optional[float] = Field(default=None, description="Hierarchical cache size ratio relative to the KV pool.")
    hicache_size: Optional[int] = Field(default=None, description="Hierarchical cache size in GiB.")
    hicache_write_policy: Optional[Literal[ "write_back", "write_through", "write_through_selective" ]] = Field(default=None, description="Hierarchical cache write policy.")
    hicache_io_backend: Optional[Literal[ "direct", "kernel" ]] = Field(default=None, description="Hierarchical cache I/O backend.")
    hicache_storage_backend: Optional[str] = Field(default=None, description="Hierarchical cache storage backend.")

    # Distributed execution
    tp_size: Optional[int] = Field(default=None, description="Number of GPUs for tensor parallelism.")
    pp_size: Optional[int] = Field(default=None, description="Number of pipeline stages.")
    dp_size: Optional[int] = Field(default=None, description="Number of data parallel replicas.")
    ep_size: Optional[int] = Field(default=None, description="Number of expert parallel groups for MoE models.")
    load_balance_method: Optional[Literal[ "round_robin", "shortest_queue" ]] = Field(default=None, description="Data parallel load balancing strategy.")
    dist_init_addr: Optional[str] = Field(default=None, description="Multi-node master address.")
    nnodes: Optional[int] = Field(default=None, description="Total number of nodes.")
    node_rank: Optional[int] = Field(default=None, description="Current node identifier.")
    base_gpu_id: Optional[int] = Field(default=None, description="Base GPU index assigned to the first worker.")
    gpu_id_step: Optional[int] = Field(default=None, description="Stride between successive worker GPU indices.")

    # Scheduling / batching
    max_running_requests: Optional[int] = Field(default=None, description="Maximum number of in-flight requests.")
    stream_interval: Optional[int] = Field(default=None, description="Token buffering interval for streaming.")
    stream_output: Optional[bool] = Field(default=None, description="Whether to stream intermediate token outputs by default.")

    # LoRA
    lora_paths: Optional[Union[List[str], Dict[str, str]]] = Field(default=None, description="LoRA adapters to load.")
    max_loras_per_batch: Optional[int] = Field(default=None, description="Maximum number of LoRA adapters in a single batch.")
    lora_backend: Optional[Literal[ "triton", "flashinfer" ]] = Field(default=None, description="LoRA kernel backend.")

    # Speculative decoding
    speculative_algorithm: Optional[str] = Field(default=None, description="Speculative decoding algorithm.")
    speculative_draft_model_path: Optional[str] = Field(default=None, description="Draft model path for speculative decoding.")
    speculative_num_steps: Optional[int] = Field(default=None, description="Number of speculative draft steps per iteration.")
    speculative_num_draft_tokens: Optional[int] = Field(default=None, description="Number of draft tokens proposed per step.")
    speculative_eagle_topk: Optional[int] = Field(default=None, description="Top-k used by Eagle speculative decoding.")

    # Expert / MoE
    enable_ep_moe: Optional[bool] = Field(default=None, description="Whether to enable expert parallelism for MoE models.")
    enable_deepep_moe: Optional[bool] = Field(default=None, description="Whether to enable DeepEP MoE communication.")
    deepep_mode: Optional[Literal[ "auto", "normal", "low_latency" ]] = Field(default=None, description="DeepEP communication mode.")

    # Runtime modes
    disable_overlap_schedule: Optional[bool] = Field(default=None, description="Whether to disable overlapped scheduling of prefill and decode.")
    enable_mixed_chunk: Optional[bool] = Field(default=None, description="Whether to allow mixing prefill and decode in a single batch.")
    enable_dp_attention: Optional[bool] = Field(default=None, description="Whether to enable data parallel attention.")
    enable_two_batch_overlap: Optional[bool] = Field(default=None, description="Whether to overlap two batches for throughput.")
    enable_memory_saver: Optional[bool] = Field(default=None, description="Whether to enable the memory-saving execution path.")
    allow_auto_truncate: Optional[bool] = Field(default=None, description="Whether to auto-truncate inputs that exceed the context length.")
    return_hidden_states: Optional[bool] = Field(default=None, description="Whether to return model hidden states alongside outputs.")

    # Chat template / tooling
    chat_template: Optional[str] = Field(default=None, description="Chat template name or path.")
    completion_template: Optional[str] = Field(default=None, description="Completion template name or path.")
    reasoning_parser: Optional[str] = Field(default=None, description="Built-in reasoning parser name.")
    tool_call_parser: Optional[str] = Field(default=None, description="Built-in tool call parser name.")

    # Observability
    log_level: Optional[str] = Field(default=None, description="Engine log level.")
    log_requests: Optional[bool] = Field(default=None, description="Whether to log request information and parameters.")
    log_requests_level: Optional[int] = Field(default=None, description="Log level used for request logging.")
    show_time_cost: Optional[bool] = Field(default=None, description="Whether to log step time cost.")
    enable_metrics: Optional[bool] = Field(default=None, description="Whether to enable Prometheus metrics.")
    decode_log_interval: Optional[int] = Field(default=None, description="Interval (in steps) between decode progress logs.")

    # Misc
    watchdog_timeout: Optional[float] = Field(default=None, description="Watchdog timeout in seconds for stalled workers.")
    download_timeout: Optional[int] = Field(default=None, description="Timeout in seconds for model downloads.")

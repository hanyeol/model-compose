from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonActionConfig

class LRSchedulerType(str, Enum):
    LINEAR               = "linear"
    COSINE               = "cosine"
    COSINE_WITH_RESTARTS = "cosine_with_restarts"
    POLYNOMIAL           = "polynomial"
    CONSTANT             = "constant"
    CONSTANT_WITH_WARMUP = "constant_with_warmup"
    INVERSE_SQRT         = "inverse_sqrt"
    REDUCE_LR_ON_PLATEAU = "reduce_lr_on_plateau"
    COSINE_WITH_MIN_LR   = "cosine_with_min_lr"
    WARMUP_STABLE_DECAY  = "warmup_stable_decay"

class OptimizerType(str, Enum):
    # AdamW variants
    ADAMW_TORCH                 = "adamw_torch"
    ADAMW_TORCH_FUSED           = "adamw_torch_fused"
    ADAMW_TORCH_XLA             = "adamw_torch_xla"
    ADAMW_TORCH_NPU_FUSED       = "adamw_torch_npu_fused"
    ADAMW_APEX_FUSED            = "adamw_apex_fused"
    ADAMW_ANYPRECISION          = "adamw_anyprecision"
    ADAMW_BNB_8BIT              = "adamw_bnb_8bit"
    ADAMW_8BIT                  = "adamw_8bit"  # Alias for adamw_bnb_8bit
    ADAMW_HF                    = "adamw_hf"

    # Specialized optimizers
    ADAFACTOR                   = "adafactor"
    ADALOMO                     = "adalomo"
    LOMO                        = "lomo"

    # Memory-efficient optimizers
    APOLLO_ADAMW                = "apollo_adamw"
    GALORE_ADAMW                = "galore_adamw"
    GALORE_ADAMW_8BIT           = "galore_adamw_8bit"
    GALORE_ADAFACTOR            = "galore_adafactor"
    GALORE_ADAMW_LAYERWISE      = "galore_adamw_layerwise"
    GALORE_ADAMW_8BIT_LAYERWISE = "galore_adamw_8bit_layerwise"
    GALORE_ADAFACTOR_LAYERWISE  = "galore_adafactor_layerwise"

    # Additional advanced optimizers
    GROKADAMW                   = "grokadamw"
    SCHEDULE_FREE_RADAMW        = "schedule_free_radamw"
    STABLEADAMW                 = "stableadamw"

    # Traditional optimizers
    SGD                         = "sgd"
    ADAGRAD                     = "adagrad"
    RMSPROP                     = "rmsprop"

class CommonModelTrainerActionConfig(CommonActionConfig):
    # Essential training parameters
    learning_rate: Union[float, str] = Field(default=5e-5, description="Learning rate for training.")
    per_device_train_batch_size: Union[int, str] = Field(default=8, description="Training batch size per device.")
    per_device_eval_batch_size: Optional[Union[int, str]] = Field(default=None, description="Evaluation batch size per device. If None, uses per_device_train_batch_size.")
    num_epochs: Union[int, str] = Field(default=3, description="Number of training epochs.")

    # Optimizer and scheduler
    optimizer: OptimizerType = Field(default=OptimizerType.ADAMW_TORCH, description="Optimizer to use for training.")
    lr_scheduler_type: LRSchedulerType = Field(default=LRSchedulerType.LINEAR, description="Learning rate scheduler type.")

    # Output configuration
    output_dir: str = Field(default="./output", description="Directory to save the trained model.")

    # Common optimization settings
    weight_decay: Union[float, str] = Field(default=0.01, description="Weight decay for regularization.")
    warmup_steps: Union[int, str] = Field(default=100, description="Number of warmup steps.")
    max_grad_norm: Union[float, str] = Field(default=1.0, description="Maximum gradient norm for gradient clipping.")
    gradient_accumulation_steps: Union[int, str] = Field(default=1, description="Number of gradient accumulation steps.")

    # Evaluation and saving
    eval_steps: Union[int, str] = Field(default=500, description="Steps between evaluations.")
    save_steps: Optional[Union[int, str]] = Field(default=None, description="Steps between model saves. If not specified, uses eval_steps.")
    logging_steps: Union[int, str] = Field(default=10, description="Steps between logging.")

    # Memory optimization
    gradient_checkpointing: Union[bool, str] = Field(default=False, description="Enable gradient checkpointing to save memory.")
    fp16: Union[bool, str] = Field(default=False, description="Enable FP16 mixed precision training.")
    bf16: Union[bool, str] = Field(default=False, description="Enable BF16 mixed precision training (recommended for A100/H100).")

    # Reproducibility
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed for reproducibility.")

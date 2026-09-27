from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Optional, Dict, List, Tuple, Any
from abc import abstractmethod
from mindor.dsl.schema.component import ModelTrainerComponentConfig, ModelTrainerTaskType, ModelTrainerDriverType, ModelConfig, ModelPrecision, ModelQuantizationConfig, ModelQuantizationType, ModelTrainerLoraConfig
from mindor.dsl.schema.action import ModelTrainerActionConfig, CommonModelTrainerActionConfig
from mindor.core.component.base import ComponentDriver
from mindor.core.component.action.base import ComponentAction
from ....context import ComponentActionContext
from ...model.utils.provision import ModelProvisioner
from ...model.utils.device import DeviceResolver

if TYPE_CHECKING:
    from datasets import Dataset, DatasetDict
    import torch

class ModelTrainerTaskAction(ComponentAction):
    def __init__(self, config: CommonModelTrainerActionConfig, trainer_config: ModelTrainerComponentConfig, model_path: str):
        self.config: CommonModelTrainerActionConfig = config
        self.trainer_config: ModelTrainerComponentConfig = trainer_config
        self.model_path: str = model_path

    def _load_datasets(self, train_dataset: Any, evaluation_dataset: Any) -> Tuple[Any, Optional[Any]]:
        """Load and normalize (train, evaluation) datasets.

        Accepts three input shapes for each argument: a HuggingFace repo ID (str,
        loaded via `load_dataset`), an already-materialized Dataset / DatasetDict
        (passed through from an upstream `datasets` component), or None.
        DatasetDicts are collapsed to a single train split and an optional
        evaluation split.

        Evaluation split lookup prefers `validation` over `test`. GLUE SST-2 and
        many other benchmarks ship hidden test labels (label=-1), so picking
        `test` first would either crash training or silently score against
        garbage. When the preferred split is unusable (all labels < 0) the next
        candidate is tried; if none of the candidates pass, evaluation is
        skipped rather than falling back to an arbitrary split — an arbitrary
        fallback would defeat the masking check and silently reintroduce the
        rejected split.
        """
        from datasets import Dataset, DatasetDict, load_dataset

        def _load_dataset(source: Any) -> Any:
            if isinstance(source, (Dataset, DatasetDict)):
                return source

            if isinstance(source, str):
                return load_dataset(source)

            # Already a dict-like or list-like from an upstream `datasets` component.
            return source

        def _pick_evaluation_dataset(dataset: DatasetDict) -> Optional[Dataset]:
            for name in ("validation", "eval", "test"):
                candidate = dataset.get(name)

                if candidate is None:
                    continue

                # Reject splits where labels are masked (e.g. GLUE SST-2 test).
                if "label" in candidate.column_names:
                    try:
                        if all(int(value) < 0 for value in candidate["label"][:32]):
                            continue
                    except (TypeError, ValueError):
                        pass

                return candidate

            return None

        train_dataset      = _load_dataset(train_dataset)
        evaluation_dataset = _load_dataset(evaluation_dataset)

        if isinstance(train_dataset, DatasetDict):
            evaluation_dataset = evaluation_dataset or _pick_evaluation_dataset(train_dataset)
            train_dataset      = train_dataset["train"] if "train" in train_dataset else next(iter(train_dataset.values()))
        # If train_dataset came in as a bare Dataset, evaluation_dataset stays
        # whatever the user supplied (possibly None). Do not call .get() on a Dataset.

        if isinstance(evaluation_dataset, DatasetDict):
            # No arbitrary fallback — if every candidate was rejected by
            # _pick_evaluation_dataset, evaluation_dataset becomes None and
            # evaluation is skipped.
            evaluation_dataset = _pick_evaluation_dataset(evaluation_dataset)

        return train_dataset, evaluation_dataset

    def _get_model_dtype(self) -> Optional[torch.dtype]:
        import torch

        # "auto" is a from_pretrained hint, not a real dtype — treat as unset.
        if self.trainer_config.precision is not None and self.trainer_config.precision != ModelPrecision.AUTO:
            return getattr(torch, self.trainer_config.precision.value)

        return None

    def _build_quantization_config(self, quantization: ModelQuantizationConfig) -> Any:
        from transformers import BitsAndBytesConfig
        import torch

        if quantization.type == ModelQuantizationType.INT8:
            return BitsAndBytesConfig(load_in_8bit=True)

        # int4/fp4/nf4 all take the 4-bit path; `quant_type` selects the block format.
        if quantization.type in (ModelQuantizationType.INT4, ModelQuantizationType.NF4):
            quant_type = "nf4"
        else:
            quant_type = "fp4"

        if quantization.compute_dtype is not None:
            compute_dtype = getattr(torch, quantization.compute_dtype)
        else:
            compute_dtype = torch.float16

        return BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type=quant_type,
            bnb_4bit_compute_dtype=compute_dtype,
            bnb_4bit_use_double_quant=quantization.double_quant,
        )

    def _build_lora_config(self, lora: ModelTrainerLoraConfig, task_type_hint: str) -> Any:
        from peft import LoraConfig

        return LoraConfig(
            r=lora.rank,
            lora_alpha=lora.alpha,
            lora_dropout=lora.dropout,
            target_modules=lora.target_modules,
            bias=lora.bias,
            task_type=task_type_hint,  # "CAUSAL_LM" | "SEQ_CLS" | ...
        )

    async def _build_training_arguments(
        self,
        context: ComponentActionContext,
        output_dir: str,
        has_evaluation: bool,
    ) -> Dict[str, Any]:
        # Render every Union[..., str] field OUTSIDE the training executor. Return a
        # plain dict so callers can spread into TrainingArguments OR SFTConfig (which
        # is a TrainingArguments subclass in TRL 0.12+).
        #
        # `has_evaluation` must be resolved by the caller AFTER _load_datasets — the
        # action's evaluation_dataset field may be None while the dataset itself is a
        # DatasetDict with a `validation` split. Checking only `action.evaluation_dataset`
        # here would leave eval_strategy="no" and silently skip evaluation on
        # split-provided data.
        num_epochs                  = await context.render_scalar(self.config.num_epochs, int)
        train_batch_size            = await context.render_scalar(self.config.per_device_train_batch_size, int)
        eval_batch_size             = await context.render_scalar(self.config.per_device_eval_batch_size, int) or train_batch_size
        learning_rate               = await context.render_scalar(self.config.learning_rate, float)
        weight_decay                = await context.render_scalar(self.config.weight_decay, float)
        warmup_steps                = await context.render_scalar(self.config.warmup_steps, int)
        max_grad_norm               = await context.render_scalar(self.config.max_grad_norm, float)
        gradient_accumulation_steps = await context.render_scalar(self.config.gradient_accumulation_steps, int)
        eval_steps                  = await context.render_scalar(self.config.eval_steps, int)
        save_steps                  = await context.render_scalar(self.config.save_steps, int) or eval_steps
        logging_steps               = await context.render_scalar(self.config.logging_steps, int)
        gradient_checkpointing      = await context.render_scalar(self.config.gradient_checkpointing, bool)
        fp16                        = await context.render_scalar(self.config.fp16, bool)
        bf16                        = await context.render_scalar(self.config.bf16, bool)
        seed                        = await context.render_scalar(self.config.seed, int) if self.config.seed is not None else 42

        return {
            "output_dir":                  output_dir,
            "num_train_epochs":            num_epochs,
            "per_device_train_batch_size": train_batch_size,
            "per_device_eval_batch_size":  eval_batch_size,
            "learning_rate":               learning_rate,
            "weight_decay":                weight_decay,
            "warmup_steps":                warmup_steps,
            "max_grad_norm":               max_grad_norm,
            "gradient_accumulation_steps": gradient_accumulation_steps,
            "eval_strategy":               "steps" if has_evaluation else "no",
            "eval_steps":                  eval_steps,
            "save_steps":                  save_steps,
            "logging_steps":               logging_steps,
            "gradient_checkpointing":      gradient_checkpointing,
            "fp16":                        fp16,
            "bf16":                        bf16,
            "optim":                       self.config.optimizer.value,
            "lr_scheduler_type":           self.config.lr_scheduler_type.value,
            "seed":                        seed,
        }

class ModelTrainerTaskDriver(ComponentDriver):
    def __init__(self, id: str, config: ModelTrainerComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: ModelTrainerComponentConfig = config
        self.model_path: Optional[str] = None

        self._model_provisioner: ModelProvisioner = ModelProvisioner()
        self._device_resolver: DeviceResolver = DeviceResolver()

    async def run(self, action: ModelTrainerActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    async def _start(self) -> None:
        await self._load_model()

        await super()._start()

    async def _load_model(self) -> None:
        self.model_path = await self._provision_model(self.config.model, prefetch=True)

    @abstractmethod
    async def _run(self, action: ModelTrainerActionConfig, context: ComponentActionContext) -> Any:
        pass

    async def _provision_model(self, model: ModelConfig, prefetch: bool = False) -> str:
        return await self._model_provisioner.provision(model, prefetch=prefetch)

    def _resolve_device(self, device: str) -> torch.device:
        return self._device_resolver.resolve(device)

def register_model_trainer_task_driver(task: ModelTrainerTaskType, driver: ModelTrainerDriverType):
    def decorator(cls: Type[ModelTrainerTaskDriver]) -> Type[ModelTrainerTaskDriver]:
        if task not in ModelTrainerTaskDriverRegistry:
            ModelTrainerTaskDriverRegistry[task] = {}
        ModelTrainerTaskDriverRegistry[task][driver] = cls
        return cls
    return decorator

ModelTrainerTaskDriverRegistry: Dict[ModelTrainerTaskType, Dict[ModelTrainerDriverType, Type[ModelTrainerTaskDriver]]] = {}

from mindor.dsl.schema.component import ModelComponentConfig, TypedDecisionModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.TYPED_DECISION, ModelDriverType.CUSTOM)
class CustomTypedDecisionTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == TypedDecisionModelFamily.NIMBLE:
            from .nimble import NimbleTypedDecisionTaskDriver
            return NimbleTypedDecisionTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")

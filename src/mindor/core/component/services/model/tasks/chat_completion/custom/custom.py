from mindor.dsl.schema.component import ModelComponentConfig, ChatCompletionModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.CHAT_COMPLETION, ModelDriverType.CUSTOM)
class CustomChatCompletionTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        raise ValueError(f"Unknown family: {config.family}")

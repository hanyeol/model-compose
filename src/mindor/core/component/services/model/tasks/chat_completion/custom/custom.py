from mindor.dsl.schema.component import ModelComponentConfig, ChatCompletionModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.CHAT_COMPLETION, ModelDriver.CUSTOM)
class CustomChatCompletionTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        raise ValueError(f"Unknown family: {config.family}")

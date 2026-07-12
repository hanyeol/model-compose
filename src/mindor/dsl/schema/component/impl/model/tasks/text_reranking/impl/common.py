from typing import Literal
from ...common import LanguageModelComponentConfig, ModelTaskType

class CommonTextRerankingModelComponentConfig(LanguageModelComponentConfig):
    task: Literal[ModelTaskType.TEXT_RERANKING]

from enum import Enum

class ModelTaskType(str, Enum):
    TEXT_GENERATION = "text-generation"
    SUMMARIZATION   = "summarization"
    TRANSLATION     = "translation"
    TEXT_EMBEDDING  = "text-embedding"

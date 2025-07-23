from enum import Enum

class ModelTaskType(str, Enum):
    TEXT_GENERATION = "text-generation"
    SUMMARIZATION   = "summarization"
    TEXT_EMBEDDING  = "text-embedding"

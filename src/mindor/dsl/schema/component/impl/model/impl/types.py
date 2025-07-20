from enum import Enum

class ModelTaskType(str, Enum):
    TEXT_GENERATION = "text-generation"
    TEXT_EMBEDDING  = "text-embedding"

from enum import Enum

class ModelTaskType(str, Enum):
    TEXT_GENERATION     = "text-generation"
    SUMMARIZATION       = "summarization"
    TRANSLATION         = "translation"
    TEXT_CLASSIFICATION = "text-classification" 
    TEXT_EMBEDDING      = "text-embedding"
    IMAGE_TO_TEXT       = "image-to-text"

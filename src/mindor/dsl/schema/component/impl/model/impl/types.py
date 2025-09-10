from enum import Enum

class ModelTaskType(str, Enum):
    TEXT_GENERATION     = "text-generation"
    CHAT_COMPLETION     = "chat-completion"
    TEXT_CLASSIFICATION = "text-classification" 
    TEXT_EMBEDDING      = "text-embedding"
    IMAGE_TO_TEXT       = "image-to-text"
    IMAGE_GENERATION    = "image-generation"
    IMAGE_UPSCALE       = "image-upscale"

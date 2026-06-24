from enum import Enum

class TracerDriver(str, Enum):
    OTLP     = "otlp"
    LANGFUSE = "langfuse"

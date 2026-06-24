from enum import Enum

class RuntimeType(str, Enum):
    NATIVE          = "native"
    EMBEDDED        = "embedded"
    PROCESS         = "process"
    VIRTUALENV      = "virtualenv"
    DOCKER          = "docker"
    APPLE_CONTAINER = "apple-container"

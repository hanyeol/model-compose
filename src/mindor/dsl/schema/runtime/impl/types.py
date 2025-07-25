from enum import Enum

class RuntimeType(str, Enum):
    NATIVE = "native"
    DOCKER = "docker"

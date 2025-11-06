from enum import Enum

class RuntimeType(str, Enum):
    NATIVE   = "native"
    EMBEDDED = "embedded"
    DOCKER   = "docker"

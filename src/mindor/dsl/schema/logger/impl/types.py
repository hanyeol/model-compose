from enum import Enum

class LoggerType(str, Enum):
    CONSOLE = "console"
    FILE    = "file"

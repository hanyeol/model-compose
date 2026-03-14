from enum import Enum

class JobType(str, Enum):
    COMPONENT     = "component"
    DELAY         = "delay"
    IF            = "if"
    SWITCH        = "switch"
    RANDOM_ROUTER = "random-router"
    FILTER        = "filter"

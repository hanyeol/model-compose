from enum import Enum

class JobType(str, Enum):
    ACTION        = "action"
    DELAY         = "delay"
    IF            = "if"
    SWITCH        = "switch"
    RANDOM_ROUTER = "random-router"
    FILTER        = "filter"

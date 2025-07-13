from enum import Enum

class JobType(str, Enum):
    ACTION = "action"
    DELAY  = "delay"

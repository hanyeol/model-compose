from enum import Enum

class JobType(str, Enum):
    ACTION = "action"
    WAIT   = "wait"

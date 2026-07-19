from mindor.core.errors import TaskError

class TaskNotFoundError(TaskError):
    code = "TASK_NOT_FOUND"

class TaskNotInterruptedError(TaskError):
    code = "TASK_NOT_INTERRUPTED"

class TaskAlreadyFinishedError(TaskError):
    code = "TASK_ALREADY_FINISHED"

class TaskCancelInProgressError(TaskError):
    code = "TASK_CANCEL_IN_PROGRESS"

class JobIdMismatchError(TaskError):
    code = "JOB_ID_MISMATCH"

class InterruptNotActiveError(TaskError):
    code = "INTERRUPT_NOT_ACTIVE"

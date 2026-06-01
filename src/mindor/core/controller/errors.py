from mindor.core.errors import TaskError

class TaskNotFoundError(TaskError):
    code = "TASK_NOT_FOUND"

class TaskNotInterruptedError(TaskError):
    code = "TASK_NOT_INTERRUPTED"

class JobIdMismatchError(TaskError):
    code = "JOB_ID_MISMATCH"

class InterruptNotActiveError(TaskError):
    code = "INTERRUPT_NOT_ACTIVE"
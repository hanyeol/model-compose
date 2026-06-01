class TaskError(ValueError):
    code: str = "INVALID_REQUEST"

class ShutdownError(RuntimeError):
    pass

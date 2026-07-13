from typing import Optional, Literal
from dataclasses import dataclass

@dataclass
class HookPoint:
    task_id: str
    job_id: str
    run_id: Optional[str]
    phase: Literal[ "before", "after" ]

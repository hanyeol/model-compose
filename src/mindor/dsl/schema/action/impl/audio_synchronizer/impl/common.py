from typing import Union, List, Optional
from pydantic import Field
from ...common import CommonActionConfig

class CommonAudioSynchronizerActionConfig(CommonActionConfig):
    sources: Union[str, List[str]] = Field(..., description="Media sources to align against each other; the first source is the reference.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of source pairs decoded in parallel.")

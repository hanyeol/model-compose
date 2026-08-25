from typing import Any, Dict, Literal, List, Optional
from pydantic import Field, model_validator
from mindor.dsl.schema.action import MusicGenerationModelActionConfig
from ...common import CommonMusicGenerationModelComponentConfig
from .common import MusicGenerationModelFamily
from .....common import ModelDriver

class AceStepMusicGenerationModelComponentConfig(CommonMusicGenerationModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[MusicGenerationModelFamily.ACE_STEP]
    preset: str = Field(default="acestep-v15-turbo", description="ACE-Step preset selecting the model variant (e.g., acestep-v15-turbo, acestep-v15-base, acestep-v15-sft).")
    thinking_model: Optional[str] = Field(default=None, description="ACE-Step 5Hz LM used for thinking (e.g., acestep-5Hz-lm-0.6B, acestep-5Hz-lm-1.7B, acestep-5Hz-lm-4B); when unset, thinking is disabled.")
    thinking_scope: List[Literal[ "metas", "caption", "language", "codes" ]] = Field(default_factory=lambda: ["metas"], description="Contributions the thinking model makes when enabled, as a single value or a list; `full` expands to all four.")
    actions: List[MusicGenerationModelActionConfig] = Field(default_factory=list, description="Actions this music generation component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_single_thinking_scope(cls, values: Dict[str, Any]):
        scope = values.get("thinking_scope")
        if isinstance(scope, str):
            values["thinking_scope"] = [ "metas", "caption", "language", "codes" ] if scope == "full" else [ scope ]
        return values

from typing import Union, Optional, Dict, Any
from pydantic import BaseModel, Field
from pydantic import model_validator, field_validator
from mindor.core.utils.time import parse_duration
import re

_RATE_LIMIT_SHORTHAND_RE = re.compile(
    r"^\s*(\d+)\s*/\s*(?:(\d+(?:\.\d+)?)(ms|s|m|h|d)|(ms|s|m|h|d))\s*$"
)

class RateLimitConfig(BaseModel):
    requests: Optional[int] = Field(default=None, description="Maximum number of requests allowed within 'period'.")
    period: Union[str, float] = Field(default="1s", description="Length of the token-bucket window (e.g. '1s', '500ms', '1m').")
    burst: Optional[int] = Field(default=None, description="Token bucket capacity. Defaults to 'requests' when omitted.")
    interval: Optional[Union[str, float]] = Field(default=None, description="Minimum gap between consecutive requests (e.g. '100ms').")

    @field_validator("requests", "burst")
    def validate_positive_int(cls, value):
        if value is not None and value <= 0:
            raise ValueError("must be a positive integer")
        return value

    @field_validator("period", "interval")
    def validate_positive_duration(cls, value):
        if value is None:
            return value
        if parse_duration(value).total_seconds() <= 0:
            raise ValueError("must be a positive duration")
        return value

    @model_validator(mode="after")
    def validate_combination(self):
        if self.burst is not None and self.requests is None:
            raise ValueError("burst is meaningless without requests")
        if self.requests is None and self.interval is None:
            raise ValueError("rate_limit requires at least one of 'requests' or 'interval'")
        return self

def inflate_rate_limit_shorthand(value: str) -> Dict[str, Any]:
    match = _RATE_LIMIT_SHORTHAND_RE.match(value)
    if not match:
        raise ValueError("Invalid rate_limit shorthand: expected '<int>/<duration>'")
    requests_str, qty, qty_unit, bare_unit = match.groups()
    period = f"{qty}{qty_unit}" if qty is not None else f"1{bare_unit}"
    return { "requests": int(requests_str), "period": period }

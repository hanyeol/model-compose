from typing import Union, Optional, Dict, List, Any
from pydantic import Field
from .common import CommonActionConfig

class HtmlFrameRendererActionConfig(CommonActionConfig):
    html: Union[List[str], str] = Field(..., description="HTML source(s) to render: http(s):// URL, file path, directory with index.html, or inline HTML.")
    props: Optional[Union[Dict[str, Any], List[Any], str]] = Field(default=None, description="Data injected into window.__renderer.props before the page loads.")
    fps: Union[int, float, str] = Field(default=30, description="Frames per second.")
    width: Union[int, str] = Field(default=1920, description="Viewport width in CSS pixels.")
    height: Union[int, str] = Field(default=1080, description="Viewport height in CSS pixels.")
    ready_timeout: Optional[str] = Field(default="30s", description="How long to wait for window.__renderer.seek to be defined.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input HTMLs per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether to stream frames one by one instead of returning a full list.")

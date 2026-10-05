from typing import Union, Optional, Literal, Dict, List, Any
from pydantic import Field
from .common import CommonActionConfig

class HtmlFrameRendererActionConfig(CommonActionConfig):
    html: Union[List[str], str] = Field(..., description="HTML source to render: an http(s) URL, file path, directory with index.html, or inline HTML.")
    props: Optional[Union[Dict[str, Any], List[Any], str]] = Field(default=None, description="Data injected into window.__renderer.props before the page loads.")
    fps: Union[int, float, str] = Field(default=30, description="Output frame rate in frames per second.")
    width: Union[int, str] = Field(default=1920, description="Rendering viewport width in CSS pixels.")
    height: Union[int, str] = Field(default=1080, description="Rendering viewport height in CSS pixels.")
    format: Union[Literal[ "jpeg", "png" ], str] = Field(default="jpeg", description="Image format of the captured frames.")
    quality: Optional[Union[int, str]] = Field(default=None, description="JPEG quality from 0 to 100. Applies only when `format` is `jpeg`.")
    transparent: Union[bool, str] = Field(default=False, description="Capture the viewport with a transparent background. Requires `format: png` and a page that leaves html/body backgrounds unset.")
    ready_timeout: Optional[str] = Field(default="60s", description="Maximum time to wait for the page to set window.__renderer.ready = true after it loads.")
    render_timeout: Optional[str] = Field(default="10s", description="Maximum time to wait for each frame's rendered() call.")
    filename_format: Optional[str] = Field(default=None, description="Per-frame filename pattern (e.g., frame-%04d.png); when set, each frame includes a filename key.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input HTMLs processed per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether frames are emitted incrementally as they are rendered.")

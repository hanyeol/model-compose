from __future__ import annotations

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from ...common import CommonActionConfig

class ImageDrawingActionMethod(str, Enum):
    POINT           = "point"
    LINE            = "line"
    ARC             = "arc"
    CHORD           = "chord"
    PIESLICE        = "pieslice"
    ELLIPSE         = "ellipse"
    CIRCLE          = "circle"
    RECTANGLE       = "rectangle"
    POLYGON         = "polygon"
    REGULAR_POLYGON = "regular-polygon"
    TEXT            = "text"
    MULTILINE_TEXT  = "multiline-text"
    BITMAP          = "bitmap"

class LineJoint(str, Enum):
    CURVE = "curve"

class TextAlign(str, Enum):
    LEFT   = "left"
    CENTER = "center"
    RIGHT  = "right"

Point = Tuple[Union[float, str], Union[float, str]]

class FontConfig(BaseModel):
    path: Optional[str] = Field(default=None, description="Path to a TrueType font file. Falls back to Pillow's default font when omitted.")
    size: Optional[Union[int, str]] = Field(default=None, description="Font size in pixels.")
    index: Union[int, str] = Field(default=0, description="Face index when the font file contains multiple faces.")
    encoding: str = Field(default="unic", description="Font encoding passed to Pillow's ImageFont.")

class CommonImageDrawingActionConfig(CommonActionConfig):
    method: ImageDrawingActionMethod = Field(..., description="Drawing operation this action performs.")
    image: Union[str, List[str]] = Field(..., description="Base image or list of images.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input images processed per batch.")

class ImageDrawingPointActionConfig(CommonImageDrawingActionConfig):
    method: Literal[ImageDrawingActionMethod.POINT]
    points: Union[List[Point], str] = Field(..., description="Points to draw as pixels.")
    fill: Optional[Union[str, Tuple[int, int, int, int], List[int]]] = Field(default=None, description="Pixel color.")

class ImageDrawingLineActionConfig(CommonImageDrawingActionConfig):
    method: Literal[ImageDrawingActionMethod.LINE]
    points: Union[List[Point], str] = Field(..., description="Vertex points connected in order.")
    fill: Optional[Union[str, Tuple[int, int, int, int], List[int]]] = Field(default=None, description="Line color.")
    line_width: Union[int, str] = Field(default=1, description="Line width in pixels.")
    joint: Optional[Union[LineJoint, str]] = Field(default=None, description="Segment joint style; 'curve' rounds corners.")

class ImageDrawingArcActionConfig(CommonImageDrawingActionConfig):
    method: Literal[ImageDrawingActionMethod.ARC]
    x: Union[float, str] = Field(..., description="X coordinate of the bounding box's top-left corner, in pixels.")
    y: Union[float, str] = Field(..., description="Y coordinate of the bounding box's top-left corner, in pixels.")
    width: Union[float, str] = Field(..., description="Bounding box width in pixels.")
    height: Union[float, str] = Field(..., description="Bounding box height in pixels.")
    start: Union[float, str] = Field(..., description="Starting angle in degrees, measured clockwise from 3 o'clock.")
    end: Union[float, str] = Field(..., description="Ending angle in degrees, measured clockwise from 3 o'clock.")
    fill: Optional[Union[str, Tuple[int, int, int, int], List[int]]] = Field(default=None, description="Arc color.")
    line_width: Union[int, str] = Field(default=1, description="Arc line width in pixels.")

class ImageDrawingChordActionConfig(CommonImageDrawingActionConfig):
    method: Literal[ImageDrawingActionMethod.CHORD]
    x: Union[float, str] = Field(..., description="X coordinate of the bounding box's top-left corner, in pixels.")
    y: Union[float, str] = Field(..., description="Y coordinate of the bounding box's top-left corner, in pixels.")
    width: Union[float, str] = Field(..., description="Bounding box width in pixels.")
    height: Union[float, str] = Field(..., description="Bounding box height in pixels.")
    start: Union[float, str] = Field(..., description="Starting angle in degrees, clockwise from 3 o'clock.")
    end: Union[float, str] = Field(..., description="Ending angle in degrees, clockwise from 3 o'clock.")
    fill: Optional[Union[str, Tuple[int, int, int, int], List[int]]] = Field(default=None, description="Interior fill color.")
    outline: Optional[Union[str, Tuple[int, int, int, int], List[int]]] = Field(default=None, description="Outline color.")
    line_width: Union[int, str] = Field(default=1, description="Outline width in pixels.")

class ImageDrawingPieSliceActionConfig(CommonImageDrawingActionConfig):
    method: Literal[ImageDrawingActionMethod.PIESLICE]
    x: Union[float, str] = Field(..., description="X coordinate of the bounding box's top-left corner, in pixels.")
    y: Union[float, str] = Field(..., description="Y coordinate of the bounding box's top-left corner, in pixels.")
    width: Union[float, str] = Field(..., description="Bounding box width in pixels.")
    height: Union[float, str] = Field(..., description="Bounding box height in pixels.")
    start: Union[float, str] = Field(..., description="Starting angle in degrees, clockwise from 3 o'clock.")
    end: Union[float, str] = Field(..., description="Ending angle in degrees, clockwise from 3 o'clock.")
    fill: Optional[Union[str, Tuple[int, int, int, int], List[int]]] = Field(default=None, description="Interior fill color.")
    outline: Optional[Union[str, Tuple[int, int, int, int], List[int]]] = Field(default=None, description="Outline color.")
    line_width: Union[int, str] = Field(default=1, description="Outline width in pixels.")

class ImageDrawingEllipseActionConfig(CommonImageDrawingActionConfig):
    method: Literal[ImageDrawingActionMethod.ELLIPSE]
    x: Union[float, str] = Field(..., description="X coordinate of the bounding box's top-left corner, in pixels.")
    y: Union[float, str] = Field(..., description="Y coordinate of the bounding box's top-left corner, in pixels.")
    width: Union[float, str] = Field(..., description="Bounding box width in pixels.")
    height: Union[float, str] = Field(..., description="Bounding box height in pixels.")
    fill: Optional[Union[str, Tuple[int, int, int, int], List[int]]] = Field(default=None, description="Interior fill color.")
    outline: Optional[Union[str, Tuple[int, int, int, int], List[int]]] = Field(default=None, description="Outline color.")
    line_width: Union[int, str] = Field(default=1, description="Outline width in pixels.")

class ImageDrawingCircleActionConfig(CommonImageDrawingActionConfig):
    method: Literal[ImageDrawingActionMethod.CIRCLE]
    x: Union[float, str] = Field(..., description="X coordinate of the circle's center, in pixels.")
    y: Union[float, str] = Field(..., description="Y coordinate of the circle's center, in pixels.")
    radius: Union[float, str] = Field(..., description="Circle radius in pixels.")
    fill: Optional[Union[str, Tuple[int, int, int, int], List[int]]] = Field(default=None, description="Interior fill color.")
    outline: Optional[Union[str, Tuple[int, int, int, int], List[int]]] = Field(default=None, description="Outline color.")
    line_width: Union[int, str] = Field(default=1, description="Outline width in pixels.")

class ImageDrawingRectangleActionConfig(CommonImageDrawingActionConfig):
    method: Literal[ImageDrawingActionMethod.RECTANGLE]
    x: Union[float, str] = Field(..., description="X coordinate of the rectangle's top-left corner, in pixels.")
    y: Union[float, str] = Field(..., description="Y coordinate of the rectangle's top-left corner, in pixels.")
    width: Union[float, str] = Field(..., description="Rectangle width in pixels.")
    height: Union[float, str] = Field(..., description="Rectangle height in pixels.")
    radius: Optional[Union[float, str]] = Field(default=None, description="Corner radius in pixels; when set the rectangle is drawn with rounded corners.")
    fill: Optional[Union[str, Tuple[int, int, int, int], List[int]]] = Field(default=None, description="Interior fill color.")
    outline: Optional[Union[str, Tuple[int, int, int, int], List[int]]] = Field(default=None, description="Outline color.")
    line_width: Union[int, str] = Field(default=1, description="Outline width in pixels.")
    corners: Optional[Union[Tuple[bool, bool, bool, bool], List[bool], str]] = Field(default=None, description="Per-corner rounding flags in order (top-left, top-right, bottom-right, bottom-left); only applied when 'radius' is set.")

class ImageDrawingPolygonActionConfig(CommonImageDrawingActionConfig):
    method: Literal[ImageDrawingActionMethod.POLYGON]
    points: Union[List[Point], str] = Field(..., description="Polygon vertex points.")
    fill: Optional[Union[str, Tuple[int, int, int, int], List[int]]] = Field(default=None, description="Interior fill color.")
    outline: Optional[Union[str, Tuple[int, int, int, int], List[int]]] = Field(default=None, description="Outline color.")
    line_width: Union[int, str] = Field(default=1, description="Outline width in pixels.")

class ImageDrawingRegularPolygonActionConfig(CommonImageDrawingActionConfig):
    method: Literal[ImageDrawingActionMethod.REGULAR_POLYGON]
    x: Union[float, str] = Field(..., description="X coordinate of the inscribing circle's center, in pixels.")
    y: Union[float, str] = Field(..., description="Y coordinate of the inscribing circle's center, in pixels.")
    radius: Union[float, str] = Field(..., description="Radius of the inscribing circle in pixels.")
    sides: Union[int, str] = Field(..., description="Number of polygon sides.")
    rotation: Union[float, str] = Field(default=0, description="Polygon rotation in degrees.")
    fill: Optional[Union[str, Tuple[int, int, int, int], List[int]]] = Field(default=None, description="Interior fill color.")
    outline: Optional[Union[str, Tuple[int, int, int, int], List[int]]] = Field(default=None, description="Outline color.")
    line_width: Union[int, str] = Field(default=1, description="Outline width in pixels.")

class ImageDrawingTextActionConfig(CommonImageDrawingActionConfig):
    method: Literal[ImageDrawingActionMethod.TEXT]
    x: Union[float, str] = Field(..., description="X coordinate of the text anchor point, in pixels.")
    y: Union[float, str] = Field(..., description="Y coordinate of the text anchor point, in pixels.")
    text: str = Field(..., description="Text to render.")
    fill: Optional[Union[str, Tuple[int, int, int, int], List[int]]] = Field(default=None, description="Text color.")
    font: Optional[FontConfig] = Field(default=None, description="Font settings.")
    anchor: Optional[str] = Field(default=None, description="Two-character text anchor code (e.g. 'la', 'mm').")
    spacing: Union[int, str] = Field(default=4, description="Line spacing in pixels for embedded newlines.")
    align: Union[TextAlign, str] = Field(default=TextAlign.LEFT, description="Horizontal alignment for embedded newlines.")
    stroke_width: Union[int, str] = Field(default=0, description="Text stroke width in pixels.")
    stroke_fill: Optional[Union[str, Tuple[int, int, int, int], List[int]]] = Field(default=None, description="Text stroke color.")

class ImageDrawingMultilineTextActionConfig(CommonImageDrawingActionConfig):
    method: Literal[ImageDrawingActionMethod.MULTILINE_TEXT]
    x: Union[float, str] = Field(..., description="X coordinate of the text block anchor point, in pixels.")
    y: Union[float, str] = Field(..., description="Y coordinate of the text block anchor point, in pixels.")
    text: str = Field(..., description="Multi-line text to render; separate lines with '\\n'.")
    fill: Optional[Union[str, Tuple[int, int, int, int], List[int]]] = Field(default=None, description="Text color.")
    font: Optional[FontConfig] = Field(default=None, description="Font settings.")
    anchor: Optional[str] = Field(default=None, description="Two-character text anchor code (e.g. 'la', 'mm').")
    spacing: Union[int, str] = Field(default=4, description="Line spacing in pixels.")
    align: Union[TextAlign, str] = Field(default=TextAlign.LEFT, description="Horizontal alignment across lines.")
    stroke_width: Union[int, str] = Field(default=0, description="Text stroke width in pixels.")
    stroke_fill: Optional[Union[str, Tuple[int, int, int, int], List[int]]] = Field(default=None, description="Text stroke color.")

class ImageDrawingBitmapActionConfig(CommonImageDrawingActionConfig):
    method: Literal[ImageDrawingActionMethod.BITMAP]
    x: Union[float, str] = Field(..., description="X coordinate where the bitmap's top-left corner is stamped, in pixels.")
    y: Union[float, str] = Field(..., description="Y coordinate where the bitmap's top-left corner is stamped, in pixels.")
    bitmap: str = Field(..., description="Bitmap image; non-zero pixels form the mask.")
    fill: Optional[Union[str, Tuple[int, int, int, int], List[int]]] = Field(default=None, description="Color applied through the bitmap mask.")

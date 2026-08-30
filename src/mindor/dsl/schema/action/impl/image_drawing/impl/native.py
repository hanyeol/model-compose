from typing import Union, Annotated
from pydantic import Field
from .common import (
    ImageDrawingPointActionConfig,
    ImageDrawingLineActionConfig,
    ImageDrawingArcActionConfig,
    ImageDrawingChordActionConfig,
    ImageDrawingPieSliceActionConfig,
    ImageDrawingEllipseActionConfig,
    ImageDrawingCircleActionConfig,
    ImageDrawingRectangleActionConfig,
    ImageDrawingPolygonActionConfig,
    ImageDrawingRegularPolygonActionConfig,
    ImageDrawingTextActionConfig,
    ImageDrawingMultilineTextActionConfig,
    ImageDrawingBitmapActionConfig,
)

NativeImageDrawingActionConfig = Annotated[
    Union[
        ImageDrawingPointActionConfig,
        ImageDrawingLineActionConfig,
        ImageDrawingArcActionConfig,
        ImageDrawingChordActionConfig,
        ImageDrawingPieSliceActionConfig,
        ImageDrawingEllipseActionConfig,
        ImageDrawingCircleActionConfig,
        ImageDrawingRectangleActionConfig,
        ImageDrawingPolygonActionConfig,
        ImageDrawingRegularPolygonActionConfig,
        ImageDrawingTextActionConfig,
        ImageDrawingMultilineTextActionConfig,
        ImageDrawingBitmapActionConfig,
    ],
    Field(discriminator="method")
]

from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Callable, List
from mindor.dsl.schema.action import BlendMethod
import math

if TYPE_CHECKING:
    from torch import Tensor

def blend_tiles(
    image: "Tensor",
    predict: Callable[["Tensor"], "Tensor"],
    tile: int,
    overlap: int,
    method: BlendMethod,
) -> "Tensor":
    """Run `predict` on each tile then merge with a separable 2-D window.

    The output accumulator stays on CPU float32 so large images don't pin GPU
    memory between tiles; `predict` returns a CPU float32 tensor (see driver's
    tile predictor).
    """
    import torch

    batch, channels, height, width = image.shape

    xs = _tile_starts(width, tile, overlap)
    ys = _tile_starts(height, tile, overlap)

    output = torch.empty_like(image, dtype=torch.float32, device="cpu")

    for b in range(batch):
        accum = torch.zeros((1, channels, height, width), dtype=torch.float32)
        denom = torch.zeros((1, 1, height, width), dtype=torch.float32)

        for iy, y in enumerate(ys):
            wy = _axis_weight(ys, iy, height, tile, method)

            for ix, x in enumerate(xs):
                wx = _axis_weight(xs, ix, width, tile, method)
                patch = image[b:b+1, :, y:y+tile, x:x+tile]
                result = predict(patch)

                weight = wy[:, None] * wx[None, :]
                h, w = result.shape[-2:]
                accum[..., y:y+h, x:x+w].add_(result * weight)
                denom[..., y:y+h, x:x+w].add_(weight)

        output[b:b+1] = accum / denom

    return output

def _tile_starts(length: int, tile: int, overlap: int) -> List[int]:
    if length <= tile:
        return [ 0 ]

    positions = list(range(0, length - tile + 1, tile - overlap))

    if positions[-1] != length - tile:
        positions.append(length - tile)

    return positions

def _axis_weight(positions: List[int], index: int, length: int, tile: int, method: BlendMethod) -> "Tensor":
    import torch

    pos = positions[index]
    size = min(tile, length - pos)
    weight = torch.ones(size, dtype=torch.float32)

    if method == BlendMethod.AVERAGE:
        return weight

    for edge, overlap in [
        ( "left",  positions[index - 1] + tile - pos if index else 0 ),
        ( "right", pos + size - positions[index + 1] if index + 1 < len(positions) else 0 ),
    ]:
        if overlap <= 0:
            continue

        t = torch.arange(1, overlap + 1, dtype=torch.float32) / (overlap + 1)

        if method == BlendMethod.COSINE:
            ramp = 0.5 - 0.5 * torch.cos(math.pi * t)
        elif method == BlendMethod.GAUSSIAN:
            ramp = torch.exp(-0.5 * ((1 - t) / 0.35) ** 2)
        elif method == BlendMethod.LINEAR:
            ramp = t
        else:
            raise ValueError(f"Unknown blend method: {method}")

        if edge == "left":
            weight[:overlap] *= ramp
        else:
            weight[-overlap:] *= ramp.flip(0)

    return weight

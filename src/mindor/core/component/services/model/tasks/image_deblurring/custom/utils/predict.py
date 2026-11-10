from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Callable, Optional
from contextlib import nullcontext

if TYPE_CHECKING:
    from torch import Tensor
    import torch

# Co-prime stride that separates the per-augmentation seeds from the user seed.
# Large prime avoids collisions between neighboring `(seed, mode)` pairs.
_SEED_STRIDE = 1000003
_SEED_MODULO = 2**63 - 1

def predict_tile(
    model: torch.nn.Module,
    image: Tensor,
    device: torch.device,
    augmented: bool,
    seed: Optional[int],
    interrupt: Callable[[], None],
) -> Tensor:
    """Run the model on one tile, optionally averaging 8 D4 augmentations.

    Keeps HI-Diff's random prior deterministic by forking the generator state
    before each augmentation (so the augmentation sweep doesn't mutate the
    caller's seed). Weights stay in float32 throughout — fp16 produces NaNs
    on both models.
    """
    import torch

    image = image.to(device=device, dtype=torch.float32)
    accum = torch.zeros_like(image, device="cpu")
    passes = 8 if augmented else 1

    if device.type == "cuda":
        device_index = device.index if device.index is not None else torch.cuda.current_device()
    else:
        device_index = None

    cuda_context = torch.cuda.device(device) if device_index is not None else nullcontext()
    fork_devices = [ device_index ] if device_index is not None else []

    for mode in range(passes):
        interrupt()

        transformed = _apply_d4(image, mode).contiguous()
        h, w = transformed.shape[-2:]

        with cuda_context, torch.random.fork_rng(devices=fork_devices), torch.autocast(device.type, enabled=False):
            if seed is not None:
                local_seed = (int(seed) + mode * _SEED_STRIDE) % _SEED_MODULO
                torch.random.default_generator.manual_seed(local_seed)

                if device_index is not None:
                    torch.cuda.default_generators[device_index].manual_seed(local_seed)

            output = model(_pad_multiple8(transformed))[..., :h, :w].clamp(0, 1)

        if not torch.isfinite(output).all().item():
            raise RuntimeError("Non-finite model output; try a smaller tile. No image returned.")

        accum.add_(_apply_d4(output, mode, inverse=True).to("cpu", torch.float32))

        del transformed, output

    return accum / passes

def _pad_multiple8(image: Tensor) -> Tensor:
    """Reflect-pad spatial dims up to the nearest multiple of 8 (min 8)."""
    import torch

    h, w = image.shape[-2:]
    target_h = max(8, (h + 7) // 8 * 8)
    target_w = max(8, (w + 7) // 8 * 8)

    for axis, length, target in [ (-2, h, target_h), (-1, w, target_w) ]:
        if length == target:
            continue

        indices = torch.arange(target, device=image.device)

        if length == 1:
            indices.zero_()
        else:
            period = 2 * (length - 1)
            indices = indices.remainder(period)
            indices = torch.minimum(indices, period - indices)

        image = image.index_select(axis, indices)

    return image.contiguous()

def _apply_d4(image: Tensor, mode: int, inverse: bool = False) -> Tensor:
    """D4 symmetry group: `mode` ∈ [0,8) encodes rotation × flip."""
    import torch

    rotation = mode // 2
    flipped = mode % 2

    if inverse:
        image = torch.rot90(image, -rotation, (-2, -1))

        return image.flip(-2) if flipped else image

    if flipped:
        image = image.flip(-2)

    return torch.rot90(image, rotation, (-2, -1))


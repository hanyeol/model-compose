from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple

if TYPE_CHECKING:
    import numpy as np
    import torch

def encode_waveform_to_pcm16(samples: Union[torch.Tensor, np.typing.ArrayLike]) -> Tuple[bytes, int]:
    """Encode a mono or stereo waveform to little-endian 16-bit PCM bytes.

    Accepts numpy arrays and torch tensors (converted via cpu().numpy()).
    Floating-point inputs are clipped to [-1.0, 1.0] then scaled to int16.
    For 2-D inputs, a (channels, samples) layout is auto-detected when
    channels <= 8 and channels < samples, and transposed to (samples, channels).

    Returns (pcm_bytes, channels).
    """
    import numpy as np

    if hasattr(samples, "detach"):
        samples = samples.detach()
    if hasattr(samples, "cpu"):
        samples = samples.cpu()
    if hasattr(samples, "numpy"):
        samples = samples.numpy()

    array = np.asarray(samples)
    if array.ndim == 1:
        channels = 1
    elif array.ndim == 2:
        if array.shape[0] <= 8 and array.shape[0] < array.shape[1]:
            array = array.T
        channels = int(array.shape[1])
    else:
        raise ValueError(f"Expected mono or stereo audio samples, got shape {array.shape}")

    if np.issubdtype(array.dtype, np.floating):
        array = np.clip(array, -1.0, 1.0)
        array = (array * 32767.0).astype("<i2")
    elif array.dtype != np.int16:
        array = array.astype("<i2")

    return array.tobytes(), channels

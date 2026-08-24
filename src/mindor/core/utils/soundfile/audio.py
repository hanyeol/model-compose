from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

def load_pcm_samples(path: str, sample_rate: int) -> np.ndarray:
    """Load an audio file as mono float32 PCM samples at ``sample_rate``.

    Uses soundfile for decoding and librosa for resampling. Returns a
    C-contiguous 1-D array in [-1, 1].
    """
    import soundfile as sf
    import numpy as np

    data, source_sample_rate = sf.read(path, dtype="float32", always_2d=False)

    if data.ndim > 1:
        data = data.mean(axis=1)

    if source_sample_rate != sample_rate:
        import librosa

        data = librosa.resample(data, orig_sr=source_sample_rate, target_sr=sample_rate)

    return np.ascontiguousarray(data, dtype=np.float32)

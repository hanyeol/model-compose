from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    import numpy as np

def load_pcm_samples(path: str, sample_rate: Optional[int] = None) -> Tuple[np.ndarray, int]:
    """Load an audio file as mono float32 PCM samples.

    Returns a ``(samples, sample_rate)`` pair. Samples are a C-contiguous 1-D
    array in [-1, 1] and downmixed to mono. When ``sample_rate`` is provided
    and differs from the file's native rate, librosa resamples the audio to it;
    the returned rate then matches the requested value. When ``sample_rate`` is
    None, the file's native rate is preserved and returned.
    """
    import soundfile as sf
    import numpy as np

    data, source_sample_rate = sf.read(path, dtype="float32", always_2d=False)

    if data.ndim > 1:
        data = data.mean(axis=1)

    if sample_rate is not None and source_sample_rate != sample_rate:
        import librosa

        data = librosa.resample(data, orig_sr=source_sample_rate, target_sr=sample_rate)
        source_sample_rate = sample_rate

    return np.ascontiguousarray(data, dtype=np.float32), int(source_sample_rate)

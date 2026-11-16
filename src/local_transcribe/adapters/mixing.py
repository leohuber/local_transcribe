import numpy as np
from numpy.typing import NDArray

from local_transcribe.domain.recording import RecordingError


def mix_pcm16(first: NDArray[np.float32], second: NDArray[np.float32]) -> bytes:
    if first.ndim != 1 or first.shape != second.shape:
        raise RecordingError("The input streams could not be aligned for mixing.")
    if not np.isfinite(first).all() or not np.isfinite(second).all():
        raise RecordingError("An input stream contains invalid audio samples.")
    mixed = (first + second) * 0.5
    pcm = np.clip(np.rint(mixed * 32768), -32768, 32767)
    return pcm.astype("<i2").tobytes()

import math

import numpy as np
from numpy.typing import NDArray

from local_transcribe.domain.recording import InputLevel, RecordingError


class InputLevels:
    def __init__(self, device_ids: tuple[int, int]) -> None:
        self._snapshot = (
            InputLevel(device_ids[0], 0.0),
            InputLevel(device_ids[1], 0.0),
        )

    def update(self, index: int, samples: NDArray[np.float32]) -> None:
        if not samples.size:
            raise RecordingError("An input stream provided an empty audio block.")
        rms = math.sqrt(float(np.mean(np.square(samples, dtype=np.float64))))
        if not math.isfinite(rms):
            raise RecordingError("An input stream contains invalid audio samples.")
        previous = self._snapshot
        level = InputLevel(previous[index].device_id, rms)
        if index == 0:
            self._snapshot = (level, previous[1])
        elif index == 1:
            self._snapshot = (previous[0], level)
        else:
            raise IndexError("input index must be 0 or 1")

    def snapshot(self) -> tuple[InputLevel, InputLevel]:
        return self._snapshot

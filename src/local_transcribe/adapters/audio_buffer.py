import math
import queue
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from local_transcribe.adapters.capture import BLOCK_FRAMES, CaptureConfig

MAX_PENDING_BLOCKS = 64


@dataclass(frozen=True, slots=True)
class AudioBlock:
    samples: NDArray[np.float32]
    adc_time: float
    callback_time: float
    host_time: float


class AudioBuffer:
    def __init__(
        self,
        config: CaptureConfig,
        *,
        max_blocks: int = MAX_PENDING_BLOCKS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_blocks < 1:
            raise ValueError("max_blocks must be positive")
        self.config = config
        self._blocks: queue.Queue[AudioBlock] = queue.Queue(maxsize=max_blocks)
        self._clock = clock
        self._error: str | None = None
        self._finished = False

    def callback(self, data: Any, frames: int, timing: Any, status: Any) -> None:
        if self._error is not None:
            return
        try:
            host_time = self._clock()
            if status:
                self._error = (
                    f"Input device {self.config.device.id} lost audio: {status}"
                )
                return
            if frames < 1 or frames > BLOCK_FRAMES:
                raise ValueError(f"invalid callback size {frames}")
            if data.shape != (frames, self.config.channels):
                raise ValueError("invalid input channel or frame count")
            adc_time = float(timing.inputBufferAdcTime)
            callback_time = float(timing.currentTime)
            if not all(map(math.isfinite, (host_time, adc_time, callback_time))):
                raise ValueError("missing or invalid audio timestamps")
            if self._blocks.full():
                self._error = f"Input device {self.config.device.id} buffer overflow"
                return
            samples = np.array(data, dtype=np.float32, copy=True)
            self._blocks.put_nowait(
                AudioBlock(samples, adc_time, callback_time, host_time)
            )
        except queue.Full:
            self._error = f"Input device {self.config.device.id} buffer overflow"
        except (AttributeError, MemoryError, TypeError, ValueError) as exc:
            self._error = f"Input device {self.config.device.id} callback failed: {exc}"

    def finished(self) -> None:
        self._finished = True

    @property
    def has_finished(self) -> bool:
        return self._finished

    @property
    def error(self) -> str | None:
        return self._error

    @property
    def queued_blocks(self) -> int:
        return self._blocks.qsize()

    def take(self, timeout: float = 0.0) -> AudioBlock | None:
        try:
            return self._blocks.get(timeout=timeout)
        except queue.Empty:
            return None


def downmix(samples: NDArray[np.float32]) -> NDArray[np.float32]:
    return samples.mean(axis=1, dtype=np.float32)

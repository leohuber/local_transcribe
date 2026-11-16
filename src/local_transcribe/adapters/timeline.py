import math
from collections import deque

import numpy as np
import soxr
from numpy.typing import NDArray

from local_transcribe.adapters.audio_buffer import AudioBlock, downmix
from local_transcribe.adapters.capture import BLOCK_FRAMES, CaptureConfig
from local_transcribe.domain.recording import RecordingError

MAX_BUFFER_SECONDS = 2
MAX_CLOCK_DEVIATION = 0.03


class _InputClock:
    def __init__(self, config: CaptureConfig) -> None:
        self._config = config
        self._offsets: deque[float] = deque(maxlen=32)
        self._history: deque[tuple[int, float]] = deque(maxlen=512)
        self._frames = 0
        self._last_time: float | None = None
        self._last_frames = 0
        self.rate = float(config.sample_rate)

    def observe(self, block: AudioBlock) -> float:
        times = (block.adc_time, block.callback_time, block.host_time)
        if not all(map(math.isfinite, times)) or block.adc_time > block.callback_time:
            raise RecordingError(
                f"Input device {self._config.device.id} has unusable audio timestamps."
            )
        self._offsets.append(block.host_time - block.callback_time)
        adc_time = block.adc_time + min(self._offsets)
        if self._last_time is not None:
            elapsed = adc_time - self._last_time
            expected = self._last_frames / self._config.sample_rate
            if elapsed <= 0 or abs(elapsed - expected) > max(0.005, expected * 0.25):
                raise RecordingError(
                    f"Input device {self._config.device.id} has discontinuous audio timestamps."
                )

        self._history.append((self._frames, adc_time))
        while len(self._history) > 2 and adc_time - self._history[0][1] > 5:
            self._history.popleft()
        first_frame, first_time = self._history[0]
        elapsed = adc_time - first_time
        if elapsed >= 0.1:
            observed = (self._frames - first_frame) / elapsed
            relative_error = observed / self._config.sample_rate - 1
            if abs(relative_error) > MAX_CLOCK_DEVIATION and elapsed >= 1:
                raise RecordingError(
                    f"Input device {self._config.device.id} has an unusable capture clock."
                )
            if abs(relative_error) <= MAX_CLOCK_DEVIATION:
                self.rate += 0.2 * (observed - self.rate)

        self._last_time = adc_time
        self._last_frames = len(block.samples)
        self._frames += self._last_frames
        return adc_time


class _Samples:
    def __init__(self, max_frames: int) -> None:
        self._chunks: deque[NDArray[np.float32]] = deque()
        self._max_frames = max_frames
        self.frames = 0

    def append(self, chunk: NDArray[np.float32]) -> None:
        if self.frames + len(chunk) > self._max_frames:
            raise RecordingError("Input synchronization buffer overflow.")
        if len(chunk):
            self._chunks.append(chunk)
            self.frames += len(chunk)

    def take(self, frames: int) -> NDArray[np.float32]:
        chunks: list[NDArray[np.float32]] = []
        remaining = frames
        while remaining:
            chunk = self._chunks.popleft()
            used = min(remaining, len(chunk))
            chunks.append(chunk[:used])
            if used < len(chunk):
                self._chunks.appendleft(chunk[used:])
            remaining -= used
        self.frames -= frames
        return chunks[0] if len(chunks) == 1 else np.concatenate(chunks)


class _InputTimeline:
    def __init__(self, config: CaptureConfig, output_rate: int) -> None:
        self.config = config
        self.clock = _InputClock(config)
        self.samples = _Samples(output_rate * MAX_BUFFER_SECONDS)
        self._output_rate = output_rate
        self._resampler = soxr.ResampleStream(
            config.sample_rate * 1.05, output_rate, 1, dtype="float32", vr=True
        )
        self._resampler.set_io_ratio(config.sample_rate, output_rate)
        self._started = False
        self._position = 0.0
        self._finished = False

    def push(
        self,
        block: AudioBlock,
        timestamp: float,
        common_start: float,
        queue_correction: float,
    ) -> None:
        samples = block.samples
        if not self._started:
            skip = max(0, round((common_start - timestamp) * self.clock.rate))
            if skip >= len(samples):
                return
            samples = samples[skip:]
            timestamp += skip / self.clock.rate
            self._position = (timestamp - common_start) * self._output_rate
            self._started = True

        expected_position = (timestamp - common_start) * self._output_rate
        phase_error = (self._position - expected_position) / self._output_rate
        phase_correction = max(-0.005, min(0.005, phase_error))
        input_rate = self.clock.rate * (1 + phase_correction + queue_correction)
        output_frames = max(1, round(len(samples) * self._output_rate / input_rate))
        self._resampler.set_io_ratio(
            input_rate, self._output_rate, slew_len=output_frames
        )
        self.samples.append(self._resampler.resample_chunk(downmix(samples)))
        self._position += len(samples) * self._output_rate / input_rate

    def finish(self) -> None:
        if self._started and not self._finished:
            self.samples.append(
                self._resampler.resample_chunk(np.empty(0, dtype=np.float32), last=True)
            )
        self._finished = True


class SynchronizedInputs:
    def __init__(
        self,
        configs: tuple[CaptureConfig, CaptureConfig],
        first_blocks: tuple[AudioBlock, AudioBlock],
    ) -> None:
        self.output_rate = configs[0].sample_rate
        self._inputs = (
            _InputTimeline(configs[0], self.output_rate),
            _InputTimeline(configs[1], self.output_rate),
        )
        timestamps = tuple(
            stream.clock.observe(block)
            for stream, block in zip(self._inputs, first_blocks, strict=True)
        )
        self.start_time = max(timestamps)
        for stream, block, timestamp in zip(
            self._inputs, first_blocks, timestamps, strict=True
        ):
            stream.push(block, timestamp, self.start_time, 0.0)

    def push(
        self,
        index: int,
        block: AudioBlock,
        queued_blocks: tuple[int, int] = (0, 0),
    ) -> None:
        stream = self._inputs[index]
        other_index = 1 - index
        other = self._inputs[other_index]
        own_backlog = (
            stream.samples.frames / self.output_rate
            + queued_blocks[index] * BLOCK_FRAMES / stream.config.sample_rate
        )
        other_backlog = (
            other.samples.frames / self.output_rate
            + queued_blocks[other_index] * BLOCK_FRAMES / other.config.sample_rate
        )
        queue_correction = max(
            -0.0002, min(0.0002, (own_backlog - other_backlog) * 0.0001)
        )
        timestamp = stream.clock.observe(block)
        stream.push(block, timestamp, self.start_time, queue_correction)

    def take(
        self, max_frames: int = BLOCK_FRAMES
    ) -> tuple[NDArray[np.float32], NDArray[np.float32]] | None:
        frames = min(max_frames, *(stream.samples.frames for stream in self._inputs))
        if frames == 0:
            return None
        return self._inputs[0].samples.take(frames), self._inputs[1].samples.take(
            frames
        )

    def finish(self) -> None:
        for stream in self._inputs:
            stream.finish()

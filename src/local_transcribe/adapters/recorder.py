import threading
import time
import wave
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO

from local_transcribe.adapters.audio_buffer import AudioBlock, AudioBuffer
from local_transcribe.adapters.capture import CaptureConfig, SoundDeviceCapture
from local_transcribe.adapters.levels import InputLevels
from local_transcribe.adapters.mixing import mix_pcm16
from local_transcribe.adapters.recording_files import (
    create_recording_file,
    find_checkout,
)
from local_transcribe.adapters.timeline import SynchronizedInputs
from local_transcribe.domain.recording import (
    InputLevel,
    RecordingError,
    RecordingRequest,
    RecordingResult,
)

MAX_WAV_DATA_BYTES = (1 << 32) - 1 - 36
INPUT_TIMEOUT_SECONDS = 3.0
POLL_SECONDS = 0.01


class _CapturePump:
    def __init__(
        self,
        configs: tuple[CaptureConfig, CaptureConfig],
        buffers: tuple[AudioBuffer, AudioBuffer],
        levels: InputLevels,
        output: wave.Wave_write,
    ) -> None:
        self._configs = configs
        self._buffers = buffers
        self._levels = levels
        self._output = output
        self._first: list[AudioBlock | None] = [None, None]
        self._timeline: SynchronizedInputs | None = None
        self._written = 0

    def check_buffers(self) -> None:
        for buffer in self._buffers:
            if buffer.error is not None:
                raise RecordingError(buffer.error)

    def consume(self) -> tuple[int, ...]:
        self.check_buffers()
        consumed: list[int] = []
        for index, buffer in enumerate(self._buffers):
            if self._timeline is None and self._first[index] is not None:
                continue
            block = buffer.take()
            if block is None:
                continue
            consumed.append(index)
            self._levels.update(index, block.samples)
            if self._timeline is None:
                self._first[index] = block
            else:
                queued = (
                    self._buffers[0].queued_blocks,
                    self._buffers[1].queued_blocks,
                )
                self._timeline.push(index, block, queued)

        if self._timeline is None and all(block is not None for block in self._first):
            first, second = self._first
            assert first is not None and second is not None
            self._timeline = SynchronizedInputs(self._configs, (first, second))
        self._write_available()
        return tuple(consumed)

    def _write_available(self) -> None:
        if self._timeline is None:
            return
        while (aligned := self._timeline.take()) is not None:
            pcm = mix_pcm16(*aligned)
            if self._written + len(pcm) > MAX_WAV_DATA_BYTES:
                raise RecordingError("The WAV file size limit was reached.")
            self._output.writeframesraw(pcm)
            self._written += len(pcm)

    def finish(self) -> None:
        while self.consume():
            pass
        self.check_buffers()
        if self._timeline is not None:
            self._timeline.finish()
            self._write_available()


class SoundDeviceRecorder:
    def __init__(
        self,
        capture: SoundDeviceCapture,
        *,
        checkout: Callable[[], Path] = find_checkout,
        create_file: Callable[[Path], tuple[Path, BinaryIO]] = create_recording_file,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._capture = capture
        self._checkout = checkout
        self._create_file = create_file
        self._clock = clock
        self._stop = threading.Event()
        self._levels: InputLevels | None = None

    def latest_levels(self) -> tuple[InputLevel, ...]:
        levels = self._levels
        return levels.snapshot() if levels is not None else ()

    def stop(self) -> None:
        self._stop.set()

    def record(self, request: RecordingRequest) -> RecordingResult:
        path: Path | None = None
        try:
            configs = (
                self._capture.configure(request.first_device_id),
                self._capture.configure(request.second_device_id),
            )
            self._levels = InputLevels(
                (request.first_device_id, request.second_device_id)
            )
            buffers = (
                AudioBuffer(configs[0], clock=self._clock),
                AudioBuffer(configs[1], clock=self._clock),
            )
            path, file = self._create_file(self._checkout())
            with file, wave.open(file, "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(configs[0].sample_rate)
                pump = _CapturePump(configs, buffers, self._levels, output)
                with self._capture.streams(
                    configs,
                    (buffers[0].callback, buffers[1].callback),
                    (buffers[0].finished, buffers[1].finished),
                ) as streams:
                    last_seen = [self._clock(), self._clock()]
                    try:
                        while not self._stop.is_set():
                            pump.check_buffers()
                            if not streams.active or any(
                                buffer.has_finished for buffer in buffers
                            ):
                                raise RecordingError(
                                    "An input stream terminated unexpectedly."
                                )
                            consumed = pump.consume()
                            now = self._clock()
                            for index in consumed:
                                last_seen[index] = now
                            if any(
                                now - seen > INPUT_TIMEOUT_SECONDS for seen in last_seen
                            ):
                                raise RecordingError(
                                    "Timed out waiting for an input stream."
                                )
                            if not consumed:
                                self._stop.wait(POLL_SECONDS)
                    except KeyboardInterrupt:
                        self.stop()
                pump.finish()
            return RecordingResult(path)
        except RecordingError as exc:
            if path is not None and exc.incomplete_path is None:
                raise RecordingError(str(exc), incomplete_path=path) from exc
            raise
        except KeyboardInterrupt as exc:
            raise RecordingError(
                "Recording was interrupted while starting or stopping.",
                incomplete_path=path,
            ) from exc
        except Exception as exc:
            raise RecordingError(
                f"Recording failed: {exc}", incomplete_path=path
            ) from exc
        finally:
            self._stop.clear()

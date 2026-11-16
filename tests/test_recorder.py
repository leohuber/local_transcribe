import tempfile
import threading
import unittest
import wave
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from itertools import count
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Self
from unittest.mock import patch

import numpy as np

from local_transcribe.adapters.capture import BLOCK_FRAMES, CaptureConfig
from local_transcribe.adapters.recorder import SoundDeviceRecorder
from local_transcribe.domain.recording import (
    InputDevice,
    RecordingError,
    RecordingRequest,
)


class FakeClock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value


class FakeStreams:
    def __init__(
        self,
        callbacks: tuple[Callable[..., None], Callable[..., None]],
        finished: tuple[Callable[[], None], Callable[[], None]],
        script: Callable[[FakeStreams], None],
    ) -> None:
        self.callbacks = callbacks
        self.finished_callbacks = finished
        self.script = script
        self.active = False
        self.closed = False

    def __enter__(self) -> Self:
        self.active = True
        self.script(self)
        return self

    def __exit__(self, *_: object) -> None:
        self.active = False
        self.closed = True
        for callback in self.finished_callbacks:
            callback()


class FakeCapture:
    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.script: Callable[[FakeStreams], None] = lambda _: None
        self.streams_created: list[FakeStreams] = []

    def configure(self, device_id: int) -> CaptureConfig:
        if device_id not in (2, 5):
            raise RecordingError("Device unavailable")
        return CaptureConfig(InputDevice(device_id, f"Device {device_id}", 1), 48000, 1)

    def streams(
        self,
        configs: tuple[CaptureConfig, CaptureConfig],
        callbacks: tuple[Callable[..., None], Callable[..., None]],
        finished: tuple[Callable[[], None], Callable[[], None]],
    ) -> FakeStreams:
        streams = FakeStreams(callbacks, finished, self.script)
        self.streams_created.append(streams)
        return streams

    def emit(
        self,
        streams: FakeStreams,
        count: int,
        *,
        stop: Callable[[], None] | None = None,
    ) -> None:
        for block_index in range(count):
            adc = 100.0 + block_index * BLOCK_FRAMES / 48000
            callback_time = adc + BLOCK_FRAMES / 48000
            self.clock.value = callback_time
            timing = SimpleNamespace(inputBufferAdcTime=adc, currentTime=callback_time)
            for index, value in enumerate((0.8, 0.2)):
                data = np.full((BLOCK_FRAMES, 1), value, dtype=np.float32)
                streams.callbacks[index](data, BLOCK_FRAMES, timing, None)
        if stop is not None:
            stop()


def fail_after_first_write() -> Callable[[wave.Wave_write, bytes], None]:
    original = wave.Wave_write.writeframesraw
    written = 0

    def write(output: wave.Wave_write, data: bytes) -> None:
        nonlocal written
        if written:
            raise OSError("disk full")
        original(output, data)
        written += 1

    return write


class RecorderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.clock = FakeClock()
        self.capture = FakeCapture(self.clock)
        self.recorder = SoundDeviceRecorder(
            self.capture, checkout=lambda: self.root, clock=self.clock
        )
        self.request = RecordingRequest(2, 5)

    def test_stop_drains_both_streams_and_finalizes_playable_wav(self) -> None:
        self.capture.script = lambda streams: self.capture.emit(
            streams, 8, stop=self.recorder.stop
        )
        result = self.recorder.record(self.request)
        self.assertTrue(self.capture.streams_created[0].closed)
        with wave.open(str(result.path), "rb") as audio:
            self.assertEqual(
                (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()),
                (1, 2, 48000),
            )
            self.assertAlmostEqual(audio.getnframes(), 8 * BLOCK_FRAMES, delta=4)
            samples = np.frombuffer(audio.readframes(audio.getnframes()), dtype="<i2")
        self.assertAlmostEqual(float(np.mean(samples[1000:-1000])), 16384, delta=10)
        levels = self.recorder.latest_levels()
        self.assertAlmostEqual(levels[0].rms, 0.8, places=5)
        self.assertAlmostEqual(levels[1].rms, 0.2, places=5)

    def test_writes_audio_while_recording_is_still_running(self) -> None:
        self.capture.script = partial(self.capture.emit, count=6)
        written = threading.Event()
        original = wave.Wave_write.writeframesraw

        def observe(output: wave.Wave_write, data: bytes) -> None:
            original(output, data)
            written.set()

        with (
            patch.object(wave.Wave_write, "writeframesraw", new=observe),
            ThreadPoolExecutor(max_workers=1) as executor,
        ):
            future = executor.submit(self.recorder.record, self.request)
            try:
                self.assertTrue(written.wait(timeout=2))
                self.assertFalse(future.done())
            finally:
                self.recorder.stop()
            result = future.result(timeout=2)
        with wave.open(str(result.path), "rb") as audio:
            self.assertGreater(audio.getnframes(), 0)

    def test_keyboard_interrupt_finalizes_and_closes_streams(self) -> None:
        self.capture.script = lambda streams: self.capture.emit(streams, 4)
        with patch.object(self.recorder._stop, "wait", side_effect=KeyboardInterrupt):
            result = self.recorder.record(self.request)
        self.assertTrue(self.capture.streams_created[0].closed)
        with wave.open(str(result.path), "rb") as audio:
            self.assertGreater(audio.getnframes(), 0)

    def test_queue_overflow_and_unexpected_termination_report_incomplete_file(
        self,
    ) -> None:
        for error in ("overflow", "termination"):
            with self.subTest(error=error):
                capture = FakeCapture(FakeClock())
                recorder = SoundDeviceRecorder(
                    capture, checkout=lambda: self.root, clock=capture.clock
                )
                if error == "overflow":
                    capture.script = partial(capture.emit, count=65)
                else:
                    capture.script = lambda streams: setattr(streams, "active", False)
                with self.assertRaises(RecordingError) as raised:
                    recorder.record(self.request)
                expected = "overflow" if error == "overflow" else "terminated"
                self.assertIn(expected, str(raised.exception).lower())
                self.assertIsNotNone(raised.exception.incomplete_path)
                self.assertTrue(raised.exception.incomplete_path.is_file())
                self.assertTrue(capture.streams_created[0].closed)

    def test_write_failure_and_wav_limit_report_incomplete_files(self) -> None:
        for failure in ("write", "limit"):
            with self.subTest(failure=failure):
                capture = FakeCapture(FakeClock())
                recorder = SoundDeviceRecorder(
                    capture, checkout=lambda: self.root, clock=capture.clock
                )
                capture.script = partial(capture.emit, count=3, stop=recorder.stop)
                if failure == "write":
                    failure_patch = patch.object(
                        wave.Wave_write, "writeframesraw", new=fail_after_first_write()
                    )
                else:
                    failure_patch = patch(
                        "local_transcribe.adapters.recorder.MAX_WAV_DATA_BYTES", 2000
                    )
                with failure_patch, self.assertRaises(RecordingError) as raised:
                    recorder.record(self.request)
                self.assertIsNotNone(raised.exception.incomplete_path)
                self.assertTrue(raised.exception.incomplete_path.is_file())
                self.assertTrue(capture.streams_created[0].closed)
                if failure == "limit":
                    self.assertIn("size limit", str(raised.exception))
                else:
                    self.assertIn("disk full", str(raised.exception))
                with wave.open(str(raised.exception.incomplete_path), "rb") as audio:
                    self.assertGreater(audio.getnframes(), 0)

    def test_stalled_stream_reports_timeout_and_closes(self) -> None:
        times = count(start=0, step=1)
        recorder = SoundDeviceRecorder(
            self.capture, checkout=lambda: self.root, clock=lambda: float(next(times))
        )
        with self.assertRaisesRegex(RecordingError, "Timed out") as raised:
            recorder.record(self.request)
        self.assertIsNotNone(raised.exception.incomplete_path)
        self.assertTrue(self.capture.streams_created[0].closed)

    def test_creation_failure_does_not_open_streams(self) -> None:
        def fail(_: Path) -> tuple[Path, Any]:
            raise RecordingError("Cannot create output")

        recorder = SoundDeviceRecorder(
            self.capture, checkout=lambda: self.root, create_file=fail
        )
        with self.assertRaisesRegex(RecordingError, "Cannot create output") as raised:
            recorder.record(self.request)
        self.assertIsNone(raised.exception.incomplete_path)
        self.assertEqual(self.capture.streams_created, [])


if __name__ == "__main__":
    unittest.main()

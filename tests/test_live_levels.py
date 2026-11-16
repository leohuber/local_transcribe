import io
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from local_transcribe.cli.commands import _record_until_stopped
from local_transcribe.cli.levels import LevelDisplay
from local_transcribe.domain.recording import (
    InputDevice,
    InputLevel,
    RecordingRequest,
    RecordingResult,
)


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value


class TerminalStream(io.StringIO):
    def isatty(self) -> bool:
        return True


class SlowStream(io.StringIO):
    def __init__(self) -> None:
        super().__init__()
        self.blocked = threading.Event()
        self.release = threading.Event()
        self.writes = 0

    def write(self, text: str) -> int:
        self.writes += 1
        if self.writes == 2:
            self.blocked.set()
            if not self.release.wait(timeout=2):
                raise TimeoutError("slow consumer was not released")
        return super().write(text)


class SlowConsumerRecording:
    def __init__(self, stream: SlowStream) -> None:
        self.stream = stream
        self.capture_progress = threading.Event()

    def list_inputs(self) -> tuple[InputDevice, ...]:
        return (InputDevice(2, "Mic", 1), InputDevice(5, "Loopback", 1))

    def record(self, request: RecordingRequest) -> RecordingResult:
        if not self.stream.blocked.wait(timeout=2):
            raise TimeoutError("meter did not reach the slow consumer")
        self.capture_progress.set()
        self.stream.release.set()
        return RecordingResult(Path("capture.wav"))

    def latest_levels(self) -> tuple[InputLevel, ...]:
        return (InputLevel(2, 0.5), InputLevel(5, 0.0))

    def stop(self) -> None:
        self.stream.release.set()


class LiveLevelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.devices = (InputDevice(2, "Mic", 1), InputDevice(5, "Loopback", 2))
        self.clock = FakeClock()

    def test_redirected_updates_are_throttled_and_independent(self) -> None:
        output = io.StringIO()
        with LevelDisplay(self.devices, stream=output, clock=self.clock) as display:
            for step in range(1, 11):
                self.clock.value = step / 10
                display.update((InputLevel(2, 0.3), InputLevel(5, 0.0)))
            lines = output.getvalue().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertIn("2: Mic", lines[-1])
            self.assertIn("5: Loopback", lines[-1])
            first, second = lines[-1].split(" | ")
            self.assertGreater(first.count("#"), 0)
            self.assertEqual(second.count("#"), 0)
            for step in range(11, 21):
                self.clock.value = step / 10
                display.update((InputLevel(2, 0.3), InputLevel(5, 0.01)))
            first, second = output.getvalue().splitlines()[-1].split(" | ")
            self.assertGreater(first.count("#"), second.count("#"))
            self.assertGreater(second.count("#"), 0)
            for step in range(21, 31):
                self.clock.value = step / 10
                display.update((InputLevel(2, 0.0), InputLevel(5, 0.1)))
        first, second = output.getvalue().splitlines()[-1].split(" | ")
        self.assertLessEqual(first.count("#"), 1)
        self.assertGreater(second.count("#"), 0)
        self.assertNotIn("\x1b", output.getvalue())

    def test_interactive_display_restores_terminal_on_exit(self) -> None:
        output = TerminalStream()
        with LevelDisplay(self.devices, stream=output, clock=self.clock) as display:
            self.clock.value = 0.2
            display.update((InputLevel(2, 0.5), InputLevel(5, 0.1)))
        text = output.getvalue()
        self.assertIn("2: Mic", text)
        self.assertIn("5: Loopback", text)
        self.assertIn("#", text)
        self.assertIn("\x1b[?25h", text)

    def test_interactive_display_restores_terminal_after_error(self) -> None:
        output = TerminalStream()
        with (
            self.assertRaisesRegex(RuntimeError, "capture failed"),
            LevelDisplay(self.devices, stream=output, clock=self.clock),
        ):
            raise RuntimeError("capture failed")
        self.assertIn("\x1b[?25h", output.getvalue())

    def test_slow_output_cannot_block_recording_worker(self) -> None:
        output = SlowStream()
        recording = SlowConsumerRecording(output)
        with LevelDisplay(self.devices, stream=output) as display:
            result = _record_until_stopped(recording, RecordingRequest(2, 5), display)
        self.assertEqual(result.path, Path("capture.wav"))
        self.assertTrue(recording.capture_progress.is_set())

    def test_interrupt_stops_capture_before_display_exits(self) -> None:
        output = io.StringIO()
        recording = SlowConsumerRecording(SlowStream())
        with (
            patch("local_transcribe.cli.commands.ThreadPoolExecutor") as executor,
            LevelDisplay(self.devices, stream=output) as display,
        ):
            future = executor.return_value.__enter__.return_value.submit.return_value
            future.result.side_effect = [
                KeyboardInterrupt,
                RecordingResult(Path("done.wav")),
            ]
            result = _record_until_stopped(recording, RecordingRequest(2, 5), display)
        self.assertEqual(result.path, Path("done.wav"))
        self.assertTrue(recording.stream.release.is_set())


if __name__ == "__main__":
    unittest.main()

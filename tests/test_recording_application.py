import subprocess
import sys
import unittest
from pathlib import Path

from local_transcribe.application.recording import Recording
from local_transcribe.domain.recording import (
    DeviceSelectionError,
    InputDevice,
    InputLevel,
    RecordingError,
    RecordingRequest,
    RecordingResult,
)


class FakeDevices:
    def __init__(self) -> None:
        self.devices = (InputDevice(2, "Mic", 1), InputDevice(5, "Loopback", 2))
        self.error: RecordingError | None = None

    def list_inputs(self) -> tuple[InputDevice, ...]:
        if self.error is not None:
            raise self.error
        return self.devices


class FakeRecorder:
    def __init__(self) -> None:
        self.requests: list[RecordingRequest] = []
        self.error: RecordingError | None = None
        self.stopped = False

    def record(self, request: RecordingRequest) -> RecordingResult:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return RecordingResult(Path("capture.wav"))

    def latest_levels(self) -> tuple[InputLevel, ...]:
        return (InputLevel(2, 0.25), InputLevel(5, 0.5))

    def stop(self) -> None:
        self.stopped = True


class RecordingApplicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.devices = FakeDevices()
        self.recorder = FakeRecorder()
        self.recording = Recording(self.devices, self.recorder)

    def test_selects_distinct_available_inputs_and_delegates(self) -> None:
        request = RecordingRequest(2, 5)
        self.assertEqual(self.recording.list_inputs(), self.devices.devices)
        self.assertEqual(self.recording.record(request).path, Path("capture.wav"))
        self.assertEqual(self.recorder.requests, [request])
        self.assertEqual(self.recording.latest_levels(), self.recorder.latest_levels())
        self.recording.stop()
        self.assertTrue(self.recorder.stopped)

    def test_rejects_duplicate_and_unavailable_inputs(self) -> None:
        for request in (
            RecordingRequest(2, 2),
            RecordingRequest(9, 5),
            RecordingRequest(2, 9),
        ):
            with self.subTest(request=request):
                with self.assertRaises(DeviceSelectionError):
                    self.recording.record(request)
        self.assertEqual(self.recorder.requests, [])

    def test_revalidates_inputs_before_recording(self) -> None:
        self.recording.list_inputs()
        self.devices.devices = self.devices.devices[:1]
        with self.assertRaisesRegex(DeviceSelectionError, "5.*unavailable"):
            self.recording.record(RecordingRequest(2, 5))
        self.assertEqual(self.recorder.requests, [])

    def test_propagates_device_and_recording_errors(self) -> None:
        error = RecordingError("capture failed", incomplete_path=Path("partial.wav"))
        self.devices.error = error
        with self.assertRaises(RecordingError) as raised:
            self.recording.record(RecordingRequest(2, 5))
        self.assertIs(raised.exception, error)

        self.devices.error = None
        self.recorder.error = error
        with self.assertRaises(RecordingError) as raised:
            self.recording.record(RecordingRequest(2, 5))
        self.assertIs(raised.exception, error)
        self.assertEqual(raised.exception.incomplete_path, Path("partial.wav"))

    def test_core_does_not_load_audio_or_mlx_frameworks(self) -> None:
        code = """
import sys
from local_transcribe.application.recording import Recording
unexpected = [name for name in sys.modules
              if name.split(".")[0] in {"numpy", "sounddevice", "soxr", "mlx", "mlx_audio"}]
if unexpected:
    raise SystemExit(str(unexpected))
"""
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

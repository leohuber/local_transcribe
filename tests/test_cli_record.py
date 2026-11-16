import unittest
from pathlib import Path

from click.testing import CliRunner

from local_transcribe.cli.commands import create_cli
from local_transcribe.domain.recording import (
    DeviceSelectionError,
    InputDevice,
    InputLevel,
    RecordingError,
    RecordingRequest,
    RecordingResult,
)


class FakeRecording:
    def __init__(self) -> None:
        self.devices = (InputDevice(2, "Mic", 1), InputDevice(5, "Loopback", 2))
        self.requests: list[RecordingRequest] = []
        self.errors: list[RecordingError] = []
        self.list_error: RecordingError | None = None
        self.stopped = False

    def list_inputs(self) -> tuple[InputDevice, ...]:
        if self.list_error is not None:
            raise self.list_error
        return self.devices

    def record(self, request: RecordingRequest) -> RecordingResult:
        self.requests.append(request)
        if self.errors:
            raise self.errors.pop(0)
        return RecordingResult(Path("/checkout/.tmp/recording.wav"))

    def latest_levels(self) -> tuple[InputLevel, ...]:
        return ()

    def stop(self) -> None:
        self.stopped = True


class RecordCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.recording = FakeRecording()
        self.cli = create_cli(lambda: self.recording)
        self.runner = CliRunner()

    def test_lists_inputs_and_retries_malformed_invalid_and_duplicate_ids(self) -> None:
        result = self.runner.invoke(self.cli, ["record"], input="bad\n999\n2\n2\n5\n")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("2: Mic (1 input channels)", result.output)
        self.assertIn("5: Loopback (2 input channels)", result.output)
        self.assertIn("not a valid integer", result.output)
        self.assertIn("listed input devices", result.output)
        self.assertIn("different input device", result.output)
        self.assertEqual(self.recording.requests, [RecordingRequest(2, 5)])
        self.assertIn("Starting recording. Press Ctrl+C to stop.", result.output)
        self.assertIn("Levels: 2: Mic [", result.output)
        self.assertIn("Recording saved: /checkout/.tmp/recording.wav", result.output)

    def test_changed_device_selection_can_be_corrected(self) -> None:
        self.recording.errors = [DeviceSelectionError("Device 5 disappeared.")]
        result = self.runner.invoke(self.cli, ["record"], input="2\n5\n5\n2\n")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Device 5 disappeared", result.output)
        self.assertEqual(
            self.recording.requests, [RecordingRequest(2, 5), RecordingRequest(5, 2)]
        )

    def test_insufficient_devices_and_enumeration_failure_exit_unsuccessfully(
        self,
    ) -> None:
        self.recording.devices = self.recording.devices[:1]
        result = self.runner.invoke(self.cli, ["record"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("At least two input devices", result.output)
        self.assertIn("2: Mic (1 input channels)", result.output)
        self.assertEqual(self.recording.requests, [])

        self.recording.list_error = RecordingError("PortAudio unavailable")
        result = self.runner.invoke(self.cli, ["record"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("PortAudio unavailable", result.output)

    def test_recording_failure_identifies_incomplete_file(self) -> None:
        self.recording.errors = [
            RecordingError("Input overflow", incomplete_path=Path("/tmp/partial.wav"))
        ]
        result = self.runner.invoke(self.cli, ["record"], input="2\n5\n")
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Input overflow", result.output)
        self.assertIn("Incomplete recording: /tmp/partial.wav", result.output)
        self.assertNotIn("Recording saved", result.output)

    def test_help_and_greeting_do_not_create_recording_use_case(self) -> None:
        def unexpected() -> FakeRecording:
            self.fail("audio dependencies should be lazy")

        cli = create_cli(unexpected)
        for args in ([], ["--help"], ["record", "--help"]):
            with self.subTest(args=args):
                result = self.runner.invoke(cli, args)
                self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(
            self.runner.invoke(cli, []).output, "Hello from local-transcribe!\n"
        )


if __name__ == "__main__":
    unittest.main()

import unittest
from typing import Any

from local_transcribe.adapters.capture import BLOCK_FRAMES, SoundDeviceCapture
from local_transcribe.domain.recording import InputDevice, RecordingError


class FakeStream:
    def __init__(self, backend: FakeAudio, options: dict[str, Any]) -> None:
        self.backend = backend
        self.options = options
        self.active = False
        self.closed = False
        self.stopped = False

    def start(self) -> None:
        if self.options["device"] == self.backend.interrupt_start:
            raise KeyboardInterrupt
        if self.options["device"] == self.backend.fail_start:
            raise OSError("start failed")
        self.active = True
        self.backend.events.append(("start", self.options["device"]))

    def stop(self) -> None:
        if self.options["device"] == self.backend.interrupt_stop:
            raise KeyboardInterrupt
        if self.options["device"] == self.backend.fail_stop:
            raise OSError("stop failed")
        self.stopped = True
        self.active = False
        self.backend.events.append(("stop", self.options["device"]))

    def close(self) -> None:
        self.closed = True
        self.backend.events.append(("close", self.options["device"]))


class FakeAudio:
    PortAudioError = OSError

    def __init__(self) -> None:
        self.devices = [
            {"name": "Speakers", "max_input_channels": 0, "default_samplerate": 48000},
            {"name": "Mic", "max_input_channels": 4, "default_samplerate": 48000},
            {"name": "Output", "max_input_channels": 0, "default_samplerate": 44100},
            {"name": "Loopback", "max_input_channels": 1, "default_samplerate": 44100},
        ]
        self.supported_channels = {1: {2}, 3: {1}}
        self.fail_start: int | None = None
        self.fail_open: int | None = None
        self.fail_stop: int | None = None
        self.interrupt_start: int | None = None
        self.interrupt_stop: int | None = None
        self.streams: list[FakeStream] = []
        self.events: list[tuple[str, int]] = []

    def query_devices(self, device: int | None = None, kind: str = "") -> Any:
        if device is None:
            return self.devices
        if device < 0 or device >= len(self.devices):
            raise ValueError("missing device")
        info = self.devices[device]
        if kind == "input" and not info["max_input_channels"]:
            raise ValueError("not an input")
        return info

    def check_input_settings(self, **options: Any) -> None:
        if options["channels"] not in self.supported_channels[options["device"]]:
            raise ValueError("unsupported channels")

    def InputStream(self, **options: Any) -> FakeStream:
        if options["device"] == self.fail_open:
            raise OSError("open failed")
        stream = FakeStream(self, options)
        self.streams.append(stream)
        return stream


def callback(data: Any, frames: int, timing: Any, status: Any) -> None:
    pass


def finished() -> None:
    pass


class CaptureDeviceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.backend = FakeAudio()
        self.capture = SoundDeviceCapture(self.backend)

    def test_lists_only_inputs_with_original_ids(self) -> None:
        self.assertEqual(
            self.capture.list_inputs(),
            (InputDevice(1, "Mic", 4), InputDevice(3, "Loopback", 1)),
        )

    def test_selects_supported_channels_and_device_rate(self) -> None:
        first = self.capture.configure(1)
        second = self.capture.configure(3)
        self.assertEqual(
            (first.device.id, first.channels, first.sample_rate), (1, 2, 48000)
        )
        self.assertEqual(
            (second.device.id, second.channels, second.sample_rate), (3, 1, 44100)
        )

    def test_rejects_missing_output_only_and_unsupported_devices(self) -> None:
        self.backend.supported_channels[1] = set()
        for device_id in (-1, 0, 1, 4):
            with self.subTest(device_id=device_id), self.assertRaises(RecordingError):
                self.capture.configure(device_id)

    def test_starts_both_streams_and_closes_them(self) -> None:
        configs = (self.capture.configure(1), self.capture.configure(3))
        with self.capture.streams(
            configs, (callback, callback), (finished, finished)
        ) as streams:
            self.assertTrue(streams.active)
            self.assertTrue(all(stream.active for stream in self.backend.streams))
            self.assertEqual(
                [stream.options["device"] for stream in self.backend.streams], [1, 3]
            )
            self.assertTrue(
                all(
                    stream.options["blocksize"] == BLOCK_FRAMES
                    for stream in self.backend.streams
                )
            )
        self.assertTrue(
            all(stream.stopped and stream.closed for stream in self.backend.streams)
        )

    def test_cleans_up_when_second_stream_cannot_open_or_start(self) -> None:
        configs = (self.capture.configure(1), self.capture.configure(3))
        for failure in ("fail_open", "fail_start"):
            with self.subTest(failure=failure):
                backend = FakeAudio()
                setattr(backend, failure, 3)
                capture = SoundDeviceCapture(backend)
                with (
                    self.assertRaisesRegex(RecordingError, "Unable to start"),
                    capture.streams(
                        configs, (callback, callback), (finished, finished)
                    ),
                ):
                    self.fail("streams should not start")
                self.assertTrue(all(stream.closed for stream in backend.streams))
                if failure == "fail_start":
                    self.assertTrue(backend.streams[0].stopped)
                    self.assertFalse(backend.streams[1].stopped)

    def test_closes_both_streams_even_if_one_stop_fails(self) -> None:
        configs = (self.capture.configure(1), self.capture.configure(3))
        self.backend.fail_stop = 3
        with (
            self.assertRaisesRegex(RecordingError, "Unable to close"),
            self.capture.streams(configs, (callback, callback), (finished, finished)),
        ):
            pass
        self.assertTrue(all(stream.closed for stream in self.backend.streams))
        self.assertTrue(self.backend.streams[0].stopped)

    def test_interrupt_during_start_or_stop_still_closes_both_streams(self) -> None:
        configs = (self.capture.configure(1), self.capture.configure(3))
        for interrupted in ("interrupt_start", "interrupt_stop"):
            with self.subTest(interrupted=interrupted):
                backend = FakeAudio()
                setattr(backend, interrupted, 3)
                capture = SoundDeviceCapture(backend)
                with (
                    self.assertRaises(KeyboardInterrupt),
                    capture.streams(
                        configs, (callback, callback), (finished, finished)
                    ),
                ):
                    pass
                self.assertTrue(all(stream.closed for stream in backend.streams))
                self.assertTrue(backend.streams[0].stopped)


if __name__ == "__main__":
    unittest.main()

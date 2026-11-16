import unittest
from types import SimpleNamespace

import numpy as np

from local_transcribe.adapters.audio_buffer import AudioBuffer, downmix
from local_transcribe.adapters.capture import BLOCK_FRAMES, CaptureConfig
from local_transcribe.domain.recording import InputDevice


class AudioBufferTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = CaptureConfig(InputDevice(7, "Stereo", 2), 48000, 2)
        self.buffer = AudioBuffer(self.config, max_blocks=2, clock=lambda: 100.0)
        self.timing = SimpleNamespace(inputBufferAdcTime=3.0, currentTime=3.1)

    def test_downmixes_all_channels_and_copies_callback_data(self) -> None:
        data = np.array([[1.0, -1.0], [0.2, 0.8], [-0.5, -0.5]], dtype=np.float32)
        self.buffer.callback(data, 3, self.timing, None)
        data.fill(0.0)
        block = self.buffer.take()
        self.assertIsNotNone(block)
        assert block is not None
        np.testing.assert_allclose(downmix(block.samples), [0.0, 0.5, -0.5])
        self.assertEqual(
            (block.adc_time, block.callback_time, block.host_time), (3.0, 3.1, 100.0)
        )

    def test_queue_is_bounded_and_reports_overflow_without_dropping_silently(
        self,
    ) -> None:
        data = np.ones((BLOCK_FRAMES, 2), dtype=np.float32)
        for _ in range(100):
            self.buffer.callback(data, BLOCK_FRAMES, self.timing, None)
        self.assertEqual(self.buffer.queued_blocks, 2)
        self.assertIn("buffer overflow", self.buffer.error or "")
        self.assertIsNotNone(self.buffer.take())
        self.assertIsNotNone(self.buffer.take())
        self.assertIsNone(self.buffer.take())

    def test_callback_status_and_oversized_blocks_are_failures(self) -> None:
        data = np.ones((BLOCK_FRAMES, 2), dtype=np.float32)
        self.buffer.callback(data, BLOCK_FRAMES, self.timing, "input overflow")
        self.assertIn("input overflow", self.buffer.error or "")
        self.assertEqual(self.buffer.queued_blocks, 0)

        other = AudioBuffer(self.config)
        large = np.ones((BLOCK_FRAMES + 1, 2), dtype=np.float32)
        other.callback(large, BLOCK_FRAMES + 1, self.timing, None)
        self.assertIn("invalid callback size", other.error or "")
        self.assertEqual(other.queued_blocks, 0)

    def test_bad_shape_or_timestamp_is_reported(self) -> None:
        samples = np.ones((10, 2), dtype=np.float32)
        for data, timing in (
            (samples[:, :1], self.timing),
            (samples, SimpleNamespace(inputBufferAdcTime=float("nan"), currentTime=3)),
            (samples, SimpleNamespace(currentTime=3)),
        ):
            with self.subTest(data_shape=data.shape, timing=timing):
                buffer = AudioBuffer(self.config)
                buffer.callback(data, 10, timing, None)
                self.assertIn("callback failed", buffer.error or "")
                self.assertIsNone(buffer.take())


if __name__ == "__main__":
    unittest.main()

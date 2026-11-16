import unittest

import numpy as np

from local_transcribe.adapters.mixing import mix_pcm16
from local_transcribe.domain.recording import RecordingError


class AudioMixingTests(unittest.TestCase):
    def test_equal_gain_and_silent_input(self) -> None:
        first = np.array([1.0, -1.0, 0.5, 0.0], dtype=np.float32)
        second = np.array([0.0, 0.0, -0.5, 0.5], dtype=np.float32)
        pcm = np.frombuffer(mix_pcm16(first, second), dtype="<i2")
        np.testing.assert_array_equal(pcm, [16384, -16384, 0, 8192])

    def test_pcm_conversion_clips_at_both_limits(self) -> None:
        first = np.array([1.0, -1.0, 2.0, -2.0], dtype=np.float32)
        pcm = np.frombuffer(mix_pcm16(first, first), dtype="<i2")
        np.testing.assert_array_equal(pcm, [32767, -32768, 32767, -32768])

    def test_rejects_misaligned_or_nonfinite_input(self) -> None:
        with self.assertRaisesRegex(RecordingError, "aligned"):
            mix_pcm16(np.zeros(2, dtype=np.float32), np.zeros(3, dtype=np.float32))
        with self.assertRaisesRegex(RecordingError, "invalid"):
            mix_pcm16(
                np.array([float("nan")], dtype=np.float32),
                np.zeros(1, dtype=np.float32),
            )


if __name__ == "__main__":
    unittest.main()

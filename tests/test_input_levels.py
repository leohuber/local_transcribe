import threading
import unittest

import numpy as np

from local_transcribe.adapters.audio_buffer import downmix
from local_transcribe.adapters.levels import InputLevels
from local_transcribe.domain.recording import InputLevel, RecordingError


class InputLevelsTests(unittest.TestCase):
    def test_silence_and_independent_levels(self) -> None:
        levels = InputLevels((2, 5))
        self.assertEqual(levels.snapshot(), (InputLevel(2, 0), InputLevel(5, 0)))
        levels.update(0, np.full((8, 1), 0.25, dtype=np.float32))
        levels.update(1, np.full((8, 2), 0.75, dtype=np.float32))
        self.assertEqual(levels.snapshot(), (InputLevel(2, 0.25), InputLevel(5, 0.75)))
        levels.update(0, np.zeros((8, 1), dtype=np.float32))
        self.assertEqual(levels.snapshot(), (InputLevel(2, 0), InputLevel(5, 0.75)))

    def test_opposite_phase_channels_still_show_activity(self) -> None:
        levels = InputLevels((2, 5))
        samples = np.array([[0.8, -0.8], [-0.8, 0.8]], dtype=np.float32)
        np.testing.assert_array_equal(downmix(samples), [0, 0])
        levels.update(0, samples)
        self.assertAlmostEqual(levels.snapshot()[0].rms, 0.8, places=6)

    def test_slow_consumer_cannot_block_or_accumulate_snapshots(self) -> None:
        levels = InputLevels((2, 5))
        started = threading.Event()
        release = threading.Event()
        captured: list[tuple[InputLevel, InputLevel]] = []

        def slow_consumer() -> None:
            captured.append(levels.snapshot())
            started.set()
            release.wait()

        thread = threading.Thread(target=slow_consumer)
        thread.start()
        self.assertTrue(started.wait(timeout=2))
        try:
            samples = np.ones((8, 2), dtype=np.float32)
            for _ in range(1000):
                levels.update(0, samples)
            self.assertEqual(levels.snapshot(), (InputLevel(2, 1), InputLevel(5, 0)))
            self.assertEqual(captured, [(InputLevel(2, 0), InputLevel(5, 0))])
        finally:
            release.set()
            thread.join(timeout=2)
        self.assertFalse(thread.is_alive())

    def test_invalid_audio_is_reported(self) -> None:
        levels = InputLevels((2, 5))
        with self.assertRaisesRegex(RecordingError, "invalid"):
            levels.update(0, np.array([[float("nan")]], dtype=np.float32))


if __name__ == "__main__":
    unittest.main()

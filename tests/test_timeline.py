import math
import unittest

import numpy as np

from local_transcribe.adapters.audio_buffer import AudioBlock
from local_transcribe.adapters.capture import BLOCK_FRAMES, CaptureConfig
from local_transcribe.adapters.timeline import SynchronizedInputs
from local_transcribe.domain.recording import InputDevice, RecordingError


def signal(t: np.ndarray) -> np.ndarray:
    return (
        0.35 * np.sin(2 * np.pi * 193 * t)
        + 0.25 * np.sin(2 * np.pi * 431 * t)
        + 0.1 * np.sin(2 * np.pi * 71 * t)
    ).astype(np.float32)


def synthetic_block(
    config: CaptureConfig,
    start: float,
    actual_rate: float,
    frame: int,
    count: int,
    offset: float,
) -> AudioBlock:
    adc_time = start + frame / actual_rate
    jitter = 0.002 * math.sin(frame / 11000)
    callback_time = adc_time + count / actual_rate + jitter
    host_jitter = 0.00002 * math.sin(frame / 7000)
    samples = signal(adc_time + np.arange(count) / actual_rate).reshape(-1, 1)
    return AudioBlock(
        samples, adc_time - offset, callback_time - offset, callback_time + host_jitter
    )


def lag(first: np.ndarray, second: np.ndarray, radius: int = 80) -> int:
    errors = [
        np.mean(
            (
                first[radius:-radius]
                - second[radius + shift : len(second) - radius + shift]
            )
            ** 2
        )
        for shift in range(-radius, radius + 1)
    ]
    return int(np.argmin(errors)) - radius


def simulate(
    drift: tuple[float, float], duration: float = 20
) -> tuple[np.ndarray, np.ndarray, float]:
    configs = (
        CaptureConfig(InputDevice(1, "First", 1), 48000, 1),
        CaptureConfig(InputDevice(2, "Second", 1), 44100, 1),
    )
    starts = (20.0, 20.037)
    offsets = (1000.0, -300.0)
    rates = tuple(
        config.sample_rate * (1 + ppm / 1_000_000)
        for config, ppm in zip(configs, drift, strict=True)
    )
    totals = tuple(round(duration * rate) for rate in rates)
    positions = [0, 0]

    def block(index: int) -> AudioBlock:
        count = min(BLOCK_FRAMES, totals[index] - positions[index])
        result = synthetic_block(
            configs[index],
            starts[index],
            rates[index],
            positions[index],
            count,
            offsets[index],
        )
        positions[index] += count
        return result

    timeline = SynchronizedInputs(configs, (block(0), block(1)))
    output: tuple[list[np.ndarray], list[np.ndarray]] = ([], [])

    def drain() -> None:
        while (aligned := timeline.take()) is not None:
            output[0].append(aligned[0])
            output[1].append(aligned[1])

    drain()
    while any(
        position < total for position, total in zip(positions, totals, strict=True)
    ):
        candidates = [
            starts[index] + positions[index] / rates[index]
            if positions[index] < totals[index]
            else math.inf
            for index in range(2)
        ]
        index = int(np.argmin(candidates))
        timeline.push(index, block(index))
        drain()
    timeline.finish()
    drain()
    return np.concatenate(output[0]), np.concatenate(output[1]), timeline.start_time


class TimelineTests(unittest.TestCase):
    def test_different_rates_and_startup_offsets_follow_common_timeline(self) -> None:
        first, second, start = simulate((0, 0), duration=5)
        self.assertAlmostEqual(start, 20.037, delta=0.00005)
        self.assertAlmostEqual(len(first) / 48000, 5 - 0.037, delta=0.003)
        expected = signal(start + np.arange(len(first)) / 48000)
        for actual in (first, second):
            self.assertLess(abs(lag(expected[5000:15000], actual[5000:15000])), 6)
            self.assertLess(abs(lag(expected[-15000:-5000], actual[-15000:-5000])), 6)

    def test_sustained_drift_in_both_directions_remains_aligned(self) -> None:
        for drift in ((1800, -1600), (-1600, 1800)):
            with self.subTest(drift=drift):
                first, second, start = simulate(drift)
                self.assertAlmostEqual(len(first) / 48000, 20 - 0.037, delta=0.01)
                for seconds in (1, 3, 10, 19):
                    begin = seconds * 48000
                    end = begin + 10000
                    expected = signal(start + np.arange(begin, end) / 48000)
                    self.assertLess(abs(lag(first[begin:end], second[begin:end])), 20)
                    self.assertLess(abs(lag(expected, first[begin:end])), 12)
                    self.assertLess(abs(lag(expected, second[begin:end])), 12)

    def test_unbalanced_input_cannot_grow_synchronization_memory(self) -> None:
        configs = (
            CaptureConfig(InputDevice(1, "First", 1), 48000, 1),
            CaptureConfig(InputDevice(2, "Second", 1), 48000, 1),
        )
        data = np.zeros((BLOCK_FRAMES, 1), dtype=np.float32)
        first = AudioBlock(data, 10.0, 10.03, 20.03)
        timeline = SynchronizedInputs(configs, (first, first))
        with self.assertRaisesRegex(RecordingError, "synchronization buffer overflow"):
            for index in range(1, 200):
                timestamp = 10.0 + index * BLOCK_FRAMES / 48000
                timeline.push(
                    0, AudioBlock(data, timestamp, timestamp + 0.03, timestamp + 10.03)
                )

    def test_rejects_missing_or_discontinuous_timestamps(self) -> None:
        configs = (
            CaptureConfig(InputDevice(1, "First", 1), 48000, 1),
            CaptureConfig(InputDevice(2, "Second", 1), 48000, 1),
        )
        data = np.zeros((BLOCK_FRAMES, 1), dtype=np.float32)
        first = AudioBlock(data, 10.0, 10.03, 20.03)
        timeline = SynchronizedInputs(configs, (first, first))
        with self.assertRaisesRegex(RecordingError, "discontinuous"):
            timeline.push(0, first)
        with self.assertRaisesRegex(RecordingError, "unusable"):
            SynchronizedInputs(configs, (first, AudioBlock(data, float("nan"), 1, 1)))


if __name__ == "__main__":
    unittest.main()

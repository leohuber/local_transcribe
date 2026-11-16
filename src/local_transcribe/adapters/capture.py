from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Self

from local_transcribe.domain.recording import InputDevice, RecordingError

BLOCK_FRAMES = 1024


@dataclass(frozen=True, slots=True)
class CaptureConfig:
    device: InputDevice
    sample_rate: int
    channels: int


AudioCallback = Callable[[Any, int, Any, Any], None]


class SoundDeviceCapture:
    def __init__(self, backend: Any | None = None) -> None:
        self._backend = backend

    def _audio(self) -> Any:
        if self._backend is None:
            try:
                import sounddevice
            except (ImportError, OSError) as exc:
                raise RecordingError(f"Unable to initialize PortAudio: {exc}") from exc
            self._backend = sounddevice
        return self._backend

    def list_inputs(self) -> tuple[InputDevice, ...]:
        try:
            devices = self._audio().query_devices()
            return tuple(
                InputDevice(index, str(info["name"]), int(info["max_input_channels"]))
                for index, info in enumerate(devices)
                if int(info["max_input_channels"]) > 0
            )
        except RecordingError:
            raise
        except Exception as exc:
            raise RecordingError(f"Unable to list audio inputs: {exc}") from exc

    def configure(self, device_id: int) -> CaptureConfig:
        backend = self._audio()
        try:
            info = backend.query_devices(device_id, "input")
            channels = int(info["max_input_channels"])
            rate = round(float(info["default_samplerate"]))
            if channels < 1 or rate < 1:
                raise ValueError("device has no usable input channels or sample rate")
            device = InputDevice(device_id, str(info["name"]), channels)
        except Exception as exc:
            raise RecordingError(
                f"Input device {device_id} is unavailable: {exc}"
            ) from exc

        last_error: Exception | None = None
        for channel_count in range(channels, 0, -1):
            try:
                backend.check_input_settings(
                    device=device_id,
                    channels=channel_count,
                    samplerate=rate,
                    dtype="float32",
                )
            except (backend.PortAudioError, OSError, ValueError) as exc:
                last_error = exc
                continue
            return CaptureConfig(device, rate, channel_count)
        raise RecordingError(
            f"Input device {device_id} has no supported capture configuration: "
            f"{last_error}"
        )

    def streams(
        self,
        configs: tuple[CaptureConfig, CaptureConfig],
        callbacks: tuple[AudioCallback, AudioCallback],
        finished_callbacks: tuple[Callable[[], None], Callable[[], None]],
    ) -> CaptureStreams:
        return CaptureStreams(self._audio(), configs, callbacks, finished_callbacks)


class CaptureStreams:
    def __init__(
        self,
        backend: Any,
        configs: tuple[CaptureConfig, CaptureConfig],
        callbacks: tuple[AudioCallback, AudioCallback],
        finished_callbacks: tuple[Callable[[], None], Callable[[], None]],
    ) -> None:
        self._backend = backend
        self._configs = configs
        self._callbacks = callbacks
        self._finished_callbacks = finished_callbacks
        self._streams: list[Any] = []
        self._started: list[Any] = []

    def __enter__(self) -> Self:
        try:
            for config, callback, finished in zip(
                self._configs, self._callbacks, self._finished_callbacks, strict=True
            ):
                stream = self._backend.InputStream(
                    device=config.device.id,
                    samplerate=config.sample_rate,
                    channels=config.channels,
                    dtype="float32",
                    blocksize=BLOCK_FRAMES,
                    callback=callback,
                    finished_callback=finished,
                )
                self._streams.append(stream)
            for stream in self._streams:
                stream.start()
                self._started.append(stream)
        except BaseException as exc:
            try:
                self.close()
            except RecordingError:
                pass
            if isinstance(exc, Exception):
                raise RecordingError(f"Unable to start input streams: {exc}") from exc
            raise
        return self

    @property
    def active(self) -> bool:
        return len(self._started) == 2 and all(
            stream.active for stream in self._started
        )

    def close(self) -> None:
        streams, started = self._streams, self._started
        self._streams = []
        self._started = []
        try:
            with ExitStack() as stack:
                for stream in streams:
                    stack.callback(stream.close)
                    if stream in started:
                        stack.callback(stream.stop)
        except Exception as exc:
            raise RecordingError(f"Unable to close input streams: {exc}") from exc

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            self.close()
        except RecordingError:
            if exc_value is None:
                raise

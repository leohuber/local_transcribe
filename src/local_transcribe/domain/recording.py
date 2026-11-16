from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class InputDevice:
    id: int
    name: str
    input_channels: int


@dataclass(frozen=True, slots=True)
class RecordingRequest:
    first_device_id: int
    second_device_id: int


@dataclass(frozen=True, slots=True)
class RecordingResult:
    path: Path


@dataclass(frozen=True, slots=True)
class InputLevel:
    device_id: int
    rms: float


class RecordingError(Exception):
    def __init__(self, message: str, *, incomplete_path: Path | None = None) -> None:
        super().__init__(message)
        self.incomplete_path = incomplete_path


class DeviceSelectionError(RecordingError):
    pass

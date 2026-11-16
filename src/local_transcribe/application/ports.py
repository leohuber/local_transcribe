from typing import Protocol

from local_transcribe.domain.recording import (
    InputDevice,
    InputLevel,
    RecordingRequest,
    RecordingResult,
)


class InputDevices(Protocol):
    def list_inputs(self) -> tuple[InputDevice, ...]: ...


class Recorder(Protocol):
    def record(self, request: RecordingRequest) -> RecordingResult: ...

    def latest_levels(self) -> tuple[InputLevel, ...]: ...

    def stop(self) -> None: ...


class RecordingUseCase(InputDevices, Recorder, Protocol):
    pass

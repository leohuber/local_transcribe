from pathlib import Path
from typing import Protocol

from local_transcribe.domain.recording import (
    InputDevice,
    InputLevel,
    RecordingRequest,
    RecordingResult,
)
from local_transcribe.domain.transcription import (
    Transcript,
    TranscriptionRequest,
    TranscriptionResult,
)


class InputDevices(Protocol):
    def list_inputs(self) -> tuple[InputDevice, ...]: ...


class Recorder(Protocol):
    def record(self, request: RecordingRequest) -> RecordingResult: ...

    def latest_levels(self) -> tuple[InputLevel, ...]: ...

    def stop(self) -> None: ...


class RecordingUseCase(InputDevices, Recorder, Protocol):
    pass


class Transcriber(Protocol):
    def transcribe(self, request: TranscriptionRequest) -> Transcript: ...


class TranscriptStore(Protocol):
    def save(self, audio_path: Path, text: str) -> Path: ...


class TranscriptionUseCase(Protocol):
    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult: ...

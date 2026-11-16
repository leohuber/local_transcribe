from dataclasses import dataclass
from pathlib import Path

DEFAULT_MODEL = "nativ-community/Nemotron-3.5-Transcribe-30B-A4B-EA-4bit"


@dataclass(frozen=True, slots=True)
class TranscriptionRequest:
    audio_path: Path
    model: str = DEFAULT_MODEL


@dataclass(frozen=True, slots=True)
class SpeakerTurn:
    speaker: int | None
    text: str


@dataclass(frozen=True, slots=True)
class Transcript:
    turns: tuple[SpeakerTurn, ...]
    truncated: bool = False

    def render(self) -> str:
        return "\n".join(
            turn.text
            if turn.speaker is None
            else f"Speaker {turn.speaker}: {turn.text}"
            for turn in self.turns
        )


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    transcript: Transcript
    saved_path: Path


class TranscriptionError(Exception):
    pass

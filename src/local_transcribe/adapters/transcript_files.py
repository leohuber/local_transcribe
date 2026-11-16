from pathlib import Path

from local_transcribe.adapters.recording_files import (
    create_transcript_file,
    find_checkout,
)
from local_transcribe.domain.recording import RecordingError
from local_transcribe.domain.transcription import TranscriptionError


class FileTranscriptStore:
    def save(self, audio_path: Path, text: str) -> Path:
        try:
            path, stream = create_transcript_file(find_checkout(), audio_path.stem)
        except RecordingError as exc:
            raise TranscriptionError(str(exc)) from exc
        try:
            with stream:
                stream.write(f"{text}\n")
        except OSError as exc:
            raise TranscriptionError(
                f"Unable to write transcript {path}: {exc}"
            ) from exc
        return path

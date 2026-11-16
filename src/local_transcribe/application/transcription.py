from local_transcribe.application.ports import Transcriber, TranscriptStore
from local_transcribe.domain.transcription import (
    TranscriptionError,
    TranscriptionRequest,
    TranscriptionResult,
)


class Transcription:
    def __init__(self, transcriber: Transcriber, store: TranscriptStore) -> None:
        self._transcriber = transcriber
        self._store = store

    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        if not request.audio_path.is_file():
            raise TranscriptionError(f"Audio file not found: {request.audio_path}")
        transcript = self._transcriber.transcribe(request)
        if not transcript.turns:
            raise TranscriptionError("No speech was transcribed.")
        saved_path = self._store.save(request.audio_path, transcript.render())
        return TranscriptionResult(transcript, saved_path)

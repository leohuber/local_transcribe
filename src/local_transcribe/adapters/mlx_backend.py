import re
from typing import Any

from local_transcribe.domain.transcription import (
    SpeakerTurn,
    Transcript,
    TranscriptionError,
    TranscriptionRequest,
)

_SPEAKER_TAG = re.compile(r"<spk:\d+>")


def _to_transcript(result: Any) -> Transcript:
    turns: list[SpeakerTurn] = []
    for segment in getattr(result, "segments", None) or ():
        text = str(segment.get("text", "")).strip()
        if text:
            speaker = segment.get("speaker")
            turns.append(
                SpeakerTurn(int(speaker) if speaker is not None else None, text)
            )
    if not turns:
        text = _SPEAKER_TAG.sub(" ", str(getattr(result, "text", ""))).strip()
        if text:
            turns.append(SpeakerTurn(None, " ".join(text.split())))
    return Transcript(
        tuple(turns), truncated=getattr(result, "finish_reason", None) == "length"
    )


class MlxTranscriber:
    def transcribe(self, request: TranscriptionRequest) -> Transcript:
        try:
            from mlx_audio.stt import load
        except ImportError as exc:
            raise TranscriptionError(f"mlx-audio is unavailable: {exc}") from exc
        try:
            model = load(request.model, strict=True)
        except Exception as exc:
            raise TranscriptionError(
                f"Unable to load model {request.model}: {exc}"
            ) from exc
        try:
            result = model.generate(str(request.audio_path), task="saa")
        except Exception as exc:
            raise TranscriptionError(
                f"Unable to transcribe {request.audio_path}: {exc}"
            ) from exc
        return _to_transcript(result)

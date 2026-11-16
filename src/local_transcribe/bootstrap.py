from local_transcribe.application.ports import RecordingUseCase, TranscriptionUseCase


def main() -> None:
    import click

    from local_transcribe.cli.commands import create_cli

    try:
        result = create_cli(_recording, _transcription)(standalone_mode=False)
    except click.ClickException as exc:
        exc.show()
        raise SystemExit(exc.exit_code) from exc
    except click.Abort as exc:
        click.echo("Aborted!", err=True)
        raise SystemExit(1) from exc
    if isinstance(result, int) and result:
        raise SystemExit(result)


def _recording() -> RecordingUseCase:
    from local_transcribe.adapters.capture import SoundDeviceCapture
    from local_transcribe.adapters.recorder import SoundDeviceRecorder
    from local_transcribe.application.recording import Recording

    capture = SoundDeviceCapture()
    return Recording(capture, SoundDeviceRecorder(capture))


def _transcription() -> TranscriptionUseCase:
    from local_transcribe.adapters.mlx_backend import MlxTranscriber
    from local_transcribe.adapters.transcript_files import FileTranscriptStore
    from local_transcribe.application.transcription import Transcription

    return Transcription(MlxTranscriber(), FileTranscriptStore())

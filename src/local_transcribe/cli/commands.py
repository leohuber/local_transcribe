from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import click
from rich.console import Console

from local_transcribe.application.ports import RecordingUseCase, TranscriptionUseCase
from local_transcribe.cli.levels import TERMINAL_INTERVAL, LevelDisplay
from local_transcribe.domain.recording import (
    DeviceSelectionError,
    InputDevice,
    RecordingError,
    RecordingRequest,
    RecordingResult,
)
from local_transcribe.domain.transcription import (
    DEFAULT_MODEL,
    TranscriptionError,
    TranscriptionRequest,
)


def _select_device(
    prompt: str, devices: tuple[InputDevice, ...], *, other_id: int | None = None
) -> int:
    available = {device.id for device in devices}
    while True:
        device_id = click.prompt(prompt, type=int)
        if device_id not in available:
            click.echo("Choose an ID from the listed input devices.", err=True)
        elif device_id == other_id:
            click.echo("Choose a different input device.", err=True)
        else:
            return device_id


def _record_until_stopped(
    recording: RecordingUseCase, request: RecordingRequest, display: LevelDisplay
) -> RecordingResult:
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="recording") as executor:
        future = executor.submit(recording.record, request)
        try:
            while True:
                try:
                    return future.result(timeout=TERMINAL_INTERVAL)
                except TimeoutError:
                    if future.done():
                        raise
                    display.update(recording.latest_levels())
        except KeyboardInterrupt:
            recording.stop()
            return future.result()
        except BaseException:
            recording.stop()
            raise


def create_cli(
    recording_factory: Callable[[], RecordingUseCase],
    transcription_factory: Callable[[], TranscriptionUseCase],
) -> click.Group:
    @click.group(
        invoke_without_command=True,
        context_settings={"help_option_names": ["-h", "--help"]},
    )
    @click.pass_context
    def cli(context: click.Context) -> None:
        """Record and transcribe local audio on this machine.

        Run a subcommand with -h or --help for details.
        """
        if context.invoked_subcommand is None:
            click.echo("Hello from local-transcribe!")

    @cli.command()
    def record() -> None:
        """Record and mix two audio input devices into a WAV file.

        Lists input devices, prompts for two distinct device IDs, shows live
        levels, and records until Ctrl+C. The mono WAV is saved in the project
        checkout's tmp/ directory.
        """
        try:
            recording = recording_factory()
            while True:
                devices = recording.list_inputs()
                click.echo("Available input devices:")
                for device in devices:
                    click.echo(
                        f"  {device.id}: {device.name} ({device.input_channels} input channels)"
                    )
                if len(devices) < 2:
                    raise RecordingError("At least two input devices are required.")
                first = _select_device("First input device ID", devices)
                second = _select_device(
                    "Second input device ID", devices, other_id=first
                )
                click.echo("Starting recording. Press Ctrl+C to stop.")
                try:
                    selected = {device.id: device for device in devices}
                    with LevelDisplay((selected[first], selected[second])) as display:
                        result = _record_until_stopped(
                            recording, RecordingRequest(first, second), display
                        )
                except DeviceSelectionError as exc:
                    click.echo(f"Input selection changed: {exc}", err=True)
                    continue
                click.echo(f"Recording saved: {result.path}")
                return
        except RecordingError as exc:
            message = str(exc)
            if exc.incomplete_path is not None:
                message += f"\nIncomplete recording: {exc.incomplete_path}"
            raise click.ClickException(message) from exc

    @cli.command()
    @click.argument(
        "audio",
        type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    )
    @click.option(
        "--model",
        default=DEFAULT_MODEL,
        show_default=True,
        help="Hugging Face model ID or local path of a Nemotron Transcribe model.",
    )
    def transcribe(audio: Path, model: str) -> None:
        """Transcribe AUDIO (a WAV file) with speaker labels.

        Prints each speaker turn as "Speaker N: text" and saves the transcript
        as a text file in the project checkout's tmp/ directory. The model is
        downloaded on first use.
        """
        console = Console(stderr=True)
        try:
            with console.status(f"Transcribing {audio.name} with {model}..."):
                result = transcription_factory().transcribe(
                    TranscriptionRequest(audio, model)
                )
        except TranscriptionError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(result.transcript.render())
        if result.transcript.truncated:
            click.echo(
                "Warning: the model reached its output limit; "
                "the transcript may be incomplete.",
                err=True,
            )
        click.echo(f"Transcript saved: {result.saved_path}")

    return cli

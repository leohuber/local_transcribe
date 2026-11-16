# Design

## Context

The CLI is a Click group built by `cli.commands.create_cli(recording_factory)` and wired in `bootstrap.py`, which lazily constructs adapters. The architecture (`.github/instructions/architecture.instructions.md`, `.importlinter`) requires: domain/application free of Click/Rich/MLX, CLI free of MLX and adapters, adapters free of Click/Rich, MLX loaded lazily, and `--help` not importing MLX (already guarded by `tests/test_entry_points.py`).

The installed `mlx-audio` contains `mlx_audio.stt.models.nemotron_transcribe`. `mlx_audio.stt.load(model_id, strict=True)` returns a model whose `generate(path, task="saa")` resamples the file to 16 kHz mono and returns a result with `text` (containing `<spk:N>` tags), `segments` (a list of `{"speaker": int, "text": str}` or `None`), and `finish_reason` (`"stop"`/`"length"`).

Recording output is created by `adapters/recording_files.py` (`find_checkout`, `create_recording_file`), currently using `checkout / ".tmp"`.

## Goals / Non-Goals

**Goals:**
- Speaker-attributed transcription of one WAV through the existing layered architecture.
- `-h`/`--help` everywhere via one setting on the root group.
- A single place defining the project output directory name `tmp`.

**Non-Goals:**
- Word timestamps, SRT/VTT export, translation, streaming output, or speculative decoding.
- Transcribing straight after `record`, batch input, or non-WAV formats beyond what `mlx-audio` already decodes.
- Migrating existing `.tmp/` recordings.
- New automated tests (user will verify manually).

## Decisions

1. **Domain model** (`domain/transcription.py`): frozen dataclasses `TranscriptionRequest(audio_path: Path, model: str)`, `SpeakerTurn(speaker: int | None, text: str)`, `Transcript(turns: tuple[SpeakerTurn, ...], truncated: bool)`, `TranscriptionResult(transcript: Transcript, saved_path: Path)`, and `TranscriptionError(Exception)`. Plain-text rendering (`Speaker N: text`, one turn per line; unlabelled text when `speaker is None`) lives as a method/function in the domain so the CLI display and saved file are identical.
   - Alternative: pass raw text with `<spk:N>` tags to the CLI — rejected; MLX output must be translated at the adapter boundary.

2. **Ports and use case**: in `application/ports.py` add `Transcriber` (`transcribe(request) -> Transcript`) and `TranscriptStore` (`save(audio_path, text) -> Path`), plus `TranscriptionUseCase` protocol. `application/transcription.py` holds `Transcription`, which validates the input file exists, calls the transcriber, renders, and saves.

3. **MLX adapter** (`adapters/mlx_backend.py`, the name the architecture doc prescribes): `MlxTranscriber.transcribe` imports `mlx_audio.stt` inside the method, loads the model with `strict=True`, calls `generate(str(path), task="saa")`, maps `segments` to `SpeakerTurn`s (falling back to a single unlabelled turn from `text` with any `<spk:N>` tags stripped when `segments` is `None`), and sets `truncated = finish_reason == "length"`. Any exception from load/generate is wrapped in `TranscriptionError`. Model is loaded per invocation (CLI is one-shot; no cache needed).
   - Default model constant `DEFAULT_MODEL = "nativ-community/Nemotron-3.5-Transcribe-30B-A4B-EA-4bit"` lives in the domain module so the CLI can show it without importing MLX. The EA exports lack MTP/CTC heads, which only affects timestamps/speculative decoding — both non-goals.

4. **Output directory**: in `adapters/recording_files.py` introduce `OUTPUT_DIRNAME = "tmp"` and a shared `ensure_output_dir(checkout)` used by `create_recording_file` and a new `create_transcript_file(checkout, stem)` that opens `tmp/<stem>.txt` with mode `"x"`, falling back to `<stem>-<uuid8>.txt` if it exists. A `FileTranscriptStore` adapter (`adapters/transcript_files.py`) calls `find_checkout` and writes UTF-8 text, converting `RecordingError`/`OSError` into `TranscriptionError`.
   - Alternative: write the `.txt` next to the source WAV — rejected for consistency with the recording requirement that outputs stay in the checkout.

5. **CLI**: `create_cli(recording_factory, transcription_factory)`. Root group gets `context_settings={"help_option_names": ["-h", "--help"]}`, which Click propagates to subcommands. New `transcribe` command: `AUDIO` argument `click.Path(exists=True, dir_okay=False, readable=True, path_type=Path)`, `--model` option with `show_default=True`. Progress uses `rich.console.Console(stderr=True).status("Transcribing…")` so stdout contains only the transcript and saved path. A truncated transcript emits a warning on stderr. `TranscriptionError` maps to `click.ClickException`. Help texts are filled in for the group, `record`, and `transcribe`.

6. **Bootstrap**: add `_transcription()` that lazily imports `MlxTranscriber`, `FileTranscriptStore`, and `Transcription`. No new top-level module, so the import-linter layers contract is unchanged.

## Risks / Trade-offs

- [Large first download (multi-GB even for the 4-bit export) and high memory use] → Document in README; allow `--model` to pick another variant.
- [`mlx-audio` API drift in result attributes] → Adapter reads `segments`/`text`/`finish_reason` defensively with `getattr` and falls back to plain text.
- [Long recordings exceed the 16,384-token budget] → Surfaced as a truncation warning, not silently.
- [Old `.tmp/` recordings become orphaned] → Keep `/.tmp/` in `.gitignore` alongside new `/tmp/` and mention in README.
- [No new tests] → Accepted per user request; existing suite and the quality gate (ruff, pyrefly, lint-imports) still run.

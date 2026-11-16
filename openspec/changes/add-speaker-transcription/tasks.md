# Tasks

## 1. Output directory `tmp/`

- [x] 1.1 In `adapters/recording_files.py`, replace `.tmp` with an `OUTPUT_DIRNAME = "tmp"` constant and shared `ensure_output_dir(checkout)` used by `create_recording_file`; verify a recording is created under `<checkout>/tmp/`
- [x] 1.2 Update existing `.tmp` assertions in `tests/test_recording_files.py` and `tests/test_cli_record.py` to `tmp` (no new tests); verify `uv run python -m unittest discover -s tests` passes
- [x] 1.3 Add `/tmp/` to `.gitignore` while keeping `/.tmp/` ignored; verify with `git check-ignore tmp/x.wav .tmp/x.wav`

## 2. Transcription core

- [x] 2.1 Add `domain/transcription.py` with `DEFAULT_MODEL`, `TranscriptionRequest`, `SpeakerTurn`, `Transcript` (with `Speaker N: text` rendering, unlabelled fallback), `TranscriptionResult`, `TranscriptionError`; verify `uv run pyrefly check` passes
- [x] 2.2 Add `Transcriber`, `TranscriptStore`, and `TranscriptionUseCase` protocols to `application/ports.py` and the `Transcription` use case in `application/transcription.py` (validate input file, transcribe, render, save); verify `uv run lint-imports` passes

## 3. Adapters

- [x] 3.1 Add `adapters/mlx_backend.py` with `MlxTranscriber` that lazily imports `mlx_audio.stt.load`, calls `generate(path, task="saa")`, maps `segments`/`text`/`finish_reason` to domain types, and wraps failures in `TranscriptionError`; verify no module-level MLX import (`grep -n "^import mlx\|^from mlx" src/local_transcribe/adapters/mlx_backend.py` is empty)
- [x] 3.2 Add `create_transcript_file(checkout, stem)` to `recording_files.py` (exclusive create, unique fallback name) and `adapters/transcript_files.py` with `FileTranscriptStore` writing UTF-8 and converting errors to `TranscriptionError`; verify `uv run lint-imports` passes

## 4. CLI and wiring

- [x] 4.1 Set `context_settings={"help_option_names": ["-h", "--help"]}` on the root group and write help text for the group and `record`; verify `uv run local-transcribe -h` and `uv run local-transcribe record -h` print help
- [x] 4.2 Add the `transcribe` command (`AUDIO` path argument, `--model` with shown default, Rich stderr status, transcript on stdout, saved path, truncation warning, `TranscriptionError` → `ClickException`) and extend `create_cli` with a `transcription_factory`; verify `uv run local-transcribe transcribe --help` shows the default model
- [x] 4.3 Wire `_transcription()` lazily in `bootstrap.py`; verify `uv run python -m unittest tests.test_entry_points` passes (help does not import MLX)
- [x] 4.4 Update `README.md` (transcribe usage, speaker labels, default model and download size, `-h`, `tmp/` location, old `.tmp/` not migrated) and the outdated "not implemented yet" note in `.github/instructions/architecture.instructions.md`; verify documented commands match `-h` output

## 5. Integration checks

- [x] 5.1 Run the `luna_check_code_quality` gate (ruff lint/format, pyrefly, lint-imports) and `uv run python -m unittest discover -s tests`; verify all pass
- [ ] 5.2 Manual (user): record with `uv run local-transcribe record`, then `uv run local-transcribe transcribe tmp/recording-<id>.wav`; verify speaker-labelled output and a saved `tmp/*.txt`

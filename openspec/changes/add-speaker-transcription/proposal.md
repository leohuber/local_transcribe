# Proposal

## Why

`local-transcribe` can record audio but cannot transcribe it, which is the tool's purpose. The command help is also only reachable via `--help`, and recordings land in a hidden `.tmp/` directory that is easy to overlook.

## What Changes

- Add a `local-transcribe transcribe <WAV>` command that transcribes a local WAV file with speaker attribution using the Nemotron 3.5 Transcribe model through `mlx-audio`.
  - The transcript is shown in the terminal as speaker-labelled turns and saved as a text file in the project `tmp/` directory.
  - The model is downloaded/loaded lazily on first use; a `--model` option overrides the default model.
- Make help available through both `-h` and `--help` on the root command and every subcommand, with descriptive help text for each command and option.
- **BREAKING** (location only): new recordings are written to the project checkout's `tmp/` directory instead of `.tmp/`. Existing files in `.tmp/` are not moved.

Assumptions (the user declined to answer clarifying questions):
- "`--h --help`" is interpreted as the conventional `-h` short flag plus `--help`.
- Input is a required WAV path argument; no automatic selection of the latest recording.
- Default model: `nativ-community/Nemotron-3.5-Transcribe-30B-A4B-EA-4bit` (MLX export, supports speaker attribution, smallest download).
- No new automated tests are added; the user will verify manually. Existing tests that hard-code `.tmp` are updated so the current suite keeps passing.

## Capabilities

### New Capabilities
- `speaker-transcription`: Transcribing a local WAV file into speaker-attributed text, displaying it, and saving it to the project `tmp/` directory.
- `cli-help`: Discoverable help for the root command and all subcommands via `-h` and `--help`.

### Modified Capabilities
- `dual-input-recording`: Recordings are stored in the project checkout's `tmp/` directory instead of `.tmp/`.

## Impact

- Code: `cli/commands.py` (new command, help settings), `bootstrap.py` (wire transcription), new domain/application/adapter modules for transcription, `adapters/recording_files.py` (directory rename).
- Dependencies: uses the already-installed `mlx-audio` (`mlx_audio.stt.load`, `nemotron_transcribe` model); no manifest change. First run downloads model weights (several GB) from Hugging Face.
- Files/docs: `.gitignore` (ignore `tmp/`), `README.md`, existing tests asserting `.tmp` paths.

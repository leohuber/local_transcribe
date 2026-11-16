# local-transcribe

Record two local audio inputs into a single mixed WAV and transcribe WAV files
on-device with speaker labels.

Every command shows its help with `-h` or `--help`, for example
`uv run local-transcribe transcribe -h`.

## Prerequisites

- Python 3.14 or newer and [uv](https://docs.astral.sh/uv/).
- Two distinct, input-capable audio devices and permission for the terminal or
  IDE to use the microphone. On macOS, check **Privacy & Security > Microphone**.
- PortAudio for `sounddevice`. Its Python package normally bundles PortAudio on
  macOS and Windows; on Linux, install the system PortAudio library (often
  named `libportaudio2`) if it is not already available.

## Record

From the project checkout, install the dependencies and start recording:

```sh
uv sync
uv run local-transcribe record
```

The command lists input device IDs, names, and channel counts. Enter two
different listed IDs; invalid or duplicate selections can be retried. Device IDs
may change when devices are connected or disconnected.

While recording, two labeled bars show each device's input level before
downmixing. In a terminal they update in place; redirected output receives
throttled plain-text updates, for example:

```text
Levels: 2: Mic [########------------] | 5: Loopback [--------------------]
```

Press **Ctrl+C** to stop both inputs and finalize the WAV. The command then
prints its location:

```text
Recording saved: /path/to/checkout/tmp/recording-<unique-id>.wav
```

The source checkout is preferred when discoverable. Otherwise, the current
directory and its ancestors are searched for this project's `pyproject.toml`
and `src/local_transcribe` package. If no checkout is found, recording fails
rather than writing elsewhere. Generated `tmp/` files are ignored by Git.
Recordings made by earlier versions remain in `.tmp/` and are not moved.

## Transcribe

Transcribe a WAV file with speaker attribution using
[Nemotron 3.5 Transcribe](https://github.com/Neywa-Labs/mlx-audio/blob/main/mlx_audio/stt/models/nemotron_transcribe/README.md)
through `mlx-audio` (Apple silicon):

```sh
uv run local-transcribe transcribe tmp/recording-<unique-id>.wav
```

The transcript is printed with one speaker turn per line and saved as
`tmp/<wav-name>.txt` (a unique suffix is added if that file exists):

```text
Speaker 0: Thanks for joining.
Speaker 1: Happy to be here.
Transcript saved: /path/to/checkout/tmp/recording-<unique-id>.txt
```

The default model is `nativ-community/Nemotron-3.5-Transcribe-30B-A4B-EA-4bit`.
It is downloaded from Hugging Face on first use, which takes several GB of disk
space and needs a correspondingly large amount of memory. Choose another
compatible model with `--model <id-or-path>`. Up to eight speakers are
distinguished; speaker numbers are local to each recording. If the model reaches
its output limit, a warning says the transcript may be incomplete.

## Limitations

Each input's channels are averaged to mono, synchronized, and mixed at equal
gain into 16-bit PCM. The first input's capture rate determines the WAV rate;
clock correction depends on usable device timestamps. Output-only devices are
not listed: capturing system output requires a separate virtual input device.

Device failures, buffer overflow, storage errors, unusable timing, and the WAV
format's approximately 4 GiB size limit stop recording with an error. Any
retained partial file is reported as `Incomplete recording:`. Forced process or
system termination can leave an unfinalized WAV.
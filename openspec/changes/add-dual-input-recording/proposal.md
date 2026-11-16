# Proposal

## Why

The application cannot yet capture audio. Recording and mixing two local inputs produces a single WAV that can later be used for transcription.

## What Changes

- Add a `local-transcribe record` console command that lists input-capable devices and prompts for two distinct device IDs.
- Capture both inputs concurrently using sounddevice, downmix each to mono, synchronize and resample them as needed, and combine them at equal gain.
- Show an independently updating, labeled input-level diagram for each selected device while recording.
- Stream the mixed audio to a uniquely named WAV in the checkout's `.tmp/` directory until Ctrl+C, then finalize and report the file.
- Report selection, device, capture, and filesystem errors clearly, and preserve the existing no-argument greeting and package entry-point compatibility.
- Ignore generated recordings in Git and document setup, invocation, limitations, and the output location.

## Capabilities

### New Capabilities

- `dual-input-recording`: Interactive selection, live input-level display, and synchronized recording of two audio inputs into a mixed WAV file.

### Modified Capabilities

None.

## Impact

- Adds a Click/Rich command, application recording use case and ports, sounddevice and WAV filesystem adapters, and bootstrap wiring.
- Adds sounddevice and any necessary resampling dependencies; updates the dependency lockfile, tests, documentation, and `.gitignore`.
- Requires accessible PortAudio input devices and permission to capture audio. This change does not capture output-only devices or implement transcription.

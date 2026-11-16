# Tasks

## 1. Dependencies and recording contracts

- [x] 1.1 Add sounddevice and direct dependencies needed for streaming variable-ratio resampling, update `uv.lock`, and verify they install and work with the project's Python version.
- [x] 1.2 Define recording device, request, result, and error domain types plus application ports and use cases; verify device selection and error propagation with fake ports without loading audio or MLX frameworks.

## 2. Device capture and synchronization

- [x] 2.1 Implement sounddevice input enumeration, configuration, and concurrent stream lifecycle; verify input filtering, correct IDs, unsupported devices, and partial-start cleanup with simulated devices.
- [x] 2.2 Implement bounded callback queues and multichannel-to-mono conversion; verify channel averaging, overflow detection, and bounded memory with simulated callbacks.
- [x] 2.3 Implement common-timeline alignment and stateful adaptive resampling; verify differing rates, startup offsets, callback jitter, and sustained clock drift in both directions against synthetic known-timeline signals.
- [x] 2.4 Mix aligned mono streams at equal gain and verify both-source, single-silent-source, and PCM conversion cases with deterministic audio samples.
- [x] 2.5 Publish bounded per-device RMS level snapshots before downmixing and mixing; verify silence, differing input levels, opposite-phase channels, and slow consumers without blocking capture.

## 3. WAV persistence and lifecycle

- [x] 3.1 Resolve the project checkout, create its `.tmp/`, ignore that directory in Git, and exclusively create collision-resistant WAV files; verify checkout discovery, missing checkout, existing files, and filesystem failures.
- [x] 3.2 Stream mono PCM WAV output and handle Ctrl+C, stream termination, overflow, write failure, and WAV size limits; verify playable finalized output, resource cleanup, and clearly identified incomplete files with a standard WAV reader.

## 4. CLI and documentation

- [x] 4.1 Add and wire `local-transcribe record`, list input IDs/names/channels, and prompt for two distinct valid IDs; verify the interaction, retry behavior, insufficient devices, and failure exit codes with Click's `CliRunner` and fakes.
- [x] 4.2 Preserve the existing no-argument greeting and inert package import, and verify command, Python entry points, `--help`, and recording do not initialize MLX or access devices unnecessarily.
- [x] 4.3 Document sounddevice/PortAudio and permission prerequisites, the recording command, live level meters, checkout resolution, Ctrl+C, output location, and limitations; verify the documented invocation and output match the CLI behavior.
- [x] 4.4 Render labeled live bars independently for both inputs and throttled plain-text updates for redirected output; verify speech/silence transitions, device labels, clean shutdown, and nonblocking behavior with fakes.

## 5. Integration checks

- [x] 5.1 Run the full test suite and the repository quality gate (Ruff lint and format, Pyrefly, and import-linter); resolve any failures introduced by the change.
- [ ] 5.2 When two input devices are available, perform a manual recording smoke test covering selection, independent live levels, simultaneous capture, Ctrl+C, and playback; otherwise record the hardware limitation in the implementation handoff.

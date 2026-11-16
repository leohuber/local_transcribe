# Design

## Context

The project currently has an inert package root, a bootstrap entry point that prints a greeting, and empty application, domain, CLI, and adapter packages. Click and Rich are dependencies, but no CLI or audio capture exists. Import-linter enforces a ports-and-adapters direction with CLI and adapters as independent siblings. See the proposal and recording spec for scope and observable behavior.

## Goals / Non-Goals

**Goals:**

- Support inputs with different nominal rates and independent clocks without recording-length-dependent memory growth.
- Keep audio, filesystem, and presentation details outside the application core, and preserve the existing no-argument entry points.
- Make failure and interruption handling explicit, testable without physical devices.

**Non-Goals:**

- Capturing output-only devices, configuring virtual loopbacks, transcription, or preserving separate source tracks.
- Guaranteeing capture when the operating system denies access, a device cannot be opened, or the machine cannot keep up.

## Decisions

### CLI and dependency boundaries

Introduce a Click command group with a `record` subcommand; retain the greeting when the group is invoked without a subcommand. The CLI uses injected application ports/use cases for device listing and recording, while bootstrap wires concrete implementations. Device metadata, requests, results, and errors use domain types; application ports live in `application/ports.py`. The audio adapter owns sounddevice, audio arrays, resampling, mixing, and WAV writing; no audio arrays or Click/Rich objects cross into the core. Keep package-root import inert and do not load MLX for recording or help.

This keeps presentation and adapters independent and avoids coupling the core to PortAudio. Putting device enumeration or audio callbacks directly in the CLI would violate the existing boundary.

### Capture and alignment

Open two independent input streams at supported device rates, using a supported capture format and channel count for each. Read device metadata and revalidate the user's selections before capture. Downmix all captured channels of each device by arithmetic mean. Use an output rate chosen deterministically from the first input's supported capture rate; convert the other input as needed.

Callbacks only transfer bounded audio blocks, timing metadata, and status flags into per-device bounded queues. A worker establishes a common monotonic timeline using each stream's ADC and callback timestamps calibrated to the host clock; it accounts for startup offsets, uses stateful sample-rate conversion, and adapts the conversion ratio gradually using clock/timestamp estimates and queue occupancy. Preserve resampler state between blocks and mix time-aligned samples at `0.5 * A + 0.5 * B`, clipping only as necessary for PCM conversion. Keep queue sizes and startup/latency waits bounded; do not insert silence merely because a callback has not arrived yet. If usable timing cannot be established or sustained without loss, stop and report failure rather than silently drifting or dropping samples.

The implementation must use a streaming variable-ratio resampling method whose Python 3.14-compatible dependencies and behavior are verified, and declare direct dependencies explicitly. A shared nominal sample rate alone does not correct independent device clocks, and whole-recording resampling would require unbounded storage or delay output until capture stops.

### Live input levels

Compute each device's level from its captured samples before downmixing and mixing, using RMS across channels so opposite-phase channels cannot hide input activity. The adapter publishes bounded, replaceable scalar level snapshots identified by device; domain values and application ports carry these snapshots to the CLI without exposing audio arrays or presentation objects. Meter updates are best-effort and must never block audio callbacks or the recording worker; discard stale meter snapshots rather than audio.

The CLI renders two labeled horizontal bars in place using Rich while recording, refreshing at a bounded rate with modest smoothing so speech is visible and silence falls back to the baseline. For redirected output, emit throttled plain-text level updates without terminal control sequences. Stop the live display cleanly before reporting a finalized recording or an error. Displaying the mixed signal would hide which input is active, and opening additional streams solely for metering could prevent devices from being recorded.

### Output and lifecycle

Resolve the checkout from the editable source location or the current directory and its ancestors, using recognizable project markers; if no matching checkout is found, fail rather than falling back to another output location. Prefer the source checkout when discoverable, and document resolution for installed invocations. Create `.tmp/` as needed and exclusively create a collision-resistant file. Stream a standard mono PCM WAV incrementally, using a single writer outside the callbacks. Ignore `.tmp/` in Git.

Start and stop both streams as a coordinated session. Ctrl+C signals shutdown, stops callbacks, processes already captured data that can be aligned, and finalizes the header before reporting success. On startup or runtime failure, close all acquired resources; if a partial file remains, identify it as incomplete and report a nonzero outcome. Treat callback overflow, queue overflow, missing timestamps, unexpected input termination, and writer errors as failures. Handle the WAV format's size limit explicitly instead of producing a corrupt file.

An unbounded queue or writing from callbacks risks memory growth or callback underruns; temporary in-memory whole-recording storage also fails for long recordings.

### Verification

Use fake port implementations for application and CLI tests, and simulated audio callbacks and clocks for adapter tests. Exercise unequal rates, startup offsets, and sustained synthetic clock drift in both directions; verify alignment against a known common timeline, bounded queues, and audible-duration preservation. Include invalid device IDs, multi-channel downmix, independent input-level snapshots and displays, equal-gain math, interrupt finalization, resource cleanup, errors, collisions, and checkout resolution. Verify slow or redirected display output cannot block recording. WAV tests read the resulting file through a standard WAV reader. Preserve and extend entry-point and architecture tests; run the repository's full test and quality gates. Real hardware and permissions are a manual smoke test, not a requirement for automated tests.

## Risks / Trade-offs

- **Unrelated device clocks and callback jitter** -> Estimate relative timing using ADC timestamps and smoothed host-clock calibration, and test sustained drift; exact alignment is limited by host API timestamp accuracy.
- **Exclusive device access or unsupported formats** -> Use supported per-device capture configurations and report errors; never silently substitute a different input.
- **Slow disk, scheduling delays, or long recordings** -> Bounded buffers, explicit overflow/size-limit errors, and a finalized partial file where possible prevent silent data loss and unbounded memory.
- **Running an installed command outside a checkout** -> Resolve only a recognized checkout and explain how to run from one if it cannot be located.
- **Abrupt process or system termination** -> Ctrl+C is handled, but forced termination may leave an unfinalized WAV.

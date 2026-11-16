# Spec Delta

## Purpose

Enable users to capture and combine two local audio inputs into a reusable WAV recording.

## ADDED Requirements

### Requirement: List input devices
The `local-transcribe record` command SHALL list available audio input devices with their selectable IDs, names, and input channel counts, and SHALL exclude output-only devices.

#### Scenario: Mixed device inventory
- **WHEN** the system finds both input-capable and output-only devices
- **THEN** the command lists every input-capable device with its ID, name, and input channel count and omits the output-only devices

#### Scenario: Too few inputs
- **WHEN** fewer than two input-capable devices are available
- **THEN** the command explains that two inputs are required and exits without recording

### Requirement: Select two distinct inputs
The command SHALL prompt for two distinct listed input device IDs and reject invalid, output-only, unavailable, or duplicate selections without starting a recording.

#### Scenario: Select two inputs
- **WHEN** the user enters two distinct IDs from the input device list
- **THEN** the command starts recording those two devices

#### Scenario: Invalid selection
- **WHEN** a selected ID is malformed, not listed, output-only, unavailable, or duplicates the other selection
- **THEN** the command explains the problem and allows the selection to be corrected

### Requirement: Show live levels for each input
During recording, the command SHALL display an independently updated level diagram for each selected device, labeled with its device ID and name, based on that device's input before mixing.

#### Scenario: One device receives speech
- **WHEN** one selected input receives speech and the other is silent
- **THEN** the speaking device's level diagram rises while the silent device's diagram remains low

#### Scenario: Speech stops
- **WHEN** an input becomes silent after receiving speech
- **THEN** its level diagram falls back toward silence

#### Scenario: Both devices receive audio
- **WHEN** both inputs receive audio at different levels
- **THEN** their diagrams update separately to reflect their respective input levels

#### Scenario: Redirected output
- **WHEN** recording output is redirected instead of displayed in an interactive terminal
- **THEN** the command emits throttled plain-text level updates without terminal control sequences

### Requirement: Mix simultaneous inputs
The system SHALL capture both selected inputs concurrently, downmix each input's channels to mono, and produce one mono stream using equal gain for each source: `0.5 * A + 0.5 * B`.

#### Scenario: Both sources contribute
- **WHEN** the selected devices produce audio concurrently
- **THEN** the output contains both mono-downmixed sources at equal gain

#### Scenario: One source is silent
- **WHEN** one input is silent while the other produces audio
- **THEN** the recording contains the active source at its equal-gain level

### Requirement: Synchronize different input clocks
The system SHALL convert input sample rates as necessary and correct independent clock drift so that the two sources remain aligned on one output timeline during recording.

#### Scenario: Different sample rates
- **WHEN** two selected devices capture at different supported sample rates
- **THEN** their audio is converted to the output timeline and mixed without changing its playback speed or pitch

#### Scenario: Long-running clock drift
- **WHEN** the devices' clocks differ slightly during a sustained recording
- **THEN** their streams remain synchronized rather than accumulating increasing timing offset

### Requirement: Stream recording to the project checkout
The system SHALL write the mono WAV incrementally to a uniquely named file under the project checkout's `.tmp/` directory, creating that directory if necessary and never overwriting an existing recording.

#### Scenario: Save a recording
- **WHEN** recording starts with a discoverable project checkout
- **THEN** the system creates a WAV in that checkout's `.tmp/` and writes audio without retaining the entire recording in memory

#### Scenario: Project checkout unavailable
- **WHEN** the project checkout cannot be located
- **THEN** the command reports the problem and does not write a recording to another directory

### Requirement: Stop and finalize on interrupt
The command SHALL record until the user presses Ctrl+C, stop both capture streams, finalize the WAV, and display its location.

#### Scenario: User stops a recording
- **WHEN** the user presses Ctrl+C during recording
- **THEN** the command closes the streams and reports a playable finalized WAV at its project `.tmp/` path

### Requirement: Report capture and storage failures
The command SHALL report device, permission, synchronization, buffer-overflow, and filesystem failures without presenting an incomplete recording as successful.

#### Scenario: Startup fails
- **WHEN** either selected input cannot be opened or the output cannot be created
- **THEN** the command releases acquired resources, reports the failure, and exits unsuccessfully

#### Scenario: Recording fails after starting
- **WHEN** an input fails, audio is lost because a buffer overflows, or output writing fails during capture
- **THEN** the command stops both streams, reports the failure, and identifies any retained partial WAV as incomplete

### Requirement: Preserve existing entry-point compatibility
The no-argument entry points SHALL retain their existing greeting, and importing the package SHALL remain free of application initialization and audio-device access.

#### Scenario: Existing invocation
- **WHEN** the installed command or existing Python entry point runs without arguments
- **THEN** it prints the existing greeting instead of starting a recording

#### Scenario: Import without recording
- **WHEN** the package is imported
- **THEN** it does not initialize audio capture or access input devices

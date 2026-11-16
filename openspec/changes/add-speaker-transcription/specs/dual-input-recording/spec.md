# Spec Delta

## MODIFIED Requirements

### Requirement: Stream recording to the project checkout
The system SHALL write the mono WAV incrementally to a uniquely named file under the project checkout's `tmp/` directory, creating that directory if necessary and never overwriting an existing recording.

#### Scenario: Save a recording
- **WHEN** recording starts with a discoverable project checkout
- **THEN** the system creates a WAV in that checkout's `tmp/` and writes audio without retaining the entire recording in memory

#### Scenario: Project checkout unavailable
- **WHEN** the project checkout cannot be located
- **THEN** the command reports the problem and does not write a recording to another directory

### Requirement: Stop and finalize on interrupt
The command SHALL record until the user presses Ctrl+C, stop both capture streams, finalize the WAV, and display its location.

#### Scenario: User stops a recording
- **WHEN** the user presses Ctrl+C during recording
- **THEN** the command closes the streams and reports a playable finalized WAV at its project `tmp/` path

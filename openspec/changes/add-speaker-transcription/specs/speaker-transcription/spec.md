# Spec Delta

## Purpose

Turn a local WAV recording into a speaker-attributed text transcript that is shown to the user and saved in the project checkout.

## ADDED Requirements

### Requirement: Transcribe a WAV file
The `local-transcribe transcribe` command SHALL accept the path of one existing local WAV file and transcribe its speech in the spoken language using an on-device speech model.

#### Scenario: Transcribe a recording
- **WHEN** the user runs `local-transcribe transcribe <path>` with a readable WAV file
- **THEN** the command transcribes the file and exits successfully

#### Scenario: Missing or invalid input
- **WHEN** the path does not exist, is a directory, or is not readable audio
- **THEN** the command reports the problem and exits unsuccessfully without writing a transcript

### Requirement: Attribute speakers
The transcript SHALL attribute each spoken turn to a speaker label, distinguishing up to eight speakers within one recording.

#### Scenario: Conversation with several speakers
- **WHEN** the recording contains speech from multiple people
- **THEN** each turn in the transcript is prefixed with a speaker label such as `Speaker 0:` and `Speaker 1:`

#### Scenario: No speaker turns detected
- **WHEN** the model returns text without speaker turns
- **THEN** the command shows the text without speaker labels instead of failing

### Requirement: Select the transcription model
The command SHALL use a documented default model and SHALL let the user choose another compatible model with a `--model` option.

#### Scenario: Default model
- **WHEN** the user omits `--model`
- **THEN** the default model is used, downloading it first if it is not cached

#### Scenario: Custom model
- **WHEN** the user passes `--model <id-or-path>`
- **THEN** that model is loaded instead, and a load failure is reported as an error

### Requirement: Show progress and the transcript
The command SHALL indicate progress while the model loads and the audio is transcribed, then print the speaker-attributed transcript to standard output.

#### Scenario: Interactive run
- **WHEN** transcription is in progress
- **THEN** the user sees a progress indication, followed by the transcript once complete

### Requirement: Save the transcript to the project
The command SHALL save the transcript as a UTF-8 text file in the project checkout's `tmp/` directory, named after the WAV file, never overwriting an existing file, and SHALL print the saved path.

#### Scenario: Save transcript
- **WHEN** transcription succeeds
- **THEN** a new `.txt` file containing the displayed transcript is created in `tmp/` and its path is printed

#### Scenario: Project checkout unavailable
- **WHEN** the project checkout cannot be located or the file cannot be written
- **THEN** the command reports the problem and exits unsuccessfully

### Requirement: Flag truncated transcripts
The command SHALL warn when the model stopped because it reached its output length limit, since the transcript may be incomplete.

#### Scenario: Output limit reached
- **WHEN** the model reports that generation ended at the token limit
- **THEN** the transcript is still shown and saved, and a warning states it may be incomplete

### Requirement: Keep help and import free of model loading
Showing help or importing the package SHALL NOT load the speech model or its ML framework.

#### Scenario: Help for transcribe
- **WHEN** the user runs `local-transcribe transcribe --help`
- **THEN** help is printed without loading the model

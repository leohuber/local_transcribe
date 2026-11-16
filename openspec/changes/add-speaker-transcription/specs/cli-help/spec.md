# Spec Delta

## Purpose

Make the command-line interface self-documenting so users can discover commands, arguments, and options from the terminal.

## ADDED Requirements

### Requirement: Short and long help flags
The root `local-transcribe` command and every subcommand SHALL print their help and exit successfully when invoked with either `-h` or `--help`, without performing their action.

#### Scenario: Root help
- **WHEN** the user runs `local-transcribe -h` or `local-transcribe --help`
- **THEN** usage, a description, and the available subcommands are printed

#### Scenario: Subcommand help
- **WHEN** the user runs `local-transcribe record -h` or `local-transcribe transcribe --help`
- **THEN** that subcommand's usage, description, arguments, and options are printed and no recording or transcription starts

### Requirement: Descriptive help text
Each command, argument, and option SHALL have a concise description in its help output, including default values for options that have them.

#### Scenario: Option defaults visible
- **WHEN** the user views `local-transcribe transcribe --help`
- **THEN** the `--model` option is described and its default model is shown

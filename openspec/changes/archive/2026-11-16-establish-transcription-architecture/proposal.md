# Proposal

## Why

The project currently contains only a greeting and has no enforced dependency boundaries. Establishing a small reusable-core architecture now will keep future transcription work independent of the CLI and MLX while avoiding a plugin framework.

## What Changes

- Establish the documented domain, application, adapter, CLI, and composition-root boundaries as a minimal package structure.
- Add import-linter contracts for dependency direction and framework isolation, and align the GitHub architecture instructions with the verified configuration.
- Move the greeting implementation to the composition root without changing its output, retaining the existing package-root callable as a lazy compatibility forwarder.
- Do not implement transcription, output formats, or new CLI behavior in this change.

## Capabilities

### New Capabilities

None. This is a structure and tooling change; it introduces no new user-facing capability.

### Modified Capabilities

None.

## Impact

- `src/local_transcribe/` and the console entry point in `pyproject.toml`.
- A root import-linter configuration and `.github/instructions/architecture.instructions.md`.
- Focused architecture and entry-point checks, using the existing development tooling. No new runtime dependencies are anticipated.

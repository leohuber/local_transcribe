---
applyTo: "**/*.py"
---

## After Code Changes

After code changes and before finishing up work, run the following commands to verify that the code is correct and consistent with the repository's standards:

* Run relevant tests with the project's uv-managed environment. At the end run full testsuite to ensure all tests pass. If there are violations, fix them and rerun until no errors remain.
* Run `uv run ruff check src/local_transcribe` and `uv run ruff format --check src/local_transcribe` to check lint and formatting. If there are violations, fix them and rerun until no errors remain.
* Run `uv run pyrefly check` to check for type violations. If there are violations, fix them and rerun until no errors remain.
* Run `uv run lint-imports` to check import boundaries. If there are violations, fix them and rerun until no errors remain.

Use the skill `check_code_quality` to run all of the above in one command and get a summary report.

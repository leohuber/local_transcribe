# Tasks

## 1. Package foundation and compatibility

- [x] 1.1 Create the four boundary packages and `bootstrap.py`, migrate the greeting and console-script target, retain a lazy package-root `main()` forwarder, and remove the empty `main.py`; verify the installed command and both callables still emit the original greeting.
- [x] 1.2 Add focused tests for the command, both entry points, and a fresh-process package import that does not load bootstrap, subpackages, or MLX; run those tests.

## 2. Dependency contracts and guidance

- [x] 2.1 Add the exhaustive layers and external-framework isolation contracts from the design; verify `uv run lint-imports` succeeds on the actual package without ignores.
- [x] 2.2 Verify contracts against isolated temporary fixtures: allowed inward imports succeed; direct and indirect reversed or sibling imports, prohibited frameworks, and undeclared top-level modules fail. Clean up the fixtures and confirm the real package remains unchanged.
- [x] 2.3 Update `.github/instructions/architecture.instructions.md` to distinguish present structure from future examples, document the lazy compatibility forwarder and unchanged greeting, and match the verified contracts; review it against the implemented configuration.

## 3. Integration checks

- [x] 3.1 Run the focused and full available test suites, `uv run ruff check src/local_transcribe`, `uv run ruff format --check src/local_transcribe`, `uv run pyrefly check`, and `uv run lint-imports`; resolve regressions attributable to this change.

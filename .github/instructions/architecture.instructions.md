---
applyTo: "src/local_transcribe/**/*.py"
---

# Architecture: local_transcribe

`local_transcribe` currently prints a greeting. Transcription and a Click CLI are not implemented yet. The intended application uses Click and Rich to transcribe local audio with `mlx_audio`, using a small **ports-and-adapters** architecture: a reusable core with no knowledge of Click, Rich, or MLX, plus thin adapters and one composition root. Do not turn this into a plugin framework.

## Current foundation

```text
src/local_transcribe/
    __init__.py          # Inert at import; main() lazily forwards to bootstrap
    bootstrap.py         # Composition root; currently prints the greeting
    cli/__init__.py
    application/__init__.py
    domain/__init__.py
    adapters/__init__.py
```

The installed `local-transcribe` command and both `local_transcribe.main()` and `local_transcribe.bootstrap.main()` print `Hello from local-transcribe!`.

## Intended expansion

When features require them, `cli` can contain commands and presentation, `application` can contain ports and transcription use cases, `domain` can contain models and errors, and `adapters` can contain MLX and transcript-export implementations. These are future examples, not implemented features or a commitment to particular output formats.

Keep the package boundaries. Add files inside a package only when there is real content for them. Do not create empty abstractions or generic `utils`, `common`, or `helpers` packages.

## Responsibilities

| Module        | Owns                                                                  | Must not contain                                     |
|---------------|-----------------------------------------------------------------------|------------------------------------------------------|
| `domain`      | Immutable value objects and domain errors in plain Python             | I/O, Click/Rich/MLX, or imports from other layers    |
| `application` | Use cases and the `Protocol` ports they depend on                     | Concrete adapters, Click/Rich/MLX                    |
| `adapters`    | Implementations of application ports for MLX, the filesystem, and formats | Click/Rich, CLI concerns, and imports from `cli`     |
| `cli`         | Argument parsing, user-facing output, and exit-code mapping           | MLX imports, concrete adapters, or business logic    |
| `bootstrap`   | Instantiating adapters and injecting them into use cases and the CLI  | Business logic                                       |

## Dependency direction

Arrows show dependency direction, not an exhaustive list of permitted imports or runtime call flow.

```text
              bootstrap
              /       \
             v         v
            cli     adapters
             \         /
              v       v
              application
                   |
                   v
                 domain
```

- `cli` and `adapters` are siblings. They must never import each other, directly or indirectly.
- `application` defines the ports it needs. Adapters implement them structurally through `typing.Protocol` and receive dependencies from `bootstrap`. The application never imports an adapter.
- `bootstrap` is the only place where concrete adapters are connected to the application and CLI.

## Rules

- **Ports live in `application/ports.py`**, and shared value objects live in `domain`. Ports accept and return domain types only.
- **Translate at the boundary:** MLX objects, numpy arrays, and model results are converted into domain models inside `adapters/mlx_backend.py`. They never leave the adapter.
- **Click and Rich objects never cross into the core.** The CLI converts arguments into domain requests and maps domain errors to messages and exit codes.
- **Load MLX models lazily** when transcription starts, never at import time. Once the CLI exists, `local-transcribe --help` must not load MLX or a model.
- **Keep the package root inert at import time:** `src/local_transcribe/__init__.py` must not load bootstrap, subpackages, or MLX when imported. Its compatibility `main()` may lazily import and delegate to `bootstrap.main`, but must not assemble dependencies.
- **Entry point:** `[project.scripts]` points to `local_transcribe.bootstrap:main`. Preserve the package-root `main()` forwarder for compatibility.
- **Testing:** test the application with fake port implementations without loading MLX. Test adapters separately against their external integrations. Test the CLI with Click's `CliRunner` and faked use cases.
- **Fix boundary violations by moving responsibilities**, not by adding `ignore_imports` entries or local workaround imports.

## Import-linter contracts

The contracts belong in `.importlinter` at the repository root and are checked with `uv run lint-imports`, which is part of the `check_code_quality` skill.

```ini
[importlinter]
root_package = local_transcribe
include_external_packages = True

[importlinter:contract:layers]
name = Dependency direction
type = layers
containers =
    local_transcribe
layers =
    bootstrap
    cli | adapters
    application
    domain
exhaustive = true

[importlinter:contract:core-framework-isolation]
name = Core is free of CLI and MLX frameworks
type = forbidden
source_modules =
    local_transcribe.application
    local_transcribe.domain
forbidden_modules =
    click
    rich
    mlx_audio
    mlx

[importlinter:contract:cli-mlx-isolation]
name = CLI does not touch MLX
type = forbidden
source_modules =
    local_transcribe.cli
forbidden_modules =
    mlx_audio
    mlx

[importlinter:contract:adapter-presentation-isolation]
name = Adapters do not touch presentation
type = forbidden
source_modules =
    local_transcribe.adapters
forbidden_modules =
    click
    rich
```

Contract notes:

- `cli | adapters` declares independent sibling layers. Neither may import the other, including through indirect imports.
- `exhaustive = true` requires every top-level module under `local_transcribe` to be listed. When you add a new top-level module, place it deliberately in the layers contract.
- `include_external_packages = True` is required for the `forbidden` contracts on third-party packages.
- Import-linter checks static imports, including imports inside functions. The root forwarder therefore creates a static edge to `bootstrap`; lower layers should import the appropriate layer directly rather than through the package root.
- Import-linter cannot detect dynamic imports or import-time side effects, so the lazy-loading and inert-root rules above still need tests and review.

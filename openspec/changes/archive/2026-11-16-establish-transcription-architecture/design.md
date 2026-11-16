# Design

## Context

The package root currently exports `main()`, which prints a greeting; `main.py` is empty, and the console script targets `local_transcribe:main`. Import-linter is already a development dependency, but no project contract exists. The architecture instructions describe the intended structure rather than the current implementation.

## Goals / Non-Goals

**Goals:**

- Make dependency boundaries enforceable before feature code is added.
- Keep the installed command's existing greeting unchanged and the package root inert.
- Make architecture instructions accurately distinguish the foundation from future functionality.

**Non-Goals:**

- Design a complete transcription API, implement MLX inference or export formats, or introduce a plugin system.
- Add a Click interface, including `--help`, before there is a separate CLI feature to implement.

## Decisions

### Package boundaries and composition

Create `domain`, `application`, `adapters`, and `cli` packages plus `bootstrap.py`. `domain` contains framework-independent concepts; `application` owns use cases and any ports they need; `adapters` implements those ports; `cli` translates user input and output; `bootstrap` is the composition root. The current greeting lives in `bootstrap.main`, with the console entry point adjusted accordingly. Keep package initializers free of import-time side effects and create no speculative models, ports, use cases, or adapters merely to populate the packages. Remove the empty placeholder `main.py` when migrating the entry point so it does not become an undeclared top-level layer.

Preserve `local_transcribe.main()` as a compatibility forwarder that imports `bootstrap.main` only when called. This is a narrow exception to a completely empty root: importing the package must not load the composition root, any subpackage, or MLX, and the forwarder must not assemble dependencies itself. Removing the callable would needlessly break an existing public import. The alternative of putting everything under the CLI would couple future orchestration to presentation and MLX.

### Enforce inward dependencies

Use the repository-root `.importlinter` with `local_transcribe` as the root, external-package analysis enabled, and an exhaustive layers contract with `bootstrap`, independent siblings `cli | adapters`, `application`, and `domain` in descending order. Add forbidden contracts isolating the core from `click`, `rich`, `mlx_audio`, and `mlx`; the CLI from MLX; and adapters from Click and Rich. No ignores should be used to mask violations. Verify that the installed import-linter version actually enforces the intended direct and indirect restrictions, including sibling isolation and undeclared top-level modules, rather than assuming the documented snippet is correct.

The alternative of relying solely on review cannot reliably catch architectural drift. The contracts govern static imports, not dynamic imports, runtime dependency injection, side effects, or external objects crossing interfaces; those remain review and test concerns.

### Future implementation guidance

Retain the architecture instruction file as the source of guidance for subsequent feature work: ports belong to the application, domain objects cross boundaries, MLX-specific objects stay in the adapter, and MLX model loading must be lazy. The future CLI should be testable with fake use cases, and application orchestration with fake ports, without loading MLX. Treat its example files, CLI behavior, model types, and output formats as future examples rather than requirements to implement now. Keep the documented contracts synchronized with the actual configuration.

## Risks / Trade-offs

- [Empty boundary packages may appear premature] -> Create only package initializers required by the contracts; defer internal abstractions until real features need them.
- [A contract may pass without testing intended restrictions] -> Exercise negative examples for each boundary and a permitted dependency, including an indirect dependency, using isolated temporary fixtures.
- [Static analysis misses dynamic imports and runtime behavior] -> Keep root imports inert and cover the entry point and import-time MLX isolation separately.
- [The compatibility forwarder could become a hidden composition root] -> Restrict it to a lazy delegation and verify that importing the package alone does not load bootstrap or MLX.

## Migration Plan

1. Establish the packages and composition root, migrate the greeting, and update the script target.
2. Add and verify contracts, then reconcile the architecture instructions with the resulting configuration.
3. Run focused boundary and entry-point checks and the repository quality gate. If rolling back, revert the entry-point target, package structure, configuration, and documentation together.

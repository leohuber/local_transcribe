import tomllib
from pathlib import Path
from typing import BinaryIO, TextIO
from uuid import uuid4

from local_transcribe.domain.recording import RecordingError

OUTPUT_DIRNAME = "tmp"


def _is_checkout(path: Path) -> bool:
    if not (path / "src" / "local_transcribe" / "__init__.py").is_file():
        return False
    try:
        with (path / "pyproject.toml").open("rb") as file:
            project = tomllib.load(file).get("project", {})
    except FileNotFoundError:
        return False
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise RecordingError(
            f"Unable to inspect project checkout {path}: {exc}"
        ) from exc
    return isinstance(project, dict) and project.get("name") == "local-transcribe"


def find_checkout(*, source: Path | None = None, cwd: Path | None = None) -> Path:
    try:
        source_path = (source or Path(__file__)).resolve()
        source_dir = source_path.parent if source_path.is_file() else source_path
        visited: set[Path] = set()
        for index in range(2):
            start = source_dir if index == 0 else (cwd or Path.cwd()).resolve()
            for candidate in (start, *start.parents):
                if candidate not in visited:
                    visited.add(candidate)
                    if _is_checkout(candidate):
                        return candidate
    except OSError as exc:
        raise RecordingError(f"Unable to locate the project checkout: {exc}") from exc
    raise RecordingError(
        "Cannot locate a local-transcribe checkout. Run the command from a checkout."
    )


def ensure_output_dir(checkout: Path) -> Path:
    directory = checkout / OUTPUT_DIRNAME
    directory.mkdir(exist_ok=True)
    if not directory.resolve().is_relative_to(checkout.resolve()):
        raise RecordingError("The output directory is outside the checkout.")
    return directory


def create_recording_file(checkout: Path) -> tuple[Path, BinaryIO]:
    directory = checkout / OUTPUT_DIRNAME
    try:
        directory = ensure_output_dir(checkout)
        for _ in range(10):
            path = directory / f"recording-{uuid4().hex}.wav"
            try:
                return path, path.open("xb")
            except FileExistsError:
                continue
    except RecordingError:
        raise
    except OSError as exc:
        raise RecordingError(
            f"Unable to create a recording in {directory}: {exc}"
        ) from exc
    raise RecordingError(f"Unable to create a unique recording in {directory}.")


def create_transcript_file(checkout: Path, stem: str) -> tuple[Path, TextIO]:
    try:
        directory = ensure_output_dir(checkout)
        candidates = [f"{stem}.txt"] + [
            f"{stem}-{uuid4().hex[:8]}.txt" for _ in range(10)
        ]
        for name in candidates:
            path = directory / name
            try:
                return path, path.open("x", encoding="utf-8")
            except FileExistsError:
                continue
    except RecordingError:
        raise
    except OSError as exc:
        raise RecordingError(
            f"Unable to create a transcript in {checkout / OUTPUT_DIRNAME}: {exc}"
        ) from exc
    raise RecordingError(f"Unable to create a unique transcript for {stem}.")

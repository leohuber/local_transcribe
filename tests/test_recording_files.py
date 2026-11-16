import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from local_transcribe.adapters.recording_files import (
    create_recording_file,
    find_checkout,
)
from local_transcribe.domain.recording import RecordingError


def make_checkout(root: Path, name: str = "local-transcribe") -> None:
    package = root / "src" / "local_transcribe"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\n', encoding="utf-8"
    )


class RecordingFilesTests(unittest.TestCase):
    def test_prefers_source_checkout_and_falls_back_to_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_repo, cwd_repo = root / "source", root / "current"
            make_checkout(source_repo)
            make_checkout(cwd_repo)
            source = source_repo / "src" / "local_transcribe" / "__init__.py"
            cwd = cwd_repo / "src"
            self.assertEqual(
                find_checkout(source=source, cwd=cwd), source_repo.resolve()
            )
            self.assertEqual(find_checkout(source=root, cwd=cwd), cwd_repo.resolve())
            with patch.object(Path, "cwd", side_effect=FileNotFoundError):
                self.assertEqual(find_checkout(source=source), source_repo.resolve())

    def test_rejects_missing_or_unrelated_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            unrelated = root / "other"
            make_checkout(unrelated, "another-project")
            with self.assertRaisesRegex(RecordingError, "Cannot locate"):
                find_checkout(source=unrelated, cwd=root)

    def test_creates_directory_and_never_overwrites_a_collision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / ".tmp"
            directory.mkdir()
            existing = directory / f"recording-{UUID(int=1).hex}.wav"
            existing.write_bytes(b"existing")
            with patch(
                "local_transcribe.adapters.recording_files.uuid4",
                side_effect=[UUID(int=1), UUID(int=2)],
            ):
                path, stream = create_recording_file(root)
            with stream:
                stream.write(b"new")
            self.assertEqual(existing.read_bytes(), b"existing")
            self.assertEqual(path.read_bytes(), b"new")
            self.assertEqual(path.parent, directory)

    def test_creates_missing_directory_and_reports_filesystem_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path, stream = create_recording_file(root)
            stream.close()
            self.assertTrue(path.is_file())
            with (
                patch.object(Path, "mkdir", side_effect=PermissionError("denied")),
                self.assertRaisesRegex(RecordingError, "denied"),
            ):
                create_recording_file(root)

    def test_refuses_recording_directory_outside_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkout, outside = root / "checkout", root / "outside"
            checkout.mkdir()
            outside.mkdir()
            (checkout / ".tmp").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(RecordingError, "outside the checkout"):
                create_recording_file(checkout)
            self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()

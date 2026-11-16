import os
import subprocess
import sys
import sysconfig
import tempfile
import unittest
from pathlib import Path


def console_command() -> Path:
    executable = "local-transcribe.exe" if os.name == "nt" else "local-transcribe"
    return Path(sysconfig.get_path("scripts")) / executable


class EntryPointTests(unittest.TestCase):
    def test_console_command(self) -> None:
        result = subprocess.run(
            [console_command()], capture_output=True, text=True, check=True
        )

        self.assertEqual(result.stdout, "Hello from local-transcribe!\n")
        self.assertEqual(result.stderr, "")

    def test_package_and_bootstrap_callables(self) -> None:
        for module in ("local_transcribe", "local_transcribe.bootstrap"):
            with self.subTest(module=module):
                result = subprocess.run(
                    [sys.executable, "-c", f"from {module} import main; main()"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                self.assertEqual(result.stdout, "Hello from local-transcribe!\n")
                self.assertEqual(result.stderr, "")

    def test_python_entry_points_return_normally(self) -> None:
        for module in ("local_transcribe", "local_transcribe.bootstrap"):
            with self.subTest(module=module):
                result = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        f"from {module} import main; main(); print('returned')",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                self.assertEqual(
                    result.stdout, "Hello from local-transcribe!\nreturned\n"
                )

    def test_console_and_help_do_not_import_audio_or_mlx(self) -> None:
        guard = """
import builtins
original_import = builtins.__import__
def guarded_import(name, *args, **kwargs):
    if name.split('.')[0] in {'sounddevice', 'numpy', 'soxr', 'mlx', 'mlx_audio'}:
        raise RuntimeError(f'unexpected audio or MLX import: {name}')
    return original_import(name, *args, **kwargs)
builtins.__import__ = guarded_import
"""
        with tempfile.TemporaryDirectory() as temporary:
            (Path(temporary) / "sitecustomize.py").write_text(guard, encoding="utf-8")
            env = os.environ.copy()
            env["PYTHONPATH"] = temporary + os.pathsep + env.get("PYTHONPATH", "")
            for args in ([], ["--help"], ["record", "--help"]):
                with self.subTest(args=args):
                    result = subprocess.run(
                        [console_command(), *args],
                        env=env,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertNotIn("unexpected audio or MLX import", result.stderr)
            self.assertIn("two audio input devices", result.stdout)

    def test_package_import_is_inert(self) -> None:
        code = """
import sys
import local_transcribe

unexpected = sorted(
    name for name in sys.modules
    if name.startswith("local_transcribe.")
    or name.split(".")[0] in {"sounddevice", "numpy", "soxr", "mlx", "mlx_audio"}
)
if unexpected:
    raise SystemExit(f"Unexpected imports: {unexpected}")
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_recording_with_fake_devices_does_not_import_mlx(self) -> None:
        test_directory = Path(__file__).resolve().parent
        code = f"""
import builtins
import sys
import tempfile
from functools import partial
from pathlib import Path
original_import = builtins.__import__
def guarded_import(name, *args, **kwargs):
    if name.split('.')[0] in {{'mlx', 'mlx_audio'}}:
        raise RuntimeError(f'unexpected MLX import: {{name}}')
    return original_import(name, *args, **kwargs)
builtins.__import__ = guarded_import
sys.path.insert(0, {str(test_directory)!r})
from click.testing import CliRunner
from test_recorder import FakeCapture, FakeClock
from local_transcribe.adapters.recorder import SoundDeviceRecorder
from local_transcribe.application.recording import Recording
from local_transcribe.cli.commands import create_cli
from local_transcribe.domain.recording import InputDevice
class Devices:
    def list_inputs(self):
        return (InputDevice(2, 'Mic', 1), InputDevice(5, 'Loopback', 1))
with tempfile.TemporaryDirectory() as temporary:
    clock = FakeClock()
    capture = FakeCapture(clock)
    recorder = SoundDeviceRecorder(capture, checkout=lambda: Path(temporary), clock=clock)
    capture.script = partial(capture.emit, count=4, stop=recorder.stop)
    command = create_cli(lambda: Recording(Devices(), recorder), lambda: None)
    result = CliRunner().invoke(command, ['record'], input='2\\n5\\n')
    if result.exit_code or 'Recording saved:' not in result.output:
        raise SystemExit(result.output or repr(result.exception))
if any(name.split('.')[0] in {{'mlx', 'mlx_audio'}} for name in sys.modules):
    raise SystemExit('MLX was initialized')
"""
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

import os
import subprocess
import sysconfig
import tempfile
import unittest
from pathlib import Path


class ImportContractTests(unittest.TestCase):
    def lint(self, overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
        files = {
            "__init__.py": (
                "def main():\n"
                "    from local_transcribe.bootstrap import main as bootstrap_main\n"
                "    bootstrap_main()\n"
            ),
            "bootstrap.py": "def main():\n    pass\n",
            "domain/__init__.py": "",
            "application/__init__.py": "",
            "adapters/__init__.py": "",
            "cli/__init__.py": "",
        }
        files.update(overrides)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "local_transcribe"
            for name, content in files.items():
                path = package / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            config = Path(__file__).resolve().parents[1] / ".importlinter"
            (root / ".importlinter").write_bytes(config.read_bytes())
            executable = "lint-imports.exe" if os.name == "nt" else "lint-imports"
            command = Path(sysconfig.get_path("scripts")) / executable
            env = os.environ.copy()
            env["PYTHONPATH"] = str(root)
            return subprocess.run(
                [command, "--no-cache", "--no-logo"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

    def assert_contract_broken(
        self, result: subprocess.CompletedProcess[str], name: str
    ) -> None:
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn(f"{name} BROKEN", output)

    def test_inward_imports_are_allowed(self) -> None:
        result = self.lint(
            {
                "bootstrap.py": (
                    "import local_transcribe.cli\nimport local_transcribe.adapters\n"
                ),
                "cli/__init__.py": "import local_transcribe.application\n",
                "adapters/__init__.py": "import local_transcribe.application\n",
                "application/__init__.py": "import local_transcribe.domain\n",
            }
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_reversed_and_sibling_imports_are_rejected(self) -> None:
        cases = (
            ("domain", "application"),
            ("application", "cli"),
            ("cli", "adapters"),
            ("adapters", "cli"),
        )
        for source, target in cases:
            with self.subTest(source=source, target=target):
                result = self.lint(
                    {f"{source}/__init__.py": f"import local_transcribe.{target}\n"}
                )
                self.assert_contract_broken(result, "Dependency direction")

    def test_indirect_reversed_and_sibling_imports_are_rejected(self) -> None:
        cases = (
            ("domain", "cli"),
            ("cli", "adapters"),
        )
        for source, target in cases:
            with self.subTest(source=source, target=target):
                # The package root is an unlayered bridge between the two layers.
                result = self.lint(
                    {
                        f"{source}/__init__.py": "import local_transcribe\n",
                        "__init__.py": f"import local_transcribe.{target}\n",
                    }
                )
                self.assert_contract_broken(result, "Dependency direction")
                self.assertIn(
                    f"local_transcribe.{source} is not allowed to import "
                    f"local_transcribe.{target}",
                    result.stdout,
                )

    def test_framework_imports_are_rejected(self) -> None:
        cases = (
            ("application", "click", "Core is free of CLI and MLX frameworks"),
            ("domain", "rich", "Core is free of CLI and MLX frameworks"),
            ("application", "mlx_audio", "Core is free of CLI and MLX frameworks"),
            ("domain", "mlx", "Core is free of CLI and MLX frameworks"),
            ("cli", "mlx_audio", "CLI does not touch MLX"),
            ("cli", "mlx", "CLI does not touch MLX"),
            ("adapters", "click", "Adapters do not touch presentation"),
            ("adapters", "rich", "Adapters do not touch presentation"),
        )
        for source, framework, contract in cases:
            with self.subTest(source=source, framework=framework):
                result = self.lint({f"{source}/__init__.py": f"import {framework}\n"})
                self.assert_contract_broken(result, contract)

    def test_indirect_framework_import_is_rejected(self) -> None:
        result = self.lint(
            {
                "cli/__init__.py": "import local_transcribe.application\n",
                "application/__init__.py": "import local_transcribe.domain\n",
                "domain/__init__.py": "import mlx_audio\n",
            }
        )
        self.assert_contract_broken(result, "CLI does not touch MLX")
        self.assertIn("local_transcribe.cli", result.stdout)
        self.assertIn("mlx_audio", result.stdout)

    def test_undeclared_top_level_module_is_rejected(self) -> None:
        result = self.lint({"unlisted.py": ""})
        self.assert_contract_broken(result, "Dependency direction")
        self.assertIn("local_transcribe.unlisted", result.stdout)

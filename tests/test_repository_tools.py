"""Basic checks for repository file reading and text search."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.read_file import read_repository_file
from tools.search_code import search_repository


class RepositoryToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "auth.py").write_text(
            "def authenticate_user():\n    return True\n", encoding="utf-8"
        )
        (self.root / "README.md").write_text("Authentication overview\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_read_file(self) -> None:
        content = read_repository_file(self.root, "src/auth.py")
        self.assertIn("def authenticate_user", content)

    def test_search_code(self) -> None:
        self.assertEqual(
            search_repository(self.root, "AUTH"),
            ["README.md", "src/auth.py"],
        )

    def test_search_skips_sensitive_files_but_keeps_env_example(self) -> None:
        secrets_dir = self.root / "secrets"
        secrets_dir.mkdir()
        (self.root / ".env").write_text("shared-marker\n", encoding="utf-8")
        (self.root / ".env.example").write_text("shared-marker\n", encoding="utf-8")
        (self.root / ".env.local").write_text("shared-marker\n", encoding="utf-8")
        (secrets_dir / "credentials.json").write_text(
            "shared-marker\n", encoding="utf-8"
        )
        (self.root / "signing.pem").write_text("shared-marker\n", encoding="utf-8")

        self.assertEqual(
            search_repository(self.root, "shared-marker"),
            [".env.example"],
        )

    def test_read_file_rejects_sensitive_files_but_allows_env_example(self) -> None:
        (self.root / ".env").write_text("local secret\n", encoding="utf-8")
        (self.root / ".env.example").write_text("safe placeholder\n", encoding="utf-8")
        (self.root / ".env.local").write_text("local secret\n", encoding="utf-8")
        (self.root / "signing.pem").write_text("private key\n", encoding="utf-8")

        self.assertEqual(
            read_repository_file(self.root, ".env.example"),
            "safe placeholder\n",
        )
        for path in (".env", ".env.local", "signing.pem"):
            with self.subTest(path=path):
                with self.assertRaisesRegex(ValueError, "excluded from repository"):
                    read_repository_file(self.root, path)

    def test_read_file_rejects_paths_outside_root(self) -> None:
        with self.assertRaisesRegex(ValueError, "inside the repository"):
            read_repository_file(self.root, "../outside.txt")

    def test_read_file_reports_missing_files(self) -> None:
        with self.assertRaisesRegex(FileNotFoundError, "file not found: missing.txt"):
            read_repository_file(self.root, "missing.txt")

    def test_read_file_reports_non_utf8_content(self) -> None:
        invalid_text = self.root / "invalid.txt"
        invalid_text.write_bytes(b"\xff")

        with self.assertRaisesRegex(ValueError, "file is not UTF-8 text"):
            read_repository_file(self.root, "invalid.txt")

    def test_read_file_reports_permission_errors(self) -> None:
        with patch("tools.read_file.Path.read_text", side_effect=PermissionError):
            with self.assertRaisesRegex(
                PermissionError, "permission denied reading file: src/auth.py"
            ):
                read_repository_file(self.root, "src/auth.py")

    def test_search_code_rejects_empty_query(self) -> None:
        with self.assertRaises(ValueError):
            search_repository(self.root, "")


if __name__ == "__main__":
    unittest.main()

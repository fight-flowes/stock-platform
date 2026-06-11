from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from stockrag.config import Settings
from stockrag.service import _enforce_local_ingest_policy, _reject_metadata_override, _resolve_local_path


class SafetyGuardsTests(unittest.TestCase):
    def test_local_ingest_policy_requires_allowed_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "sample.md"
            target.write_text("# report", encoding="utf-8")
            settings = Settings(local_ingest_allowed_roots=())

            with self.assertRaisesRegex(PermissionError, "LOCAL_INGEST_ALLOWED_ROOTS is empty"):
                _enforce_local_ingest_policy(target, settings)

    def test_local_ingest_policy_rejects_paths_outside_roots(self) -> None:
        with tempfile.TemporaryDirectory() as allowed_dir, tempfile.TemporaryDirectory() as other_dir:
            allowed_root = Path(allowed_dir).resolve()
            target = Path(other_dir).resolve() / "sample.md"
            target.write_text("# report", encoding="utf-8")
            settings = Settings(local_ingest_allowed_roots=(allowed_root,))

            with self.assertRaisesRegex(PermissionError, "outside LOCAL_INGEST_ALLOWED_ROOTS"):
                _enforce_local_ingest_policy(target, settings)

    def test_local_ingest_policy_rejects_non_markdown_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            target = root / "sample.txt"
            target.write_text("hello", encoding="utf-8")
            settings = Settings(local_ingest_allowed_roots=(root,))

            with self.assertRaisesRegex(PermissionError, "only allows markdown files"):
                _enforce_local_ingest_policy(target, settings)

    def test_resolve_local_path_accepts_allowed_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            target = root / "sample.md"
            target.write_text("# report", encoding="utf-8")
            settings = Settings(local_ingest_allowed_roots=(root,))

            resolved = _resolve_local_path(
                str(target),
                settings,
                enforce_local_ingest_policy=True,
                expect_directory=False,
            )

            self.assertEqual(resolved, target)

    def test_metadata_override_is_rejected_for_structured_import(self) -> None:
        with self.assertRaisesRegex(ValueError, "do not support metadata overrides"):
            _reject_metadata_override({"report_date": "2026-05-07"})


if __name__ == "__main__":
    unittest.main()

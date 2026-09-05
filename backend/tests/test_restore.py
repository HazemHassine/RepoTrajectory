import os
import subprocess
from pathlib import Path


def test_restore_failure_is_not_reported_as_success(tmp_path):
    archive = tmp_path / "backup.dump"
    archive.write_bytes(b"test fixture")
    restore = tmp_path / "pg_restore"
    restore.write_text("#!/bin/sh\nexit 7\n")
    restore.chmod(0o755)
    script = Path(__file__).resolve().parents[2] / "scripts" / "restore.sh"
    result = subprocess.run(
        ["bash", str(script), str(archive)],
        env={**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"},
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 7
    assert "completed successfully" not in result.stdout
    assert "Restore failed" in result.stderr

"""Build a portable stdlib-only zipapp, using an explicit package allowlist."""
from pathlib import Path
import io
import zipapp
import zipfile

root = Path(__file__).resolve().parents[1]
dist = root / "dist"
dist.mkdir(exist_ok=True)
archive = io.BytesIO()
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
    for path in sorted((root / "src" / "brain_cli").glob("*.py")):
        z.writestr("brain_cli/" + path.name, path.read_bytes())
    z.writestr("__main__.py", "from brain_cli.cli import main\nraise SystemExit(main())\n")
archive.seek(0)
zipapp.create_archive(archive, target=dist / "brain.pyz", interpreter="/usr/bin/env python3")
(dist / "brain.pyz").chmod(0o755)
print("Built dist/brain.pyz")

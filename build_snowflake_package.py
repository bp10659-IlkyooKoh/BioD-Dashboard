"""Build a source-only Snowflake upload directory and ZIP using a strict allowlist."""
import hashlib
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RUNTIME_FILES = (
    "streamlit_app.py", "app.py", "biod_analysis.py", "biod_ui.py",
    "biod_reporting.py", "biod_labels.py", "biod_mollim.py", "environment.yml",
    "fonts/NanumGothic-Regular.ttf", "fonts/NanumGothic-Bold.ttf", "fonts/OFL.txt",
)


def build(output_root=None):
    output_root = Path(output_root) if output_root is not None else ROOT / "dist"
    source_dir = output_root / "BioD_Snowflake"
    # Refuse stale/extra files rather than accidentally distributing them.
    if source_dir.exists():
        existing = {p.relative_to(source_dir).as_posix() for p in source_dir.rglob("*") if p.is_file()}
        unexpected = existing - set(RUNTIME_FILES)
        if unexpected:
            raise RuntimeError(f"업로드 폴더에 불필요한 파일이 있습니다: {sorted(unexpected)}")
    for relative in RUNTIME_FILES:
        if not (ROOT / relative).is_file():
            raise FileNotFoundError(ROOT / relative)
    for relative in RUNTIME_FILES:
        target = source_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    archive = output_root / "BioD_Snowflake.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for relative in RUNTIME_FILES:
            bundle.write(source_dir / relative, arcname=relative)
    shutil.copyfile(ROOT / "SNOWFLAKE_UPLOAD.md", output_root / "업로드_안내.md")
    hashes = [f"{hashlib.sha256((source_dir / p).read_bytes()).hexdigest()}  {p}" for p in RUNTIME_FILES]
    (output_root / "SHA256SUMS.txt").write_text("\n".join(hashes) + "\n", encoding="utf-8")
    return source_dir, archive


if __name__ == "__main__":
    for path in build():
        print(path)

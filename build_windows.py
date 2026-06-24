from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ICON_SCRIPT = ROOT / "tools" / "generate_app_icon.py"
SOURCE_ICON = ROOT / "news-ticker-icon.png"
ICON_PATH = ROOT / "assets" / "generated" / "app_icon.ico"
SPEC_PATH = ROOT / "news_ticker.spec"
DIST_EXE = ROOT / "dist" / "NewsTicker.exe"


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def ensure_output_not_locked(path: Path) -> None:
    if not path.exists():
        return

    try:
        temp_path = path.with_name(f"{path.stem}.lockcheck{path.suffix}")
        os.replace(path, temp_path)
        os.replace(temp_path, path)
    except PermissionError as exc:
        raise RuntimeError(
            f"Build output is locked: {path}\n"
            "Close the running NewsTicker executable from dist/ and try again."
        ) from exc


def main() -> int:
    if not SOURCE_ICON.exists():
        raise FileNotFoundError(f"Missing source icon: {SOURCE_ICON}")

    print("Converting app icon...")
    run([sys.executable, str(ICON_SCRIPT)])

    if not ICON_PATH.exists():
        raise FileNotFoundError(f"Expected icon at {ICON_PATH}")

    ensure_output_not_locked(DIST_EXE)

    print("Building Windows executable with PyInstaller...")
    try:
        run([sys.executable, "-m", "PyInstaller", "--noconfirm", str(SPEC_PATH)])
    except subprocess.CalledProcessError as exc:
        if DIST_EXE.exists():
            ensure_output_not_locked(DIST_EXE)
        raise exc

    print("Build complete. See dist/NewsTicker/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

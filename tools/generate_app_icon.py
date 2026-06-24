from __future__ import annotations

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PNG = ROOT / "news-ticker-icon.png"
OUTPUT_DIR = ROOT / "assets" / "generated"
PNG_PATH = OUTPUT_DIR / "app_icon.png"
ICO_PATH = OUTPUT_DIR / "app_icon.ico"


def main() -> int:
    if not SOURCE_PNG.exists():
        raise FileNotFoundError(f"Missing source icon: {SOURCE_PNG}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with Image.open(SOURCE_PNG) as image:
        image = image.convert("RGBA")

        png_image = image.copy()
        png_image.thumbnail((256, 256))
        png_image.save(PNG_PATH, format="PNG")

        image.save(
            ICO_PATH,
            format="ICO",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )

    print(f"Using source icon {SOURCE_PNG}")
    print(f"Generated {PNG_PATH}")
    print(f"Generated {ICO_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

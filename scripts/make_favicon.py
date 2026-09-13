"""Pack site/.icon-256.png (from scripts/make_icons.mjs) into site/app/favicon.ico at 16, 32 and 48 px."""
from pathlib import Path

from PIL import Image

root = Path(__file__).resolve().parents[1]
src = root / "site" / ".icon-256.png"
Image.open(src).convert("RGBA").save(root / "site" / "app" / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
src.unlink()
print("wrote site/app/favicon.ico (16, 32, 48)")

"""Generate the Windows application icon with a guaranteed solid-black tile."""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent
source = Image.open(ROOT / "assets" / "logo.png").convert("RGBA")
tile = Image.new("RGBA", (256, 256), (0, 0, 0, 255))
source.thumbnail((188, 188), Image.Resampling.LANCZOS)
tile.alpha_composite(source, ((256 - source.width) // 2, (256 - source.height) // 2))
out = ROOT / "assets" / "smth-black.ico"
tile.save(out, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(f"Generated {out}")

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from PIL import Image


if __name__ == "__main__":
    files = sorted([p for p in Path(".").iterdir() if p.is_file() and p.name.startswith("test_") and p.suffix.lower() in {".png", ".jpg", ".jpeg"}])
    if not files:
        raise SystemExit("no test images")

    cols = 3
    rows = (len(files) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(15, 5 * rows))
    axes_list = axes.flatten() if hasattr(axes, "flatten") else [axes]

    for idx, path in enumerate(files):
        img = Image.open(path)
        axes_list[idx].imshow(img)
        axes_list[idx].set_title(path.name, fontsize=10)
        axes_list[idx].axis("off")

    for idx in range(len(files), len(axes_list)):
        axes_list[idx].axis("off")

    plt.tight_layout()
    out = "all_test_tiles_comparison.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"saved: {out}")

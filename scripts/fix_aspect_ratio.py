#!/usr/bin/env python3
"""Trim whitespace and pad portfolio thumbnails to a uniform aspect ratio."""

from __future__ import annotations

import math
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, List

try:
    from PIL import Image, ImageChops
except ModuleNotFoundError as exc:  # pragma: no cover - dependency missing
    raise SystemExit("Pillow is required: pip install Pillow") from exc


ROOT = Path(__file__).resolve().parent.parent
PORTFOLIO_HTML = ROOT / "portfolio.html"
SUPPORTED_SUFFIXES = {".png", ".webp"}
TARGET_ASPECT = 16 / 9


class _ImageCollector(HTMLParser):
    """Collect `src` attributes from `img` tags in an HTML document."""

    def __init__(self) -> None:
        super().__init__()
        self.sources: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[tuple[str, str | None]]) -> None:
        if tag.lower() != "img":
            return
        for name, value in attrs:
            if name and name.lower() == "src" and value:
                self.sources.append(value)

    handle_startendtag = handle_starttag  # type: ignore[assignment]


def _iter_local_image_paths(html_file: Path) -> Iterable[Path]:
    parser = _ImageCollector()
    parser.feed(html_file.read_text(encoding="utf-8"))

    seen: set[str] = set()
    for raw_src in parser.sources:
        if not raw_src or raw_src in seen:
            continue
        seen.add(raw_src)
        if "://" in raw_src or raw_src.startswith("data:"):
            continue
        path = (ROOT / raw_src).resolve()
        if not path.exists():
            print(f"warning: skipping missing image {raw_src}", file=sys.stderr)
            continue
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            print(f"warning: skipping unsupported format {raw_src}", file=sys.stderr)
            continue
        yield path


def _crop_whitespace(image: Image.Image) -> tuple[Image.Image, bool]:
    """Remove surrounding transparent or near-white padding."""

    # Ensure RGBA for consistent alpha handling.
    rgba = image.convert("RGBA")
    width, height = rgba.size

    # First attempt: rely on alpha channel when present.
    alpha = rgba.getchannel("A")
    bbox = alpha.getbbox()
    if bbox and bbox != (0, 0, width, height):
        return rgba.crop(bbox), True

    # Fallback: detect light borders in opaque images by comparing against white.
    rgb = rgba.convert("RGB")
    background = Image.new("RGB", rgb.size, (255, 255, 255))
    diff = ImageChops.difference(rgb, background)
    # Amplify differences so subtle edges are detected.
    diff = ImageChops.add(diff, diff, 2.0, -100)
    bbox = diff.getbbox()
    if bbox and bbox != (0, 0, width, height):
        return rgba.crop(bbox), True

    return rgba, False


def _pad_to_ratio(image_path: Path) -> bool:
    with Image.open(image_path) as image:
        cropped, did_crop = _crop_whitespace(image)
        width, height = cropped.size
        if width == 0 or height == 0:
            return False

        current_ratio = width / height
        if math.isclose(current_ratio, TARGET_ASPECT, rel_tol=1e-2, abs_tol=1e-2):
            if did_crop:
                cropped.save(image_path)
                return True
            return False

        if current_ratio > TARGET_ASPECT:
            # Image is wider than target ratio: extend height.
            new_height = int(round(width / TARGET_ASPECT))
            new_width = width
        else:
            # Image is taller/narrower than target ratio: extend width.
            new_width = int(round(height * TARGET_ASPECT))
            new_height = height

        padded = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))
        offset = ((new_width - width) // 2, (new_height - height) // 2)
        padded.paste(cropped, offset, cropped)
        padded.save(image_path)
    return True


def main() -> int:
    html_file = PORTFOLIO_HTML
    if not html_file.exists():
        print(f"error: {html_file} not found", file=sys.stderr)
        return 1

    processed = 0
    for image_path in _iter_local_image_paths(html_file):
        if _pad_to_ratio(image_path):
            processed += 1
            print(f"padded {image_path.relative_to(ROOT)}")

    print(f"done. padded {processed} image(s).")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

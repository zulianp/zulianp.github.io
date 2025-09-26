#!/usr/bin/env python3
"""Pad portfolio thumbnails with transparency to unify their aspect ratio."""

from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, List

try:
    from PIL import Image
except ModuleNotFoundError as exc:  # pragma: no cover - dependency missing
    raise SystemExit("Pillow is required: pip install Pillow") from exc


ROOT = Path(__file__).resolve().parent.parent
PORTFOLIO_HTML = ROOT / "portfolio.html"
SUPPORTED_SUFFIXES = {".png", ".webp"}


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


def _pad_to_square(image_path: Path) -> bool:
    with Image.open(image_path) as image:
        width, height = image.size
        if width == height:
            return False
        target = max(width, height)
        padded = Image.new("RGBA", (target, target), (0, 0, 0, 0))
        offset = ((target - width) // 2, (target - height) // 2)
        padded.paste(image.convert("RGBA"), offset)
        padded.save(image_path)
    return True


def main() -> int:
    html_file = PORTFOLIO_HTML
    if not html_file.exists():
        print(f"error: {html_file} not found", file=sys.stderr)
        return 1

    processed = 0
    for image_path in _iter_local_image_paths(html_file):
        if _pad_to_square(image_path):
            processed += 1
            print(f"padded {image_path.relative_to(ROOT)}")

    print(f"done. padded {processed} image(s).")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

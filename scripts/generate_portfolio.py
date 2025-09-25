#!/usr/bin/env python3
"""Generate portfolio.html from structured entries using a fast template pattern."""

from __future__ import annotations

import html
import os
import textwrap
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parent.parent
PORTFOLIO_DIR = ROOT / "portfolio"
OUTPUT_FILE = ROOT / "portfolio.html"


def read_portfolio_entries(portfolio_dir: Path) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for entry_dir in sorted((p for p in portfolio_dir.iterdir() if p.is_dir()), reverse=True):
        data_file = entry_dir / "content.yaml"
        if not data_file.exists():
            continue
        raw = data_file.read_text(encoding="utf-8")
        parsed = parse_simple_yaml(raw)
        parsed["_path"] = entry_dir
        entries.append(parsed)
    return entries


def parse_simple_yaml(source: str) -> Dict[str, Any]:
    """Parse a limited YAML subset suitable for the portfolio entries."""

    lines = source.splitlines()
    data: Dict[str, Any] = {}
    idx = 0

    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            idx += 1
            continue
        if ":" not in line:
            idx += 1
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.lstrip()

        if value.startswith('"'):
            text, idx = _parse_quoted_block(lines, idx, value)
            data[key] = _normalize_multiline(text)
            continue

        if not value:
            idx += 1
            items, idx = _parse_list_block(lines, idx)
            data[key] = items
            continue

        data[key] = _clean_scalar(value)
        idx += 1

    return data


def _clean_scalar(value: str) -> str:
    value = value.strip()
    if value.startswith('"') and value.endswith('"') and len(value) >= 2:
        value = value[1:-1]
    return value.strip()


def _parse_quoted_block(lines: List[str], idx: int, current: str) -> Tuple[str, int]:
    text = current[1:]
    if text.endswith('"') and not text.endswith('\\"'):
        return text[:-1], idx + 1

    pieces: List[str] = []
    if text:
        pieces.append(text)
    idx += 1

    while idx < len(lines):
        segment = lines[idx]
        stripped = segment.strip()
        if not stripped:
            pieces.append("")
            idx += 1
            continue
        if stripped.startswith("#"):
            idx += 1
            continue
        if stripped.endswith('"') and not stripped.endswith('\\"'):
            pieces.append(segment.rstrip()[:-1])
            idx += 1
            break
        pieces.append(segment.rstrip())
        idx += 1

    return "\n".join(pieces), idx


def _parse_list_block(lines: List[str], idx: int) -> Tuple[List[Dict[str, Any]], int]:
    items: List[Dict[str, Any]] = []
    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            idx += 1
            continue
        if not line.startswith("  "):
            break
        if stripped.startswith("-"):
            entry: Dict[str, Any] = {}
            inline = stripped[1:].strip()
            if inline and ":" in inline:
                sub_key, sub_value = inline.split(":", 1)
                entry[sub_key.strip()] = _clean_scalar(sub_value)
            idx += 1
            while idx < len(lines):
                detail = lines[idx]
                stripped_detail = detail.strip()
                if not stripped_detail or stripped_detail.startswith("#"):
                    idx += 1
                    continue
                if not detail.startswith("    "):
                    break
                if ":" in stripped_detail:
                    sub_key, sub_value = stripped_detail.split(":", 1)
                    entry[sub_key.strip()] = _clean_scalar(sub_value)
                idx += 1
            items.append(entry)
        else:
            idx += 1
    return items, idx


def _normalize_multiline(text: str) -> str:
    lines = text.splitlines()
    # Trim leading/trailing blank lines
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return ""
    dedented = textwrap.dedent("\n".join(lines))
    return dedented.strip()


def render_page(entries: Iterable[Dict[str, Any]]) -> str:
    cards_html = "\n".join(render_card(data) for data in entries)
    return PAGE_TEMPLATE.replace("{{CARDS}}", cards_html)


def render_card(data: Dict[str, Any]) -> str:
    entry_dir: Path = data.get("_path", PORTFOLIO_DIR)
    title = html.escape(data.get("title", "Untitled"))
    description_html = format_description(data.get("description", ""))
    description_block = DESCRIPTION_TEMPLATE.replace("{{CONTENT}}", description_html) if description_html else ""

    images = data.get("images") or []
    gallery_html = render_gallery(images, entry_dir, title)

    paper_items = data.get("paper") or []
    status_info = first_dict_with_key(paper_items, "status")
    status = status_info.get("status", "") if status_info else ""
    paper_info = first_dict_with_key(paper_items, "url")
    paper_url = paper_info.get("url") if paper_info else ""

    video_info = data.get("video") or first_dict_with_key(data.get("videos") or [], "url")
    video_url = ""
    if isinstance(video_info, dict):
        video_url = video_info.get("url", "")
    elif isinstance(video_info, str):
        video_url = video_info

    paper_button = ""
    status_badge = ""
    if status.lower() == "accepted" and paper_url:
        paper_button = render_paper_button(paper_url)
    elif status:
        status_badge = render_status_badge(status)

    video_button = render_video_button(video_url)
    links_html = render_links([paper_button, status_badge, video_button])

    card = CARD_TEMPLATE
    card = card.replace("{{TITLE}}", title)
    card = card.replace("{{GALLERY}}", gallery_html)
    card = card.replace("{{DESCRIPTION}}", description_block)
    card = card.replace("{{LINKS}}", links_html)
    return card


def first_dict_with_key(items: Iterable[Dict[str, Any]], key: str) -> Dict[str, Any]:
    for item in items:
        if isinstance(item, dict) and key in item:
            return item
    return {}


def format_description(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    paragraphs = [
        f"<p>{html.escape(part.strip())}</p>"
        for part in split_paragraphs(text)
        if part.strip()
    ]
    return "\n".join(paragraphs)


def split_paragraphs(text: str) -> Iterable[str]:
    buffer: List[str] = []
    for line in text.splitlines():
        if not line.strip():
            if buffer:
                yield " ".join(buffer)
                buffer = []
            continue
        buffer.append(line.strip())
    if buffer:
        yield " ".join(buffer)


def render_paper_button(url: str) -> str:
    if not url:
        return ""
    escaped = html.escape(url)
    return PAPER_BUTTON_TEMPLATE.replace("{{URL}}", escaped)


def render_video_button(url: str) -> str:
    if not url:
        return ""
    escaped = html.escape(url)
    return VIDEO_BUTTON_TEMPLATE.replace("{{URL}}", escaped)


def render_status_badge(status: str) -> str:
    clean = html.escape(status.strip())
    return STATUS_BADGE_TEMPLATE.replace("{{STATUS}}", clean)


def render_links(components: Iterable[str]) -> str:
    items = [item for item in components if item]
    if not items:
        return ""
    joined = "\n".join(items)
    return LINKS_TEMPLATE.replace("{{ITEMS}}", joined)


def render_gallery(images: List[Dict[str, Any]], entry_dir: Path, fallback_title: str) -> str:
    figures = []
    for image in images:
        src_value = image.get("src")
        if not src_value:
            continue
        relative = os.path.relpath(entry_dir / src_value, ROOT)
        img_src = html.escape(Path(relative).as_posix())
        caption_raw = image.get("caption", "")
        caption_html = html.escape(caption_raw) if caption_raw else ""
        alt_text = caption_html or html.escape(fallback_title)
        figure = FIGURE_TEMPLATE.replace("{{SRC}}", img_src).replace("{{ALT}}", alt_text)
        if caption_html:
            figure = figure.replace("{{CAPTION}}", FIGURE_CAPTION_TEMPLATE.replace("{{TEXT}}", caption_html))
        else:
            figure = figure.replace("{{CAPTION}}", "")
        figures.append(figure)
    if not figures:
        return ""
    return GALLERY_TEMPLATE.replace("{{FIGURES}}", "\n".join(figures))


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Patrick Zulian | Portfolio</title>
  <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">
  <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>
  <link href=\"https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap\" rel=\"stylesheet\">
  <link rel=\"stylesheet\" href=\"assets/css/style.css\">
</head>
<body>
  <header class=\"hero hero--compact\" id=\"top\">
    <nav class=\"nav\">
      <a class=\"nav__brand\" href=\"index.html#top\">Patrick Zulian</a>
      <div class=\"nav__links\">
        <a href=\"index.html#about\">About</a>
        <a href=\"index.html#research\">Research</a>
        <a href=\"index.html#experience\">Experience</a>
        <a href=\"index.html#projects\">Projects</a>
        <a href=\"index.html#service\">Service</a>
        <a href=\"portfolio.html\" aria-current=\"page\">Portfolio</a>
      </div>
    </nav>
    <div class=\"hero__content\">
      <p class=\"hero__eyebrow\">Scientific work</p>
      <!--<h1>Portfolio</h1>-->
      <p class=\"hero__lede\">
        Projects, articles, and open-source software.
      </p>
    </div>
  </header>

  <main>
    <section class=\"section\" id=\"portfolio\">
      <div class=\"section__inner\">
       <!--<h2>Featured Work</h2>-->
        <div class=\"portfolio-grid\">
{{CARDS}}
        </div>
      </div>
    </section>
  </main>

  <footer class=\"footer\">
    <p>© <span id=\"year\"></span> Patrick Zulian</p>
  </footer>

  <a href=\"#top\" class=\"back-to-top\" aria-label=\"Back to top\">↑</a>

  <script>
    document.getElementById('year').textContent = new Date().getFullYear();
  </script>
</body>
</html>
"""


CARD_TEMPLATE = """          <article class=\"portfolio-card\">
            <h3>{{TITLE}}</h3>
{{GALLERY}}
{{DESCRIPTION}}
{{LINKS}}
          </article>"""


GALLERY_TEMPLATE = """            <div class=\"portfolio-card__gallery\">
{{FIGURES}}
            </div>"""


FIGURE_TEMPLATE = """              <figure class=\"portfolio-card__figure\">
                <img src=\"{{SRC}}\" alt=\"{{ALT}}\">
{{CAPTION}}
              </figure>"""


FIGURE_CAPTION_TEMPLATE = """                <figcaption>{{TEXT}}</figcaption>"""


DESCRIPTION_TEMPLATE = """            <details class=\"portfolio-card__details\">
              <summary class=\"portfolio-card__summary\">Project overview</summary>
              <div class=\"portfolio-card__description\">
{{CONTENT}}
              </div>
            </details>"""


LINKS_TEMPLATE = """            <div class=\"portfolio-card__links\">
{{ITEMS}}
            </div>"""


PAPER_BUTTON_TEMPLATE = """<a class=\"button button--doc\" href=\"{{URL}}\" target=\"_blank\" rel=\"noopener\">
                  <span class=\"button__icon\" aria-hidden=\"true\">
                    <svg viewBox=\"0 0 32 32\" role=\"img\" focusable=\"false\">
                      <path d=\"M9 3h11l7 7v15a4 4 0 0 1-4 4H9a4 4 0 0 1-4-4V7a4 4 0 0 1 4-4z\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linejoin=\"round\"/>
                      <path d=\"M20 3v8h7\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linejoin=\"round\"/>
                      <rect x=\"9\" y=\"19\" width=\"14\" height=\"8\" rx=\"1.6\" fill=\"currentColor\"/>
                      <text x=\"16\" y=\"25\" text-anchor=\"middle\" font-family=\"Inter, 'Segoe UI', sans-serif\" font-size=\"7\" font-weight=\"700\" fill=\"#ffffff\">PDF</text>
                    </svg>
                  </span>
                  <span class=\"button__label\">Read Paper</span>
                </a>"""


VIDEO_BUTTON_TEMPLATE = """<a class=\"button button--video\" href=\"{{URL}}\" target=\"_blank\" rel=\"noopener\">
                  <span class=\"button__label\">Watch Video</span>
                </a>"""


STATUS_BADGE_TEMPLATE = """<span class=\"badge badge--status\">{{STATUS}}</span>"""


def main() -> None:
    entries = read_portfolio_entries(PORTFOLIO_DIR)
    html_content = render_page(entries)
    OUTPUT_FILE.write_text(html_content, encoding="utf-8")


if __name__ == "__main__":
    main()

"""Shared page chrome, the media list, and the sitemap (standard library only)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import date
from html import escape
from pathlib import Path
from string import Template

SITE_URL = "https://quantumalliance.foundation"
FORUM_URL = "https://forum.quantumalliance.foundation/"
CHARTER_URL = "https://github.com/QuantumAllianceFoundation/governance/blob/main/CHARTER.md"

# (href, label). External links open in a new tab.
NAV = (
    ("/#why", "Why now"),
    ("/#groups", "Working groups"),
    (CHARTER_URL, "Charter"),
    ("/#members", "Members"),
    ("/registry/", "Registries"),
    ("/#signup", "Stay informed"),
)

MEDIA_SECTIONS = ("coverage", "syndication", "press-release")
_EXTERNAL = 'target="_blank" rel="noopener noreferrer"'


def _e(text: str) -> str:
    return escape(text, quote=True)


def nav_html(path: str) -> str:
    """The main nav links. The Registries link is current on every registry page."""
    lines = []
    for href, label in NAV:
        attrs = f' {_EXTERNAL}' if href.startswith("https://") else ""
        if href == "/registry/" and path.startswith("/registry/"):
            attrs += ' aria-current="page"'
        lines.append(f'        <a href="{_e(href)}"{attrs}>{_e(label)}</a>')
    lines.append(f'        <a href="{FORUM_URL}" class="btn btn-signal" {_EXTERNAL}>Participate</a>')
    return "\n".join(lines)


def render_page(
    template: str,
    *,
    title: str,
    description: str,
    path: str | None,
    body: str,
    year: int,
    scripts: tuple[str, ...] = (),
    robots: str = "index, follow",
    og_type: str = "website",
    head_extra: str = "",
) -> str:
    """Fill the shared page template. A page with no path (the 404 page) has no canonical URL."""
    url_meta = (
        f'  <link rel="canonical" href="{SITE_URL}{_e(path)}">\n'
        f'  <meta property="og:url" content="{SITE_URL}{_e(path)}">'
        if path
        else ""
    )
    script_tags = "\n".join(
        f'  <script type="module" src="/assets/{_e(name)}"></script>' for name in scripts
    )
    return Template(template).substitute(
        title=_e(title),
        description=_e(description),
        url_meta=url_meta,
        scripts=script_tags,
        robots=robots,
        og_type=og_type,
        head_extra=head_extra,
        nav=nav_html(path or ""),
        body=body,
        year=year,
    )


def fill_markers(text: str, values: dict[str, str]) -> str:
    """Replace each `<!-- name -->` marker. A missing marker is an error, not a silent skip."""
    for name, value in values.items():
        marker = f"<!-- {name} -->"
        if marker not in text:
            raise ValueError(f"marker {marker} not found")
        text = text.replace(marker, value)
    return text


@dataclass(frozen=True)
class MediaItem:
    section: str
    outlet: str
    title: str
    url: str
    format: str
    date: date
    image: str | None = None
    lang: str | None = None


def load_media(path: Path, images: Path) -> list[MediaItem]:
    """Read the media list. Every error names the item, so a bad edit is easy to find."""
    with path.open("rb") as f:
        raw = tomllib.load(f)
    items, errors = [], []
    fields = set(MediaItem.__dataclass_fields__)
    for number, entry in enumerate(raw.get("item", []), start=1):
        where = f"{path.name} item {number}"
        unknown = set(entry) - fields
        missing = {"section", "outlet", "title", "url", "format", "date"} - set(entry)
        if unknown or missing:
            errors.append(f"{where}: unknown {sorted(unknown)}, missing {sorted(missing)}")
            continue
        item = MediaItem(**entry)
        if item.section not in MEDIA_SECTIONS:
            errors.append(f"{where}: section must be one of {', '.join(MEDIA_SECTIONS)}")
        if not isinstance(item.date, date):
            errors.append(f"{where}: date must be a TOML date, for example 2026-10-15")
        if item.image and not (images / item.image).is_file():
            errors.append(f"{where}: image {item.image} not found in {images}")
        items.append(item)
    if errors:
        raise ValueError("\n".join(errors))
    return items


def media_card(item: MediaItem, indent: str) -> str:
    preview = (
        f'<img src="/assets/media/{_e(item.image)}" alt="" width="640" height="336" loading="lazy">'
        if item.image
        else f'<span class="preview-fallback" aria-hidden="true">{_e(item.outlet)}</span>'
    )
    lang = f' lang="{_e(item.lang)}"' if item.lang else ""
    day = item.date
    return (
        f'{indent}<a href="{_e(item.url)}" class="card media-card preview-card" {_EXTERNAL}>\n'
        f"{indent}  {preview}\n"
        f'{indent}  <span class="tag">{_e(item.outlet)}</span>\n'
        f"{indent}  <h3{lang}>{_e(item.title)}</h3>\n"
        f'{indent}  <span class="muted">{_e(item.format)} · '
        f'<time datetime="{day.isoformat()}">{day:%B} {day.day}, {day.year}</time></span>\n'
        f"{indent}</a>"
    )


def media_cards(items: list[MediaItem], section: str, indent: str) -> str:
    return "\n".join(media_card(i, indent) for i in items if i.section == section)


def sitemap(paths: list[str]) -> str:
    urls = "\n".join(f"  <url><loc>{SITE_URL}{_e(p)}</loc></url>" for p in paths)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>\n"
    )

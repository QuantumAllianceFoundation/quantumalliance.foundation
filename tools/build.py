"""Build the whole site into one output directory (dist/ by default).

Static page bodies live in content/, the media list in content/media.toml, and
the registry data in registry/data/. Every page shares tools/page.html.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.registry.model import Registry, RegistryError, chain_slug, library_slug, load_registry
from tools.registry.render import (
    LIBRARIES_TITLE,
    registry_cards,
    render_algorithm,
    render_algorithms_index,
    render_blockchains,
    render_chain,
    render_hub,
    render_libraries,
    render_library,
    render_products,
)
from tools.site import fill_markers, load_media, media_cards, render_page, sitemap

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = Path(__file__).parent / "page.html"
# Copied into the output as they are.
STATIC_FILES = ("assets", "favicon.svg", "robots.txt")

JSON_LD = (
    '  <script type="application/ld+json">\n'
    '  {"@context":"https://schema.org","@graph":[{"@type":"Organization",'
    '"@id":"https://quantumalliance.foundation/#organization","name":"Quantum Alliance",'
    '"url":"https://quantumalliance.foundation/","description":"An open standards body that '
    "defines what post-quantum readiness means for blockchain networks, wallets, and "
    'infrastructure, and how to test and verify any claim of quantum resistance.",'
    '"sameAs":["https://github.com/QuantumAllianceFoundation"]},{"@type":"WebSite",'
    '"@id":"https://quantumalliance.foundation/#website","name":"Quantum Alliance",'
    '"url":"https://quantumalliance.foundation/","publisher":'
    '{"@id":"https://quantumalliance.foundation/#organization"}}]}\n'
    "  </script>"
)


@dataclass(frozen=True)
class StaticPage:
    source: str  # path under content/, also the output path
    path: str | None  # URL path; None for the 404 page
    title: str
    description: str
    scripts: tuple[str, ...] = ()
    robots: str = "index, follow"
    og_type: str = "website"
    head_extra: str = ""

    @property
    def in_sitemap(self) -> bool:
        return self.path is not None and self.robots.startswith("index")


STATIC_PAGES = (
    StaticPage(
        "index.html", "/",
        "Quantum Alliance | Defining and verifying post-quantum readiness for blockchain",
        "The Quantum Alliance is an open standards body that defines what post-quantum "
        "readiness means for blockchain networks, wallets, and infrastructure, and how to "
        "test and verify any claim of quantum resistance.",
        scripts=("media-slider.js",),
        head_extra=JSON_LD,
    ),
    StaticPage(
        "media/index.html", "/media/", "Media | Quantum Alliance",
        "News coverage, reprints, and press release distribution of the Quantum Alliance.",
    ),
    StaticPage(
        "news/launch/index.html", "/news/launch/",
        "Quantum Alliance Forms to Define and Verify Post-Quantum Readiness for the "
        "Blockchain Industry | Quantum Alliance",
        "CEOs, CTOs, and founders from nine blockchain organizations launch the Quantum "
        "Alliance, an open standards body for post-quantum readiness in blockchain.",
        og_type="article",
        head_extra='  <meta property="article:published_time" content="2026-10-15">',
    ),
    StaticPage(
        "thanks/index.html", "/thanks/", "Thank you | Quantum Alliance",
        "Thank you for signing up for Quantum Alliance updates.", robots="noindex",
    ),
    StaticPage("404.html", None, "Page not found | Quantum Alliance", "Page not found.",
               robots="noindex"),
)

# (output path, URL path, title, description, renderer, has a sortable table)
REGISTRY_PAGES: tuple[tuple[str, str, str, str, Callable[[Registry], str], bool], ...] = (
    ("registry/index.html", "/registry/", "Registries | Quantum Alliance",
     "Open, community-maintained records of post-quantum readiness.", render_hub, False),
    ("registry/blockchains/index.html", "/registry/blockchains/",
     "Blockchain registry | Quantum Alliance",
     "Post-quantum readiness of blockchain networks.", render_blockchains, True),
    ("registry/algorithms/index.html", "/registry/algorithms/",
     "Algorithm registry | Quantum Alliance",
     "Post-quantum algorithms, with safety and implementing libraries.",
     render_algorithms_index, True),
    ("registry/libraries/index.html", "/registry/libraries/",
     f"{LIBRARIES_TITLE} | Quantum Alliance",
     "Post-quantum cryptography libraries, with safety, maturity, and sizes.",
     render_libraries, True),
    ("registry/products/index.html", "/registry/products/",
     "Product registry | Quantum Alliance",
     "Products built by Quantum Alliance members.", render_products, True),
)


@dataclass(frozen=True)
class Output:
    file: str
    path: str | None
    html: str
    in_sitemap: bool


def build_static(content: Path, reg: Registry, template: str, year: int) -> list[Output]:
    media = load_media(content / "media.toml", ROOT / "assets" / "media")
    markers = {
        "index.html": {
            "media:slider": media_cards(media, "coverage", "            "),
            "registry:cards": registry_cards(reg, "h4"),
        },
        "media/index.html": {
            "media:count": str(len(media)),
            **{
                f"media:{section}": media_cards(media, section, "          ")
                for section in ("coverage", "syndication", "press-release")
            },
        },
    }
    outputs = []
    for page in STATIC_PAGES:
        body = (content / page.source).read_text(encoding="utf-8").rstrip("\n")
        body = fill_markers(body, markers.get(page.source, {}))
        html = render_page(
            template, title=page.title, description=page.description, path=page.path,
            body=body, year=year, scripts=page.scripts, robots=page.robots,
            og_type=page.og_type, head_extra=page.head_extra,
        )
        outputs.append(Output(page.source, page.path, html, page.in_sitemap))
    return outputs


def build_registry(reg: Registry, template: str, year: int) -> list[Output]:
    def page(file: str, path: str, title: str, description: str, body: str,
             sortable: bool = False) -> Output:
        scripts = ("table-sort.js",) if sortable else ()
        html = render_page(template, title=title, description=description, path=path,
                           body=body, year=year, scripts=scripts)
        return Output(file, path, html, True)

    outputs = [
        page(file, path, title, description, render(reg), sortable)
        for file, path, title, description, render, sortable in REGISTRY_PAGES
    ]
    for algorithm in reg.algorithms.values():
        path = f"/registry/algorithms/{algorithm.id}/"
        outputs.append(page(f"{path[1:]}index.html", path, f"{algorithm.name} | Quantum Alliance",
                            algorithm.summary, render_algorithm(reg, algorithm.id)))
    for library in reg.libraries:
        slug = library_slug(library.name)
        path = f"/registry/libraries/{slug}/"
        outputs.append(page(
            f"{path[1:]}index.html", path, f"{library.name} | Quantum Alliance",
            f"{library.name}: post-quantum cryptography library details.",
            render_library(reg, slug),
        ))
    for chain in reg.chains:
        slug = chain_slug(chain.name)
        path = f"/registry/blockchains/{slug}/"
        outputs.append(page(
            f"{path[1:]}index.html", path, f"{chain.name} | Quantum Alliance",
            f"{chain.name}: post-quantum readiness of the blockchain.",
            render_chain(reg, slug),
        ))
    return outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "registry" / "data")
    parser.add_argument("--logos", type=Path, default=None)
    parser.add_argument("--auditors", type=Path, default=None)
    parser.add_argument("--content", type=Path, default=ROOT / "content")
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    args = parser.parse_args(argv)

    out = args.out.resolve()
    if out == ROOT or (out / ".git").exists():
        print(f"refusing to replace {out}: choose an output directory", file=sys.stderr)
        return 1

    try:
        reg = load_registry(args.data, args.logos, args.auditors)
        template = TEMPLATE.read_text(encoding="utf-8")
        year = date.today().year
        outputs = build_static(args.content, reg, template, year)
        outputs += build_registry(reg, template, year)
    except RegistryError as exc:
        for error in exc.errors:
            print(error, file=sys.stderr)
        return 1
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    # Start from an empty directory, so pages for removed entries do not linger.
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for name in STATIC_FILES:
        source = ROOT / name
        if source.is_dir():
            shutil.copytree(source, out / name)
        else:
            shutil.copy2(source, out / name)
    for item in outputs:
        file = out / item.file
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(item.html, encoding="utf-8")
    (out / "sitemap.xml").write_text(
        sitemap([item.path for item in outputs if item.in_sitemap and item.path]),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

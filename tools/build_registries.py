"""Build the registry pages from the TOML data files."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.registry.model import Registry, RegistryError, library_slug, load_registry
from tools.registry.render import (
    render_algorithm,
    render_algorithms_index,
    render_blockchains,
    render_hub,
    render_libraries,
    render_library,
    render_page,
    render_products,
)

TEMPLATE = Path(__file__).parent / "registry" / "page.html"

# (output path, URL path, title, description, renderer)
PAGES: tuple[tuple[str, str, str, str, Callable[[Registry], str]], ...] = (
    ("registry/index.html", "/registry/", "Registries | Quantum Alliance",
     "Open, community-maintained records of post-quantum readiness.", render_hub),
    ("registry/blockchains/index.html", "/registry/blockchains/",
     "Blockchain registry | Quantum Alliance",
     "Post-quantum readiness of blockchain networks.", render_blockchains),
    ("registry/algorithms/index.html", "/registry/algorithms/",
     "Algorithm registry | Quantum Alliance",
     "Post-quantum signature algorithms, with safety and implementing libraries.",
     render_algorithms_index),
    ("registry/libraries/index.html", "/registry/libraries/",
     "Library registry | Quantum Alliance",
     "Post-quantum signature libraries, with safety, maturity, and sizes.", render_libraries),
    ("registry/products/index.html", "/registry/products/",
     "Product registry | Quantum Alliance",
     "Products built by Quantum Alliance members.", render_products),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("registry/data"))
    parser.add_argument("--logos", type=Path, default=None)
    parser.add_argument("--auditors", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=Path("."))
    args = parser.parse_args(argv)

    try:
        reg = load_registry(args.data, args.logos, args.auditors)
    except RegistryError as exc:
        for error in exc.errors:
            print(error, file=sys.stderr)
        return 1

    template = TEMPLATE.read_text(encoding="utf-8")
    rendered = [
        (
            args.out / out_path,
            render_page(template, title=title, description=description, path=url, body=render(reg)),
        )
        for out_path, url, title, description, render in PAGES
    ]
    for algorithm in reg.algorithms.values():
        url = f"/registry/algorithms/{algorithm.id}/"
        rendered.append((
            args.out / f"registry/algorithms/{algorithm.id}/index.html",
            render_page(
                template,
                title=f"{algorithm.name} | Quantum Alliance",
                description=algorithm.summary,
                path=url,
                body=render_algorithm(reg, algorithm.id),
            ),
        ))
    for library in reg.libraries:
        slug = library_slug(library.name)
        rendered.append((
            args.out / f"registry/libraries/{slug}/index.html",
            render_page(
                template,
                title=f"{library.name} | Quantum Alliance",
                description=f"{library.name}: post-quantum signature library details.",
                path=f"/registry/libraries/{slug}/",
                body=render_library(reg, slug),
            ),
        ))
    for file, html in rendered:
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(html, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

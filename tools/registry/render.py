"""Render registry pages as HTML (standard library only)."""

from __future__ import annotations

from collections.abc import Sequence
from html import escape
from string import Template

from .model import (
    CATEGORIES,
    CATEGORY_LABELS,
    SAFETY_BY_FAMILY,
    SAFETY_RANK,
    Registry,
    Size,
    library_safety,
)

REPO_URL = "https://github.com/QuantumAllianceFoundation/quantumalliance.foundation"

CATEGORY_DEFINITIONS = {
    "post-quantum": "Has deployed a post-quantum solution.",
    "post-quantum-ready": "Has published source code for a post-quantum solution that is not yet deployed.",
    "quantum-aware": (
        "Not yet post-quantum, but working on solutions that we believe will mitigate "
        "most of the risk, with a team that is on top of the transition."
    ),
    "quantum-vulnerable": (
        "No work, or some work with no clear deployment path. "
        "Example: Bitcoin, where BIP-360 is proposed but has no deployment path."
    ),
}

EMPTY_STATE = '<p class="intro">No entries yet. Be the first to add one.</p>'


def _e(text: str) -> str:
    return escape(text, quote=True)


def _link(url: str, text: str) -> str:
    return f'<a href="{_e(url)}">{_e(text)}</a>'


def _external(url: str, text: str) -> str:
    return f'<a href="{_e(url)}" target="_blank" rel="noopener noreferrer">{_e(text)}</a>'


def _td(content: str, sort: str | int) -> str:
    return f'<td data-sort="{_e(str(sort))}">{content}</td>'


def _th(label: str, numeric: bool = False) -> str:
    kind = ' data-sort-type="number"' if numeric else ""
    return f'<th scope="col"{kind}>{_e(label)}</th>'


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    head = "".join(headers)
    body = "\n".join(f"        <tr>{''.join(cells)}</tr>" for cells in rows)
    return (
        '<div class="table-wrap">\n'
        "    <table data-sortable>\n"
        f"      <thead><tr>{head}</tr></thead>\n"
        f"      <tbody>\n{body}\n      </tbody>\n"
        "    </table>\n"
        "  </div>"
    )


def edit_links(data_file: str, issue_template: str) -> str:
    return (
        '<div class="registry-actions">\n'
        "    <p class=\"muted\">Spotted an error or a missing entry? Edit this registry on "
        "GitHub to open a pull request, or suggest a change in an issue.</p>\n"
        f'    {_external(f"{REPO_URL}/edit/main/registry/data/{data_file}", "Edit on GitHub")}\n'
        f'    {_external(f"{REPO_URL}/issues/new?template={issue_template}", "Suggest a change")}\n'
        "  </div>"
    )


def format_size(size: Size | None) -> str:
    if size is None:
        return "—"
    return f"{size.bytes} B ({size.parameter_set})"


def _registry_section(
    eyebrow: str,
    heading: str,
    intro: str,
    data_file: str,
    issue_template: str,
    table: str | None,
    extra: str = "",
) -> str:
    links = edit_links(data_file, issue_template)
    middle = f"{table}\n  {links}" if table else EMPTY_STATE
    return (
        '    <section class="section">\n'
        '      <div class="wrap">\n'
        f'        <p class="eyebrow">{_e(eyebrow)}</p>\n'
        f"        <h1>{_e(heading)}</h1>\n"
        f'        <p class="intro">{_e(intro)}</p>\n'
        f"        {extra}\n"
        f"        {links}\n"
        f"        {middle}\n"
        "      </div>\n"
        "    </section>"
    )


def render_hub(reg: Registry) -> str:
    cards = [
        ("Blockchains", "/registry/blockchains/", len(reg.chains),
         "Post-quantum readiness of blockchain networks."),
        ("Libraries", "/registry/libraries/", len(reg.libraries),
         "Post-quantum cryptography libraries and their maturity."),
        ("Products", "/registry/products/", len(reg.products),
         "Products built by Quantum Alliance members."),
    ]
    items = "\n".join(
        '          <div class="card">\n'
        f'            <h3>{_link(path, name)}</h3>\n'
        f'            <p class="muted">{_e(blurb)}</p>\n'
        f'            <p class="muted">{count} {"entry" if count == 1 else "entries"}</p>\n'
        "          </div>"
        for name, path, count, blurb in cards
    )
    return (
        '    <section class="section">\n'
        '      <div class="wrap">\n'
        '        <p class="eyebrow">Registries</p>\n'
        "        <h1>Quantum readiness registries</h1>\n"
        '        <p class="intro">Open, community-maintained records of post-quantum readiness. '
        "Anyone can propose a change on GitHub.</p>\n"
        '        <div class="grid-3">\n'
        f"{items}\n"
        "        </div>\n"
        "      </div>\n"
        "    </section>"
    )


def render_blockchains(reg: Registry) -> str:
    legend = (
        '<dl class="legend">\n'
        + "\n".join(
            f'          <div><dt><span class="badge badge--{key}">{_e(CATEGORY_LABELS[key])}</span></dt>'
            f"<dd>{_e(CATEGORY_DEFINITIONS[key])}</dd></div>"
            for key in CATEGORIES
        )
        + "\n        </dl>"
    )
    chains = sorted(reg.chains, key=lambda c: (CATEGORIES.index(c.category), c.name.casefold()))
    rows = []
    for c in chains:
        algs = [reg.algorithms[a] for a in c.algorithms]
        rows.append([
            _td(_e(c.name), c.name.casefold()),
            _td(
                f'<span class="badge badge--{c.category}">{_e(CATEGORY_LABELS[c.category])}</span>',
                CATEGORIES.index(c.category),
            ),
            _td(
                ", ".join(_link(a.url, a.name) for a in algs) or "—",
                ", ".join(a.name for a in algs).casefold(),
            ),
            _td(_link(c.website, "Website"), c.website.casefold()),
            _td(_link(c.source, "Source"), c.source.casefold()),
            _td(
                "<br>".join(_link(n.url, n.title) for n in c.notes) or "—",
                " ".join(n.title for n in c.notes).casefold(),
            ),
        ])
    table = (
        _table(
            [_th("Chain"), _th("Category", True), _th("Algorithms"), _th("Website"),
             _th("Source"), _th("Notes")],
            rows,
        )
        if rows
        else None
    )
    return _registry_section(
        "Registries", "Blockchains",
        "How ready each blockchain is for quantum computers.",
        "blockchains.toml", "registry-blockchain.yml", table, legend,
    )


def render_libraries(reg: Registry) -> str:
    legend = (
        '<p class="muted">Safety reflects the hardness assumption of the algorithms: '
        "High for hash-based, Medium for lattice-based (including FN-DSA), Low for others.</p>"
    )
    libs = sorted(
        reg.libraries,
        key=lambda lib: (SAFETY_RANK[library_safety(lib, reg.algorithms)], lib.name.casefold()),
    )
    rows = []
    for lib in libs:
        safety = library_safety(lib, reg.algorithms)
        chips = " ".join(
            f'<span class="alg safety--{SAFETY_BY_FAMILY[reg.algorithms[a].family].lower()}">'
            f"{_e(reg.algorithms[a].name)} "
            f"<small>{SAFETY_BY_FAMILY[reg.algorithms[a].family]}</small></span>"
            for a in lib.algorithms
        )
        audited = (
            "Yes: " + ", ".join(_link(a.url, a.title) for a in lib.audits)
            if lib.audits
            else "No"
        )
        rows.append([
            _td(_link(lib.source, lib.name), lib.name.casefold()),
            _td(chips, " ".join(reg.algorithms[a].name for a in lib.algorithms).casefold()),
            _td(f'<span class="safety safety--{safety.lower()}">{safety}</span>', SAFETY_RANK[safety]),
            _td(audited, "yes" if lib.audits else "no"),
            _td(_e(lib.maturity), lib.maturity),
            _td("Yes" if lib.blockchain_friendly else "No", "yes" if lib.blockchain_friendly else "no"),
            _td(_e(format_size(lib.min_signature)), lib.min_signature.bytes if lib.min_signature else ""),
            _td(_e(format_size(lib.min_public_key)), lib.min_public_key.bytes if lib.min_public_key else ""),
            _td("<br>".join(_e(n) for n in lib.notes) or "—", " ".join(lib.notes).casefold()),
        ])
    table = (
        _table(
            [_th("Library"), _th("Algorithms"), _th("Safety", True), _th("Audited"),
             _th("Maturity"), _th("Blockchain friendly"), _th("Min signature", True),
             _th("Min public key", True), _th("Notes")],
            rows,
        )
        if rows
        else None
    )
    return _registry_section(
        "Registries", "Libraries",
        "Post-quantum signature libraries, with the smallest sizes each one offers.",
        "libraries.toml", "registry-library.yml", table, legend,
    )


def render_products(reg: Registry) -> str:
    products = sorted(reg.products, key=lambda p: (p.member.casefold(), p.name.casefold()))
    rows = [
        [
            _td(_link(p.url, p.name), p.name.casefold()),
            _td(_e(p.member), p.member.casefold()),
            _td(_e(p.description), p.description.casefold()),
            _td(_e(", ".join(p.chains)), ", ".join(p.chains).casefold()),
        ]
        for p in products
    ]
    table = (
        _table([_th("Name"), _th("Member"), _th("What it is"), _th("Supported chains")], rows)
        if rows
        else None
    )
    return _registry_section(
        "Registries", "Products", "Products built by Quantum Alliance members.",
        "products.toml", "registry-product.yml", table,
    )


def render_page(template: str, *, title: str, description: str, path: str, body: str) -> str:
    return Template(template).substitute(
        title=_e(title), description=_e(description), path=_e(path), body=body
    )

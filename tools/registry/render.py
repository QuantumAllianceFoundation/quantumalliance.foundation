"""Render registry pages as HTML (standard library only)."""

from __future__ import annotations

from collections.abc import Sequence
from html import escape
from string import Template

from .model import (
    CATEGORIES,
    CATEGORY_LABELS,
    LAYER_VALUES,
    SAFETY_BY_FAMILY,
    SAFETY_RANK,
    Link,
    Registry,
    Size,
    library_safety,
    overall_category,
)

REPO_URL = "https://github.com/QuantumAllianceFoundation/quantumalliance.foundation"

CATEGORY_DEFINITIONS = {
    "post-quantum": "Has deployed a post-quantum solution.",
    "no-signatures": (
        "The layer does not use digital signatures, for example proof-of-work mining, "
        "which relies on hashing."
    ),
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

INFO_ICON = (
    '<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false">'
    '<circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" stroke-width="1.5"/>'
    '<circle cx="8" cy="4.75" r="1" fill="currentColor"/>'
    '<path d="M8 7.25v4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>'
    "</svg>"
)

EMPTY_STATE = '<p class="intro">No entries yet. Be the first to add one.</p>'


def _e(text: str) -> str:
    return escape(text, quote=True)


def _link(url: str, text: str) -> str:
    return f'<a href="{_e(url)}">{_e(text)}</a>'


def _external(url: str, text: str) -> str:
    return f'<a href="{_e(url)}" target="_blank" rel="noopener noreferrer">{_e(text)}</a>'


def _td(content: str, sort: str | int, css_class: str = "") -> str:
    cls = f' class="{css_class}"' if css_class else ""
    return f'<td{cls} data-sort="{_e(str(sort))}">{content}</td>'


def _badge(layer: str) -> str:
    return f'<span class="badge badge--{layer}">{_e(CATEGORY_LABELS[layer])}</span>'


def _layer_td(layer: str) -> str:
    return _td(_badge(layer), LAYER_VALUES.index(layer))


def _notes_parts(table: str, row: int, name: str, note: str | None, links: Sequence[Link]):
    """Return (notes cell, name-cell extras, sort value) for one row.

    Wide screens show the inline notes cell. Narrow screens hide that cell and show the
    icon button and popover that sit beside the name.
    """
    if not note and not links:
        return _td("—", "", "col-notes"), ""
    parts = ([_e(note)] if note else []) + [_link(link.url, link.title) for link in links]
    inline = "<br>".join(parts)
    popover_id = f"notes-{table}-{row}"
    sort = " ".join(([note] if note else []) + [link.title for link in links]).casefold()
    extras = (
        f'<button type="button" class="notes-toggle" popovertarget="{popover_id}" '
        f'aria-label="Notes for {_e(name)}">{INFO_ICON}</button>'
        f'<div id="{popover_id}" popover class="notes-popover">'
        f"<h3>{_e(name)}</h3>"
        f"<p>{inline}</p>"
        f'<button type="button" class="notes-close" popovertarget="{popover_id}" '
        'popovertargetaction="hide">Close</button>'
        "</div>"
    )
    return _td(inline, sort, "col-notes"), extras


def _th(label: str, numeric: bool = False, css_class: str = "") -> str:
    cls = f' class="{css_class}"' if css_class else ""
    kind = ' data-sort-type="number"' if numeric else ""
    return f'<th scope="col"{cls}{kind}>{_e(label)}</th>'


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
            f"          <div><dt>{_badge(key)}</dt><dd>{_e(CATEGORY_DEFINITIONS[key])}</dd></div>"
            for key in LAYER_VALUES
        )
        + "\n        </dl>\n"
        '        <p class="muted">Overall is the less ready of the two layers.</p>'
    )
    chains = sorted(
        reg.chains, key=lambda c: (CATEGORIES.index(overall_category(c)), c.name.casefold())
    )
    rows = []
    for index, c in enumerate(chains):
        algs = [reg.algorithms[a] for a in c.algorithms]
        notes_cell, notes_extras = _notes_parts("blockchains", index, c.name, c.note, c.links)
        rows.append([
            _td(_e(c.name) + notes_extras, c.name.casefold(), "name-cell"),
            _layer_td(overall_category(c)),
            _layer_td(c.consensus),
            _layer_td(c.transactions),
            _td(
                ", ".join(_link(a.url, a.name) for a in algs) or "—",
                ", ".join(a.name for a in algs).casefold(),
            ),
            _td(_link(c.website, "Website"), c.website.casefold()),
            _td(_link(c.source, "Source"), c.source.casefold()),
            notes_cell,
        ])
    table = (
        _table(
            [_th("Chain"), _th("Overall", True), _th("Consensus", True),
             _th("Transactions", True), _th("Algorithms"), _th("Website"),
             _th("Source"), _th("Notes", css_class="col-notes")],
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
    for index, lib in enumerate(libs):
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
        notes_cell, notes_extras = _notes_parts("libraries", index, lib.name, lib.note, lib.links)
        rows.append([
            _td(_link(lib.source, lib.name) + notes_extras, lib.name.casefold(), "name-cell"),
            _td(chips, " ".join(reg.algorithms[a].name for a in lib.algorithms).casefold()),
            _td(f'<span class="safety safety--{safety.lower()}">{safety}</span>', SAFETY_RANK[safety]),
            _td(audited, "yes" if lib.audits else "no"),
            _td(_e(lib.maturity), lib.maturity),
            _td("Yes" if lib.blockchain_friendly else "No", "yes" if lib.blockchain_friendly else "no"),
            _td(_e(format_size(lib.min_signature)), lib.min_signature.bytes if lib.min_signature else ""),
            _td(_e(format_size(lib.min_public_key)), lib.min_public_key.bytes if lib.min_public_key else ""),
            notes_cell,
        ])
    table = (
        _table(
            [_th("Library"), _th("Algorithms"), _th("Safety", True), _th("Audited"),
             _th("Maturity"), _th("Blockchain friendly"), _th("Min signature", True),
             _th("Min public key", True), _th("Notes", css_class="col-notes")],
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

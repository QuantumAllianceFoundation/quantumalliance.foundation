"""Render registry pages as HTML (standard library only)."""

from __future__ import annotations

from collections.abc import Sequence
from html import escape
from urllib.parse import urlsplit
from string import Template

from .model import (
    CATEGORY_LABELS,
    LAYER_VALUES,
    SAFETY_RANK,
    Audit,
    Link,
    Registry,
    Size,
    Chain,
    Library,
    Repository,
    algorithm_safety,
    chain_slug,
    library_capabilities,
    library_safety,
    library_safety_reason,
    library_slug,
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

SPRITE = "/assets/icons/registry-icons.svg"
LOGO_DIR = "/assets/registry/logos"
AUDITOR_LOGO_DIR = "/assets/registry/auditors"
SOURCE_ICONS = {"github.com": "github", "gitlab.com": "gitlab"}

EMPTY_STATE = '<p class="intro">No entries yet. Be the first to add one.</p>'


def _e(text: str) -> str:
    return escape(text, quote=True)


def _link(url: str, text: str) -> str:
    return f'<a href="{_e(url)}">{_e(text)}</a>'


def _link_html(url: str, inner_html: str) -> str:
    return f'<a href="{_e(url)}">{inner_html}</a>'


def _external(url: str, text: str) -> str:
    return f'<a href="{_e(url)}" target="_blank" rel="noopener noreferrer">{_e(text)}</a>'


def _icon_link(url: str, label: str, symbol: str) -> str:
    return (
        f'<a href="{_e(url)}" class="icon-link" aria-label="{_e(label)}">'
        '<svg class="icon" aria-hidden="true" focusable="false">'
        f'<use href="{SPRITE}#{symbol}"/></svg></a>'
    )


def _source_symbol(url: str) -> str:
    return SOURCE_ICONS.get((urlsplit(url).hostname or "").lower(), "git")


def _algorithm_url(algorithm_id: str) -> str:
    return f"/registry/algorithms/{algorithm_id}/"


def _safety_badge(safety: str) -> str:
    return f'<span class="safety safety--{safety.lower()}">{safety}</span>'


def _library_url(lib: Library) -> str:
    return f"/registry/libraries/{library_slug(lib.name)}/"


def _chain_url(chain: Chain) -> str:
    return f"/registry/blockchains/{chain_slug(chain.name)}/"


def _capability_tags(reg: Registry, lib: Library) -> str:
    return " ".join(
        f'<span class="cap-tag">{_e(label)}</span>' for label in library_capabilities(lib, reg.algorithms)
    )


def _algorithm_chips(reg: Registry, ids: Sequence[str]) -> str:
    return " ".join(
        f'<a href="{_algorithm_url(a)}" class="alg">{_e(reg.algorithms[a].name)}</a>' for a in ids
    )


def _repo_icon_link(lib: Library, repo: Repository) -> str:
    return _icon_link(
        repo.url, f"{lib.name} {repo.language} source code", _source_symbol(repo.url)
    )


def _bool_icon(value: bool) -> str:
    word, symbol = ("Yes", "check") if value else ("No", "x")
    return (
        f'<span class="bool-icon {word.lower()}">'
        '<svg class="icon" aria-hidden="true" focusable="false">'
        f'<use href="{SPRITE}#{symbol}"/></svg>'
        f'<span class="visually-hidden">{word}</span></span>'
    )


def _audit_link(audit: Audit) -> str:
    inner = (
        f'<img src="{AUDITOR_LOGO_DIR}/{_e(audit.logo)}" alt="" width="20" height="20">'
        if audit.logo
        else _e(audit.auditor)
    )
    return (
        f'<a href="{_e(audit.url)}" class="audit-link" '
        f'aria-label="{_e(audit.auditor)} audit report">{inner}</a>'
    )


def _audits_html(audits: Sequence[Audit]) -> str:
    return "Yes " + " ".join(_audit_link(a) for a in audits) if audits else "No"


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


def _table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    table_class: str = "",
) -> str:
    head = "".join(headers)
    body = "\n".join(f"        <tr>{''.join(cells)}</tr>" for cells in rows)
    cls = f' class="{table_class}"' if table_class else ""
    return (
        '<div class="table-wrap">\n'
        f"    <table data-sortable{cls}>\n"
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
        ("Algorithms", "/registry/algorithms/", len(reg.algorithms),
         "Post-quantum algorithms, with safety and research papers."),
        (LIBRARIES_TITLE, "/registry/libraries/", len(reg.libraries),
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
        '        <p class="muted">Consensus covers how the network agrees on blocks, '
        "such as validator votes or mining. Transactions covers the signatures "
        "that authorize moving funds.</p>"
    )
    chains = sorted(
        reg.chains,
        key=lambda c: (
            LAYER_VALUES.index(c.transactions),
            LAYER_VALUES.index(c.consensus),
            c.name.casefold(),
        ),
    )
    rows = []
    for index, c in enumerate(chains):
        algs = [reg.algorithms[a] for a in c.algorithms]
        notes_cell, notes_extras = _notes_parts("blockchains", index, c.name, c.note, c.links)
        rows.append([
            _td(_link_html(_chain_url(c), _chain_name(c)) + notes_extras, c.name.casefold(), "name-cell"),
            _layer_td(c.consensus),
            _layer_td(c.transactions),
            _td(
                ", ".join(_link(_algorithm_url(a.id), a.name) for a in algs) or "—",
                ", ".join(a.name for a in algs).casefold(),
            ),
            _td(_icon_link(c.website, f"{c.name} website", "globe"), c.website.casefold(), "col-icon"),
            _td(
                _icon_link(c.source, f"{c.name} source code", _source_symbol(c.source)),
                c.source.casefold(),
                "col-icon",
            ),
            notes_cell,
        ])
    table = (
        _table(
            [_th("Chain"), _th("Consensus", True), _th("Transactions", True),
             _th("Algorithms"), _th("Website", css_class="col-icon"),
             _th("Source", css_class="col-icon"), _th("Notes", css_class="col-notes")],
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


def _chain_name(chain: Chain, size: int = 20) -> str:
    if chain.logo is None:
        return _e(chain.name)
    return (
        f'<img src="{LOGO_DIR}/{_e(chain.logo)}" alt="" width="{size}" height="{size}" '
        f'class="chain-logo">{_e(chain.name)}'
    )


LIBRARY_SAFETY_LEGEND = (
    "High safety requires a hybrid design, where a classical and a post-quantum "
    "signature must both verify. Without one, hash-based libraries rate Medium, "
    "and lattice-based and other libraries rate Low."
)


LIBRARIES_TITLE = "Post-Quantum Cryptography Libraries"


def render_libraries(reg: Registry) -> str:
    legend = f'<p class="muted">{_e(LIBRARY_SAFETY_LEGEND)}</p>'
    libs = sorted(
        reg.libraries,
        key=lambda lib: (SAFETY_RANK[library_safety(lib, reg.algorithms)], lib.name.casefold()),
    )
    rows = []
    for index, lib in enumerate(libs):
        safety = library_safety(lib, reg.algorithms)
        languages = ", ".join(r.language for r in lib.repositories)
        notes_cell, notes_extras = _notes_parts("libraries", index, lib.name, lib.note, lib.links)
        rows.append([
            _td(
                _link(_library_url(lib), lib.name)
                + f'<span class="cap-tags">{_capability_tags(reg, lib)}</span>'
                + notes_extras,
                lib.name.casefold(),
                "name-cell",
            ),
            _td(
                _algorithm_chips(reg, lib.algorithms),
                " ".join(reg.algorithms[a].name for a in lib.algorithms).casefold(),
            ),
            _td(
                "".join(
                    f'<span class="repo-line">{_repo_icon_link(lib, r)} {_e(r.language)}</span>'
                    for r in lib.repositories
                ),
                languages.casefold(),
                "col-source",
            ),
            _td(_safety_badge(safety), SAFETY_RANK[safety]),
            _td(_audits_html(lib.audits), "yes" if lib.audits else "no"),
            _td(_e(lib.maturity), lib.maturity),
            _td(_bool_icon(lib.blockchain_friendly), int(lib.blockchain_friendly)),
            _td(_e(format_size(lib.min_signature)), lib.min_signature.bytes if lib.min_signature else ""),
            _td(_e(format_size(lib.min_public_key)), lib.min_public_key.bytes if lib.min_public_key else ""),
            notes_cell,
        ])
    table = (
        _table(
            [_th("Library"), _th("Algorithms"), _th("Source"), _th("Safety", True), _th("Audited"),
             _th("Maturity"), _th("Blockchain friendly"), _th("Min signature", True),
             _th("Min public key", True), _th("Notes", css_class="col-notes")],
            rows,
            "libraries-table",
        )
        if rows
        else None
    )
    return _registry_section(
        "Registries", LIBRARIES_TITLE,
        "Post-quantum cryptography libraries, with the smallest sizes each one offers.",
        "libraries.toml", "registry-library.yml", table, legend,
    )


def _detail_row(label: str, content: str) -> str:
    return f"          <div><dt>{_e(label)}</dt><dd>{content}</dd></div>"


def render_library(reg: Registry, slug: str) -> str:
    lib = next((lib for lib in reg.libraries if library_slug(lib.name) == slug), None)
    if lib is None:
        raise ValueError(f"unknown library slug: {slug}")
    safety = library_safety(lib, reg.algorithms)
    repos = "\n".join(
        f"          <li>{_repo_icon_link(lib, r)} {_e(r.language)}</li>" for r in lib.repositories
    )
    notes = " ".join(
        ([_e(lib.note)] if lib.note else []) + [_link(link.url, link.title) for link in lib.links]
    )
    rows = [
        _detail_row("Repositories", f'<ul class="repo-list">\n{repos}\n        </ul>'),
        _detail_row("Algorithms", _algorithm_chips(reg, lib.algorithms)),
        _detail_row(
            "Safety",
            f"{_safety_badge(safety)} {_e(library_safety_reason(lib, reg.algorithms))}",
        ),
        _detail_row("Hybrid", "Yes" if lib.hybrid else "No"),
        _detail_row("Audits", _audits_html(lib.audits)),
        _detail_row("Maturity", _e(lib.maturity)),
        _detail_row("Blockchain friendly", _bool_icon(lib.blockchain_friendly)),
        _detail_row("Minimum signature", _e(format_size(lib.min_signature))),
        _detail_row("Minimum public key", _e(format_size(lib.min_public_key))),
        _detail_row("Note and links", notes or "—"),
    ]
    return (
        '    <section class="section">\n'
        '      <div class="wrap">\n'
        '        <p class="eyebrow">Library</p>\n'
        f"        <h1>{_e(lib.name)}</h1>\n"
        f'        <p class="cap-tags">{_capability_tags(reg, lib)}</p>\n'
        '        <dl class="detail-list">\n' + "\n".join(rows) + "\n        </dl>\n"
        f"        {edit_links('libraries.toml', 'registry-library.yml')}\n"
        "      </div>\n"
        "    </section>"
    )


def render_chain(reg: Registry, slug: str) -> str:
    chain = next((c for c in reg.chains if chain_slug(c.name) == slug), None)
    if chain is None:
        raise ValueError(f"unknown chain slug: {slug}")
    algorithms = (
        _algorithm_chips(reg, chain.algorithms) if chain.algorithms else "None deployed"
    )
    notes = " ".join(
        ([_e(chain.note)] if chain.note else [])
        + [_link(link.url, link.title) for link in chain.links]
    )
    rows = [
        _detail_row("Consensus", _rating(chain.consensus, chain.consensus_reason)),
        _detail_row("Transactions", _rating(chain.transactions, chain.transactions_reason)),
        _detail_row("Algorithms", algorithms),
        _detail_row(
            "Website",
            _icon_link(chain.website, f"{chain.name} website", "globe") + " Website",
        ),
        _detail_row(
            "Source",
            _icon_link(chain.source, f"{chain.name} source code", _source_symbol(chain.source))
            + " Source",
        ),
        _detail_row("Note and links", notes or "—"),
    ]
    return (
        '    <section class="section">\n'
        '      <div class="wrap">\n'
        '        <p class="eyebrow">Blockchain</p>\n'
        f"        <h1>{_chain_name(chain, 32)}</h1>\n"
        '        <dl class="detail-list">\n' + "\n".join(rows) + "\n        </dl>\n"
        f"        {edit_links('blockchains.toml', 'registry-blockchain.yml')}\n"
        "      </div>\n"
        "    </section>"
    )


def _rating(layer: str, reason: str) -> str:
    return (
        f"{_badge(layer)}\n"
        '            <p class="rating-reason"><strong>Why this rating.</strong> '
        f"{_e(reason)}</p>"
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


def _implementers(reg: Registry, algorithm_id: str) -> list[Library]:
    libs = [lib for lib in reg.libraries if algorithm_id in lib.algorithms]
    return sorted(libs, key=lambda lib: lib.name.casefold())


def render_algorithms_index(reg: Registry) -> str:
    algorithms = sorted(reg.algorithms.values(), key=lambda a: a.name.casefold())
    rows = []
    for a in algorithms:
        count = len(_implementers(reg, a.id))
        rows.append([
            _td(_link(_algorithm_url(a.id), a.name), a.name.casefold()),
            _td(_e(a.family), a.family),
            _td(
                _safety_badge(algorithm_safety(a)),
                SAFETY_RANK[algorithm_safety(a)],
            ),
            _td(str(count), count),
        ])
    table = (
        _table(
            [_th("Algorithm"), _th("Family"), _th("Safety", True), _th("Libraries", True)],
            rows,
        )
        if rows
        else None
    )
    return _registry_section(
        "Registries", "Algorithms",
        "Post-quantum algorithms, with the libraries that implement each one.",
        "algorithms.toml", "registry-algorithm.yml", table,
    )


def render_algorithm(reg: Registry, algorithm_id: str) -> str:
    a = reg.algorithms[algorithm_id]
    safety = algorithm_safety(a)
    libs = _implementers(reg, algorithm_id)
    papers = "\n".join(f"          <li>{_external(p.url, p.title)}</li>" for p in a.papers)
    implemented = (
        '<ul class="link-list">\n'
        + "\n".join(
            f"          <li>{_link(_library_url(lib), lib.name)}</li>"
            for lib in libs
        )
        + "\n        </ul>"
        if libs
        else '<p class="muted">No libraries listed yet.</p>'
    )
    return (
        '    <section class="section">\n'
        '      <div class="wrap">\n'
        '        <p class="eyebrow">Algorithm</p>\n'
        f"        <h1>{_e(a.name)}</h1>\n"
        f'        <p class="muted">Family: {_e(a.family)}.</p>\n'
        f'        <p class="intro">{_e(a.summary)}</p>\n'
        f'        <p class="muted">Safety: {_safety_badge(safety)}</p>\n'
        '        <h2 class="link-list-heading">Why this rating</h2>\n'
        f"        <p>{_e(a.rationale)}</p>\n"
        '        <h2 class="link-list-heading">Standard</h2>\n'
        f"        <p>{_external(a.url, a.url)}</p>\n"
        '        <h2 class="link-list-heading">Research</h2>\n'
        f'        <ul class="link-list">\n{papers}\n        </ul>\n'
        '        <h2 class="link-list-heading">Implemented by</h2>\n'
        f"        {implemented}\n"
        f"        {edit_links('algorithms.toml', 'registry-algorithm.yml')}\n"
        "      </div>\n"
        "    </section>"
    )


def render_page(template: str, *, title: str, description: str, path: str, body: str) -> str:
    return Template(template).substitute(
        title=_e(title), description=_e(description), path=_e(path), body=body
    )

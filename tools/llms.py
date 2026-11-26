"""The /llms.txt index for language models (https://llmstxt.org/)."""

from __future__ import annotations

from tools.registry.model import CATEGORY_LABELS, Registry, chain_slug, library_slug
from tools.site import CHARTER_URL, FORUM_URL, SITE_URL

REPO_URL = "https://github.com/QuantumAllianceFoundation/quantumalliance.foundation"
STANDARDS_URL = "https://github.com/QuantumAllianceFoundation/standards"
RAW_DATA_URL = (
    "https://raw.githubusercontent.com/QuantumAllianceFoundation/"
    "quantumalliance.foundation/main/registry/data"
)


def _text(value: str) -> str:
    """One line of list text: no line breaks, and no brackets that would end a link."""
    return " ".join(value.split()).replace("[", "(").replace("]", ")")


def _item(name: str, url: str, notes: str = "") -> str:
    line = f"- [{_text(name)}]({url})"
    return f"{line}: {_text(notes)}" if notes else line


def llms_txt(reg: Registry) -> str:
    chains = [
        _item(
            c.name,
            f"{SITE_URL}/registry/blockchains/{chain_slug(c.name)}/",
            f"transactions {CATEGORY_LABELS[c.transactions]}; "
            f"consensus {CATEGORY_LABELS[c.consensus]}",
        )
        for c in reg.chains
    ]
    algorithms = [
        _item(a.name, f"{SITE_URL}/registry/algorithms/{a.id}/", a.summary)
        for a in reg.algorithms.values()
    ]
    libraries = [
        _item(lib.name, f"{SITE_URL}/registry/libraries/{library_slug(lib.name)}/",
              f"maturity {lib.maturity}")
        for lib in reg.libraries
    ]
    products = [_item(p.name, p.url, f"{p.member}. {p.description}") for p in reg.products]
    data = [
        _item(f"{kind}.toml", f"{RAW_DATA_URL}/{kind}.toml",
              "source data; the file header defines every field and value")
        for kind in ("blockchains", "algorithms", "libraries", "products")
    ]
    sections = [
        "# Quantum Alliance",
        "> An open standards body that defines what post-quantum readiness means for "
        "blockchain networks, wallets, and infrastructure, and how to test and verify "
        "any claim of quantum resistance.",
        "The registries are open, community-maintained records. Each blockchain gets one "
        "readiness value for its transaction layer and one for its consensus layer. "
        "Each blockchain page gives the reason for each value and links to the evidence. "
        "To propose a change, open a pull request on GitHub and follow the contribution "
        "rules for agents.",
        "## Pages\n\n" + "\n".join([
            _item("Home", f"{SITE_URL}/", "mission, working groups, founding members"),
            _item("Registries", f"{SITE_URL}/registry/", "index of the four registries"),
            _item("Media", f"{SITE_URL}/media/", "press coverage and press releases"),
            _item("Launch announcement", f"{SITE_URL}/news/launch/"),
            _item("Charter", CHARTER_URL),
        ]),
        "## Blockchain registry\n\n" + "\n".join(chains),
        "## Algorithm registry\n\n" + "\n".join(algorithms),
        "## Library registry\n\n" + "\n".join(libraries),
        "## Registry data\n\n" + "\n".join(data),
        "## Contributing\n\n" + "\n".join([
            _item("Contribution rules for agents", f"{REPO_URL}/blob/main/AGENTS.md",
                  "one content change per pull request; no style changes"),
            _item("Forum", FORUM_URL, "standards proposals and discussion"),
            _item("Standards repository", STANDARDS_URL),
        ]),
        "## Optional\n\n" + "\n".join(
            [_item("Product registry", f"{SITE_URL}/registry/products/")] + products
        ),
    ]
    return "\n\n".join(sections) + "\n"

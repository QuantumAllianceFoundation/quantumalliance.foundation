import re
import unittest
from pathlib import Path

from tools.registry.model import (
    Algorithm,
    Chain,
    Library,
    Link,
    Product,
    Registry,
    Size,
    library_slug,
    load_registry,
)
from tools.registry.render import (
    REPO_URL,
    edit_links,
    format_size,
    render_algorithm,
    render_algorithms_index,
    render_blockchains,
    render_hub,
    render_libraries,
    render_page,
    render_products,
)

VALID = Path(__file__).parent / "fixtures" / "valid"

ALGS = {
    "ml-dsa": Algorithm("ml-dsa", "ML-DSA", "lattice", "https://example.org/ml", "S", ()),
    "slh-dsa": Algorithm(
        "slh-dsa", "SLH-DSA", "hash-based", "https://example.org/slh", "S", ()
    ),
}


def chain(
    name,
    consensus="post-quantum",
    transactions="post-quantum",
    note=None,
    links=(),
    website="https://example.org/",
    source="https://example.org/src",
    algorithms=(),
    logo=None,
):
    return Chain(
        name, consensus, transactions, website, source,
        tuple(algorithms), note, tuple(links), logo,
    )


def library(
    name="Lib",
    algorithms=("ml-dsa",),
    maturity="production",
    blockchain_friendly=False,
    audits=(),
    min_signature: Size | None = None,
    min_public_key: Size | None = None,
    note: str | None = None,
    links=(),
):
    return Library(
        name=name,
        source="https://example.org/lib",
        algorithms=algorithms,
        maturity=maturity,
        blockchain_friendly=blockchain_friendly,
        audits=audits,
        min_signature=min_signature,
        min_public_key=min_public_key,
        note=note,
        links=links,
    )


def registry(chains=(), libraries=(), products=()):
    return Registry(dict(ALGS), tuple(chains), tuple(libraries), tuple(products))


class RenderTests(unittest.TestCase):
    def test_no_overall_column(self):
        btc = chain("Bitcoin", "no-signatures", "quantum-vulnerable")
        out = render_blockchains(registry(chains=[btc]))
        heads = re.findall(r"<th [^>]*>([^<]*)</th>", out)
        self.assertEqual(
            heads,
            ["Chain", "Consensus", "Transactions", "Algorithms", "Website", "Source", "Notes"],
        )
        self.assertNotIn("Overall", out)
        body = out[out.index("<tbody"):].replace("\n", "")
        self.assertIn(
            '<td data-sort="1"><span class="badge badge--no-signatures">'
            "No Signatures / Quantum Resistant</span></td>"
            '<td data-sort="4"><span class="badge badge--quantum-vulnerable">'
            "Quantum-Vulnerable</span></td>",
            body,
        )

    def test_rows_sorted_transactions_then_consensus_then_name(self):
        reg = registry(
            chains=[
                chain("Zeta", "post-quantum", "post-quantum"),
                chain("Alpha", "post-quantum", "quantum-vulnerable"),
                chain("Beta", "no-signatures", "post-quantum"),
                chain("Gamma", "quantum-aware", "post-quantum"),
                chain("Able", "post-quantum", "post-quantum"),
            ]
        )
        out = render_blockchains(reg)
        body = out[out.index("<tbody"):]
        order = [body.index(f">{n}<") for n in ("Able", "Zeta", "Beta", "Gamma", "Alpha")]
        self.assertEqual(order, sorted(order))

    def test_website_and_source_are_icon_links_with_labels(self):
        reg = registry(
            chains=[
                chain("Gh", website="https://example.org/", source="https://github.com/a/b"),
                chain("Gl", source="https://gitlab.com/a/b"),
                chain("Other", source="https://git.example.org/a/b"),
                chain("Tricky", source="https://example.org/github.com"),
            ]
        )
        out = render_blockchains(reg)
        rows = {
            name: row
            for name, row in zip(
                ("Gh", "Gl", "Other", "Tricky"),
                re.findall(r"<tr>(.*?)</tr>", out[out.index("<tbody"):], re.S),
            )
        }
        sprite = "/assets/icons/registry-icons.svg"

        def icon_link(url, label, symbol):
            return (
                f'<a href="{url}" class="icon-link" aria-label="{label}">'
                '<svg class="icon" aria-hidden="true" focusable="false">'
                f'<use href="{sprite}#{symbol}"/></svg></a>'
            )

        self.assertIn(icon_link("https://example.org/", "Gh website", "globe"), rows["Gh"])
        self.assertIn(icon_link("https://github.com/a/b", "Gh source code", "github"), rows["Gh"])
        self.assertIn(icon_link("https://gitlab.com/a/b", "Gl source code", "gitlab"), rows["Gl"])
        self.assertIn(icon_link("https://git.example.org/a/b", "Other source code", "git"), rows["Other"])
        self.assertIn("#git\"", rows["Tricky"])
        self.assertNotIn("#github", rows["Tricky"])

    def test_chain_logo_rendered_when_set(self):
        out = render_blockchains(
            registry(chains=[chain("With", logo="with.svg"), chain("Without")])
        )
        rows = re.findall(r"<tr>(.*?)</tr>", out[out.index("<tbody"):], re.S)
        logo = (
            '<img src="/assets/registry/logos/with.svg" alt="" width="20" height="20" '
            'class="chain-logo">'
        )
        with_row = next(r for r in rows if ">With<" in r)
        without_row = next(r for r in rows if ">Without<" in r)
        self.assertLess(with_row.index(logo), with_row.index("With</"))
        self.assertNotIn("<img", without_row)

    def test_algorithm_links_point_to_algorithm_pages(self):
        reg = registry(
            chains=[chain("C", algorithms=("ml-dsa",))],
            libraries=[library("L", algorithms=("ml-dsa", "slh-dsa"))],
        )
        chain_out = render_blockchains(reg)
        self.assertIn('<a href="/registry/algorithms/ml-dsa/">ML-DSA</a>', chain_out)
        lib_out = render_libraries(reg)
        self.assertIn('<a href="/registry/algorithms/ml-dsa/" class="alg safety--medium">', lib_out)
        self.assertIn('<a href="/registry/algorithms/slh-dsa/" class="alg safety--high">', lib_out)

    def test_library_rows_have_slug_ids(self):
        out = render_libraries(registry(libraries=[library("Open C++ Lib (v2)")]))
        self.assertEqual(library_slug("Open C++ Lib (v2)"), "open-c-lib-v2")
        self.assertIn('<tr id="lib-open-c-lib-v2">', out)

    def test_algorithm_page_lists_implementing_libraries(self):
        reg = registry(libraries=[library("Zed Lib"), library("Alpha", algorithms=("slh-dsa",))])
        out = render_algorithm(reg, "ml-dsa")
        self.assertIn('<a href="/registry/libraries/#lib-zed-lib">Zed Lib</a>', out)
        self.assertNotIn("Alpha", out)
        self.assertIn("Implemented by", out)
        empty = render_algorithm(registry(), "ml-dsa")
        self.assertIn("No libraries listed yet.", empty)

    def test_algorithm_page_content(self):
        algs = {
            "x": Algorithm(
                "x", "Xsig", "hash-based", "https://example.org/std", "Plain summary.",
                (Link("Paper A", "https://example.org/a"), Link("Paper B", "https://example.org/b")),
            )
        }
        reg = Registry(algs, (), (), ())
        out = render_algorithm(reg, "x")
        self.assertIn('<p class="eyebrow">Algorithm</p>', out)
        self.assertIn("<h1>Xsig</h1>", out)
        self.assertIn("hash-based", out)
        self.assertIn("High", out)
        self.assertIn("Plain summary.", out)
        self.assertIn("Standard", out)
        self.assertIn('<a href="https://example.org/std"', out)
        self.assertIn("Research", out)
        self.assertIn('<a href="https://example.org/a"', out)
        self.assertIn('<a href="https://example.org/b"', out)

    def test_algorithm_page_escapes_summary(self):
        algs = {
            "x": Algorithm(
                "x", "<i>X</i>", "other", "https://example.org/s", "<script>alert(1)</script>",
                (Link("<b>P</b>", "https://example.org/p"),),
            )
        }
        out = render_algorithm(Registry(algs, (), (), ()), "x")
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", out)
        self.assertNotIn("<script>", out)
        self.assertNotIn("<i>", out)
        self.assertNotIn("<b>P", out)

    def test_algorithm_page_has_edit_links(self):
        out = render_algorithm(registry(), "ml-dsa")
        self.assertIn(f"{REPO_URL}/edit/main/registry/data/algorithms.toml", out)
        self.assertIn(f"{REPO_URL}/issues/new?template=registry-algorithm.yml", out)

    def test_algorithms_index(self):
        reg = registry(libraries=[library("A"), library("B", algorithms=("ml-dsa", "slh-dsa"))])
        out = render_algorithms_index(reg)
        heads = re.findall(r"<th [^>]*>([^<]*)</th>", out)
        self.assertEqual(heads, ["Algorithm", "Family", "Safety", "Libraries"])
        self.assertIn('<a href="/registry/algorithms/ml-dsa/">ML-DSA</a>', out)
        self.assertIn('<td data-sort="2">2</td>', out)
        self.assertIn('<td data-sort="1">1</td>', out)
        self.assertIn("registry/data/algorithms.toml", out)
        self.assertIn("template=registry-algorithm.yml", out)

    def test_legend_lists_five_values(self):
        out = render_blockchains(registry(chains=[chain("A")]))
        legend = out[out.index('<dl class="legend">'):out.index("</dl>")]
        for label in ("Post-Quantum", "No Signatures / Quantum Resistant", "Post-Quantum Ready",
                      "Quantum-Aware", "Quantum-Vulnerable"):
            self.assertIn(f">{label}</span>", legend)
        self.assertEqual(legend.count("<dt>"), 5)
        self.assertIn(
            "The layer does not use digital signatures, for example proof-of-work mining, "
            "which relies on hashing.",
            out,
        )
        self.assertNotIn("Overall", out)

    def test_notes_popover_ids_unique_and_linked(self):
        chains = [chain("A", note="Short note"), chain("B", links=[Link("T", "https://example.org/t")])]
        libs = [library("L", note="Lib note")]
        for out in (
            render_blockchains(registry(chains=chains)),
            render_libraries(registry(libraries=libs)),
        ):
            targets = re.findall(r'popovertarget="([^"]+)"', out)
            ids = re.findall(r'<div id="([^"]+)" popover', out)
            self.assertTrue(ids)
            self.assertEqual(len(ids), len(set(ids)))
            for target in targets:
                self.assertEqual(ids.count(target), 1)
            self.assertEqual(set(targets), set(ids))
        out = render_blockchains(registry(chains=chains))
        self.assertIn('class="notes-toggle" popovertarget="notes-blockchains-0" aria-label="Notes for A"', out)
        self.assertIn('popovertargetaction="hide"', out)
        self.assertIn('class="notes-popover"', out)

    def test_notes_button_in_name_cell(self):
        chains = [chain("A", note="Short note"), chain("B")]
        out = render_blockchains(registry(chains=chains))
        rows = re.findall(r"<tr>(.*?)</tr>", out[out.index("<tbody"):], re.S)
        match = re.match(r"<td[^>]*>.*?</td>", rows[0], re.S)
        assert match is not None
        first_cell = match.group(0)
        self.assertIn('popovertarget="notes-blockchains-0"', first_cell)
        self.assertIn('<div id="notes-blockchains-0" popover', first_cell)
        self.assertNotIn("popovertarget", rows[0][len(first_cell):])
        self.assertNotIn("popovertarget", rows[1])
        self.assertIn('<th scope="col" class="col-notes">Notes</th>', out)
        self.assertEqual(rows[0].count('class="col-notes"'), 1)

    def test_empty_notes_has_no_popover(self):
        out = render_blockchains(registry(chains=[chain("A")]))
        self.assertIn('<td data-sort="">—</td>', out)
        self.assertNotIn("popover", out)
        self.assertNotIn("notes-toggle", out)

    def test_popover_content_escaped(self):
        out = render_blockchains(registry(chains=[chain("A", note="<b>bold</b>")]))
        self.assertIn("&lt;b&gt;bold&lt;/b&gt;", out)
        self.assertNotIn("<b>", out)

    def test_notes_cell_keeps_sort_value_and_links(self):
        c = chain("A", note="Short Note", links=[Link("BIP-360", "https://example.org/bip")])
        out = render_blockchains(registry(chains=[c]))
        self.assertIn('data-sort="short note bip-360"', out)
        self.assertEqual(out.count('<a href="https://example.org/bip">BIP-360</a>'), 2)

    def test_library_notes_render_note_then_links(self):
        lib = library(note="Audit scope limited", links=(Link("Audit", "https://example.org/a"),))
        out = render_libraries(registry(libraries=[lib]))
        self.assertIn('popovertarget="notes-libraries-0"', out)
        self.assertLess(out.index("Audit scope limited"), out.index('<a href="https://example.org/a">Audit</a>'))

    def test_blockchain_legend_and_links(self):
        reg = load_registry(VALID)
        out = render_blockchains(reg)
        self.assertIn("Has deployed a post-quantum solution.", out)
        self.assertIn("BIP-360 is proposed but has no deployment path.", out)
        self.assertIn('<a href="/registry/algorithms/ml-dsa/">ML-DSA</a>', out)
        self.assertIn('<table data-sortable>', out)
        self.assertIn(
            "Consensus covers how the network agrees on blocks, such as validator "
            "votes or mining. Transactions covers the signatures that authorize "
            "moving funds.",
            out,
        )

    def test_escapes_data_text(self):
        lib = library(note="<script>alert(1)</script>")
        out = render_libraries(registry(libraries=[lib]))
        self.assertIn("&lt;script&gt;", out)
        self.assertNotIn("<script>alert", out)

    def test_escapes_attribute_values(self):
        c = chain("X", website='https://e.org/"onmouseover="x')
        out = render_blockchains(registry(chains=[c]))
        self.assertNotIn('"onmouseover="x', out)

    def test_missing_size_renders_dash(self):
        out = render_libraries(registry(libraries=[library()]))
        self.assertIn('<td data-sort="">—</td>', out)

    def test_size_cell_sorts_by_bytes(self):
        lib = library(min_signature=Size(666, "Falcon-512"))
        out = render_libraries(registry(libraries=[lib]))
        self.assertIn('<td data-sort="666">666 B (Falcon-512)</td>', out)

    def test_format_size(self):
        self.assertEqual(format_size(Size(666, "Falcon-512")), "666 B (Falcon-512)")
        self.assertEqual(format_size(None), "—")

    def test_library_safety_column(self):
        lib = library(algorithms=("ml-dsa", "slh-dsa"))
        out = render_libraries(registry(libraries=[lib]))
        self.assertIn('<td data-sort="0"><span class="safety safety--high">High</span></td>', out)

    def test_library_rows_sorted_by_safety_then_name(self):
        reg = registry(
            libraries=[
                library("Bravo"),
                library("Zulu", algorithms=("slh-dsa",)),
                library("Alpha"),
            ]
        )
        out = render_libraries(reg)
        body = out[out.index("<tbody"):]
        self.assertLess(body.index("Zulu"), body.index("Alpha"))
        self.assertLess(body.index("Alpha"), body.index("Bravo"))

    def test_algorithm_chip_shows_name_and_safety(self):
        out = render_libraries(registry(libraries=[library()]))
        self.assertIn('class="alg safety--medium"', out)
        self.assertNotIn('class="tag', out)

    def test_audited_shows_links_or_no(self):
        audited = library("A", audits=(Link("Audit by X", "https://example.org/audit"),))
        plain = library("B")
        out = render_libraries(registry(libraries=[audited, plain]))
        self.assertIn('<a href="https://example.org/audit">Audit by X</a>', out)
        self.assertIn(">No</td>", out)

    def test_blockchain_friendly_yes_no(self):
        out = render_libraries(registry(libraries=[library(blockchain_friendly=True)]))
        self.assertIn('<td data-sort="yes">Yes</td>', out)

    def test_products_sorted_by_member_then_name(self):
        products = [
            Product("B", "Zed Corp", "Does b.", ("Ethereum",), "https://example.org/b"),
            Product("A", "Acme", "Does a.", ("Ethereum", "Bitcoin"), "https://example.org/a"),
        ]
        out = render_products(registry(products=products))
        self.assertLess(out.index("Acme"), out.index("Zed Corp"))
        self.assertIn("Products built by Quantum Alliance members.", out)
        self.assertIn("Ethereum, Bitcoin", out)

    def test_edit_links_target_repo(self):
        html = edit_links("blockchains.toml", "registry-blockchain.yml")
        self.assertIn(f"{REPO_URL}/edit/main/registry/data/blockchains.toml", html)
        self.assertIn(f"{REPO_URL}/issues/new?template=registry-blockchain.yml", html)
        self.assertIn("Spotted an error or a missing entry?", html)

    def test_edit_links_around_table(self):
        out = render_blockchains(load_registry(VALID))
        self.assertEqual(out.count("registry/data/blockchains.toml"), 2)
        self.assertLess(out.index("registry/data/"), out.index("<table"))

    def test_empty_registry_shows_empty_state_and_edit_links(self):
        out = render_products(registry())
        self.assertIn('<p class="intro">No entries yet. Be the first to add one.</p>', out)
        self.assertNotIn("<table", out)
        self.assertIn("registry/data/products.toml", out)

    def test_hub_lists_counts(self):
        out = render_hub(load_registry(VALID))
        self.assertIn("Quantum readiness registries", out)
        self.assertIn('href="/registry/blockchains/"', out)
        self.assertIn('href="/registry/libraries/"', out)
        self.assertIn('href="/registry/products/"', out)
        self.assertIn('href="/registry/algorithms/"', out)
        self.assertEqual(out.count('class="card"'), 4)

    def test_render_page_fills_template(self):
        template = "<title>$title</title>$description|$path|$body"
        out = render_page(template, title="T & U", description="D", path="/registry/", body="<b>x</b>")
        self.assertEqual(out, "<title>T &amp; U</title>D|/registry/|<b>x</b>")


if __name__ == "__main__":
    unittest.main()

import re
import unittest
from pathlib import Path

from tools.registry.model import (
    Algorithm,
    Audit,
    Broken,
    Chain,
    Library,
    Link,
    Product,
    Registry,
    Repository,
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
    render_chain,
    render_hub,
    render_libraries,
    render_library,
    render_page,
    render_products,
)

VALID = Path(__file__).parent / "fixtures" / "valid"

ALGS = {
    "ml-dsa": Algorithm("ml-dsa", "ML-DSA", "lattice", "signature", "https://example.org/ml", "S", "Because lattices.", ()),
    "slh-dsa": Algorithm(
        "slh-dsa", "SLH-DSA", "hash-based", "signature", "https://example.org/slh", "S", "Hash only.", ()
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
    consensus_reason="Consensus reason.",
    transactions_reason="Transactions reason.",
):
    return Chain(
        name, consensus, transactions, consensus_reason, transactions_reason, website, source,
        tuple(algorithms), note, tuple(links), logo,
    )


def library(
    name="Lib",
    algorithms=("ml-dsa",),
    maturity="production",
    blockchain_friendly=False,
    audits=(),
    hybrid=False,
    repositories=(Repository("Rust", "https://example.org/lib"),),
    min_signature: Size | None = None,
    min_public_key: Size | None = None,
    note: str | None = None,
    links=(),
):
    return Library(
        name=name,
        repositories=tuple(repositories),
        algorithms=tuple(algorithms),
        hybrid=hybrid,
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

    def test_chain_algorithm_links_point_to_algorithm_pages(self):
        reg = registry(chains=[chain("C", algorithms=("ml-dsa",))])
        self.assertIn('<a href="/registry/algorithms/ml-dsa/">ML-DSA</a>', render_blockchains(reg))

    def test_library_name_links_to_detail_page(self):
        out = render_libraries(registry(libraries=[library("Open C++ Lib (v2)")]))
        self.assertEqual(library_slug("Open C++ Lib (v2)"), "open-c-lib-v2")
        self.assertIn('<a href="/registry/libraries/open-c-lib-v2/">Open C++ Lib (v2)</a>', out)
        self.assertNotIn('id="lib-', out)
        name_cell = out.split("<tbody")[1].split("</td>")[0]
        self.assertNotIn("https://example.org/lib", name_cell)

    def test_library_table_columns(self):
        out = render_libraries(registry(libraries=[library()]))
        heads = re.findall(r"<th [^>]*>([^<]*)</th>", out)
        self.assertEqual(
            heads,
            ["Library", "Algorithms", "Source", "Safety", "Audited", "Maturity",
             "Blockchain friendly", "Min signature", "Min public key", "Notes"],
        )

    def test_algorithm_chips_have_no_safety_suffix(self):
        reg = registry(libraries=[library("L", algorithms=("ml-dsa", "slh-dsa"))])
        out = render_libraries(reg)
        self.assertIn('<a href="/registry/algorithms/ml-dsa/" class="alg">ML-DSA</a>', out)
        self.assertIn('<a href="/registry/algorithms/slh-dsa/" class="alg">SLH-DSA</a>', out)
        self.assertNotIn("<small>", out)
        self.assertNotIn("alg safety--", out)

    def test_source_cell_lists_each_language_with_icon_link(self):
        lib = library("L", repositories=(
            Repository("Rust", "https://github.com/a/b"),
            Repository("Solidity", "https://github.com/a/c"),
        ))
        out = render_libraries(registry(libraries=[lib]))
        self.assertNotIn("Languages", out)
        self.assertIn('<td class="col-source" data-sort="rust, solidity">', out)
        for lang, url in (("Rust", "https://github.com/a/b"), ("Solidity", "https://github.com/a/c")):
            self.assertRegex(
                out,
                rf'<span class="repo-line"><a href="{url}" class="icon-link" '
                rf'aria-label="L {lang} source code">.*?</a> {lang}</span>',
            )

    def test_one_source_icon_per_repository_with_labels(self):
        lib = library("Hashsigs", repositories=(
            Repository("Rust", "https://github.com/a/b"),
            Repository("Go", "https://gitlab.com/a/c"),
            Repository("C", "https://git.example.org/a/d"),
        ))
        out = render_libraries(registry(libraries=[lib]))
        row = re.findall(r"<tr>(.*?)</tr>", out[out.index("<tbody"):], re.S)[0]
        for url, label, symbol in (
            ("https://github.com/a/b", "Hashsigs Rust source code", "github"),
            ("https://gitlab.com/a/c", "Hashsigs Go source code", "gitlab"),
            ("https://git.example.org/a/d", "Hashsigs C source code", "git"),
        ):
            self.assertIn(
                f'<a href="{url}" class="icon-link" aria-label="{label}">'
                '<svg class="icon" aria-hidden="true" focusable="false">'
                f'<use href="/assets/icons/registry-icons.svg#{symbol}"/></svg></a>',
                row,
            )
        self.assertEqual(row.count('class="icon-link"'), 3)

    def test_blockchain_friendly_icons_with_hidden_text(self):
        out = render_libraries(registry(libraries=[
            library("Yes", blockchain_friendly=True), library("No", blockchain_friendly=False),
        ]))
        sprite = "/assets/icons/registry-icons.svg"
        self.assertIn(
            '<td data-sort="1"><span class="bool-icon yes"><svg class="icon" aria-hidden="true" '
            f'focusable="false"><use href="{sprite}#check"/></svg>'
            '<span class="visually-hidden">Yes</span></span></td>',
            out,
        )
        self.assertIn(
            '<td data-sort="0"><span class="bool-icon no"><svg class="icon" aria-hidden="true" '
            f'focusable="false"><use href="{sprite}#x"/></svg>'
            '<span class="visually-hidden">No</span></span></td>',
            out,
        )

    def test_audited_yes_with_auditor_logo_links(self):
        audits = (
            Audit("Oak <Security>", "https://example.org/oak", "oak.svg"),
            Audit("Plain Co", "https://example.org/plain", None),
        )
        out = render_libraries(registry(libraries=[library(audits=audits)]))
        self.assertIn('data-sort="yes">Yes ', out)
        self.assertIn(
            '<a href="https://example.org/oak" class="audit-link" '
            'aria-label="Oak &lt;Security&gt; audit report">'
            '<img src="/assets/registry/auditors/oak.svg" alt="" width="20" height="20"></a>',
            out,
        )
        self.assertIn(
            '<a href="https://example.org/plain" class="audit-link" '
            'aria-label="Plain Co audit report">Plain Co</a>',
            out,
        )

    def test_audited_no(self):
        out = render_libraries(registry(libraries=[library()]))
        self.assertIn('<td data-sort="no">No</td>', out)

    def test_safety_legend_text(self):
        out = render_libraries(registry(libraries=[library()]))
        self.assertIn(
            "High safety requires a hybrid design, where a classical and a post-quantum "
            "signature must both verify. Without one, hash-based libraries rate Medium, "
            "and lattice-based and other libraries rate Low.",
            out,
        )
        self.assertNotIn("hardness assumption", out)

    def test_library_safety_uses_hybrid_rule(self):
        out = render_libraries(registry(libraries=[
            library("Hyb", algorithms=("ml-dsa",), hybrid=True),
            library("Hash", algorithms=("slh-dsa",)),
            library("Lat", algorithms=("ml-dsa",)),
        ]))
        self.assertIn('<td data-sort="0"><span class="safety safety--high">High</span></td>', out)
        self.assertIn('<td data-sort="1"><span class="safety safety--medium">Medium</span></td>', out)
        self.assertIn('<td data-sort="2"><span class="safety safety--low">Low</span></td>', out)

    def test_library_detail_page_contents(self):
        lib = library(
            "Hash<sigs>",
            algorithms=("slh-dsa", "ml-dsa"),
            hybrid=True,
            audits=(Audit("Oak", "https://example.org/oak", "oak.svg"),),
            repositories=(
                Repository("Rust", "https://github.com/a/b"),
                Repository("Solidity", "https://gitlab.com/a/c"),
            ),
            blockchain_friendly=True,
            min_signature=Size(666, "Falcon-512"),
            min_public_key=Size(897, "Falcon-512"),
            note="Short <note>",
            links=(Link("Docs", "https://example.org/docs"),),
        )
        out = render_library(registry(libraries=[lib]), "hash-sigs")
        positions = [
            out.index(needle)
            for needle in (
                '<p class="eyebrow">Library</p>',
                "<h1>Hash&lt;sigs&gt;</h1>",
                ">Repositories<",
                ">Algorithms<",
                ">Safety<",
                ">Hybrid<",
                ">Audits<",
                ">Maturity<",
                ">Blockchain friendly<",
                ">Minimum signature<",
                ">Minimum public key<",
                ">Note and links<",
                "registry/data/libraries.toml",
            )
        ]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('aria-label="Hash&lt;sigs&gt; Rust source code"', out)
        self.assertIn("Rust", out)
        self.assertIn("Solidity", out)
        self.assertIn('#github"', out)
        self.assertIn('#gitlab"', out)
        self.assertIn('<a href="/registry/algorithms/slh-dsa/" class="alg">SLH-DSA</a>', out)
        self.assertIn('<a href="/registry/algorithms/ml-dsa/" class="alg">ML-DSA</a>', out)
        self.assertIn('<span class="safety safety--high">High</span>', out)
        self.assertIn(
            "Hybrid design: a classical and a post-quantum signature must both verify.", out
        )
        self.assertIn("Yes", out)
        self.assertIn('aria-label="Oak audit report"', out)
        self.assertIn("production", out)
        self.assertIn('<span class="visually-hidden">Yes</span>', out)
        self.assertIn("666 B (Falcon-512)", out)
        self.assertIn("897 B (Falcon-512)", out)
        self.assertIn("Short &lt;note&gt;", out)
        self.assertIn('<a href="https://example.org/docs">Docs</a>', out)
        self.assertIn(f"{REPO_URL}/issues/new?template=registry-library.yml", out)
        self.assertNotIn("<sigs>", out)
        self.assertNotIn("<note>", out)

    def test_render_library_unknown_slug_raises_value_error(self):
        with self.assertRaisesRegex(ValueError, "unknown library slug: nope"):
            render_library(registry(libraries=[library("Plain")]), "nope")

    def test_library_detail_page_empty_values(self):
        out = render_library(registry(libraries=[library("Plain")]), "plain")
        self.assertIn(
            "Best algorithm family is lattice-based; "
            "without a hybrid design the rating drops one level.",
            out,
        )
        self.assertIn(">No<", out)
        self.assertIn("—", out)

    def test_algorithm_page_links_library_pages(self):
        reg = registry(libraries=[library("Zed Lib"), library("Alpha", algorithms=("slh-dsa",))])
        out = render_algorithm(reg, "ml-dsa")
        self.assertIn('<a href="/registry/libraries/zed-lib/">Zed Lib</a>', out)
        self.assertNotIn("#lib-", out)
        self.assertNotIn("Alpha", out)
        self.assertIn("Implemented by", out)
        empty = render_algorithm(registry(), "ml-dsa")
        self.assertIn("No libraries listed yet.", empty)

    def test_algorithm_page_shows_rationale(self):
        algs = {
            "x": Algorithm(
                "x", "Xsig", "hash-based", "signature", "https://example.org/std", "Summary.",
                "Only hashes matter & <b>nothing</b> else.",
                (Link("Paper A", "https://example.org/a"),),
            )
        }
        out = render_algorithm(Registry(algs, (), (), ()), "x")
        self.assertIn("Why this rating", out)
        self.assertIn("Only hashes matter &amp; &lt;b&gt;nothing&lt;/b&gt; else.", out)
        self.assertNotIn("<b>", out)
        self.assertLess(out.index("Summary."), out.index('<span class="safety'))
        self.assertLess(out.index("Family:"), out.index("Summary."))
        self.assertLess(out.index('<span class="safety'), out.index("Why this rating"))
        self.assertLess(out.index("Why this rating"), out.index("Only hashes"))
        self.assertNotIn("Why this rating", render_algorithms_index(Registry(algs, (), (), ())))

    def test_algorithm_page_content(self):
        algs = {
            "x": Algorithm(
                "x", "Xsig", "hash-based", "signature", "https://example.org/std", "Plain summary.",
                "Only hashes matter & <b>nothing</b> else.",
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
                "x", "<i>X</i>", "other", "kem", "https://example.org/s", "<script>alert(1)</script>", "<i>why</i>",
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

    def test_chain_name_links_to_card(self):
        out = render_blockchains(registry(chains=[chain("Open C++ Chain", logo="x.svg")]))
        row = re.findall(r"<tr>(.*?)</tr>", out[out.index("<tbody"):], re.S)[0]
        self.assertIn('<a href="/registry/blockchains/open-c-chain/">', row)
        link = row[row.index('<a href="/registry/blockchains/'):]
        link = link[: link.index("</a>")]
        self.assertIn("chain-logo", link)
        self.assertIn("Open C++ Chain", link)

    def test_chain_name_link_keeps_notes_button(self):
        out = render_blockchains(registry(chains=[chain("C", note="A note")]))
        cell = out[out.index("<tbody"):].split("</td>")[0]
        self.assertLess(cell.index("</a>"), cell.index("notes-toggle"))

    def test_chain_card_shows_both_reasons_escaped(self):
        c = chain(
            "Ch<ain>",
            consensus_reason="Judgment call: <b>x</b> & more.",
            transactions_reason="Tx <i>why</i>.",
            algorithms=("ml-dsa",),
            note="Short <note>",
            links=(Link("Docs", "https://example.org/docs"),),
            logo="c.svg",
        )
        out = render_chain(registry(chains=[c]), "ch-ain")
        self.assertEqual(out.count("Why this rating"), 2)
        self.assertIn("Judgment call: &lt;b&gt;x&lt;/b&gt; &amp; more.", out)
        self.assertIn("Tx &lt;i&gt;why&lt;/i&gt;.", out)
        self.assertNotIn("<b>", out)
        self.assertNotIn("<i>", out)
        positions = [
            out.index(needle)
            for needle in (
                '<p class="eyebrow">Blockchain</p>',
                "<h1>",
                'width="32" height="32"',
                ">Consensus<",
                'badge--post-quantum',
                "Why this rating",
                "Judgment call",
                ">Transactions<",
                "Tx &lt;i&gt;",
                ">Algorithms<",
                '<a href="/registry/algorithms/ml-dsa/" class="alg">ML-DSA</a>',
                "</svg> Website</a>",
                "</svg> Source</a>",
                "Short &lt;note&gt;",
                '<a href="https://example.org/docs">Docs</a>',
                "registry/data/blockchains.toml",
            )
        ]
        self.assertEqual(positions, sorted(positions))

    def test_chain_card_website_and_source_text_is_inside_the_link(self):
        out = render_chain(
            registry(chains=[chain("Gh", website="https://example.org/", source="https://github.com/a/b")]),
            "gh",
        )
        for url, text in (("https://example.org/", "Website"), ("https://github.com/a/b", "Source")):
            self.assertRegex(
                out, rf'<a href="{re.escape(url)}" class="icon-link"><svg[^>]*>.*?</svg> {text}</a>'
            )
        self.assertNotIn("aria-label", out.split("Algorithms")[1].split("Note and links")[0])

    def test_chain_card_note_and_links_are_separate_elements(self):
        c = chain(
            "Ch",
            note="Short <note>",
            links=(Link("Docs", "https://example.org/docs"), Link("Spec", "https://example.org/spec")),
        )
        out = render_chain(registry(chains=[c]), "ch")
        self.assertIn("<p>Short &lt;note&gt;</p>", out)
        self.assertIn(
            '<ul class="card-links"><li><a href="https://example.org/docs">Docs</a></li>'
            '<li><a href="https://example.org/spec">Spec</a></li></ul>',
            out,
        )

    def test_library_note_and_links_are_separate_elements(self):
        lib = library(
            "Hash",
            note="Lib note",
            links=(Link("Docs", "https://example.org/docs"),),
        )
        out = render_library(registry(libraries=[lib]), "hash")
        self.assertIn("<p>Lib note</p>", out)
        self.assertIn(
            '<ul class="card-links"><li><a href="https://example.org/docs">Docs</a></li></ul>', out
        )

    def test_chain_card_without_algorithms_or_logo(self):
        out = render_chain(registry(chains=[chain("Plain")]), "plain")
        self.assertIn("None listed", out)
        self.assertNotIn("None deployed", out)
        self.assertNotIn("<img", out)

    def test_chain_card_has_edit_links(self):
        out = render_chain(registry(chains=[chain("Plain")]), "plain")
        self.assertIn(f"{REPO_URL}/edit/main/registry/data/blockchains.toml", out)
        self.assertIn(f"{REPO_URL}/issues/new?template=registry-blockchain.yml", out)

    def test_render_chain_unknown_slug_raises_value_error(self):
        with self.assertRaisesRegex(ValueError, "unknown chain slug: nope"):
            render_chain(registry(chains=[chain("Plain")]), "nope")

    def test_libraries_page_title_is_pqc_libraries(self):
        reg = registry(libraries=[library()])
        out = render_libraries(reg)
        self.assertIn("<h1>Post-Quantum Cryptography Libraries</h1>", out)
        self.assertNotIn("signature libraries", out)
        hub = render_hub(reg)
        self.assertIn(
            '<h3><a href="/registry/libraries/">Post-Quantum Cryptography Libraries</a></h3>', hub
        )

    def test_capability_tags_in_table_and_card(self):
        reg = registry(
            libraries=[
                library("Sig", algorithms=("ml-dsa",)),
                library("Both", algorithms=("ml-dsa", "kem-alg")),
            ]
        )
        reg.algorithms["kem-alg"] = Algorithm(
            "kem-alg", "KEM", "lattice", "kem", "https://example.org/k", "S", "R.", ()
        )
        table = render_libraries(reg)
        rows = re.findall(r"<tr>(.*?)</tr>", table[table.index("<tbody"):], re.S)
        both = next(r for r in rows if ">Both<" in r)
        sig = next(r for r in rows if ">Sig<" in r)
        name_cell = both.split("</td>")[0]
        self.assertLess(
            name_cell.index('<span class="cap-tag">Signatures</span>'),
            name_cell.index('<span class="cap-tag">Key exchange</span>'),
        )
        self.assertNotIn("Key exchange", sig)
        card = render_library(reg, "both")
        self.assertLess(card.index("<h1>"), card.index('<span class="cap-tag">Signatures</span>'))
        self.assertIn('<span class="cap-tag">Key exchange</span>', card)
        self.assertNotIn("Key exchange", render_library(reg, "sig"))

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
        reg = load_registry(VALID, auditors_dir=VALID / "auditors")
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
        self.assertIn('<td data-sort="1"><span class="safety safety--medium">Medium</span></td>', out)

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
        out = render_blockchains(load_registry(VALID, auditors_dir=VALID / "auditors"))
        self.assertEqual(out.count("registry/data/blockchains.toml"), 2)
        self.assertLess(out.index("registry/data/"), out.index("<table"))

    def test_empty_registry_shows_empty_state_and_edit_links(self):
        out = render_products(registry())
        self.assertIn('<p class="intro">No entries yet. Be the first to add one.</p>', out)
        self.assertNotIn("<table", out)
        self.assertIn("registry/data/products.toml", out)

    def test_hub_lists_counts(self):
        out = render_hub(load_registry(VALID, auditors_dir=VALID / "auditors"))
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


BROKEN_ALGS = {
    **ALGS,
    "rainbow": Algorithm(
        "rainbow", "Rain<bow>", "other", "signature", "https://example.org/rb", "S", "R", (),
        Broken("Key <recovery> attack.", Link("Attack & paper", "https://example.org/attack")),
    ),
}


def broken_registry():
    return Registry(
        dict(BROKEN_ALGS),
        (chain("Cell", algorithms=("rainbow", "ml-dsa")), chain("Clean", algorithms=("ml-dsa",))),
        (library("BrokenLib", algorithms=("rainbow",)), library("GoodLib", algorithms=("ml-dsa",))),
        (),
    )


def plain(html):
    return re.sub(r"<[^>]+>", "", html)


def row_for(html, name):
    rows = html[html.index("<tbody"):].split("<tr>")[1:]
    return next(r for r in rows if name in r)


class BrokenWarningTests(unittest.TestCase):
    def test_algorithm_page_broken_callout_and_badge(self):
        out = render_algorithm(broken_registry(), "rainbow")
        self.assertIn('<div class="callout callout--danger" role="note">', out)
        self.assertIn("Do not trust: Rain&lt;bow&gt; is broken. Key &lt;recovery&gt; attack.", plain(out))
        self.assertIn("Key &lt;recovery&gt; attack.", out)
        self.assertIn("Attack &amp; paper</a>", out)
        self.assertIn('href="https://example.org/attack"', out)
        self.assertIn("badge--broken", out)
        self.assertIn(">Broken</span>", out)
        self.assertNotIn("Do not trust", render_algorithm(broken_registry(), "ml-dsa"))

    def test_chain_card_warns_for_broken_algorithm(self):
        reg = broken_registry()
        out = render_chain(reg, "cell")
        self.assertIn('<div class="callout callout--danger" role="note">', out)
        self.assertIn("Do not trust Rain&lt;bow&gt; keys: Key &lt;recovery&gt; attack.", plain(out))
        self.assertIn('href="https://example.org/attack"', out)
        self.assertEqual(out.count("callout--danger"), 1)
        self.assertNotIn("Do not trust", render_chain(reg, "clean"))

    def test_library_card_warns_for_broken_algorithm(self):
        reg = broken_registry()
        out = render_library(reg, "brokenlib")
        self.assertIn('<div class="callout callout--danger" role="note">', out)
        self.assertIn("Do not trust Rain&lt;bow&gt; keys: Key &lt;recovery&gt; attack.", plain(out))
        self.assertIn('href="https://example.org/attack"', out)
        self.assertNotIn("Do not trust", render_library(reg, "goodlib"))

    def test_table_rows_show_warning_icon_with_hidden_text(self):
        reg = broken_registry()
        icon = "#triangle-alert"
        hidden = '<span class="visually-hidden">Uses a broken algorithm</span>'
        pages = (
            (render_blockchains(reg), "Cell", "Clean"),
            (render_libraries(reg), "BrokenLib", "GoodLib"),
            (render_algorithms_index(reg), "Rain&lt;bow&gt;", "ML-DSA"),
        )
        for html, bad, good in pages:
            with self.subTest(bad=bad):
                self.assertIn(icon, row_for(html, bad))
                self.assertIn(hidden, row_for(html, bad))
                self.assertNotIn(icon, row_for(html, good))
                self.assertNotIn("Uses a broken algorithm", row_for(html, good))
        self.assertIn(
            'data-sort="cell"', row_for(render_blockchains(reg), "Cell")
        )

    def test_broken_chip_modifier(self):
        out = render_libraries(broken_registry())
        self.assertIn('class="alg alg--broken">Rain&lt;bow&gt;</a>', out)
        self.assertIn('class="alg">ML-DSA</a>', out)
        self.assertIn('class="alg alg--broken"', render_library(broken_registry(), "brokenlib"))

    def test_broken_algorithms_sort_last_and_build(self):
        reg = broken_registry()
        out = render_libraries(reg)
        self.assertLess(out.index("GoodLib"), out.index("BrokenLib"))
        index = render_algorithms_index(reg)
        self.assertIn('<td data-sort="3"><span class="safety safety--broken', index)


if __name__ == "__main__":
    unittest.main()

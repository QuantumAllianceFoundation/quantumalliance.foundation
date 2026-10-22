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
    load_registry,
)
from tools.registry.render import (
    REPO_URL,
    edit_links,
    format_size,
    render_blockchains,
    render_hub,
    render_libraries,
    render_page,
    render_products,
)

VALID = Path(__file__).parent / "fixtures" / "valid"

ALGS = {
    "ml-dsa": Algorithm("ml-dsa", "ML-DSA", "lattice", "https://example.org/ml"),
    "slh-dsa": Algorithm("slh-dsa", "SLH-DSA", "hash-based", "https://example.org/slh"),
}


def chain(name, category):
    return Chain(name, category, "https://example.org/", "https://example.org/src", (), ())


def library(name="Lib", **overrides):
    fields = dict(
        name=name,
        source="https://example.org/lib",
        algorithms=("ml-dsa",),
        maturity="production",
        blockchain_friendly=False,
        audits=(),
        min_signature=None,
        min_public_key=None,
        notes=(),
    )
    fields.update(overrides)
    return Library(**fields)


def registry(chains=(), libraries=(), products=()):
    return Registry(dict(ALGS), tuple(chains), tuple(libraries), tuple(products))


class RenderTests(unittest.TestCase):
    def test_blockchain_rows_sorted_by_category_then_name(self):
        reg = registry(
            chains=[
                chain("Zeta", "post-quantum"),
                chain("Alpha", "quantum-vulnerable"),
                chain("Beta", "post-quantum"),
            ]
        )
        out = render_blockchains(reg)
        body = out[out.index("<tbody"):]
        self.assertLess(body.index("Beta"), body.index("Zeta"))
        self.assertLess(body.index("Zeta"), body.index("Alpha"))

    def test_blockchain_legend_and_links(self):
        reg = load_registry(VALID)
        out = render_blockchains(reg)
        self.assertIn("Has deployed a post-quantum solution.", out)
        self.assertIn("BIP-360 is proposed but has no deployment path.", out)
        self.assertIn('<a href="https://csrc.nist.gov/pubs/fips/204/final">ML-DSA</a>', out)
        self.assertIn('<th scope="col" data-sort-type="number">Category</th>', out)
        self.assertIn('<table data-sortable>', out)

    def test_escapes_data_text(self):
        lib = library(notes=("<script>alert(1)</script> (ML-DSA)",))
        out = render_libraries(registry(libraries=[lib]))
        self.assertIn("&lt;script&gt;", out)
        self.assertNotIn("<script>alert", out)

    def test_escapes_attribute_values(self):
        c = Chain("X", "post-quantum", 'https://e.org/"onmouseover="x', "https://e.org/", (), ())
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
        self.assertEqual(out.count('class="card"'), 3)

    def test_render_page_fills_template(self):
        template = "<title>$title</title>$description|$path|$body"
        out = render_page(template, title="T & U", description="D", path="/registry/", body="<b>x</b>")
        self.assertEqual(out, "<title>T &amp; U</title>D|/registry/|<b>x</b>")


if __name__ == "__main__":
    unittest.main()

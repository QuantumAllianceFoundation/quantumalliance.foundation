import tempfile
import unittest
from pathlib import Path

from tools.registry.model import (
    Algorithm,
    Library,
    RegistryError,
    library_safety,
    library_slug,
    load_registry,
)

FIXTURES = Path(__file__).parent / "fixtures"
LOGOS = FIXTURES / "valid" / "logos"

ALGORITHMS = """
[[algorithm]]
id = "ml-dsa"
name = "ML-DSA"
family = "lattice"
url = "https://csrc.nist.gov/pubs/fips/204/final"
summary = "A lattice-based signature scheme."
papers = [{ title = "CRYSTALS-Dilithium (2018)", url = "https://example.org/dilithium" }]
"""

CHAIN = """
[[chain]]
name = "Quantus"
consensus = "post-quantum"
transactions = "post-quantum"
website = "https://quantus.com/"
source = "https://github.com/Quantus-Network"
algorithms = ["ml-dsa"]
"""

LIBRARY = """
[[library]]
name = "TestLib"
source = "https://example.org/testlib"
algorithms = ["ml-dsa"]
maturity = "production"
blockchain_friendly = false
"""


def write_data(tmp: Path, **files: str) -> Path:
    contents = {
        "algorithms": ALGORITHMS,
        "blockchains": CHAIN,
        "libraries": LIBRARY,
        "products": "",
    }
    contents.update(files)
    for key, text in contents.items():
        (tmp / f"{key}.toml").write_text(text, encoding="utf-8")
    return tmp


class RegistryTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    logos_dir: Path | None = None

    def errors_for(self, **files: str) -> list[str]:
        write_data(self.tmp, **files)
        with self.assertRaises(RegistryError) as cm:
            load_registry(self.tmp, self.logos_dir)
        return cm.exception.errors


class LoadRegistryTest(RegistryTestCase):
    def test_reports_file_that_is_not_utf8(self):
        write_data(self.tmp)
        (self.tmp / "libraries.toml").write_bytes(b'# caf\xe9\n')
        with self.assertRaises(RegistryError) as cm:
            load_registry(self.tmp)
        (message,) = cm.exception.errors
        self.assertTrue(message.startswith("libraries.toml: file: "))
        self.assertIn("not valid UTF-8", message)

    def test_loads_valid_registry(self):
        reg = load_registry(FIXTURES / "valid")
        self.assertEqual(reg.algorithms["ml-dsa"].family, "lattice")
        self.assertEqual(reg.chains[0].algorithms, ("ml-dsa",))
        self.assertIsNone(reg.libraries[0].min_signature)
        self.assertEqual(reg.products, ())

    def test_loads_optional_fields(self):
        write_data(
            self.tmp,
            libraries=LIBRARY
            + 'audits = [{ title = "Audit", url = "https://example.org/a" }]\n'
            + 'min_signature = { bytes = 666, parameter_set = "Falcon-512" }\n'
            + 'note = "Fast"\n'
            + 'links = [{ title = "Docs", url = "https://example.org/d" }]\n',
            products="""
[[product]]
name = "Wallet"
member = "Acme"
description = "A wallet."
chains = ["Ethereum"]
url = "https://example.org/wallet"
""",
        )
        reg = load_registry(self.tmp)
        lib = reg.libraries[0]
        self.assertEqual(lib.audits[0].title, "Audit")
        assert lib.min_signature is not None
        self.assertEqual(lib.min_signature.bytes, 666)
        self.assertEqual(lib.min_signature.parameter_set, "Falcon-512")
        self.assertEqual(lib.note, "Fast")
        self.assertEqual(lib.links[0].url, "https://example.org/d")
        self.assertEqual(reg.products[0].chains, ("Ethereum",))

    def test_rejects_unknown_layer_value(self):
        errors = self.errors_for(
            blockchains=CHAIN.replace("post-quantum", "quantum-safe", 1)
        )
        self.assertIn("blockchains.toml: Quantus: consensus:", errors[0])

    def test_rejects_no_signatures_for_transactions(self):
        errors = self.errors_for(
            blockchains=CHAIN.replace(
                'transactions = "post-quantum"', 'transactions = "no-signatures"'
            )
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("blockchains.toml: Quantus: transactions:", errors[0])
        self.assertIn("allowed for consensus only", errors[0])

    def test_accepts_no_signatures_for_consensus(self):
        write_data(
            self.tmp,
            blockchains=CHAIN.replace(
                'consensus = "post-quantum"', 'consensus = "no-signatures"'
            ),
        )
        self.assertEqual(load_registry(self.tmp).chains[0].consensus, "no-signatures")

    def test_rejects_old_category_key(self):
        errors = self.errors_for(
            blockchains=CHAIN + 'category = "post-quantum"\n'
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("blockchains.toml: Quantus: category: unknown key", errors[0])

    def test_rejects_old_notes_key(self):
        errors = self.errors_for(libraries=LIBRARY + 'notes = ["Fast"]\n')
        self.assertIn("libraries.toml: TestLib: notes: unknown key", errors[0])

    def test_rejects_more_than_two_links(self):
        links = ", ".join(
            f'{{ title = "T{i}", url = "https://example.org/{i}" }}' for i in range(3)
        )
        for files, name in (
            ({"blockchains": CHAIN + f"links = [{links}]\n"}, "Quantus"),
            ({"libraries": LIBRARY + f"links = [{links}]\n"}, "TestLib"),
        ):
            with self.subTest(name=name):
                errors = self.errors_for(**files)
                self.assertEqual(len(errors), 1)
                self.assertIn(f": {name}: links:", errors[0])
                self.assertIn("2", errors[0])

    def test_rejects_note_over_five_words(self):
        errors = self.errors_for(
            blockchains=CHAIN + 'note = "one two three four five six"\n'
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("blockchains.toml: Quantus: note:", errors[0])
        self.assertIn("5 words", errors[0])

    def test_accepts_five_word_note(self):
        write_data(
            self.tmp,
            blockchains=CHAIN + 'note = "one two three four five"\n',
            libraries=LIBRARY + 'note = "one two three four five"\n',
        )
        reg = load_registry(self.tmp)
        self.assertEqual(reg.chains[0].note, "one two three four five")
        self.assertEqual(reg.libraries[0].note, "one two three four five")

    def test_note_and_links_optional(self):
        reg = load_registry(FIXTURES / "valid")
        self.assertIsNone(reg.chains[0].note)
        self.assertEqual(reg.chains[0].links, ())
        self.assertIsNone(reg.libraries[0].note)
        self.assertEqual(reg.libraries[0].links, ())

    def test_rejects_unknown_key(self):
        errors = self.errors_for(
            blockchains=CHAIN.replace("website", "webiste")
        )
        self.assertTrue(any("webiste" in e for e in errors))

    def test_rejects_unknown_algorithm_id(self):
        errors = self.errors_for(
            libraries=LIBRARY.replace('["ml-dsa"]', '["ml-dsaa"]')
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("libraries.toml: TestLib: algorithms:", errors[0])
        self.assertIn("ml-dsaa", errors[0])

    def test_rejects_non_https_url(self):
        chains = CHAIN.replace("https://quantus.com/", "javascript:alert(1)")
        chains += CHAIN.replace("Quantus", "Other").replace(
            "https://quantus.com/", "http://x.org"
        )
        errors = self.errors_for(blockchains=chains)
        self.assertEqual(len(errors), 2)
        self.assertIn("website", errors[0])

    def test_rejects_duplicate_names_case_insensitive(self):
        errors = self.errors_for(
            blockchains=CHAIN + CHAIN.replace("Quantus", "quantus")
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("blockchains.toml: quantus: name:", errors[0])

    def test_rejects_empty_library_algorithms(self):
        errors = self.errors_for(
            libraries=LIBRARY.replace('["ml-dsa"]', "[]")
        )
        self.assertIn("libraries.toml: TestLib: algorithms:", errors[0])

    def test_rejects_non_positive_size(self):
        errors = self.errors_for(
            libraries=LIBRARY
            + 'min_signature = { bytes = 0, parameter_set = "X" }\n'
        )
        self.assertIn("libraries.toml: TestLib: min_signature:", errors[0])

    def test_rejects_non_slug_algorithm_id(self):
        errors = self.errors_for(
            algorithms=ALGORITHMS.replace('"ml-dsa"', '"ML DSA!"')
        )
        self.assertTrue(
            any(e.startswith("algorithms.toml:") and ": id:" in e for e in errors)
        )

    def test_rejects_invalid_toml_with_file_name(self):
        errors = self.errors_for(blockchains="[[chain]\nname=")
        self.assertTrue(errors[0].startswith("blockchains.toml:"))

    def test_rejects_missing_required_field(self):
        errors = self.errors_for(
            blockchains=CHAIN.replace('transactions = "post-quantum"\n', "")
        )
        self.assertIn("blockchains.toml: Quantus: transactions:", errors[0])

    def test_reports_every_error_with_location(self):
        errors = self.errors_for(
            blockchains=CHAIN.replace("post-quantum", "quantum-safe", 1),
            libraries=LIBRARY.replace('["ml-dsa"]', '["nope"]')
            + LIBRARY.replace("TestLib", "Other").replace("production", "stable"),
        )
        self.assertEqual(len(errors), 3)
        self.assertTrue(all(": " in e for e in errors))


class AlgorithmContentTest(RegistryTestCase):
    def algorithm_errors(self, algorithms: str) -> list[str]:
        """Return the algorithms.toml errors; dangling references add others."""
        errors = self.errors_for(algorithms=algorithms)
        return [e for e in errors if e.startswith("algorithms.toml:")]

    def test_loads_summary_and_papers(self):
        alg = load_registry(FIXTURES / "valid").algorithms["ml-dsa"]
        self.assertTrue(alg.summary)
        self.assertEqual(len(alg.papers), 1)
        self.assertEqual(alg.papers[0].url, "https://csrc.nist.gov/pubs/fips/204/final")

    def test_rejects_missing_summary(self):
        errors = self.algorithm_errors(
            ALGORITHMS.replace('summary = "A lattice-based signature scheme."\n', "")
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("algorithms.toml: ml-dsa: summary: required", errors[0])

    def test_rejects_summary_over_80_words(self):
        too_long = " ".join(["word"] * 81)
        errors = self.algorithm_errors(
            ALGORITHMS.replace("A lattice-based signature scheme.", too_long)
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("algorithms.toml: ml-dsa: summary:", errors[0])
        self.assertIn("80 words", errors[0])

    def test_accepts_summary_of_80_words(self):
        eighty = " ".join(["word"] * 80)
        write_data(
            self.tmp,
            algorithms=ALGORITHMS.replace("A lattice-based signature scheme.", eighty),
        )
        self.assertEqual(load_registry(self.tmp).algorithms["ml-dsa"].summary, eighty)

    def test_rejects_zero_or_more_than_three_papers(self):
        paper = '{ title = "P", url = "https://example.org/p" }'
        cases = {
            "papers = []": "must not be empty",
            "papers = [" + ", ".join([paper] * 4) + "]": "at most 3",
        }
        for papers, message in cases.items():
            with self.subTest(papers=papers[:20]):
                text = ALGORITHMS.split("papers =")[0] + papers + "\n"
                errors = self.algorithm_errors(text)
                self.assertEqual(len(errors), 1)
                self.assertIn("algorithms.toml: ml-dsa: papers:", errors[0])
                self.assertIn(message, errors[0])

    def test_rejects_missing_papers(self):
        errors = self.algorithm_errors(ALGORITHMS.split("papers =")[0])
        self.assertIn("algorithms.toml: ml-dsa: papers: required", errors[0])


class ChainLogoTest(RegistryTestCase):
    def logo_errors(self, logo: str) -> list[str]:
        return self.errors_for(blockchains=CHAIN + f'logo = "{logo}"\n')

    def setUp(self):
        super().setUp()
        self.logos = self.tmp / "logos"
        self.logos.mkdir()
        self.logos_dir = self.logos

    def test_accepts_valid_logos(self):
        write_data(
            self.tmp,
            blockchains=CHAIN
            + 'logo = "mark.svg"\n'
            + CHAIN.replace("Quantus", "Other")
            + 'logo = "mark.png"\n',
        )
        reg = load_registry(self.tmp, LOGOS)
        self.assertEqual([c.logo for c in reg.chains], ["mark.svg", "mark.png"])

    def test_logo_is_optional(self):
        self.assertIsNone(load_registry(FIXTURES / "valid").chains[0].logo)

    def test_default_logos_dir_is_assets_registry_logos(self):
        site = self.tmp / "site"
        data = site / "registry" / "data"
        logos = site / "assets" / "registry" / "logos"
        data.mkdir(parents=True)
        logos.mkdir(parents=True)
        (logos / "mark.svg").write_bytes((LOGOS / "mark.svg").read_bytes())
        write_data(data, blockchains=CHAIN + 'logo = "mark.svg"\n')
        self.assertEqual(load_registry(data).chains[0].logo, "mark.svg")

    def test_rejects_logo_missing_file(self):
        errors = self.logo_errors("nope.svg")
        self.assertEqual(len(errors), 1)
        self.assertIn("blockchains.toml: Quantus: logo:", errors[0])
        self.assertIn("nope.svg", errors[0])

    def test_rejects_logo_bad_extension(self):
        (self.logos / "mark.gif").write_bytes(b"GIF89a")
        errors = self.logo_errors("mark.gif")
        self.assertEqual(len(errors), 1)
        self.assertIn("blockchains.toml: Quantus: logo:", errors[0])
        self.assertIn(".svg, .png, or .webp", errors[0])

    def test_rejects_logo_over_64kb(self):
        (self.logos / "big.png").write_bytes(b"0" * (65536 + 1))
        errors = self.logo_errors("big.png")
        self.assertEqual(len(errors), 1)
        self.assertIn("blockchains.toml: Quantus: logo:", errors[0])
        self.assertIn("65536", errors[0])

    def test_accepts_logo_of_exactly_64kb(self):
        (self.logos / "edge.png").write_bytes(b"0" * 65536)
        write_data(self.tmp, blockchains=CHAIN + 'logo = "edge.png"\n')
        self.assertEqual(load_registry(self.tmp, self.logos).chains[0].logo, "edge.png")

    def test_rejects_svg_logo_with_script(self):
        cases = {
            "script.svg": '<svg xmlns="http://www.w3.org/2000/svg"><SCRIPT>1</SCRIPT></svg>',
            "onload.svg": '<svg xmlns="http://www.w3.org/2000/svg" onload="x()"></svg>',
            "onclick.svg": '<svg xmlns="http://www.w3.org/2000/svg"><g\nOnClick = "x()"/></svg>',
        }
        for name, text in cases.items():
            with self.subTest(name=name):
                (self.logos / name).write_text(text, encoding="utf-8")
                errors = self.logo_errors(name)
                self.assertEqual(len(errors), 1)
                self.assertIn("blockchains.toml: Quantus: logo:", errors[0])

    def test_rejects_logo_path_outside_logos_dir(self):
        errors = self.logo_errors("../mark.svg")
        self.assertEqual(len(errors), 1)
        self.assertIn("blockchains.toml: Quantus: logo:", errors[0])


class LibrarySlugTest(unittest.TestCase):
    def test_library_slug(self):
        cases = {
            "qp-rusty-crystals": "qp-rusty-crystals",
            "AWS LC (rs)": "aws-lc-rs",
            "PQClean": "pqclean",
            "  --Bouncy  Castle!! ": "bouncy-castle",
        }
        for name, slug in cases.items():
            with self.subTest(name=name):
                self.assertEqual(library_slug(name), slug)


class LibrarySafetyTest(unittest.TestCase):
    def setUp(self):
        self.algorithms = {
            "ml-dsa": Algorithm("ml-dsa", "ML-DSA", "lattice", "https://a.org", "S", ()),
            "slh-dsa": Algorithm("slh-dsa", "SLH-DSA", "hash-based", "https://b.org", "S", ()),
            "other-alg": Algorithm("other-alg", "Other", "other", "https://c.org", "S", ()),
        }

    def lib(self, *ids: str) -> Library:
        return Library(
            name="L",
            source="https://x.org",
            algorithms=ids,
            maturity="production",
            blockchain_friendly=False,
            audits=(),
            min_signature=None,
            min_public_key=None,
            note=None,
            links=(),
        )

    def test_library_safety_is_highest_of_its_algorithms(self):
        self.assertEqual(library_safety(self.lib("ml-dsa", "slh-dsa"), self.algorithms), "High")
        self.assertEqual(library_safety(self.lib("ml-dsa"), self.algorithms), "Medium")
        self.assertEqual(library_safety(self.lib("other-alg"), self.algorithms), "Low")


if __name__ == "__main__":
    unittest.main()

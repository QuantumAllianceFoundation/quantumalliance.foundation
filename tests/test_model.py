import tempfile
import unittest
from pathlib import Path

from tools.registry.model import (
    Algorithm,
    Library,
    RegistryError,
    library_safety,
    load_registry,
)

FIXTURES = Path(__file__).parent / "fixtures"

ALGORITHMS = """
[[algorithm]]
id = "ml-dsa"
name = "ML-DSA"
family = "lattice"
url = "https://csrc.nist.gov/pubs/fips/204/final"
"""

CHAIN = """
[[chain]]
name = "Quantus"
category = "post-quantum"
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

    def errors_for(self, **files: str) -> list[str]:
        write_data(self.tmp, **files)
        with self.assertRaises(RegistryError) as cm:
            load_registry(self.tmp)
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
            + 'notes = ["Fast"]\n',
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
        self.assertEqual(lib.min_signature.bytes, 666)
        self.assertEqual(lib.min_signature.parameter_set, "Falcon-512")
        self.assertEqual(lib.notes, ("Fast",))
        self.assertEqual(reg.products[0].chains, ("Ethereum",))

    def test_rejects_unknown_category(self):
        errors = self.errors_for(
            blockchains=CHAIN.replace("post-quantum", "quantum-safe", 1)
        )
        self.assertIn("blockchains.toml: Quantus: category:", errors[0])

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
            blockchains=CHAIN.replace('category = "post-quantum"\n', "")
        )
        self.assertIn("blockchains.toml: Quantus: category:", errors[0])

    def test_reports_every_error_with_location(self):
        errors = self.errors_for(
            blockchains=CHAIN.replace("post-quantum", "quantum-safe", 1),
            libraries=LIBRARY.replace('["ml-dsa"]', '["nope"]')
            + LIBRARY.replace("TestLib", "Other").replace("production", "stable"),
        )
        self.assertEqual(len(errors), 3)
        self.assertTrue(all(": " in e for e in errors))


class LibrarySafetyTest(unittest.TestCase):
    def setUp(self):
        self.algorithms = {
            "ml-dsa": Algorithm("ml-dsa", "ML-DSA", "lattice", "https://a.org"),
            "slh-dsa": Algorithm("slh-dsa", "SLH-DSA", "hash-based", "https://b.org"),
            "other-alg": Algorithm("other-alg", "Other", "other", "https://c.org"),
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
            notes=(),
        )

    def test_library_safety_is_highest_of_its_algorithms(self):
        self.assertEqual(library_safety(self.lib("ml-dsa", "slh-dsa"), self.algorithms), "High")
        self.assertEqual(library_safety(self.lib("ml-dsa"), self.algorithms), "Medium")
        self.assertEqual(library_safety(self.lib("other-alg"), self.algorithms), "Low")


if __name__ == "__main__":
    unittest.main()

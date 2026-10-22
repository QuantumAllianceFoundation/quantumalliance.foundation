import tempfile
import unittest
from pathlib import Path

from tools.registry.model import (
    Algorithm,
    Library,
    RegistryError,
    Repository,
    algorithm_safety,
    library_safety,
    library_safety_reason,
    chain_slug,
    library_capabilities,
    library_slug,
    load_registry,
)

FIXTURES = Path(__file__).parent / "fixtures"
LOGOS = FIXTURES / "valid" / "logos"
AUDITORS = FIXTURES / "valid" / "auditors"

ALGORITHMS = """
[[algorithm]]
id = "ml-dsa"
name = "ML-DSA"
family = "lattice"
kind = "signature"
url = "https://csrc.nist.gov/pubs/fips/204/final"
summary = "A lattice-based signature scheme."
rationale = "Relies on structured lattice assumptions with mature cryptanalysis."
papers = [{ title = "CRYSTALS-Dilithium (2018)", url = "https://example.org/dilithium" }]
"""

CHAIN = """
[[chain]]
name = "Quantus"
consensus = "post-quantum"
transactions = "post-quantum"
consensus_reason = "Judgment call: active work, no deployment path yet."
transactions_reason = "Transactions are signed with a post-quantum scheme."
website = "https://quantus.com/"
source = "https://github.com/Quantus-Network"
algorithms = ["ml-dsa"]
"""

LIBRARY = """
[[library]]
name = "TestLib"
repositories = [{ language = "Rust", url = "https://example.org/testlib" }]
algorithms = ["ml-dsa"]
hybrid = false
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
        reg = load_registry(FIXTURES / "valid", auditors_dir=AUDITORS)
        self.assertEqual(reg.algorithms["ml-dsa"].family, "lattice")
        self.assertEqual(reg.chains[0].algorithms, ("ml-dsa",))
        self.assertIsNone(reg.libraries[0].min_signature)
        self.assertEqual(reg.products, ())

    def test_loads_optional_fields(self):
        write_data(
            self.tmp,
            libraries=LIBRARY
            + 'audits = [{ auditor = "Audit Co", url = "https://example.org/a" }]\n'
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
        self.assertEqual(lib.audits[0].auditor, "Audit Co")
        self.assertIsNone(lib.audits[0].logo)
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
        reg = load_registry(FIXTURES / "valid", auditors_dir=AUDITORS)
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

    def test_rejects_empty_library_slug(self):
        errors = self.errors_for(libraries=LIBRARY.replace("TestLib", "+++"))
        self.assertEqual(
            errors,
            ["libraries.toml: +++: name: needs at least one letter or digit for its page address"],
        )

    def test_rejects_colliding_library_slugs(self):
        errors = self.errors_for(
            libraries=LIBRARY.replace("TestLib", "C") + LIBRARY.replace("TestLib", "C++")
        )
        self.assertEqual(
            errors,
            ['libraries.toml: C++: name: page address "c" is already used by C'],
        )

    def test_rejects_empty_or_colliding_chain_slugs(self):
        errors = self.errors_for(blockchains=CHAIN.replace("Quantus", "+++"))
        self.assertEqual(
            errors,
            ["blockchains.toml: +++: name: needs at least one letter or digit for its page address"],
        )
        errors = self.errors_for(
            blockchains=CHAIN.replace("Quantus", "C") + CHAIN.replace("Quantus", "C++")
        )
        self.assertEqual(
            errors,
            ['blockchains.toml: C++: name: page address "c" is already used by C'],
        )

    def test_chain_slug_matches_library_slug(self):
        for name in ("Quantus", "Bitcoin Cash", "C++", "+++"):
            with self.subTest(name=name):
                self.assertEqual(chain_slug(name), library_slug(name))

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


class AlgorithmKindTest(RegistryTestCase):
    def test_rejects_missing_or_unknown_kind(self):
        cases = {
            ALGORITHMS.replace('kind = "signature"\n', ""): "algorithms.toml: ml-dsa: kind: required",
            ALGORITHMS.replace('"signature"', '"cipher"'): "algorithms.toml: ml-dsa: kind: must be one of signature, kem",
        }
        for text, expected in cases.items():
            with self.subTest(expected=expected):
                errors = self.errors_for(algorithms=text)
                self.assertIn(expected, [e[: len(expected)] for e in errors])

    def test_loads_kem_kind(self):
        write_data(self.tmp, algorithms=ALGORITHMS.replace('"signature"', '"kem"'))
        self.assertEqual(load_registry(self.tmp).algorithms["ml-dsa"].kind, "kem")


class ChainReasonTest(RegistryTestCase):
    def test_rejects_missing_chain_reasons(self):
        for field in ("consensus_reason", "transactions_reason"):
            with self.subTest(field=field):
                text = "\n".join(
                    line for line in CHAIN.splitlines() if not line.startswith(field)
                )
                errors = self.errors_for(blockchains=text)
                self.assertEqual(errors, [f"blockchains.toml: Quantus: {field}: required"])

    def test_rejects_chain_reason_over_40_words(self):
        for field in ("consensus_reason", "transactions_reason"):
            with self.subTest(field=field):
                text = "\n".join(
                    f'{field} = "{" ".join(["word"] * 41)}"' if line.startswith(field) else line
                    for line in CHAIN.splitlines()
                )
                (error,) = self.errors_for(blockchains=text)
                self.assertTrue(error.startswith(f"blockchains.toml: Quantus: {field}:"))
                self.assertIn("40 words", error)

    def test_accepts_chain_reason_of_40_words(self):
        forty = " ".join(["word"] * 40)
        text = CHAIN.replace("Judgment call: active work, no deployment path yet.", forty)
        write_data(self.tmp, blockchains=text)
        self.assertEqual(load_registry(self.tmp).chains[0].consensus_reason, forty)


class AlgorithmContentTest(RegistryTestCase):
    def algorithm_errors(self, algorithms: str) -> list[str]:
        """Return the algorithms.toml errors; dangling references add others."""
        errors = self.errors_for(algorithms=algorithms)
        return [e for e in errors if e.startswith("algorithms.toml:")]

    def test_loads_summary_and_papers(self):
        alg = load_registry(FIXTURES / "valid", auditors_dir=AUDITORS).algorithms["ml-dsa"]
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

    def test_rejects_missing_rationale(self):
        errors = self.algorithm_errors(
            ALGORITHMS.replace(
                'rationale = "Relies on structured lattice assumptions with mature cryptanalysis."\n',
                "",
            )
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("algorithms.toml: ml-dsa: rationale: required", errors[0])

    def test_rejects_rationale_over_60_words(self):
        errors = self.algorithm_errors(
            ALGORITHMS.replace(
                "Relies on structured lattice assumptions with mature cryptanalysis.",
                " ".join(["word"] * 61),
            )
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("algorithms.toml: ml-dsa: rationale:", errors[0])
        self.assertIn("60 words", errors[0])

    def test_accepts_rationale_of_60_words(self):
        sixty = " ".join(["word"] * 60)
        write_data(
            self.tmp,
            algorithms=ALGORITHMS.replace(
                "Relies on structured lattice assumptions with mature cryptanalysis.", sixty
            ),
        )
        self.assertEqual(load_registry(self.tmp).algorithms["ml-dsa"].rationale, sixty)

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
        self.assertIsNone(load_registry(FIXTURES / "valid", auditors_dir=AUDITORS).chains[0].logo)

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


class LibraryCapabilitiesTest(unittest.TestCase):
    def setUp(self):
        self.algorithms = {
            "sig": Algorithm("sig", "Sig", "lattice", "signature", "https://a.org", "S", "R", ()),
            "sig2": Algorithm("sig2", "Sig2", "lattice", "signature", "https://a.org", "S", "R", ()),
            "kem": Algorithm("kem", "Kem", "lattice", "kem", "https://b.org", "S", "R", ()),
        }

    def lib(self, *ids: str) -> Library:
        return Library(
            name="L",
            repositories=(Repository("Rust", "https://x.org"),),
            algorithms=ids,
            hybrid=False,
            maturity="production",
            blockchain_friendly=False,
            audits=(),
            min_signature=None,
            min_public_key=None,
            note=None,
            links=(),
        )

    def test_library_capabilities_signatures_only(self):
        self.assertEqual(library_capabilities(self.lib("sig", "sig2"), self.algorithms), ("Signatures",))

    def test_library_capabilities_kem_only(self):
        self.assertEqual(library_capabilities(self.lib("kem"), self.algorithms), ("Key exchange",))

    def test_library_capabilities_both_in_order(self):
        for ids in (("kem", "sig"), ("sig", "kem")):
            with self.subTest(ids=ids):
                self.assertEqual(
                    library_capabilities(self.lib(*ids), self.algorithms),
                    ("Signatures", "Key exchange"),
                )


class LibrarySafetyTest(unittest.TestCase):
    def setUp(self):
        self.algorithms = {
            "ml-dsa": Algorithm("ml-dsa", "ML-DSA", "lattice", "signature", "https://a.org", "S", "R", ()),
            "slh-dsa": Algorithm("slh-dsa", "SLH-DSA", "hash-based", "signature", "https://b.org", "S", "R", ()),
            "other-alg": Algorithm("other-alg", "Other", "other", "signature", "https://c.org", "S", "R", ()),
        }

    def lib(self, *ids: str, hybrid: bool = False) -> Library:
        return Library(
            name="L",
            repositories=(Repository("Rust", "https://x.org"),),
            algorithms=ids,
            hybrid=hybrid,
            maturity="production",
            blockchain_friendly=False,
            audits=(),
            min_signature=None,
            min_public_key=None,
            note=None,
            links=(),
        )

    def test_library_safety_hybrid_is_high(self):
        for ids in (("ml-dsa",), ("other-alg",), ("slh-dsa", "ml-dsa")):
            with self.subTest(ids=ids):
                lib = self.lib(*ids, hybrid=True)
                self.assertEqual(library_safety(lib, self.algorithms), "High")

    def test_library_safety_nonhybrid_hash_is_medium(self):
        self.assertEqual(library_safety(self.lib("slh-dsa"), self.algorithms), "Medium")

    def test_library_safety_nonhybrid_lattice_is_low(self):
        self.assertEqual(library_safety(self.lib("ml-dsa"), self.algorithms), "Low")
        self.assertEqual(library_safety(self.lib("other-alg"), self.algorithms), "Low")

    def test_library_safety_uses_best_family(self):
        lib = self.lib("ml-dsa", "slh-dsa")
        self.assertEqual(library_safety(lib, self.algorithms), "Medium")

    def test_algorithm_safety_family_rule(self):
        self.assertEqual(algorithm_safety(self.algorithms["slh-dsa"]), "High")
        self.assertEqual(algorithm_safety(self.algorithms["ml-dsa"]), "Medium")
        self.assertEqual(algorithm_safety(self.algorithms["other-alg"]), "Low")

    def test_library_safety_reason_hybrid(self):
        lib = self.lib("ml-dsa", hybrid=True)
        self.assertEqual(
            library_safety_reason(lib, self.algorithms),
            "Hybrid design: a classical and a post-quantum signature must both verify.",
        )

    def test_library_safety_reason_best_family(self):
        cases = {
            ("ml-dsa",): "lattice-based",
            ("ml-dsa", "slh-dsa"): "hash-based",
            ("other-alg",): "other",
        }
        for ids, family in cases.items():
            with self.subTest(ids=ids):
                self.assertEqual(
                    library_safety_reason(self.lib(*ids), self.algorithms),
                    f"Best algorithm family is {family}; "
                    "without a hybrid design the rating drops one level.",
                )


class LibraryFieldsTest(RegistryTestCase):
    def library_errors(self, libraries: str) -> list[str]:
        return [e for e in self.errors_for(libraries=libraries) if e.startswith("libraries.toml:")]

    def test_loads_repositories_hybrid_and_audits(self):
        reg = load_registry(FIXTURES / "valid", auditors_dir=AUDITORS)
        lib = reg.libraries[0]
        self.assertEqual(lib.repositories[0], Repository("Rust", "https://example.org/testlib"))
        self.assertFalse(lib.hybrid)
        self.assertEqual(lib.audits[0].auditor, "Test Auditor")
        self.assertEqual(lib.audits[0].logo, "auditor.svg")

    def test_rejects_missing_hybrid(self):
        errors = self.library_errors(LIBRARY.replace("hybrid = false\n", ""))
        self.assertEqual(len(errors), 1)
        self.assertIn("libraries.toml: TestLib: hybrid: required", errors[0])

    def test_rejects_zero_or_five_repositories(self):
        repo = '{ language = "Rust", url = "https://example.org/r" }'
        cases = {
            "repositories = []": "must not be empty",
            "repositories = [" + ", ".join([repo] * 5) + "]": "at most 4",
        }
        for repositories, message in cases.items():
            with self.subTest(repositories=repositories[:20]):
                text = LIBRARY.replace(
                    'repositories = [{ language = "Rust", url = "https://example.org/testlib" }]',
                    repositories,
                )
                errors = self.library_errors(text)
                self.assertEqual(len(errors), 1)
                self.assertIn("libraries.toml: TestLib: repositories:", errors[0])
                self.assertIn(message, errors[0])

    def test_rejects_repository_without_language(self):
        text = LIBRARY.replace('language = "Rust", ', "")
        errors = self.library_errors(text)
        self.assertEqual(len(errors), 1)
        self.assertIn("libraries.toml: TestLib: repositories:", errors[0])
        self.assertIn("language", errors[0])

    def test_rejects_old_source_key(self):
        errors = self.library_errors(LIBRARY + 'source = "https://example.org/x"\n')
        self.assertEqual(len(errors), 1)
        self.assertIn("libraries.toml: TestLib: source: unknown key", errors[0])

    def test_audit_requires_auditor_and_url(self):
        for audit, missing in (
            ('{ url = "https://example.org/a" }', "auditor"),
            ('{ auditor = "Audit Co" }', "url"),
        ):
            with self.subTest(missing=missing):
                errors = self.library_errors(LIBRARY + f"audits = [{audit}]\n")
                self.assertEqual(len(errors), 1)
                self.assertIn("libraries.toml: TestLib: audits:", errors[0])
                self.assertIn(missing, errors[0])


class AuditLogoTest(RegistryTestCase):
    def audit_errors(self, logo: str) -> list[str]:
        audit = f'audits = [{{ auditor = "A", url = "https://example.org/a", logo = "{logo}" }}]\n'
        return self.errors_for(libraries=LIBRARY + audit)

    def setUp(self):
        super().setUp()
        self.auditors = self.tmp / "auditors"
        self.auditors.mkdir()

    def errors_for(self, **files: str) -> list[str]:
        write_data(self.tmp, **files)
        with self.assertRaises(RegistryError) as cm:
            load_registry(self.tmp, auditors_dir=self.auditors)
        return cm.exception.errors

    def test_accepts_audit_logo(self):
        (self.auditors / "a.svg").write_bytes((AUDITORS / "auditor.svg").read_bytes())
        audit = 'audits = [{ auditor = "A", url = "https://example.org/a", logo = "a.svg" }]\n'
        write_data(self.tmp, libraries=LIBRARY + audit)
        reg = load_registry(self.tmp, auditors_dir=self.auditors)
        self.assertEqual(reg.libraries[0].audits[0].logo, "a.svg")

    def test_default_auditors_dir_is_assets_registry_auditors(self):
        site = self.tmp / "site"
        data = site / "registry" / "data"
        auditors = site / "assets" / "registry" / "auditors"
        data.mkdir(parents=True)
        auditors.mkdir(parents=True)
        (auditors / "a.svg").write_bytes((AUDITORS / "auditor.svg").read_bytes())
        audit = 'audits = [{ auditor = "A", url = "https://example.org/a", logo = "a.svg" }]\n'
        write_data(data, libraries=LIBRARY + audit)
        self.assertEqual(load_registry(data).libraries[0].audits[0].logo, "a.svg")

    def test_rejects_audit_logo_missing_file(self):
        errors = self.audit_errors("nope.svg")
        self.assertEqual(len(errors), 1)
        self.assertIn("libraries.toml: TestLib: audits:", errors[0])
        self.assertIn("nope.svg", errors[0])

    def test_rejects_svg_audit_logo_with_script(self):
        (self.auditors / "bad.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><script>1</script></svg>',
            encoding="utf-8",
        )
        errors = self.audit_errors("bad.svg")
        self.assertEqual(len(errors), 1)
        self.assertIn("libraries.toml: TestLib: audits:", errors[0])
        self.assertIn("<script>", errors[0])

    def test_rejects_audit_logo_path_and_extension(self):
        (self.auditors / "a.gif").write_bytes(b"GIF89a")
        for name in ("../a.svg", "a.gif"):
            with self.subTest(name=name):
                errors = self.audit_errors(name)
                self.assertEqual(len(errors), 1)
                self.assertIn("libraries.toml: TestLib: audits:", errors[0])


if __name__ == "__main__":
    unittest.main()

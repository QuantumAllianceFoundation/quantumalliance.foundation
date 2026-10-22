import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from tools.build_registries import main

VALID = Path(__file__).parent / "fixtures" / "valid"
PAGES = {
    "registry/index.html": "/registry/",
    "registry/blockchains/index.html": "/registry/blockchains/",
    "registry/libraries/index.html": "/registry/libraries/",
    "registry/products/index.html": "/registry/products/",
    "registry/algorithms/index.html": "/registry/algorithms/",
    "registry/algorithms/ml-dsa/index.html": "/registry/algorithms/ml-dsa/",
    "registry/algorithms/slh-dsa/index.html": "/registry/algorithms/slh-dsa/",
    "registry/algorithms/other-alg/index.html": "/registry/algorithms/other-alg/",
}


class BuildTests(unittest.TestCase):
    def test_build_writes_algorithm_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = main(["--data", str(VALID), "--out", tmp])
            self.assertEqual(rc, 0)
            for page, path in PAGES.items():
                file = Path(tmp) / page
                self.assertTrue(file.is_file(), page)
                html = file.read_text(encoding="utf-8")
                self.assertIn(
                    f'<link rel="canonical" href="https://quantumalliance.foundation{path}">',
                    html,
                )
                self.assertIn('<a href="/registry/">Registries</a>', html)
                self.assertIn("/assets/table-sort.js", html)

    def test_build_writes_logos_option_and_algorithm_page_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = main(["--data", str(VALID), "--logos", str(VALID / "logos"), "--out", tmp])
            self.assertEqual(rc, 0)
            html = (Path(tmp) / "registry/algorithms/ml-dsa/index.html").read_text(encoding="utf-8")
            self.assertIn("<h1>ML-DSA</h1>", html)
            self.assertIn("/registry/libraries/#lib-testlib", html)

    def test_build_returns_1_and_writes_nothing_on_invalid_data(self):
        with tempfile.TemporaryDirectory() as data, tempfile.TemporaryDirectory() as out:
            for f in VALID.glob("*.toml"):
                (Path(data) / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
            chains = Path(data) / "blockchains.toml"
            chains.write_text(
                chains.read_text(encoding="utf-8").replace("post-quantum", "bogus", 1),
                encoding="utf-8",
            )
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = main(["--data", data, "--out", out])
            self.assertEqual(rc, 1)
            self.assertIn("blockchains.toml", err.getvalue())
            self.assertEqual(list(Path(out).iterdir()), [])


if __name__ == "__main__":
    unittest.main()

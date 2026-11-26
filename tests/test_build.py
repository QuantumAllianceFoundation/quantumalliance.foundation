import contextlib
import io
import re
import tempfile
import tomllib
import unittest
from pathlib import Path

from tools.build import ROOT, main

VALID = Path(__file__).parent / "fixtures" / "valid"
ASSETS = ["--logos", str(VALID / "logos"), "--auditors", str(VALID / "auditors")]
PAGES = {
    "registry/index.html": "/registry/",
    "registry/blockchains/index.html": "/registry/blockchains/",
    "registry/libraries/index.html": "/registry/libraries/",
    "registry/products/index.html": "/registry/products/",
    "registry/algorithms/index.html": "/registry/algorithms/",
    "registry/algorithms/ml-dsa/index.html": "/registry/algorithms/ml-dsa/",
    "registry/algorithms/slh-dsa/index.html": "/registry/algorithms/slh-dsa/",
    "registry/algorithms/other-alg/index.html": "/registry/algorithms/other-alg/",
    "registry/libraries/testlib/index.html": "/registry/libraries/testlib/",
    "registry/blockchains/quantus/index.html": "/registry/blockchains/quantus/",
    "index.html": "/",
    "media/index.html": "/media/",
    "news/launch/index.html": "/news/launch/",
}
TABLE_PAGES = {
    "registry/blockchains/index.html",
    "registry/libraries/index.html",
    "registry/products/index.html",
    "registry/algorithms/index.html",
}


class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls._tmp.name) / "dist"
        rc = main(["--data", str(VALID), *ASSETS, "--out", str(cls.out)])
        assert rc == 0

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def read(self, page):
        return (self.out / page).read_text(encoding="utf-8")

    def html_files(self):
        return sorted(self.out.rglob("*.html"))

    def test_pages_have_canonical_urls(self):
        for page, path in PAGES.items():
            self.assertIn(
                f'<link rel="canonical" href="https://quantumalliance.foundation{path}">',
                self.read(page),
                page,
            )

    def test_every_page_shares_the_chrome(self):
        for file in self.html_files():
            html = file.read_text(encoding="utf-8")
            self.assertIn('<a class="skip-link" href="#main">Skip to content</a>', html, file)
            self.assertIn('<nav class="nav-links" aria-label="Main">', html, file)
            self.assertIn('<nav aria-label="Footer">', html, file)
            self.assertIn('<main id="main">', html, file)
            self.assertIn("/assets/og-image.png", html, file)

    def test_no_inline_styles(self):
        # The CSP sets style-src 'self', so a style attribute would be blocked.
        for file in self.html_files():
            self.assertIsNone(re.search(r"\sstyle=", file.read_text(encoding="utf-8")), file)

    def test_registries_link_is_current_on_registry_pages(self):
        current = '<a href="/registry/" aria-current="page">Registries</a>'
        self.assertIn(current, self.read("registry/blockchains/quantus/index.html"))
        self.assertNotIn(current, self.read("index.html"))

    def test_table_sort_loads_only_with_tables(self):
        for page in PAGES:
            has_script = "/assets/table-sort.js" in self.read(page)
            self.assertEqual(has_script, page in TABLE_PAGES, page)

    def test_chain_page(self):
        html = self.read("registry/blockchains/quantus/index.html")
        self.assertIn("<h1>", html)
        self.assertIn("Judgment call: active work, no deployment path yet.", html)
        self.assertIn("<title>Quantus | Quantum Alliance</title>", html)
        libs = self.read("registry/libraries/index.html")
        self.assertIn("<title>Post-Quantum Cryptography Libraries | Quantum Alliance</title>", libs)

    def test_library_page(self):
        html = self.read("registry/libraries/testlib/index.html")
        self.assertIn("<h1>TestLib</h1>", html)
        self.assertIn("Test Auditor audit report", html)
        self.assertIn("/assets/registry/auditors/auditor.svg", html)

    def test_algorithm_page(self):
        html = self.read("registry/algorithms/ml-dsa/index.html")
        self.assertIn("<h1>ML-DSA</h1>", html)
        self.assertIn("/registry/libraries/testlib/", html)

    def test_media_comes_from_one_list(self):
        with (ROOT / "content" / "media.toml").open("rb") as f:
            items = tomllib.load(f)["item"]
        coverage = sum(1 for item in items if item["section"] == "coverage")
        home = self.read("index.html")
        slider = home[home.index('<div class="media-track">'):home.index('id="why"')]
        self.assertEqual(slider.count('class="card media-card preview-card"'), coverage)
        media = self.read("media/index.html")
        self.assertEqual(media.count('class="card media-card preview-card"'), len(items))
        self.assertIn(f'<p class="intro">{len(items)} published', media)
        self.assertNotIn("<!--", media)

    def test_homepage_lists_registries(self):
        home = self.read("index.html")
        self.assertIn('<a href="/registry/blockchains/" class="card media-card">', home)
        self.assertIn("/assets/media-slider.js", home)

    def test_every_member_card_links_to_its_site(self):
        home = self.read("index.html")
        orgs = home[home.index('<div class="orgs">'):home.index('id="signup"')]
        self.assertEqual(orgs.count('class="org"'), 9)
        self.assertEqual(orgs.count('<h3><a href="https://'), 9)

    def test_page_specific_head(self):
        self.assertIn('content="2026-10-15"', self.read("news/launch/index.html"))
        self.assertIn('<meta name="robots" content="noindex">', self.read("thanks/index.html"))
        not_found = self.read("404.html")
        self.assertNotIn('rel="canonical"', not_found)
        self.assertNotIn("og:url", not_found)

    def test_sitemap_lists_indexable_pages(self):
        sitemap = self.read("sitemap.xml")
        self.assertIn("<loc>https://quantumalliance.foundation/</loc>", sitemap)
        self.assertIn("/registry/blockchains/quantus/</loc>", sitemap)
        self.assertNotIn("/thanks/", sitemap)
        self.assertNotIn("404", sitemap)

    def test_static_files_are_copied(self):
        for name in ("assets/styles.css", "favicon.svg", "robots.txt"):
            self.assertTrue((self.out / name).is_file(), name)
        self.assertFalse((self.out / "tools").exists())
        self.assertFalse((self.out / "content").exists())


class BuildOutputTests(unittest.TestCase):
    def test_removes_stale_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            stale = Path(tmp) / "registry/blockchains/gone/index.html"
            stale.parent.mkdir(parents=True)
            stale.write_text("old", encoding="utf-8")
            self.assertEqual(main(["--data", str(VALID), *ASSETS, "--out", tmp]), 0)
            self.assertFalse(stale.exists())

    def test_refuses_repository_root(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = main(["--data", str(VALID), *ASSETS, "--out", str(ROOT)])
        self.assertEqual(rc, 1)
        self.assertIn("refusing", err.getvalue())

    def test_returns_1_and_writes_nothing_on_invalid_data(self):
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
                rc = main(["--data", data, *ASSETS, "--out", out])
            self.assertEqual(rc, 1)
            self.assertIn("blockchains.toml", err.getvalue())
            self.assertEqual(list(Path(out).iterdir()), [])


if __name__ == "__main__":
    unittest.main()

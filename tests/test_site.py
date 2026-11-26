import tempfile
import unittest
from datetime import date
from pathlib import Path

from tools.site import MediaItem, fill_markers, load_media, media_card, nav_html, render_page, sitemap

TEMPLATE = "$title|$description|$url_meta|$scripts|$robots|$og_type|$head_extra|$nav|$body|$year"


def write_media(folder: Path, text: str) -> Path:
    path = folder / "media.toml"
    path.write_text(text, encoding="utf-8")
    (folder / "a.webp").write_bytes(b"")
    return path


ITEM = """
[[item]]
section = "coverage"
outlet = "Outlet"
title = "Title"
url = "https://example.org/a"
format = "News article"
date = 2026-10-16
"""


class SiteTests(unittest.TestCase):
    def test_render_page_escapes_and_fills(self):
        out = render_page(TEMPLATE, title="T & U", description="D", path="/media/",
                          body="<b>x</b>", year=2027, scripts=("a.js",))
        self.assertTrue(out.startswith("T &amp; U|D|"))
        self.assertIn('<link rel="canonical" href="https://quantumalliance.foundation/media/">', out)
        self.assertIn('<script type="module" src="/assets/a.js"></script>', out)
        self.assertTrue(out.endswith("|<b>x</b>|2027"))

    def test_render_page_without_path_has_no_canonical(self):
        out = render_page(TEMPLATE, title="T", description="D", path=None, body="", year=2027)
        self.assertNotIn("canonical", out)
        self.assertNotIn("og:url", out)

    def test_nav_marks_registries_current(self):
        self.assertIn('href="/registry/" aria-current="page"', nav_html("/registry/libraries/"))
        self.assertNotIn("aria-current", nav_html("/"))
        self.assertIn('class="btn btn-signal"', nav_html("/"))

    def test_fill_markers_rejects_missing_marker(self):
        self.assertEqual(fill_markers("a <!-- x --> b", {"x": "1"}), "a 1 b")
        with self.assertRaisesRegex(ValueError, "<!-- y -->"):
            fill_markers("a", {"y": "1"})

    def test_load_media_reads_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_media(Path(tmp), ITEM + 'image = "a.webp"\nlang = "de"\n')
            [item] = load_media(path, Path(tmp))
        self.assertEqual(item.date, date(2026, 10, 16))
        self.assertEqual(item.lang, "de")

    def test_load_media_reports_every_error(self):
        bad = ITEM.replace('"coverage"', '"blog"') + 'image = "missing.webp"\n'
        with tempfile.TemporaryDirectory() as tmp:
            path = write_media(Path(tmp), bad + "\n[[item]]\noutlet = 'x'\n")
            with self.assertRaises(ValueError) as caught:
                load_media(path, Path(tmp))
        message = str(caught.exception)
        self.assertIn("item 1: section must be one of", message)
        self.assertIn("item 1: image missing.webp not found", message)
        self.assertIn("item 2: unknown [], missing", message)

    def test_media_card(self):
        item = MediaItem("coverage", "O & P", "<T>", "https://example.org/?a=1&b=2",
                         "News article", date(2026, 10, 5), lang="pl")
        card = media_card(item, "  ")
        self.assertIn('<span class="preview-fallback" aria-hidden="true">O &amp; P</span>', card)
        self.assertIn('<h3 lang="pl">&lt;T&gt;</h3>', card)
        self.assertIn('href="https://example.org/?a=1&amp;b=2"', card)
        self.assertIn('<time datetime="2026-10-05">October 5, 2026</time>', card)

    def test_sitemap(self):
        xml = sitemap(["/", "/media/"])
        self.assertIn("<url><loc>https://quantumalliance.foundation/media/</loc></url>", xml)
        self.assertTrue(xml.startswith('<?xml version="1.0" encoding="UTF-8"?>'))


if __name__ == "__main__":
    unittest.main()

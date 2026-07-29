import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from x3publisher.epub import build_epub, page_xhtml


class EpubTests(unittest.TestCase):
    def test_page_has_linked_footnote(self):
        markup = page_xhtml(
            40,
            [
                {"kind": "body", "text": "Gangohi[21] taught."},
                {"kind": "footnote", "text": "21 A biographical note."},
            ],
        )

        self.assertIn('epub:type="noteref"', markup)
        self.assertIn('href="#note-40-21"', markup)
        self.assertIn('id="note-40-21"', markup)
        self.assertIn('href="#ref-40-21"', markup)

    def test_page_reapplies_latest_verified_glossary(self):
        markup = page_xhtml(
            15,
            [{"kind": "body", "text": "Hadrat ke Shuyitkb-o-Akabir."}],
        )

        self.assertIn("Shuyu\u0304kh-o-Aka\u0304bir", markup)
        self.assertNotIn("Shuyitkb", markup)

    def test_page_decomposes_scholarly_diacritics_for_crossink(self):
        markup = page_xhtml(
            48,
            [{"kind": "body", "text": "al-Lawḥ al-Maḥfūẓ"}],
        )

        self.assertIn("Lawh\u0323", markup)
        self.assertIn("Mah\u0323fu\u0304z\u0323", markup)
        self.assertNotIn("Lawḥ", markup)

    def test_epub_has_valid_container_and_uncompressed_mimetype(self):
        payload = {
            "regions": [{"page": 16, "kind": "body", "text": "Sample text."}]
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ocr = root / "ocr.json"
            epub = root / "sample.epub"
            ocr.write_text(json.dumps(payload), encoding="utf-8")
            build_epub(ocr, epub, {16})

            with zipfile.ZipFile(epub) as archive:
                self.assertEqual(archive.namelist()[0], "mimetype")
                self.assertEqual(
                    archive.getinfo("mimetype").compress_type,
                    zipfile.ZIP_STORED,
                )
                ElementTree.fromstring(archive.read("META-INF/container.xml"))
                ElementTree.fromstring(archive.read("OEBPS/package.opf"))
                ElementTree.fromstring(archive.read("OEBPS/nav.xhtml"))
                ElementTree.fromstring(archive.read("OEBPS/text/page-16.xhtml"))


if __name__ == "__main__":
    unittest.main()

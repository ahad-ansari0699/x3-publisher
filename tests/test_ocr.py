import unittest

import numpy as np

from x3publisher.ocr import extract_page_regions, parse_pages, scale_bbox


class FakeEngine:
    def __init__(self):
        self.kinds = []

    def recognize(self, rgb, kind):
        self.kinds.append(kind)
        return f"{kind} text"


class OcrTests(unittest.TestCase):
    def test_parse_pages_supports_ranges(self):
        self.assertEqual(parse_pages("2,4-6"), {2, 4, 5, 6})

    def test_scale_bbox_scales_pads_and_clamps(self):
        self.assertEqual(
            scale_bbox([0, 10, 100, 100], (100, 100), (200, 300), padding=8),
            [0, 22, 200, 300],
        )

    def test_body_and_footnote_are_recognized_separately(self):
        page = {
            "page": 17,
            "width": 100,
            "height": 100,
            "regions": [
                {"kind": "header", "bbox": [0, 0, 100, 10], "confidence": 0.7},
                {"kind": "body", "bbox": [10, 10, 90, 70], "confidence": 0.9},
                {
                    "kind": "footnote",
                    "bbox": [10, 75, 90, 95],
                    "confidence": 0.84,
                },
            ],
        }
        engine = FakeEngine()
        results, review = extract_page_regions(
            np.full((200, 200, 3), 255, dtype=np.uint8), page, engine
        )

        self.assertEqual(engine.kinds, ["body", "footnote"])
        self.assertEqual([result.kind for result in results], ["body", "footnote"])
        self.assertEqual([result.text for result in results], ["body text", "footnote text"])
        self.assertEqual(len(review), 2)


if __name__ == "__main__":
    unittest.main()

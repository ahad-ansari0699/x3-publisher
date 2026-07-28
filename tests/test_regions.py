import unittest

import numpy as np

from x3publisher.regions import detect_regions


class RegionDetectionTests(unittest.TestCase):
    def test_regular_body_does_not_become_footnote(self):
        gray = np.full((1000, 700), 255, dtype=np.uint8)
        lines = [(80, y, 520, 12) for y in range(160, 860, 32)]

        regions = detect_regions(gray, lines)

        self.assertEqual([region.kind for region in regions], ["body"])
        self.assertEqual(regions[0].line_count, len(lines))

    def test_smaller_bottom_text_after_gap_becomes_footnote(self):
        gray = np.full((1000, 700), 255, dtype=np.uint8)
        body = [(80, y, 520, 14) for y in range(160, 700, 34)]
        footnotes = [(90, 820, 480, 8), (90, 838, 430, 8)]

        regions = detect_regions(gray, body + footnotes)

        by_kind = {region.kind: region for region in regions}
        self.assertEqual(by_kind["footnote"].line_count, 2)
        self.assertEqual(by_kind["body"].line_count, len(body))

    def test_header_and_footer_are_separate(self):
        gray = np.full((1000, 700), 255, dtype=np.uint8)
        lines = [
            (250, 50, 200, 10),
            (80, 180, 520, 14),
            (80, 220, 520, 14),
            (330, 940, 40, 10),
        ]

        regions = detect_regions(gray, lines)

        self.assertEqual(
            [region.kind for region in regions], ["header", "body", "footer"]
        )

    def test_region_coordinates_are_json_native_integers(self):
        gray = np.full((1000, 700), 255, dtype=np.uint8)
        lines = [(np.int32(80), np.int32(180), np.int32(520), np.int32(14))]

        region = detect_regions(gray, lines)[0]

        self.assertTrue(all(type(value) is int for value in region.bbox))

    def test_footnotes_can_be_disabled_for_non_body_pages(self):
        gray = np.full((1000, 700), 255, dtype=np.uint8)
        body = [(80, y, 520, 14) for y in range(160, 700, 34)]
        small_bottom_text = [(90, 820, 480, 8)]

        regions = detect_regions(
            gray, body + small_bottom_text, allow_footnotes=False
        )

        self.assertNotIn("footnote", [region.kind for region in regions])


if __name__ == "__main__":
    unittest.main()

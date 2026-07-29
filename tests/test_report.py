import unittest

from x3publisher.analyzer import PageAnalysis, region_overlay_html


def sample_page(regions):
    return PageAnalysis(
        page=1,
        width=1000,
        height=2000,
        dark_ink_ratio=0.1,
        medium_ink_ratio=0.2,
        colorfulness=0.0,
        text_line_count=10,
        text_block_count=2,
        body_bbox=[100, 200, 900, 1800],
        top_ink_ratio=0.0,
        bottom_ink_ratio=0.0,
        left_margin_ratio=0.1,
        right_margin_ratio=0.1,
        classification="Body text",
        confidence=0.9,
        warnings=[],
        regions=regions,
        thumbnail="",
    )


class ReportOverlayTests(unittest.TestCase):
    def test_overlay_uses_percentage_coordinates(self):
        page = sample_page(
            [
                {
                    "kind": "body",
                    "bbox": [100, 200, 900, 1800],
                    "confidence": 0.9,
                    "line_count": 20,
                }
            ]
        )

        overlay = region_overlay_html(page)

        self.assertIn('data-region="body"', overlay)
        self.assertIn("left:10.00%", overlay)
        self.assertIn("top:10.00%", overlay)
        self.assertIn("width:80.00%", overlay)
        self.assertIn("height:80.00%", overlay)

    def test_overlay_clamps_boxes_to_page(self):
        page = sample_page(
            [
                {
                    "kind": "footnote",
                    "bbox": [-20, 1900, 1100, 2100],
                    "confidence": 0.8,
                    "line_count": 2,
                }
            ]
        )

        overlay = region_overlay_html(page)

        self.assertIn("left:0.00%", overlay)
        self.assertIn("top:95.00%", overlay)
        self.assertIn("width:100.00%", overlay)
        self.assertIn("height:5.00%", overlay)


if __name__ == "__main__":
    unittest.main()

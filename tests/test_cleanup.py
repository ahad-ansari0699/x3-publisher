import unittest

from x3publisher.cleanup import clean_page_texts, recover_inline_footnotes


class CleanupTests(unittest.TestCase):
    def test_normalizes_repeated_names_and_merged_capital_i(self):
        body, _, changes = clean_page_texts(
            "Thad studied at Dar al-‘Uliim with Mufti Muhammad Shaff‘."
        )

        self.assertEqual(
            body, "I had studied at Dar al-‘Ulum with Mufti Muhammad Shafi‘."
        )
        self.assertTrue(changes)

    def test_recovers_inline_numbers_from_footnote_block(self):
        body = "Mawlana Gangohi*' went to Roorkee.* Mawlana Usmani*3 taught."
        footnotes = "21 First note.\n22 Second note.\n23 Third note."

        recovered, changes = recover_inline_footnotes(body, footnotes)

        self.assertEqual(
            recovered,
            "Mawlana Gangohi[21] went to Roorkee.[22] Mawlana Usmani[23] taught.",
        )
        self.assertEqual(changes, ["Recovered inline footnotes: 21, 22, 23"])

    def test_does_not_guess_when_marker_count_does_not_match(self):
        body = "One* and two*."
        recovered, changes = recover_inline_footnotes(body, "7 Only note.")

        self.assertEqual(recovered, body)
        self.assertEqual(changes, [])


if __name__ == "__main__":
    unittest.main()

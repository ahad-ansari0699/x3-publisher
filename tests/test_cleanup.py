import unittest

from x3publisher.cleanup import (
    clean_page_texts,
    recover_inline_footnotes,
    reflow_paragraphs,
)


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

    def test_reflows_wrapped_footnote_without_losing_paragraphs(self):
        text = (
            "21 One of the found-\ning fathers of the school.\n"
            "The next sentence continues.\n\n22 A city in India."
        )

        self.assertEqual(
            reflow_paragraphs(text),
            "21 One of the founding fathers of the school. "
            "The next sentence continues.\n\n22 A city in India.",
        )

    def test_corrects_verified_italic_transliteration_errors(self):
        body, _, _ = clean_page_texts(
            "Within 4o days, Haji Sabib granted Kdilafahb. "
            "Mawlana Sahil Bhaghalpiri taught in Saharanpar. "
            "See Tadbkirat ar-Rashid."
        )

        self.assertEqual(
            body,
            "within 40 days, Haji Sahib granted Khilafah. "
            "Mawlana Sahil Bhaghalpuri taught in Saharanpur. "
            "See Tadhkirat ar-Rashid.",
        )


if __name__ == "__main__":
    unittest.main()

"""Run the actual pinned author GMT reader in the optional scientific runtime."""
from pathlib import Path
import tempfile
import unittest

from tools.sampled_audit.wiki_current_view import author_memberships


class NativeWikiReaderTests(unittest.TestCase):
    def test_actual_author_reader_preserves_gene_ids_versions_and_duplicate_memberships(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "invented.gmt"
            path.write_text(
                "Invented pathway%WikiPathways_20261110%WP123%Homo sapiens\t"
                "https://example.invalid/WP123\t5885\t5885\t123\n"
                "Second%WikiPathways_20261110%WP124%Homo sapiens\t"
                "https://example.invalid/WP124\t5885\n", encoding="utf-8")
            source = Path(__file__).parent / "fixtures/pywikipathways_reader"
            frame, native = author_memberships(path, source)
            self.assertEqual(list(frame.columns), ["name", "version", "wpid", "org", "gene"])
            self.assertEqual(frame["gene"].tolist(), ["5885", "5885", "123", "5885"])
            self.assertEqual(frame["wpid"].tolist(), ["WP123", "WP123", "WP123", "WP124"])
            self.assertEqual(set(frame["version"]), {"WikiPathways_20261110"})
            self.assertEqual(set(frame["org"]), {"Homo sapiens"})
            self.assertEqual(len(native), 2)
            self.assertEqual(native[0][2:], ["5885", "5885", "123"])


if __name__ == "__main__":
    unittest.main()

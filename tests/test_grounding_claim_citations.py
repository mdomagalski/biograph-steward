"""Documented INDRA reader-metadata compatibility, not biological labels."""
import unittest

from tools.grounding_claims.prepare import inventory_publication_consensus, publication_consensus


class GroundingCitationCompatibility(unittest.TestCase):
    def test_stale_reader_reference_does_not_discard_the_native_citation(self):
        source = {'pmid': '12345', 'text_refs': {'PMID': 'TEXT00037_RT0001611'}}
        self.assertIsNone(inventory_publication_consensus(source))
        self.assertEqual(publication_consensus(source), '12345')
        self.assertEqual(source['text_refs']['PMID'], 'TEXT00037_RT0001611')

    def test_two_real_publication_identifiers_are_not_arbitrarily_reconciled(self):
        source = {'pmid': '12345', 'text_refs': {'PMID': '67890'}}
        self.assertIsNone(publication_consensus(source))

    def test_pmc_looking_reader_id_is_not_reinterpreted_as_a_pubmed_id(self):
        self.assertIsNone(publication_consensus({'pmid': None, 'text_refs': {'PMID': 'PMC24079887375'}}))


if __name__ == '__main__':
    unittest.main()

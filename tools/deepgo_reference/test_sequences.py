"""Invented sequence strings only, using the SeqRecord interface."""
import unittest
from types import SimpleNamespace
from .sequences import collect


def record(accession, sequence='MAST', taxon='9606', prefix='sp'):
    value = f'{prefix}|{accession}|INVENTED'
    return SimpleNamespace(id=value, description=f'{value} Invented fixture OX={taxon} GN=FAKE', seq=sequence)


class SequenceTests(unittest.TestCase):
    def test_exact_identity_join_does_not_depend_on_source_order(self):
        found = collect([record('P04637', 'M' * 1023), record('P00533')], {'P00533', 'P04637', 'P01116'})
        self.assertEqual(set(found), {'P00533', 'P04637'})
        self.assertTrue(found['P04637']['native_first1022_truncation'])
        self.assertEqual(found['P04637']['native_residues_used'], 1022)
        self.assertEqual(found['P04637']['residues'], 1023)
        self.assertEqual(found['P04637']['sequence'], 'M' * 1023)
        self.assertNotIn('P01116', found)  # Missing remains missing, no alias guess.

    def test_duplicate_species_or_provider_mismatch_is_not_repaired(self):
        for records in ([record('P00533'), record('P00533')],
                        [record('P00533', taxon='10090')],
                        [record('P00533', prefix='tr')]):
            with self.subTest(records=records), self.assertRaises(ValueError):
                collect(records, {'P00533'})

    def test_unknown_letters_are_preserved_but_sequence_is_not_rewritten(self):
        self.assertEqual(collect([record('P00533', 'MAUX')], {'P00533'})['P00533']['sequence'], 'MAUX')
        for sequence in ('', 'mast', 'MA-ST', 'MA\x00ST'):
            with self.subTest(sequence=sequence), self.assertRaises(ValueError):
                collect([record('P00533', sequence)], {'P00533'})


if __name__ == '__main__': unittest.main()

"""Invented source fixtures test bounded comparison, not biological accuracy."""
from copy import deepcopy
import unittest

from biograph_steward.client import digest
from biograph_steward.fact_comparison import compare_claim, parse_claim
from biograph_steward.source_facts import compile_source


def paper(methods, results):
    return {'pmid': '90000771', 'title': 'INVENTED source-pattern software fixture',
            'abstract': [{'text': methods, 'section': 'METHODS', 'locator': 'fixture/abstract/methods'},
                         {'text': results, 'section': 'RESULTS', 'locator': 'fixture/abstract/results'}]}


def response_source():
    return compile_source(paper(
        'Patients with mutant KRAS G12C received adagrasib monotherapy (600 mg orally twice daily) '
        'or adagrasib (at the same dose) in combination with intravenous cetuximab.',
        'In the monotherapy group (18 evaluable patients), a response was reported in 31% of the patients. '
        'In the combination-therapy group (12 evaluable patients), the response was 67%.'))


def survival_source(molecular='wild-type (WT) KRAS', extra=''):
    return compile_source(paper(
        'Patients received panitumumab-FOLFOX4 versus FOLFOX4.',
        'In the ' + molecular + ' stratum, panitumumab-FOLFOX4 significantly improved PFS compared with FOLFOX4 '
        '(median PFS, 9.6 v 8.0 months; P = .02). '
        'A nonsignificant increase in OS was also observed for panitumumab-FOLFOX4 versus FOLFOX4 '
        '(median OS, 23.9 v 19.7 months; P = .072).' + extra))


def response_claim(rate='67', arm='adagrasib and cetuximab combination group'):
    return f'The {arm} had a reported response rate of {rate}% in evaluable patients.'


def survival_claim(significance='nonsignificant', molecular='wild-type KRAS', endpoint='overall survival'):
    return ('In the ' + molecular + ' stratum, the increase in ' + endpoint +
            ' with panitumumab-FOLFOX4 compared with FOLFOX4 was ' + significance + '.')


class ClaimGrammarTests(unittest.TestCase):
    def test_claim_normalization_has_exact_spans_and_explicit_scope(self):
        claim = response_claim('67.00', 'cetuximab and adagrasib combination group')
        parsed = parse_claim(claim)
        self.assertTrue(parsed['supported'])
        self.assertEqual(parsed['facets']['regimen']['value'], ['adagrasib', 'cetuximab'])
        self.assertEqual(parsed['facets']['value']['value'], '67')
        self.assertNotIn('molecular', parsed['facets'])
        for facet in parsed['facets'].values():
            self.assertTrue(facet['normalization_rule'])
            for span in facet['claim_spans']:
                self.assertEqual(claim[span['start']:span['end']], span['text'])
        self.assertTrue(parse_claim('Cetuximab monotherapy had a reported response rate of 46% in evaluable patients.')['supported'])

    def test_fullmatch_never_discards_extra_qualifiers_or_unspecified_partners(self):
        unsupported = [response_claim() + ' This proves clinical benefit.',
            response_claim().replace(' in evaluable patients.', ' in mice.'),
            response_claim().replace('a reported', 'a statistically significant'),
            response_claim(arm='adagrasib combination group'),
            response_claim(arm='adagrasib and cetuximab monotherapy'),
            response_claim(arm='cetuximab'), response_claim('101'),
            response_claim().replace('and cetuximab', 'or cetuximab'),
            'The therapy had a response rate of 67% in evaluable patients.',
            survival_claim().replace('panitumumab-FOLFOX4', 'panitumumab'),
            survival_claim().replace('was nonsignificant.', 'was nonsignificant in patients.')]
        for claim in unsupported:
            with self.subTest(claim=claim):
                self.assertFalse(parse_claim(claim)['supported'])

    def test_named_regimen_is_not_assumed_to_be_a_single_drug(self):
        parsed = parse_claim(survival_claim())
        self.assertEqual(parsed['facets']['regimen']['value'], ['folfox4', 'panitumumab'])
        self.assertEqual(parsed['facets']['comparator']['value'], ['folfox4'])
        self.assertFalse(parse_claim(response_claim(arm='FOLFOX4 monotherapy'))['supported'])
        self.assertTrue(parse_claim(response_claim(arm='FOLFOX4 combination group'))['supported'])


class FactComparisonTests(unittest.TestCase):
    def assert_review_only(self, result):
        self.assertFalse(result['auto_approval'])
        self.assertFalse(result['entailment_established'])
        self.assertTrue(result['association_review_pending'])
        self.assertEqual(result['action'], 'request_review')
        self.assertEqual(result['graph_mutations'], 0)

    def test_correct_arm_value_matches_without_other_arm_false_flags_or_mutation(self):
        dossier = response_source(); before = digest(dossier)
        self.assertEqual(len(dossier['records']), 2)
        for claim in (response_claim(), response_claim('31', 'adagrasib monotherapy')):
            with self.subTest(claim=claim):
                result = compare_claim(claim, dossier)
                self.assertEqual(result['status'], 'limited_context_compatible')
                self.assertEqual(len(result['matched_record_ids']), 1)
                self.assertFalse(result['source_record_disagreement'])
                self.assert_review_only(result)
        self.assertEqual(digest(dossier), before)

    def test_words_and_numbers_from_different_arms_are_never_joined(self):
        dossier = response_source()
        result = compare_claim(response_claim('31'), dossier)
        self.assertEqual(result['status'], 'review_report_difference')
        self.assertEqual(result['matched_record_ids'], [])
        combo = next(c for c in result['candidates'] if c['asserted_context_matches'])
        value = next(f for f in combo['facets'] if f['field'] == 'value')
        self.assertEqual(value['status'], 'explicit_conflict')
        self.assertEqual(value['conflict_kind'], 'reported_value_difference')
        self.assertTrue(value['source_provenance'])
        other = next(c for c in result['candidates'] if not c['asserted_context_matches'])
        self.assertEqual(next(f for f in other['facets'] if f['field'] == 'value')['status'], 'unresolved')
        self.assert_review_only(result)

    def test_monotherapy_context_difference_is_not_a_biological_contradiction(self):
        result = compare_claim(response_claim(arm='cetuximab monotherapy'), response_source())
        self.assertEqual(result['status'], 'review_context_difference')
        for candidate in result['candidates']:
            self.assertFalse(candidate['asserted_context_matches'])
            value = next(f for f in candidate['facets'] if f['field'] == 'value')
            self.assertEqual(value['status'], 'unresolved')
            self.assertIsNone(value['conflict_kind'])
        self.assert_review_only(result)

    def test_endpoint_and_qualification_stay_on_the_same_record(self):
        dossier = survival_source()
        self.assertEqual({r['endpoint'] for r in dossier['records']}, {'PFS', 'OS'})
        self.assertEqual(compare_claim(survival_claim(), dossier)['status'], 'limited_context_compatible')
        self.assertEqual(compare_claim(survival_claim('statistically significant', endpoint='progression-free survival'), dossier)['status'],
                         'limited_context_compatible')
        result = compare_claim(survival_claim('statistically significant'), dossier)
        self.assertEqual(result['status'], 'review_report_difference')
        conflict = next(c for c in result['candidates'] if c['status'] == 'review_report_difference')
        self.assertEqual(next(f for f in conflict['facets'] if f['field'] == 'significance')['conflict_kind'], 'opposing_report')
        for other in (c for c in result['candidates'] if not c['asserted_context_matches']):
            self.assertEqual(next(f for f in other['facets'] if f['field'] == 'significance')['status'], 'unresolved')
        self.assert_review_only(result)

    def test_increase_cannot_match_a_reported_reduction(self):
        dossier = compile_source(paper('Invented methods.',
            'In the mutant KRAS stratum, PFS was significantly reduced in the panitumumab-FOLFOX4 '
            'arm versus the FOLFOX4 arm (P = .02).'))
        result = compare_claim(survival_claim('statistically significant', 'mutant KRAS',
                                             'progression-free survival'), dossier)
        self.assertEqual(result['status'], 'review_report_difference')
        candidate = next(c for c in result['candidates'] if c['asserted_context_matches'])
        direction = next(f for f in candidate['facets'] if f['field'] == 'effect_direction')
        self.assertEqual(direction['status'], 'explicit_conflict')
        self.assertEqual(direction['conflict_kind'], 'opposing_report')
        self.assert_review_only(result)

    def test_missing_direction_does_not_establish_an_increase(self):
        dossier = compile_source(paper('Invented methods.',
            'In the wild-type KRAS stratum, OS for panitumumab-FOLFOX4 compared with FOLFOX4 '
            'was statistically significant (P = .02).'))
        result = compare_claim(survival_claim('statistically significant'), dossier)
        self.assertEqual(result['status'], 'review_unresolved')
        self.assertEqual(result['matched_record_ids'], [])
        self.assert_review_only(result)

    def test_explicit_allele_and_gene_differences_cannot_be_opposing_reports(self):
        dossier = survival_source('KRAS G12C')
        self.assertEqual(compare_claim(survival_claim(molecular='KRAS p.G12C'), dossier)['status'], 'limited_context_compatible')
        for molecular in ('KRAS G12D', 'wild-type KRAS', 'NRAS G12C'):
            with self.subTest(molecular=molecular):
                result = compare_claim(survival_claim('statistically significant', molecular), dossier)
                self.assertEqual(result['status'], 'review_context_difference')
                self.assertFalse(any(f['conflict_kind'] == 'opposing_report'
                                     for c in result['candidates'] for f in c['facets']))
                self.assert_review_only(result)

    def test_unspecified_mutants_do_not_establish_allele_specific_results(self):
        generic = survival_source('mutant KRAS')
        self.assertEqual(compare_claim(survival_claim(molecular='KRAS G12D'), generic)['status'], 'review_unresolved')
        specific = survival_source('KRAS G12C')
        self.assertEqual(compare_claim(survival_claim(molecular='mutant KRAS'), specific)['status'], 'review_unresolved')

    def test_same_scope_disagreement_remains_unresolved(self):
        dossier = survival_source(extra=' An increase in OS with panitumumab-FOLFOX4 compared with FOLFOX4 '
                                       'was statistically significant (P = .01).')
        result = compare_claim(survival_claim(), dossier)
        self.assertTrue(result['matched_record_ids'])
        self.assertTrue(result['source_record_disagreement'])
        self.assertEqual(result['status'], 'review_unresolved')
        self.assert_review_only(result)

    def test_absent_records_unsupported_claims_and_synonyms_remain_unknown(self):
        empty = compile_source(paper('Invented design only.', 'No supported source-pattern facts.'))
        for claim, dossier in ((response_claim(), empty),
                ('Patients with no prior chemotherapy had improved outcomes.', survival_source()),
                ('Cetuximab had activity in previously untreated cancer.', response_source())):
            with self.subTest(claim=claim):
                result = compare_claim(claim, dossier)
                self.assertEqual(result['status'], 'review_unresolved')
                self.assertEqual(result['matched_record_ids'], [])
                self.assert_review_only(result)

    def test_source_replay_rejects_value_swaps_even_for_unsupported_claims(self):
        dossier = response_source()
        for unsupported in (False, True):
            altered = deepcopy(dossier)
            altered['records'][0]['value'] = altered['records'][1]['value']
            altered['records'][0]['provenance']['value'] = deepcopy(altered['records'][1]['provenance']['value'])
            with self.subTest(unsupported=unsupported), self.assertRaises(ValueError):
                compare_claim('Unsupported narrative.' if unsupported else response_claim(), altered)


if __name__ == '__main__':
    unittest.main()

"""Source-context presentation must preserve the evidence contract; invented data."""
from copy import deepcopy
import csv
from pathlib import Path
import tempfile
import unittest

from biograph_steward.civic_context import record_context, answer_display_coverage
from biograph_steward.client import digest
from biograph_steward.civic_questions import answer_civic_question
from biograph_steward.graph import build_graph
from biograph_steward.questions import answer_html, answer_text, save_answer, verify_answer
from biograph_steward.planning import execute_plan
from test_civic import CivicAPI, fixture
from test_planning import civic_plan


class CivicContextTests(unittest.TestCase):
    def mixed_graph(self):
        api=CivicAPI();api.rows=api.rows[:2]
        api.rows[1].update(significance='RESISTANCE',evidenceLevel='B')
        api.rows[1]['source']=deepcopy(api.rows[0]['source'])
        api.rows[0]['description']='INVENTED cell experiment; not a clinical result.'
        api.rows[1]['description']='INVENTED retrospective cohort; drug + chemotherapy and monotherapy were mixed.'
        p,c=fixture(api)
        return build_graph(p,civic_snapshot=c)

    def test_mixed_levels_stay_attached_to_their_records_and_shared_source_is_visible(self):
        graph=self.mixed_graph();answer=answer_civic_question(graph,view='candidates')
        self.assertEqual(len(answer['citations']),1)
        context=answer['citations'][0]['study_context'];records=context['records']
        self.assertEqual([(r['evidence_id'],r['evidence_level_label']) for r in records],
                         [('CIViC.evidence:100','Preclinical evidence'),('CIViC.evidence:101','Clinical evidence')])
        self.assertEqual(context['overview']['displayed_records'],2);self.assertEqual(context['overview']['cited_sources'],1)
        self.assertEqual(context['overview']['shared_references'][0]['evidence_ids'],['CIViC.evidence:100','CIViC.evidence:101'])
        self.assertIn('monotherapy is not established',answer['summary'][0]['context_text'])

    def test_display_does_not_rewrite_graph_claims_regimens_or_review_states(self):
        graph=self.mixed_graph();before=deepcopy(graph)
        answer=answer_civic_question(graph,view='candidates');record=answer['citations'][0]['study_context']['records'][1]
        self.assertEqual(record['description'],'INVENTED retrospective cohort; drug + chemotherapy and monotherapy were mixed.')
        self.assertEqual(len(record['therapy_members']),1)
        self.assertIsNone(record['therapy_interaction']);self.assertNotIn('study_design',record)
        self.assertEqual(record['paper_check'],'not_recorded_in_context_display')
        self.assertEqual(graph,before);self.assertFalse(answer_civic_question(graph)['results'])
        planned=execute_plan(civic_plan(),graph)['answer']
        self.assertEqual(planned['citations'][0]['study_context'],answer['citations'][0]['study_context'])

    def test_complete_therapy_sets_keep_substitutes_combination_and_unspecified_sequence_order(self):
        for interaction,phrase in [('COMBINATION','does not isolate a single-drug effect'),
                                   ('SUBSTITUTES','does not resolve individual exposure'),
                                   ('SEQUENTIAL','order is not supplied')]:
            api=CivicAPI();api.rows=[api.rows[-1]];api.rows[0]['therapyInteractionType']=interaction
            p,c=fixture(api);a=answer_civic_question(build_graph(p,civic_snapshot=c),view='candidates')
            r=a['citations'][0]['study_context']['records'][0]
            self.assertEqual(len(r['therapy_members']),2);self.assertEqual(r['therapy_interaction'],interaction)
            self.assertIn(phrase,r['therapy_scope_note'])

    def test_unknown_level_or_non_pubmed_source_does_not_invent_category_or_link(self):
        p,c=fixture();graph=build_graph(p,civic_snapshot=c)
        edge=deepcopy(next(e for e in graph['edges'] if e['record_kind']=='variant_therapy_response'))
        edge['evidence_record']['evidenceLevel']='UNRECOGNIZED'
        edge['evidence_record']['source'].update(sourceType='ASCO',citationId='12345')
        r=record_context(edge)
        self.assertEqual(r['evidence_level_label'],'Unmapped source level');self.assertIsNone(r['publication_url'])
        self.assertTrue(r['source_reference'].startswith('CIViC.source:'))

    def test_text_html_and_tsv_exports_keep_full_descriptions_and_record_locators(self):
        graph=self.mixed_graph();a=answer_civic_question(graph,view='candidates');verify_answer(a)
        text=answer_text(a);html=answer_html(a)
        self.assertIn('Preclinical evidence',text);self.assertIn('Clinical evidence',text)
        self.assertIn('drug + chemotherapy and monotherapy were mixed',text)
        self.assertIn('is shared by CIViC.evidence:100, CIViC.evidence:101',html)
        with tempfile.TemporaryDirectory() as directory:
            save_answer(a,Path(directory))
            with (Path(directory)/'evidence_context.tsv').open(newline='') as f:rows=list(csv.DictReader(f,delimiter='\t'))
        self.assertEqual(len(rows),2)
        source_records={'CIViC.evidence:'+str(e['evidence_record']['id']):e['evidence_record'] for e in a['citations'][0]['evidence_records']}
        self.assertEqual(rows[1]['description'],source_records[rows[1]['evidence_id']]['description'])
        self.assertIn('civic_snapshot.json#/items/',rows[0]['record_locators'])
        self.assertEqual(rows[0]['snapshot_sha256'],graph['civic_snapshot_sha256'])

    def test_source_text_is_escaped_in_html_and_empty_accepted_view_remains_empty(self):
        api=CivicAPI();api.rows=api.rows[:1]
        api.rows[0]['description']='<script>alert("invented")</script>'
        api.rows[0]['source']['title']='<img src=x onerror=alert("invented")>'
        p,c=fixture(api);graph=build_graph(p,civic_snapshot=c)
        html=answer_html(answer_civic_question(graph,view='candidates'))
        self.assertNotIn('<script>',html);self.assertNotIn('<img ',html)
        self.assertIn('&lt;script&gt;',html)
        empty=answer_civic_question(graph)
        self.assertFalse(empty['summary']);self.assertFalse(empty['citations'])
        self.assertEqual(empty['source_context_overview']['displayed_records'],0)

    def test_caps_disclose_both_hidden_profiles_and_assertions_before_the_exported_claims(self):
        api=CivicAPI();extra=api.row(104,'RESISTANCE')
        extra['molecularProfile'].update(id=82,name='ZZZ INVENTED profile',rawName='#VID82')
        extra['molecularProfile']['variants'][0].update(id=82,name='ZZZ INVENTED variant')
        api.rows.append(extra)
        p,c=fixture(api);graph=build_graph(p,civic_snapshot=c);before=deepcopy(graph)
        answer=answer_civic_question(graph,view='candidates',max_results=1,max_paths=1)
        coverage=answer['display_coverage']
        self.assertEqual((coverage['shown_assertions'],coverage['eligible_assertions'],coverage['omitted_assertions']),(1,5,4))
        self.assertEqual((coverage['shown_profiles'],coverage['matching_profiles'],coverage['omitted_profiles']),(1,2,1))
        self.assertEqual((coverage['profiles'][0]['shown'],coverage['profiles'][0]['eligible'],coverage['profiles'][0]['omitted']),(1,4,3))
        self.assertEqual(coverage['discordant_groups'],1)
        for output in (answer_text(answer),answer_html(answer)):
            self.assertIn('1 of 5 eligible response assertions shown',output)
            self.assertIn('1 matching molecular profiles omitted',output)
            self.assertIn('3 omitted by the per-profile display limit',output)
            self.assertIn('not adjudicated contradictions',output)
            self.assertIn('relevant assertions may be outside the display limits',output)
            self.assertLess(output.index('1 of 5 eligible response assertions shown'),output.index('CIViC does not support'))
        self.assertEqual(graph,before)
        verify_answer(answer)

    def test_display_coverage_uses_selected_therapy_and_review_view_not_whole_graph(self):
        p,c=fixture();graph=build_graph(p,civic_snapshot=c)
        pan=answer_civic_question(graph,view='candidates',therapy='panitumumab')
        self.assertEqual(pan['display_coverage']['eligible_assertions'],1)
        self.assertEqual(pan['display_coverage']['discordant_groups'],0)
        self.assertNotIn('Differing annotations:',answer_text(pan))
        accepted=answer_civic_question(graph,view='accepted')
        self.assertEqual(accepted['display_coverage']['eligible_assertions'],0)
        for output in (answer_text(accepted),answer_html(accepted)):
            self.assertIn('4 structurally inspectable candidate/accepted assertions match this question before the local-review filter',output)
            self.assertIn('does not establish absence of candidate evidence or biological absence',output)
        self.assertFalse(accepted['results']);self.assertFalse(accepted['citations'])
        self.assertEqual(accepted['display_coverage']['discordant_groups'],0)

    def test_old_saved_answer_gets_equivalent_coverage_without_changing_saved_content(self):
        p,c=fixture();answer=answer_civic_question(build_graph(p,civic_snapshot=c),view='candidates',max_paths=1)
        old=deepcopy(answer);old.pop('display_coverage');old.pop('answer_sha256');old['answer_sha256']=digest(old)
        before=deepcopy(old)
        self.assertEqual(answer_display_coverage(old),answer['display_coverage'])
        for render in (answer_text,answer_html):
            output=render(old)
            self.assertIn('1 of 4 eligible response assertions shown',output)
            self.assertIn('3 omitted by the per-profile display limit',output)
        self.assertEqual(old,before);verify_answer(old)

    def test_profile_names_are_escaped_in_coverage_html(self):
        api=CivicAPI()
        for r in api.rows:r['molecularProfile']['name']='INVENTED <img src=x onerror=alert(1)>'
        p,c=fixture(api);answer=answer_civic_question(build_graph(p,civic_snapshot=c),view='candidates',max_paths=1)
        html=answer_html(answer)
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;',html)
        self.assertNotIn('<img ',html)

if __name__=='__main__':unittest.main()

"""Invented PubMed XML checks context provenance, not biological accuracy."""
from hashlib import sha256
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from biograph_steward.client import digest
from tools.grounding_claims import context


def xml(pmids, *, abstract=True, title=True):
    articles = []
    for pmid in pmids:
        articles.append('<PubmedArticle><MedlineCitation><PMID>' + pmid + '</PMID><Article>'
                        + ('<ArticleTitle>Invented <i>title</i> ' + pmid + '</ArticleTitle>' if title else '')
                        + ('<Abstract><AbstractText Label="METHODS">Invented abstract ' + pmid
                           + '.</AbstractText><CopyrightInformation>Invented copyright notice</CopyrightInformation></Abstract>' if abstract else '')
                        + '</Article></MedlineCitation><PubmedData><ArticleIdList>'
                        '<ArticleId IdType="pmc">PMC999</ArticleId></ArticleIdList></PubmedData></PubmedArticle>')
    return ('<PubmedArticleSet>' + ''.join(articles) + '</PubmedArticleSet>').encode()


def reseal(path):
    p = path / 'manifest.json'; manifest = json.loads(p.read_text())
    manifest['files'] = {f.name: sha256(f.read_bytes()).hexdigest() for f in path.iterdir() if f.name != 'manifest.json'}
    manifest.pop('content_sha256', None);manifest['content_sha256'] = digest(manifest)
    p.write_text(json.dumps(manifest))
    return manifest


class GroundingContextTests(unittest.TestCase):
    def test_existing_parser_source_identity_and_join_are_replayed(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'capture';calls=[]
            def fetch(url):
                calls.append(url);return xml(['1','2'])
            manifest=context.capture_context(['2','1'],out,transport=fetch,pace=0)
            papers=context.load_context(out)
            self.assertEqual(list(papers),['1','2'])
            self.assertEqual(calls,[context.literature.PUBMED+'1,2'])
            self.assertEqual(papers['1']['context_text'],'Invented title 1\n\nInvented abstract 1.')
            self.assertEqual(papers['1']['context_sha256'],sha256(papers['1']['context_text'].encode()).hexdigest())
            self.assertEqual(papers['1']['copyright'],'Invented copyright notice')
            self.assertIn('AbstractText[1]',papers['1']['locators']['abstract'][0])
            self.assertEqual(manifest['available_contexts'],2)
            self.assertEqual(manifest['transport'],'injected_transport')
            self.assertIn('not oracle full text',manifest['policy'])

    def test_missing_identity_and_title_only_remain_unavailable_without_PMC_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'capture';calls=[]
            def fetch(url):
                calls.append(url);return xml(['1'],abstract=False)
            context.capture_context(['1','2'],out,transport=fetch,pace=0)
            papers=context.load_context(out)
            self.assertEqual(papers['1']['reasons'],['abstract_unavailable'])
            self.assertEqual(papers['2']['reasons'],['pubmed_identity_missing'])
            self.assertTrue(all(p['context_text'] is None for p in papers.values()))
            self.assertEqual(len(calls),1)

    def test_abstract_without_title_is_not_available_context(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'capture'
            context.capture_context(['1'],out,transport=lambda _:xml(['1'],title=False),pace=0)
            self.assertEqual(context.load_context(out)['1']['reasons'],['title_unavailable'])

    def test_HTTP_failure_has_bound_receipt_and_unavailable_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'capture'
            def fail(url):
                raise HTTPError(url,503,'Unavailable',None,io.BytesIO(b'failure'))
            manifest=context.capture_context(['1'],out,transport=fail,pace=0)
            request=manifest['requests'][0]
            self.assertEqual(request['http_status'],503)
            self.assertTrue((out/request['error_file']).is_file())
            paper=context.load_context(out)['1']
            self.assertIsNone(paper['context_text'])
            self.assertEqual(paper['reasons'],['transport_unavailable'])

    def test_batches_never_exceed_thirty_and_all_PMIDs_remain(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'capture';sizes=[]
            def fetch(url):
                ids=url.removeprefix(context.literature.PUBMED).split(',');sizes.append(len(ids));return xml(ids)
            context.capture_context([str(i) for i in range(1,32)],out,transport=fetch,pace=0)
            self.assertEqual(sizes,[30,1])
            self.assertEqual(len(context.load_context(out)),31)

    def test_bad_input_does_not_create_output_or_request_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            for i,pmids in enumerate([[],['1','1'],['01'],[1],['0'],'123',[str(i) for i in range(1,6002)]]):
                out=Path(temp)/str(i)
                with self.assertRaises(ValueError):context.capture_context(pmids,out,transport=lambda _:self.fail('transport called'),pace=0)
                self.assertFalse(out.exists())

    def test_invalid_XML_duplicate_or_unrequested_identity_rejects_and_preserves_raw(self):
        responses=[b'<broken>',xml(['1','1']),xml(['2'])]
        with tempfile.TemporaryDirectory() as temp:
            for i,raw in enumerate(responses):
                out=Path(temp)/str(i)
                with self.assertRaisesRegex(ValueError,'rejected'):
                    context.capture_context(['1'],out,transport=lambda _,raw=raw:raw,pace=0)
                self.assertEqual((out/'pubmed_batch_0001.xml').read_bytes(),raw)
                self.assertTrue((out/'capture_rejected.json').is_file())
                self.assertFalse((out/'manifest.json').exists())

    def test_raw_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'capture'
            context.capture_context(['1'],out,transport=lambda _:xml(['1']),pace=0)
            (out/'pubmed_batch_0001.xml').write_bytes(xml(['1'],title=False))
            with self.assertRaisesRegex(ValueError,'bytes'):context.load_context(out)

    def test_resealed_context_tampering_still_fails_native_semantic_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'capture'
            context.capture_context(['1'],out,transport=lambda _:xml(['1']),pace=0)
            p=out/'contexts.json';rows=json.loads(p.read_text());rows[0]['context_text']='Invented replacement'
            p.write_text(json.dumps(rows));manifest=reseal(out)
            manifest['contexts_sha256']=digest(rows);manifest.pop('content_sha256');manifest['content_sha256']=digest(manifest)
            (out/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'native source replay'):context.load_context(out)

    def test_source_context_metadata_tampering_and_code_pin_changes_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'capture'
            context.capture_context(['1'],out,transport=lambda _:xml(['1']),pace=0)
            p=out/'manifest.json';manifest=json.loads(p.read_text());manifest['code']['native_parser_module_sha256']='0'*64
            manifest.pop('content_sha256');manifest['content_sha256']=digest(manifest);p.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'code'):context.load_context(out)

    def test_resealed_boolean_count_or_changed_policy_is_not_valid_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            for index,(field,value) in enumerate([('requests_attempted',True),('context_join','Different context'),('license_note','Unqualified permission')]):
                out=Path(temp)/str(index)
                context.capture_context(['1'],out,transport=lambda _:xml(['1']),pace=0)
                p=out/'manifest.json';manifest=json.loads(p.read_text());manifest[field]=value
                manifest.pop('content_sha256');manifest['content_sha256']=digest(manifest);p.write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):context.load_context(out)

    def test_overwrite_and_symlink_sources_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'capture'
            context.capture_context(['1'],out,transport=lambda _:xml(['1']),pace=0)
            with self.assertRaisesRegex(ValueError,'new immutable'):
                context.capture_context(['1'],out,transport=lambda _:self.fail('transport called'),pace=0)
            raw=out/'pubmed_batch_0001.xml';external=Path(temp)/'copy.xml';external.write_bytes(raw.read_bytes());raw.unlink();raw.symlink_to(external)
            with self.assertRaisesRegex(ValueError,'ordinary'):context.load_context(out)

    def test_total_budget_reserve_stops_requests_and_preserves_missing_contexts(self):
        with tempfile.TemporaryDirectory() as temp,patch.multiple(context,MAX_FETCH_BYTES=20_000,MAX_TOTAL_BYTES=25_000):
            out=Path(temp)/'capture';calls=[]
            def fetch(url):
                calls.append(url);return xml(url.removeprefix(context.literature.PUBMED).split(','))
            manifest=context.capture_context([str(i) for i in range(1,32)],out,transport=fetch,pace=0)
            papers=context.load_context(out)
            self.assertEqual(len(calls),1)
            self.assertEqual(manifest['requests_attempted'],1)
            self.assertEqual(papers['31']['reasons'],['remaining_total_budget_below_fetch_bound'])


if __name__=='__main__':unittest.main()

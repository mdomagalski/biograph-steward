"""Read immutable historical function-context publications with standard libraries.

This consumer verifies saved hashes, identities and contribution arithmetic.
It neither reruns the scientific producer nor establishes curator truth.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re

FORMAT='biograph-steward.exact-onehop-LocalPlus-publication.v1'

QUERY='biograph-steward.exact-onehop-LocalPlus-query.v1'

MAX_MANIFEST_BYTES=1048576
MAX_QUERY_BYTES=8*1048576
MAX_PUBLICATION_BYTES=64*1048576

def need(ok,message):
    if not ok:raise ValueError('Historical query publication: '+message)

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for b in iter(lambda:stream.read(1048576),b''):h.update(b)
    return h.hexdigest()

def validate_query(value,publication_id):
    need(isinstance(value,dict),'query response must be an object.')
    need(value.get('format')==QUERY and value.get('publication_id')==publication_id,'query format or publication differs.')
    q=value.get('query',{});need(isinstance(q,dict) and isinstance(q.get('id'),str)
        and re.fullmatch(r'UniProtKB:[A-Z0-9]{6}(?:[A-Z0-9]{4})?',q['id']),'exact source protein ID required.')
    need(value.get('uncalibrated_score') is True and value.get('knowledge_level')=='prediction'
         and value.get('curated_acceptance') is False,'prediction/acceptance boundary differs.')
    degree=value.get('weighted_degree');need(type(degree) in (int,float) and math.isfinite(degree) and degree>=0,'invalid degree.')
    candidates=value.get('candidates');need(isinstance(candidates,list) and len(candidates)<=9,'at most top3/aspect display candidates required.')
    seen=set();aspects=Counter()
    for row in candidates:
        need(isinstance(row,dict),'candidate must be an object.')
        term=row.get('GO_ID');aspect=row.get('aspect');need(isinstance(term,str) and re.fullmatch(r'GO:[0-9]{7}',term)
            and isinstance(aspect,str) and aspect in {'BPO','MFO','CCO'},'invalid GO identity/aspect.')
        need((aspect,term) not in seen and row.get('known_in_training_snapshot') is False,'duplicate or known-training display candidate.')
        seen.add((aspect,term));aspects[aspect]+=1
        score=row.get('score');need(type(score) in (int,float) and math.isfinite(score) and 0<score<=1+1e-10,'invalid model ranking score.')
        contributors=row.get('contributors');need(isinstance(contributors,list) and contributors and row.get('complete_contributions') is True,'complete contributor list required.')
        neighbors=set()
        for c in contributors:
            need(isinstance(c,dict),'contributor must be an object.')
            p=c.get('protein','');w=c.get('raw_STRING_weight');part=c.get('normalized_contribution')
            need(isinstance(p,str) and re.fullmatch(r'UniProtKB:[A-Z0-9]{6}(?:[A-Z0-9]{4})?',p) and p not in neighbors,'invalid or duplicate contributor.')
            neighbors.add(p)
            need(type(w) in (int,float) and math.isfinite(w) and 0<w<=1
                 and type(part) in (int,float) and math.isfinite(part) and 0<part<=1+1e-10,'invalid contribution.')
            need(c.get('known_t0_term_row')==[p.split(':',1)[1],term,aspect],'contributing seed triple differs.')
            pair=c.get('source_pair',{});need(isinstance(pair,dict)
                 and isinstance(pair.get('subject'),str) and isinstance(pair.get('object'),str)
                 and {pair['subject'],pair['object']}=={q['id'],p}
                 and type(pair.get('weight')) in (str,int,float)
                 and re.fullmatch(r'pharos319ppi:[0-9]+:[0-9]+',str(pair.get('pair_id',''))),'source pair differs.')
            try:source_weight=float(pair['weight'])
            except (ValueError,OverflowError) as exc:raise ValueError('Historical query publication: invalid source weight.') from exc
            need(source_weight==w,'source pair weight differs.')
            need(degree>0 and abs(part-w/degree)<=1e-12,'normalized source weight differs.')
            ids=c.get('native_STRING_pair');need(isinstance(ids,list) and len(ids)==2
                 and all(isinstance(s,str) and re.fullmatch(r'9606\.ENSP[0-9]+',s) for s in ids),'native human STRING pair required.')
        need(degree>0 and abs(math.fsum(c['normalized_contribution'] for c in contributors)-score)<=1e-12,'contribution arithmetic differs.')
    need(all(n<=3 for n in aspects.values()),'display exceeds top3 per aspect.')
    if degree==0:need(not candidates and value.get('state')=='no_qualified_neighbor_context','isolated source node must abstain.')
    return value

def load_publication(folder,expected_sha256=None):
    """Validate saved files and arithmetic; do not claim to rerun PyG/science."""
    folder=Path(folder).absolute();path=folder/'publication.json'
    need(folder.is_dir() and not folder.is_symlink() and path.is_file() and not path.is_symlink(),'ordinary publication folder required.')
    need(path.stat().st_size<=MAX_MANIFEST_BYTES,'publication manifest exceeds the bounded reader.')
    need(expected_sha256 is None or isinstance(expected_sha256,str) and re.fullmatch(r'[a-f0-9]{64}',expected_sha256),'invalid explicit publication SHA.')
    need(expected_sha256 is None or sha(path)==expected_sha256,'explicit publication SHA differs.')
    m=json.loads(path.read_text());need(isinstance(m,dict) and m.get('format')==FORMAT and m.get('content_sha256')==digest({k:v for k,v in m.items() if k!='content_sha256'}),'manifest format/seal differs.')
    need(m.get('source_graph_modified') is False and m.get('future_reference_labels_included') is False,'source/holdout boundary differs.')
    need(isinstance(m.get('files'),dict) and 1<=len(m['files'])<=128
         and isinstance(m.get('query_files'),dict) and 1<=len(m['query_files'])<=25,'bounded source/query inventory required.')
    need(isinstance(m.get('downloads',{}),dict) and all(isinstance(key,str) and isinstance(name,str)
         and name in m['files'] for key,name in m.get('downloads',{}).items()),'invalid declared downloads.')
    need(all(isinstance(name,str) for name in m['query_files'].values()),'invalid query file inventory.')
    query_names=set(m['query_files'].values());total_bytes=0;root=folder.resolve(strict=True)
    for name,record in m['files'].items():
        need(isinstance(name,str) and isinstance(record,dict) and type(record.get('bytes')) is int
             and 0<=record['bytes']<=MAX_PUBLICATION_BYTES
             and isinstance(record.get('sha256'),str) and re.fullmatch(r'[a-f0-9]{64}',record['sha256']),'invalid file size/hash declaration.')
        rel=Path(name);p=folder/rel
        need(not rel.is_absolute() and '..' not in rel.parts and '\\' not in name and p.is_file() and not p.is_symlink(),'invalid saved file path.')
        need(p.resolve(strict=True).is_relative_to(root),'saved file escapes the publication folder.')
        parent=p.parent
        while parent!=folder:
            need(parent.is_dir() and not parent.is_symlink(),'saved file has a nonordinary parent directory.')
            parent=parent.parent
        if name in query_names:need(record['bytes']<=MAX_QUERY_BYTES,'query response exceeds the bounded reader.')
        total_bytes+=record['bytes'];need(total_bytes<=MAX_PUBLICATION_BYTES,'publication exceeds the bounded reader.')
        need(p.stat().st_size==record['bytes'] and sha(p)==record['sha256'],'saved file differs: '+name)
    queries={}
    for protein,name in m['query_files'].items():
        need(name in m['files'],'query file is outside declared inventory.')
        q=validate_query(json.loads((folder/name).read_text()),m['publication_id'])
        need(q['query']['id']==protein,'manifest query identity differs.');queries[protein]=q
    return m,queries


def publication_summary(manifest,queries):
    """Return a compact public catalogue without operator filesystem paths."""
    return {'format':manifest['format'],'publication_id':manifest['publication_id'],
        'purpose':manifest.get('purpose'),'source_versions':deepcopy(manifest.get('source_versions',{})),
        'query_count':len(queries),'proteins':[{'id':p,'symbol':q['query'].get('symbol'),
            'display_label':q['query'].get('display_label',p),'state':q['state'],
            'candidate_count':len(q['candidates'])} for p,q in sorted(queries.items())],
        'downloads':deepcopy(manifest.get('downloads',{})),'limitations':deepcopy(manifest.get('limitations',[])),
        'scientific_accuracy_claimed':manifest.get('scientific_accuracy_claimed',False),
        'uncalibrated_score':True,'source_graph_modified':False}


def list_publications(sources):
    """Read configured {id,path,sha256} sources; never discover arbitrary files."""
    need(isinstance(sources,list),'explicit configured publication sources required.')
    result=[];seen=set()
    for source in sources:
        need(isinstance(source,dict) and set(source)=={'id','path','sha256'}
             and isinstance(source['id'],str) and re.fullmatch(r'[A-Za-z0-9_-]{1,100}',source['id'])
             and isinstance(source['sha256'],str) and re.fullmatch(r'[a-f0-9]{64}',source['sha256'])
             and source['id'] not in seen,'invalid or duplicate configured source.')
        seen.add(source['id']);manifest,queries=load_publication(source['path'],source['sha256'])
        result.append({'id':source['id'],**publication_summary(manifest,queries)})
    return result


def get_query(manifest,queries,protein):
    """Return one saved response; prefix wrapping does not resolve any alias."""
    need(isinstance(protein,str),'an exact source protein identifier is required.')
    protein=protein if protein.startswith('UniProtKB:') else 'UniProtKB:'+protein
    need(protein in queries,'protein is outside this declared historical query example.')
    return deepcopy(validate_query(queries[protein],manifest['publication_id']))


def download_path(folder,name,expected_sha256=None):
    """Resolve a declared logical download only, after immutable-file checks."""
    manifest,_=load_publication(folder,expected_sha256)
    downloads=manifest.get('downloads',{})
    need(isinstance(name,str) and name in downloads,'download is not declared by this publication.')
    relative=downloads[name]
    need(relative in manifest['files'],'declared download is outside the source inventory.')
    return Path(folder).absolute()/relative


def load_display_notes(path,expected_sha256,manifest,queries,*,manifest_file_sha256):
    """Verify a separate annotation-overlap diagnostic, never a new forecast.

    Exact historical query/term/aspect/score alignment is required. Later native
    annotations retain their relations and product context; they are not truth
    labels and never replace or filter the saved ranking.
    """
    path=Path(path).absolute()
    need(path.is_file() and not path.is_symlink() and path.stat().st_size<=4*1048576,
         'display notes must be an ordinary bounded file.')
    for value in (expected_sha256,manifest_file_sha256):
        need(isinstance(value,str) and re.fullmatch(r'[a-f0-9]{64}',value),'explicit notes/manifest SHA required.')
    raw=path.read_bytes();need(hashlib.sha256(raw).hexdigest()==expected_sha256,'display notes file SHA differs.')
    report=json.loads(raw)
    need(isinstance(report,dict) and report.get('format')=='biograph-steward.historical-display-annotation-overlap.v1'
         and report.get('content_sha256')==digest({k:v for k,v in report.items() if k!='content_sha256'}),
         'display notes format/content seal differs.')
    need(report.get('publication_manifest_sha256')==manifest_file_sha256
         and report.get('publication_content_sha256')==manifest.get('content_sha256'),
         'display notes belong to another historical publication.')
    need(all(report.get(key) is False for key in ('scientific_accuracy_claimed','forecast_modified','future_reference_labels_read'))
         and isinstance(report.get('author_parser'),dict)
         and report['author_parser'].get('future_labels_read') is False,'display notes scientific boundary differs.')
    need(isinstance(report.get('original_report'),dict)
         and all(isinstance(report['original_report'].get(key),str)
                 and re.fullmatch(r'[a-f0-9]{64}',report['original_report'][key]) for key in ('sha256','content_sha256')),
         'the preserved original audit pin is missing.')
    inputs=report.get('inputs')
    need(isinstance(inputs,dict) and set(inputs)=={'baseline_archive','historical_ontology','known_t0','current_gaf','current_ontology'},
         'display notes source inventory differs.')
    for record in inputs.values():
        need(isinstance(record,dict) and set(record)=={'bytes','sha256'} and type(record['bytes']) is int
             and record['bytes']>0 and isinstance(record['sha256'],str) and re.fullmatch(r'[a-f0-9]{64}',record['sha256']),
             'invalid or unsanitized source pin.')
    need(inputs['historical_ontology']['sha256']==manifest.get('input_source_pins',{}).get('ontology',{}).get('sha256'),
         'historical ontology source differs.')
    need(isinstance(report.get('native_gaf'),dict),'native annotation metadata missing.')
    headers=report['native_gaf'].get('headers')
    need(isinstance(headers,list) and all(isinstance(h,str) for h in headers)
         and headers and headers[0]=='!gaf-version: 2.2'
         and report['native_gaf'].get('gaf_sha256')==inputs['current_gaf']['sha256'],
         'native annotation source binding differs.')
    dates=[h.removeprefix('!date-generated:').strip() for h in headers if h.startswith('!date-generated:')]
    gaf_go=[h.removeprefix('!go-version:').strip() for h in headers if h.startswith('!go-version:')]
    ontology=report.get('matching_current_ontology')
    need(isinstance(ontology,dict) and ontology.get('file_sha256')==inputs['current_ontology']['sha256']
         and isinstance(ontology.get('ontology_version'),str),'native ontology source binding differs.')
    release=re.fullmatch(r'http://purl.obolibrary.org/obo/go/releases/([0-9]{4}-[0-9]{2}-[0-9]{2})/go.owl',ontology['ontology_version'])
    need(release and len(dates)==1 and len(gaf_go)==1
         and gaf_go[0]=='http://purl.obolibrary.org/obo/go/releases/'+release[1]+'/extensions/go-plus.ofn',
         'native annotations and ontology releases differ.')
    hierarchy=report.get('current_hierarchy')
    predicates={'is_a','http://purl.obolibrary.org/obo/BFO_0000050'}
    need(isinstance(hierarchy,dict) and hierarchy.get('library')=='networkx'
         and hierarchy.get('admitted_predicates')==sorted(predicates),'display hierarchy policy differs.')
    expected={(p,c['GO_ID'],c['aspect']):c for p,q in queries.items() for c in q['candidates']}
    rows=report.get('rows');need(isinstance(rows,list) and len(rows)==len(expected),'complete display-candidate audit required.')
    seen=set();by_query={p:[] for p in queries}
    go=lambda value:isinstance(value,str) and re.fullmatch(r'GO:[0-9]{7}',value)
    native_id=lambda value:isinstance(value,str) and re.fullmatch(r'goa\.native:[a-f0-9]{24}',value)
    for row in rows:
        need(isinstance(row,dict) and set(row)=={'query','GO_ID','aspect','label','published_score',
             'known_t0_literal','known_t0_author_closure','pre_t0_all_evidence','july2026_goa'}
             and all(isinstance(row.get(k),str) for k in ('query','GO_ID','aspect')),'invalid display note identity.')
        key=row['query'],row['GO_ID'],row['aspect']
        need(key in expected and key not in seen and type(row.get('published_score')) in (int,float)
             and row['published_score']==expected[key]['score']
             and row.get('label')==expected[key].get('label'),'display note identity/ranking differs.')
        seen.add(key)
        need(row.get('known_t0_literal') is False and row.get('known_t0_author_closure') is False,
             'display note contradicts the historical training mask.')
        prior=row.get('pre_t0_all_evidence')
        need(isinstance(prior,dict) and set(prior)=={'released_target_rows','literal_source_row','author_admitted','status'}
             and type(prior.get('released_target_rows')) is int and prior['released_target_rows']>=0
             and type(prior.get('literal_source_row')) is bool and type(prior.get('author_admitted')) is bool,
             'invalid pre-cutoff source coverage.')
        status=('literal_released_row' if prior['literal_source_row'] else 'author_admitted_ancestor_or_alias'
                if prior['author_admitted'] else 'not_in_released_target_annotations' if prior['released_target_rows']
                else 'outside_released_baseline_target_scope')
        need(prior.get('status')==status and (not prior['literal_source_row'] or prior['author_admitted'])
             and (not prior['author_admitted'] or prior['released_target_rows']>0),'pre-cutoff overlap flags differ.')
        current=row.get('july2026_goa')
        need(isinstance(current,dict) and set(current)=={'term_in_matching_ontology','term_deprecated',
             'positive_matches','exact_NOT_record_ids','absence_is_biological_negative'}
             and current.get('absence_is_biological_negative') is False
             and type(current.get('term_in_matching_ontology')) is bool and type(current.get('term_deprecated')) is bool
             and (not current['term_deprecated'] or current['term_in_matching_ontology'])
             and isinstance(current.get('positive_matches'),list) and len(current['positive_matches'])<=10000
             and isinstance(current.get('exact_NOT_record_ids'),list)
             and all(native_id(v) for v in current['exact_NOT_record_ids'])
             and len(set(current['exact_NOT_record_ids']))==len(current['exact_NOT_record_ids'])
             and (not current['positive_matches'] or current['term_in_matching_ontology'] and not current['term_deprecated']),
             'native current source flags differ.')
        matched=set()
        for match in current['positive_matches']:
            need(isinstance(match,dict) and set(match)=={'native_record_id','source_line','membership','source_term',
                 'source_relation','evidence','references','product_form','extension','with_from','taxa',
                 'product_form_equals_query_identifier','context_or_form_specific','ontology_path','path_predicates'} and native_id(match.get('native_record_id'))
                 and match['native_record_id'] not in matched and type(match.get('source_line')) is int
                 and match['source_line']>0 and go(match.get('source_term')),'invalid native matching record.')
            matched.add(match['native_record_id'])
            need(match.get('membership') in ('literal_term','admitted_ancestor')
                 and (match['membership']=='literal_term')==(match['source_term']==row['GO_ID']),
                 'literal/ancestor source membership differs.')
            need(isinstance(match.get('source_relation'),str) and re.fullmatch(r'[a-z][a-z_]*',match['source_relation'])
                 and match['source_relation']!='NOT' and isinstance(match.get('evidence'),str)
                 and re.fullmatch(r'[A-Z]{2,3}',match['evidence'])
                 and isinstance(match.get('extension'),str)
                 and (match.get('product_form') is None or isinstance(match['product_form'],str)),
                 'native polarity/relation/product context differs.')
            form=match['product_form'];same_identifier=form==row['query'] if form else None
            need(match.get('product_form_equals_query_identifier') is same_identifier
                 and match.get('context_or_form_specific') is bool(match['extension'] or form and same_identifier is False),
                 'native literal product identity/context differs.')
            for field in ('references','with_from','taxa'):
                need(isinstance(match.get(field),list) and all(isinstance(v,str) for v in match[field]),'native provenance fields differ.')
            need(match['references'] and match['taxa'] and all(re.fullmatch(r'taxon:[0-9]+',t) for t in match['taxa']),
                 'native reference/taxon context missing.')
            path=match.get('ontology_path');rels=match.get('path_predicates')
            need(isinstance(path,list) and all(go(v) for v in path) and path
                 and len(set(path))==len(path) and path[0]==match['source_term'] and path[-1]==row['GO_ID']
                 and isinstance(rels,list) and len(rels)==len(path)-1 and all(isinstance(v,str) and v in predicates for v in rels),
                 'native ancestor path differs.')
        need(not matched.intersection(current['exact_NOT_record_ids']),'one native record cannot have both polarities.')
        by_query[row['query']].append(deepcopy(row))
    counts={'candidates':len(rows),'queries':len(queries),
        'known_t0_literal':sum(row['known_t0_literal'] for row in rows),
        'known_t0_author_closure':sum(row['known_t0_author_closure'] for row in rows),
        'all_evidence_status':dict(Counter(row['pre_t0_all_evidence']['status'] for row in rows)),
        'july2026_positive_literal':sum(any(m['membership']=='literal_term' for m in r['july2026_goa']['positive_matches']) for r in rows),
        'july2026_positive_ancestor_only':sum(bool(r['july2026_goa']['positive_matches']) and not any(m['membership']=='literal_term' for m in r['july2026_goa']['positive_matches']) for r in rows),
        'july2026_no_positive_match':sum(not r['july2026_goa']['positive_matches'] for r in rows),
        'july2026_exact_NOT_present':sum(bool(r['july2026_goa']['exact_NOT_record_ids']) for r in rows)}
    need(report.get('counts')==counts,'display overlap counts do not replay.')
    counts['july2026_deprecated_terms']=sum(r['july2026_goa']['term_deprecated'] for r in rows)
    return {'format':report['format'],'content_sha256':report['content_sha256'],
        'original_report':deepcopy(report['original_report']),'counts':counts,'queries':by_query,
        'source_dates':{'historical_training_cutoff':manifest.get('source_versions',{}).get('t0_date'),
            'native_annotations_generated':dates[0],'matching_native_ontology':release[1]},
        'inputs':deepcopy(inputs),'scientific_accuracy_claimed':False,'forecast_modified':False,
        'limitations':deepcopy(report.get('limitations',[]))}


CONTENT_NOTES = 'biograph-steward.historical-term-content-notes.v1'


def load_content_notes(path,expected_sha256,manifest,queries,*,manifest_file_sha256):
    """Read only a small, source-pinned ontology-content projection.

    Full ontology bodies and the full used-term index are never opened by this
    web consumer. Date-specific source content qualifies a historical term; it
    cannot replace a forecast, annotation, identifier or review decision.
    """
    from .go_content_currency import validate_term
    path=Path(path).absolute()
    need(path.is_file() and not path.is_symlink() and path.stat().st_size<=2*1048576,
         'content notes must be an ordinary bounded file.')
    pin=lambda value:isinstance(value,str) and re.fullmatch(r'[a-f0-9]{64}',value)
    need(pin(expected_sha256) and pin(manifest_file_sha256) and sha(path)==expected_sha256,
         'explicit content notes/publication FILE SHA differs.')
    report=json.loads(path.read_text())
    need(isinstance(report,dict) and set(report)=={'format','publication_manifest_sha256','publication_content_sha256',
         'source_currency_index','source_versions','terms','queries','scientific_accuracy_claimed','forecast_modified',
         'semantic_equivalence_claimed','automatic_mapping_or_pruning','graph_modified','limitations','content_sha256'}
         and report.get('format')==CONTENT_NOTES
         and report.get('content_sha256')==digest({k:v for k,v in report.items() if k!='content_sha256'}),
         'content notes format/content seal differs.')
    need(report.get('publication_manifest_sha256')==manifest_file_sha256
         and report.get('publication_content_sha256')==manifest.get('content_sha256'),
         'content notes belong to another historical publication.')
    need(all(report.get(k) is False for k in ('scientific_accuracy_claimed','forecast_modified',
         'semantic_equivalence_claimed','automatic_mapping_or_pruning','graph_modified')),
         'content notes cannot make a biological decision or change a forecast.')
    source=report.get('source_currency_index')
    source_pins={'manifest_file_sha256','manifest_content_sha256','term_frame_sha256',
                 'index_file_sha256','historical_ontology_file_sha256','comparison_ontology_file_sha256'}
    need(isinstance(source,dict) and set(source)==source_pins|{'term_count'}
         and all(pin(source[k]) for k in source_pins)
         and type(source['term_count']) is int and 0<source['term_count']<=50000,
         'full currency-index provenance is required without operator paths.')
    need(source['historical_ontology_file_sha256']==manifest.get('input_source_pins',{}).get('ontology',{}).get('sha256'),
         'content notes historical ontology differs from forecast input.')
    versions=report.get('source_versions')
    need(isinstance(versions,dict) and set(versions)=={'historical_predictor','comparison_snapshot',
         'graph_Pharos_GO_vintage','latest_release_claimed'}
         and all(isinstance(versions[k],str) and re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',versions[k])
                 for k in ('historical_predictor','comparison_snapshot'))
         and versions['graph_Pharos_GO_vintage']=='UNKNOWN' and versions['latest_release_claimed'] is False,
         'explicit dated-source/unknown-vintage qualification required.')
    expected={p:[{'GO_ID':c['GO_ID'],'aspect':c['aspect'],'published_score':c['score'],
                   'label':c.get('label')} for c in q['candidates']] for p,q in queries.items()}
    need(report.get('queries')==expected,'content notes do not match the exact saved candidate inventory/order/scores.')
    expected_ids={c['GO_ID'] for q in queries.values() for c in q['candidates']}
    terms=report.get('terms')
    need(isinstance(terms,list) and len(terms)==len(expected_ids)<=225,'complete compact candidate term inventory required.')
    by_term={}
    for row in terms:
        need(isinstance(row,dict) and set(row)=={'term_id','scopes','graph_labels','historical','comparison',
             'flags','semantic_equivalence_inferred','biological_falsehood_inferred','automatic_action'}
             and isinstance(row.get('term_id'),str) and row['term_id'] in expected_ids
             and row['term_id'] not in by_term,'invalid or repeated projected term.')
        for name in ('historical','comparison'):
            value=row.get(name)
            common={'present','state','name','definition','namespace','synonyms','parents'}
            extras=({'present_in_author_active_view','definition_raw','declared_alt_ids','declared_replaced_by',
                     'declared_consider','stanza_utf8_sha256'} if name=='historical' else
                    {'declared_lifecycle','replacement_applied','node_canonical_json_sha256'})
            need(isinstance(value,dict) and common<=set(value)<=common|extras,
                 'raw ontology bodies belong in the full offline source index.')
            need(isinstance(value.get('synonyms'),list) and len(value['synonyms'])<=2000
                 and all(isinstance(s,dict) and set(s)=={'scope','value'} and isinstance(s['scope'],str)
                         and s['scope'] in {'EXACT','RELATED','BROAD','NARROW'}
                         and isinstance(s['value'],str) for s in value['synonyms']), 'projected synonym fields differ.')
            need(isinstance(value.get('parents'),list) and len(value['parents'])<=500
                 and all(isinstance(p,dict) and set(p)=={'predicate','object'} and isinstance(p['predicate'],str)
                         and p['predicate'] in {'is_a','part_of'}
                         and isinstance(p['object'],str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*:[A-Za-z0-9_]+',p['object'])
                         for p in value['parents']), 'projected explicit parent fields differ.')
            need(value.get('namespace') is None or isinstance(value['namespace'],str),'invalid projected namespace.')
            if 'replacement_applied' in value:need(value['replacement_applied'] is False,'content notes cannot apply a replacement.')
            for key in ('stanza_utf8_sha256','node_canonical_json_sha256'):
                if key in value:need(pin(value[key]),'projected native source pin differs.')
            for key in ('declared_alt_ids','declared_replaced_by','declared_consider'):
                if key in value:need(isinstance(value[key],list) and all(isinstance(x,str) for x in value[key]),'projected lifecycle declarations differ.')
            if 'declared_lifecycle' in value:
                life=value['declared_lifecycle']
                need(isinstance(life,dict) and set(life)=={'state','declared_replaced_by','consider_only','ontology_node_sha256'}
                     and life['state']==value['state'] and pin(life['ontology_node_sha256'])
                     and all(isinstance(life[k],list) and all(isinstance(x,str) for x in life[k])
                             for k in ('declared_replaced_by','consider_only')), 'projected lifecycle source scope differs.')
        validate_term(row);by_term[row['term_id']]=deepcopy(row)
    need(set(by_term)==expected_ids,'a saved candidate term is absent from content notes.')
    need(isinstance(report.get('limitations'),list) and all(isinstance(v,str) for v in report['limitations']),
         'content note interpretation limits are missing.')
    return {'format':CONTENT_NOTES,'content_sha256':report['content_sha256'],
        'source_currency_index':deepcopy(source),'source_versions':deepcopy(versions),
        'terms':by_term,'scientific_accuracy_claimed':False,'forecast_modified':False,
        'limitations':deepcopy(report['limitations'])}

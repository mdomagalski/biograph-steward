"""Pure, scope-bounded accounting for the separately frozen IntAct final flow.

No helper in this module opens source bodies or infers scientific independence.
The existing official reader, original eligibility and source-fidelity oracle are
reused unchanged by the caller.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from biograph_steward.client import digest
from biograph_steward.gold_packet import _decode
from scripts.inspect_intact_development import values, dbname
from scripts.validate_intact_xml_provenance import references, xref_tuple
from scripts.inspect_intact_xml_development import xml_evidence_ids

DEVELOPMENT = ('40075158','40404733','40071126','40739265')
RESERVED = ('39833857','40211762','39972491','40555359')
PROTOCOL_SHA = 'd4948f584b8eed374ddfa49084ee58f1fb352d3d68a6630a202bf25742f8920a'
AMENDMENT_SHA = '2cd2cb485836228ce71dd9d62201c61dd5de45d18563894ac883f188f245e98c'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def seal(value):
    value = deepcopy(value)
    value['content_sha256'] = digest(value)
    return value


def load_json(path):
    return _decode(Path(path).read_bytes())


def save_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


def ordinary(path):
    path = Path(path).absolute()
    if any(parent.is_symlink() for parent in (path, *path.parents)) or not path.is_file():
        raise ValueError('An explicit ordinary file without symlink traversal is required: ' + str(path))
    return path


def study_ids(split):
    if split == 'development_replay': return DEVELOPMENT
    if split == 'reserved_final': return RESERVED
    raise ValueError('Only the consumed development replay or original reserved panel is permitted.')


def fraction(n, d):
    return {'numerator': n, 'denominator': d, 'value': n/d if d else None,
            'status': 'evaluated' if d else 'unevaluated_empty_stratum'}


def participant_pair(row):
    """Literal primary database+accession identities; no alias/isoform collapse."""
    sides = [tuple(sorted((dbname(x), x.get('id')) for x in values(row, 'primary_ids_' + side)))
             for side in ('a','b')]
    return tuple(sorted(sides))


def overlap_inventory(records):
    participants, pairs, evidence = set(), set(), set()
    for wrapper in records:
        row = wrapper['reader_record']
        if row.get('row_status') in {'header','comment','blank'}: continue
        pair = participant_pair(row)
        pairs.add(pair)
        for side in pair: participants.update(side)
        evidence.update((dbname(x),x.get('id')) for x in values(row,'evidence_ids'))
    return {'participants': sorted(participants), 'pairs': sorted(pairs), 'evidence_ids': sorted(evidence)}


def _tuple_tree(value):
    return tuple(_tuple_tree(item) for item in value) if isinstance(value,(list,tuple)) else value


def provenance_audit(xml_by_study, records, consumed):
    """Audit exact exposure and conservatively stop on qualified lineage ambiguity.

    Generic citations, matching proteins and IMEx registrations do not imply
    shared experiments. A primary/subsidiary dataset comment with references is
    retained as a qualified statement; only a known consumed link excludes a
    connected study component. Unresolved qualified comments stop scoring.
    """
    if consumed.get('format') != 'biograph-steward.intact-consumed-inventory.v1':
        raise ValueError('Use a declared bounded consumed-reference inventory.')
    pmids = set(consumed.get('publication_ids', []))
    dois = {str(value).casefold().removeprefix('https://doi.org/').removeprefix('doi:') for value in consumed.get('dois',[])}
    evidence_ids = {_tuple_tree(item) for item in consumed.get('evidence_ids',[])}
    consumed_pairs = {_tuple_tree(item) for item in consumed.get('pairs',[])}
    consumed_participants = {_tuple_tree(item) for item in consumed.get('participants',[])}
    studies = list(xml_by_study)
    links, ambiguities, annotations, evidence_groups = [], [], [], []
    see_also_by_study=defaultdict(set)
    consumed_see_also={tuple(item) for item in consumed.get('qualified_see_also_links',[])}
    connected = {pmid:set() for pmid in studies}
    touched = set()
    touched.update(set(studies)&pmids)
    for pmid, objects in xml_by_study.items():
        for record in objects:
            evidence = record['evidence']
            ids = [xref_tuple(x) for x in references(evidence)]
            exact_evidence_overlap = sorted(xml_evidence_ids(evidence)&evidence_ids)
            if exact_evidence_overlap: touched.add(pmid)
            experiments = evidence.get('experiments') or []
            evidence_groups.append({'publication_id':pmid,'evidence_sequence':record['evidence_sequence'],
                'xml_id':evidence.get('xml_id'),'identifiers':ids,
                'experiments':[{'xml_id':exp.get('xml_id'),'references':[xref_tuple(x) for x in references(exp)]} for exp in experiments],
                'participants':len(evidence.get('participants') or []),
                'exact_consumed_evidence_overlap':exact_evidence_overlap})
            contexts = [('interaction',evidence)]
            for exp in experiments:
                contexts += [('experiment',exp),('publication',exp.get('publication') or {})]
            for kind,obj in contexts:
                for ref in references(obj):
                    db,identity,qualifier=xref_tuple(ref)
                    if db=='pubmed' and qualifier=='MI:0361' and identity!=pmid:
                        see_also_by_study[pmid].add(identity)
                for ann in obj.get('annotations') or []:
                    topic=(ann.get('topic') or {})
                    text=' '.join(str(x) for x in (topic.get('name'),topic.get('mi_id'),ann.get('value')) if x)
                    # These are conservative flags, never a custom biological classifier.
                    if re.search(r'(?i)\b(primary|subsidiary|secondary)\b.*\b(data\s*set|dataset|data)\b|\b(shared|reused)\s+(data|dataset)',text):
                        refs=[xref_tuple(x) for x in references(obj)]
                        if kind=='experiment': refs += [xref_tuple(x) for x in references(obj.get('publication') or {})]
                        external=[]
                        for db,identity,qualifier in refs:
                            if qualifier!='MI:0361':continue
                            if db=='pubmed' and identity!=pmid: external.append(('pubmed',identity))
                            if db=='doi': external.append(('doi',str(identity).casefold().removeprefix('https://doi.org/').removeprefix('doi:')))
                        known=[x for x in external if (x[0]=='pubmed' and x[1] in pmids) or (x[0]=='doi' and x[1] in dois)]
                        selected=[identity for db,identity in external if db=='pubmed' and identity in connected]
                        entry={'publication_id':pmid,'context':kind,'source_locator':obj.get('source_locator'),
                               'annotation':deepcopy(ann),'references':refs,'known_consumed_links':known,
                               'selected_study_links':selected}
                        annotations.append(entry)
                        if known or selected:
                            links.append(entry)
                        else:
                            ambiguities.append(entry)
    for entry in links:
        pmid=entry['publication_id']
        unresolved=[]
        for db,other in entry['known_consumed_links']:
            if db=='pubmed' and (other,pmid) in consumed_see_also:
                touched.add(pmid)
            else:unresolved.append([db,other])
        for other in entry['selected_study_links']:
            if pmid in see_also_by_study[other]:
                connected[pmid].add(other);connected[other].add(pmid)
            else:unresolved.append(['pubmed',other])
        if unresolved:
            ambiguities.append({**entry,'reason':'qualified_dataset_link_lacks_verified_mutual_see_also','unresolved_links':unresolved})
    excluded=set(touched)
    frontier=list(touched)
    while frontier:
        current=frontier.pop()
        for other in connected.get(current,set())-excluded:
            excluded.add(other);frontier.append(other)
    exposure=[]
    for wrapper in records:
        row=wrapper['reader_record']
        if row.get('row_status') in {'header','comment','blank'}:continue
        pair=participant_pair(row)
        overlap=sorted({identity for side in pair for identity in side}&consumed_participants)
        exposure.append({'publication_id':wrapper['publication_id'],'source_line':row['line_number'],
                         'exact_pair_exposed':pair in consumed_pairs,'exact_participants_exposed':overlap})
    return {'status':'blocked_ambiguous_dataset_lineage' if ambiguities else 'bounded_audit_complete_independence_unverified',
            'excluded_publication_ids':sorted(excluded),'qualified_dataset_links':links,
            'ambiguous_dataset_statements':ambiguities,'qualified_annotations':annotations,
            'evidence_experiment_groups':evidence_groups,'exact_exposure':exposure,
            'study_independence':'unverified','inventory_scope':consumed.get('scope'),
            'article_status_scope':consumed.get('article_status_scope','No new article-level status checks; not clearance.'),
            'pair_or_participant_overlap_is_exclusion':False}


def assess_alignment(alignment, records, xml_records):
    """A source-annotated expansion may map several MITAB rows to one XML object."""
    errors=[]
    byline={r['ledger']['source_line']:r for r in records}
    for result in alignment['rows']:
        if result['alignment']!='unique':errors.append({'source':result['source'],'reason':'unresolved_evidence_projection'})
        bad=[x for x in result['checks'] if x['status']!='equal']
        if bad:errors.append({'source':result['source'],'reason':'critical_cross_format_field_mismatch','checks':bad})
    for group in alignment['multiple_mitab_rows_per_xml_record']:
        affected=[r for r in alignment['rows'] if r.get('xml_evidence_sequence')==group['xml_sequence']]
        annotated=all(byline[r['source']['source_line']]['reader_record']['raw_cells'][15]!='-' for r in affected)
        xml=next((r['evidence'] for r in xml_records if r['evidence_sequence']==group['xml_sequence']),{})
        if not annotated or len(xml.get('participants') or [])<=2:
            errors.append({'xml_sequence':group['xml_sequence'],'reason':'unexplained_multiple_mitab_views'})
    if alignment['unmatched_xml_sequences']:errors.append({'reason':'unmatched_xml_records','sequences':alignment['unmatched_xml_sequences']})
    return errors


def summarize(evaluation, references, publications):
    """Original all-eligible denominator, including unavailable downstream outputs."""
    from scripts.evaluate_intact_evidence_fidelity import PARSED_GROUPS
    rows=evaluation['rows'];den=sum(bool(ref['ledger']['eligible']) for ref in references)
    if len(rows)!=den:raise ValueError('Every final-eligible source row must have exactly one evaluation row.')
    completed=sum(bool(row['completed']) for row in rows);strict=sum(bool(row['strict_fidelity']) for row in rows)
    per=[]
    for pmid in publications:
        chosen=[row for row in rows if row['source']['publication_id']=='pubmed:'+pmid]
        per.append({'publication_id':'pubmed:'+pmid,'coverage':fraction(sum(row['completed'] for row in chosen),len(chosen)),
                    'strict_fidelity':fraction(sum(row['strict_fidelity'] for row in chosen),len(chosen))})
    valid=[p['strict_fidelity']['value'] for p in per if p['strict_fidelity']['value'] is not None]
    groups={g:{m:fraction(sum(row['groups'][g][m] for row in rows),den) for m in ('raw_preserved','structured_preserved','readable_covered')} for g in PARSED_GROUPS}
    strata={}
    for field,keys in (('negative_literal',('true','false','-')),('expansion_stratum',('supplied','not_supplied'))):
        strata[field]={k:fraction(sum(row['strict_fidelity'] for row in rows if row[field]==k),sum(row[field]==k for row in rows)) for k in keys}
    # Preserve arbitrary source method/type values, while explicit '-' strata
    # and missing-context strata remain visible even when empty.
    bykey={tuple(ref['ledger'][k] for k in ('publication_id','artifact_sha256','source_line')):ref['reader_record'] for ref in references if ref['ledger']['eligible']}
    for name,column in (('detection_method_literal',6),('interaction_type_literal',11)):
        keys=sorted({'-',*[reader['raw_cells'][column] for reader in bykey.values()]})
        strata[name]={value:fraction(sum(row['strict_fidelity'] for row in rows if bykey[tuple(row['source'][k] for k in ('publication_id','artifact_sha256','source_line'))]['raw_cells'][column]==value),sum(reader['raw_cells'][column]==value for reader in bykey.values())) for value in keys}
    context_columns={'host_context':[28],'biological_roles':[16,17],'experimental_roles':[18,19],'features_and_stoichiometry':[36,37,38,39]}
    for name,indices in context_columns.items():
        def state(reader):
            absent=sum(reader['raw_cells'][i]=='-' for i in indices)
            return 'all_missing' if absent==len(indices) else 'some_missing' if absent else 'all_supplied'
        strata[name]={value:fraction(sum(row['strict_fidelity'] for row in rows if state(bykey[tuple(row['source'][k] for k in ('publication_id','artifact_sha256','source_line'))])==value),sum(state(reader)==value for reader in bykey.values())) for value in ('all_missing','some_missing','all_supplied')}
    return {'coverage':fraction(completed,den),'strict_fidelity':fraction(strict,den),
            'conditional_fidelity':fraction(strict,completed),'per_publication':per,
            'macro_strict_fidelity':sum(valid)/len(valid) if valid else None,
            'eligible_publications_in_macro':len(valid),'per_field_group':groups,'strata':strata,
            'field_error_counts':dict(Counter(c['category'] for row in rows for c in row['checks'] if not c['passed']))}


def output_inventory_checks(references, observations, results, packet, exported):
    """Check whole outputs before any scoring-scope subset is selected."""
    expected={tuple(ref['ledger'][k] for k in ('publication_id','artifact_sha256','source_line')) for ref in references if ref['ledger']['eligible']}
    checks=[]
    for name,rows,is_answer in (('observations',observations,False),('answer_results',results,True),('packet',packet,False),('answer_export',exported,True)):
        source_rows=[row.get('source_observation',{}) if is_answer else row for row in rows]
        keys=[tuple(row.get('source',{}).get(k) for k in ('publication_id','artifact_sha256','source_line')) for row in source_rows]
        identifiers=[row.get('observation_id') if is_answer else row.get('id') for row in rows]
        checks += [{'name':name+'.no_unexpected_locators','passed':not(set(keys)-expected),
                    'unexpected':[list(key) for key in set(keys)-expected]},
                   {'name':name+'.unique_source_locators','passed':len(keys)==len(set(keys))},
                   {'name':name+'.unique_observation_ids','passed':len(identifiers)==len(set(identifiers))}]
    return checks

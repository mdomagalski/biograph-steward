# SPDX-License-Identifier: MIT
# Path-parameter adaptation of the successful source-only preparation; no label/scoring-policy changes.
"""Qualify the official author crosswalk using GO CC containment, before labels."""
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path

import argparse

_parser = argparse.ArgumentParser(description=__doc__)
_parser.add_argument('--repo', type=Path, required=True)
_parser.add_argument('--work-dir', type=Path, required=True)
_parser.add_argument('--artifacts-dir', type=Path, required=True)
_parser.add_argument('--source-readiness-sha256', required=True)
_args = _parser.parse_args()

ROOTS = {'cytoskeleton':'GO:0005856','actin-filaments':'GO:0005884',
    'intermediate-filaments':'GO:0005882','centrosome':'GO:0005813','microtubules':'GO:0005874',
    'plasma-membrane':'GO:0005886','cytosol':'GO:0005829','endoplasmic-reticulum':'GO:0005783',
    'golgi-apparatus':'GO:0005794','vesicles':'GO:0031982','endosomes':'GO:0005768',
    'lysosomes':'GO:0005764','peroxisomes':'GO:0005777','lipid-droplets':'GO:0005811',
    'mitochondria':'GO:0005739','nucleoplasm':'GO:0005654','nuclear-bodies':'GO:0016604',
    'nuclear-membrane':'GO:0031965','nuclear-speckles':'GO:0016607','nucleoli':'GO:0005730',
    'nucleoli-fibrillar-center':'GO:0001650'}


def main():
    out=_args.work_dir.resolve()
    p=out/'HOU_source_crosswalk_before_label_join.json';raw=p.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==_args.source_readiness_sha256
    source=json.loads(raw);op=Path(source['input_pins']['ontology']['file'])
    assert hashlib.sha256(op.read_bytes()).hexdigest()==source['input_pins']['ontology']['sha256']
    graph=json.loads(gzip.decompress(op.read_bytes()))['graphs'][0]
    go=lambda s:s.replace('http://purl.obolibrary.org/obo/GO_','GO:')
    nodes={go(n['id']):n for n in graph['nodes'] if n.get('type')=='CLASS'}
    parents=defaultdict(set)
    for e in graph['edges']:
        if e['pred'] in ('is_a','http://purl.obolibrary.org/obo/BFO_0000050'):
            parents[go(e['sub'])].add(go(e['obj']))
    qualified={};excluded=[]
    for uid,label in source['crosswalk'].items():
        seen={uid};todo=[uid]
        while todo:
            for parent in parents[todo.pop()]-seen:seen.add(parent);todo.append(parent)
        if ROOTS[label] in seen:qualified[uid]=label
        else:excluded.append({'GO_ID':uid,'GO_preferred_label':nodes[uid]['lbl'],
            'author_coarse_label':label,'required_label_GO_root':ROOTS[label],
            'reason':'GO term does not equal or entail a part of the standardized compartment via declared is_a/part_of'})
    assert 'GO:0016020' not in qualified and 'GO:0005737' not in qualified and 'GO:0005634' not in qualified
    result={'format':'biograph-steward.HOU-source-scope-qualified-crosswalk.v1',
        'source_crosswalk_sha256':hashlib.sha256(raw).hexdigest(),
        'ontology_sha256':source['input_pins']['ontology']['sha256'],
        'root_policy':'Literal standard compartment GO IDs below, inspected against active publisher preferred names before cohort outcomes. Only is_a and part_of establish containment; associations/adjacency/regulates do not.',
        'root_nodes':{label:{'GO_ID':uid,'preferred_name':nodes[uid]['lbl'],
            'ontology_node_sha256':hashlib.sha256(json.dumps(nodes[uid],sort_keys=True,separators=(',',':')).encode()).hexdigest()} for label,uid in ROOTS.items()},
        'qualified_exact_GO_crosswalk':qualified,'excluded_lossy_coarse_crosswalk':excluded,
        'qualification_only_does_not_expand_input_term_mapping':True,
        'unaltered_author_crosswalk_preserved_in_source':True,
        'cohort_reference_labels_or_predictions_opened':False,
        'producer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    dest=out/'HOU_scope_qualified_crosswalk_v1.json'
    with dest.open('x') as f:json.dump(result,f,sort_keys=True,indent=2);f.write('\n')
    print(json.dumps({'output':str(dest),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),
        'qualified':len(qualified),'excluded':len(excluded)}))


if __name__=='__main__':main()

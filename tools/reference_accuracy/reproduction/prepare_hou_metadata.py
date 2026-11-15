# SPDX-License-Identifier: MIT
# Path-parameter adaptation of the successful source-only preparation; no label/scoring-policy changes.
"""Source-only HOU crosswalk and identifier coverage; no cohort label join."""
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys

import argparse

_parser = argparse.ArgumentParser(description=__doc__)
_parser.add_argument('--repo', type=Path, required=True)
_parser.add_argument('--work-dir', type=Path, required=True)
_parser.add_argument('--artifacts-dir', type=Path, required=True)
_parser.add_argument('--yaml-module-dir', type=Path)
_args = _parser.parse_args()
REPO = _args.repo.resolve()
if _args.yaml_module_dir is not None:
    sys.path.insert(0, str(_args.yaml_module_dir.resolve()))
import yaml

OUT = _args.work_dir.resolve()
OUT.mkdir(parents=True, exist_ok=True)
ART = _args.artifacts_dir.resolve()


def spec(path):
    path = Path(path).resolve()
    return {'file': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size}


def main():
    hierarchy = ART / 'HOU_hierarchical_label_set.zenodo18435290.yaml'
    raw = hierarchy.read_bytes()
    assert hashlib.md5(raw).hexdigest() == '0d54098a5aade413a4867a1e33a8f894'
    mappings = yaml.safe_load(raw)
    official = []
    row = None
    for line in (ART / 'uniprot_subcell.txt').read_text().splitlines():
        code, text = line[:2], line[5:].strip()
        if code in {'ID','IT','IO'}:
            row = {'kind':code,'name':text.removesuffix('.'),'go_ids':[]}
        elif row is not None and code == 'AC': row['sl_id'] = text
        elif row is not None and code == 'GO':
            match = re.match(r'(GO:[0-9]{7});', text)
            assert match, text
            row['go_ids'].append(match[1])
        elif line == '//' and row is not None:
            official.append(row);row=None
    by_name = {r['name'].casefold(): r for r in official if r['kind'] == 'ID'}
    assert len(by_name) == sum(r['kind'] == 'ID' for r in official)
    ontology_file=REPO/'runs/crc_go_ontology_qualification_20261112/ontology/source.json.gz'
    ontology=json.loads(gzip.decompress(ontology_file.read_bytes()))['graphs'][0]
    active={r['id'].removeprefix('http://purl.obolibrary.org/obo/').replace('GO_','GO:')
            for r in ontology['nodes'] if r.get('type')=='CLASS' and not r.get('meta',{}).get('deprecated',False)}
    bridge=defaultdict(set);provenance=defaultdict(list);missing=[];outside=[]
    for name, label in mappings['uniprot_to_lvl1'].items():
        if not label:continue
        r=by_name.get(name.casefold())
        if r is None:missing.append(name);continue
        for go in r['go_ids']:
            if go not in active:outside.append(go);continue
            bridge[go].add(label);provenance[go].append({'author_location':name,'official_SL':r['sl_id'],'official_name':r['name'],'label1':label})
    accepted={go:next(iter(ls)) for go,ls in bridge.items() if len(ls)==1}
    ambiguous={go:sorted(ls) for go,ls in bridge.items() if len(ls)>1}
    # Identifier-column projection only; no localization outcomes are retained.
    csv_file=ART/'HOU_hou_testset.csv'
    assert hashlib.md5(csv_file.read_bytes()).hexdigest()=='d7e070b24761ba7ee5f7837adfa65cc6'
    with csv_file.open() as stream:
        reader=csv.DictReader(stream);assert reader.fieldnames==['uniprot_id','ensembl_id','level1','level2','level3','sequence']
        identifiers=[r['uniprot_id'] for r in reader]
    assert len(identifiers)==len(set(identifiers))==3814
    eligibility=json.loads((OUT/'source_eligibility_before_label_join.json').read_text())
    all_ids={r['protein_id'].split(':',1)[1] for r in eligibility['rows']}
    primary={r['protein_id'].split(':',1)[1] for r in eligibility['rows'] if r['primary_source_eligible']}
    primary_rows=[r for r in eligibility['rows'] if r['primary_source_eligible'] and r['protein_id'].split(':',1)[1] in identifiers]
    result={'format':'biograph-steward.HOU-source-crosswalk-before-label-join.v1',
        'author_test_rows':3814,'primary99_exact_ID_coverage':len(set(identifiers)&primary),
        'primary_matched_unique_GeneIDs':len({r['gene_id'] for r in primary_rows}),
        'all218_exact_ID_coverage_only':len(set(identifiers)&all_ids),
        'proposed_reference_unit':'Exact canonical protein and its released positive localization labels; no cross-product gene aggregation',
        'crosswalk':accepted,'crosswalk_evidence':dict(provenance),'ambiguous_GO_crosswalk_excluded':ambiguous,
        'unmatched_author_vocabulary_locations':missing,'outside_active_ontology_GO_ids':sorted(set(outside)),
        'mapping_policy':'Exact author UniProt-location name (casefold only) -> official UniProt subcell vocabulary GO crossref -> unique author level1; no GO ancestor expansion, aliases, guessed label names or membrane-root propagation',
        'level1':mappings['level1'],'level2':mappings['level2'],'level3':mappings['level3'],
        'level1_to_level2':mappings['lvl1_to_lvl2'],'level1_to_level3':mappings['lvl1_to_lvl3'],
        'all_author_maps_reused_without_modification':True,
        'source_exposure':'HPA, UniProt and OpenCell source/study overlap possible. Released labels have no source mask; upstream consensus notebook admits OpenCell-only labels in an invented-input source reproduction.',
        'cohort_localization_labels_joined_or_inspected':False,
        'predictions_or_metrics_computed':False,
        'proposed_metrics':'Positive-reference label recall and supported/unresolved output counts at all three released levels. No specificity, biological precision, F1 or MCC from unlisted compartments.',
        'input_pins':{n:spec(p) for n,p in {'hierarchy':hierarchy,'testset':csv_file,
            'official_UniProt_subcell_vocabulary':ART/'uniprot_subcell.txt','ontology':ontology_file,
            'source_eligibility':OUT/'source_eligibility_before_label_join.json',
            'native_author_construction':ART/'HOU_1-generating_datasets.ipynb',
            'producer':Path(__file__)}.items()},
        'yaml_parser':{'version':yaml.__version__,'source':spec(yaml.__file__)}}
    path=OUT/'HOU_source_crosswalk_before_label_join.json'
    with path.open('x') as f:json.dump(result,f,sort_keys=True,indent=2);f.write('\n')
    print(json.dumps({'output':spec(path),'accepted_exact_GO_maps':len(accepted),'ambiguous_excluded':len(ambiguous),
        'primary99_exact_ID_coverage':result['primary99_exact_ID_coverage'],'primary_matched_unique_GeneIDs':result['primary_matched_unique_GeneIDs'],
        'all218_exact_ID_coverage_only':result['all218_exact_ID_coverage_only'], 'author_names_without_official_CV_match':len(missing)}))


if __name__=='__main__':main()

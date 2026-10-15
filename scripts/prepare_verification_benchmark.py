"""Prepare local SciFact claim/abstract tasks; never sends data to a model.

Run after downloading the official release and recording source_manifest.json.
Model inputs and expert answer keys are deliberately separate files.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import tarfile
from urllib.request import urlopen

LABELS = {'SUPPORT', 'CONTRADICT', 'NOT_ENOUGH_INFORMATION'}
RELEASE_URL='https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz'
LICENSE_URL='https://raw.githubusercontent.com/allenai/scifact/master/LICENSE.md'


def download_source(output):
    output=Path(output)
    if output.exists() and any(output.iterdir()):raise ValueError('Choose a new empty source directory.')
    with urlopen(RELEASE_URL,timeout=45) as response:archive_bytes=response.read(50_000_001)
    if len(archive_bytes)>50_000_000:raise ValueError('Source archive exceeds 50 MB.')
    files={}
    with tarfile.open(fileobj=io.BytesIO(archive_bytes),mode='r:gz') as archive:
        for name in ['corpus.jsonl','claims_train.jsonl','claims_dev.jsonl']:
            members=[m for m in archive.getmembers() if m.isfile() and m.name=='data/'+name]
            if len(members)!=1 or members[0].size>50_000_000:raise ValueError('Unexpected release inventory.')
            files[name]=archive.extractfile(members[0]).read()
    with urlopen(LICENSE_URL,timeout=20) as response:license_bytes=response.read(100_001)
    if len(license_bytes)>100_000:raise ValueError('License response exceeds 100 KB.')
    output.mkdir(parents=True,exist_ok=True)
    (output/'data.tar.gz').write_bytes(archive_bytes);(output/'LICENSE.md').write_bytes(license_bytes)
    for name,data in files.items():(output/name).write_bytes(data)
    manifest={'download_url':RELEASE_URL,'retrieved_at':datetime.now(timezone.utc).isoformat(),
              'archive_sha256':sha(output/'data.tar.gz'),
              'files':{name:{'sha256':sha(output/name),'rows':len(data.splitlines())} for name,data in files.items()},
              'license_url':LICENSE_URL,'license_sha256':sha(output/'LICENSE.md'),
              'claim_annotations_license':'CC-BY-4.0','abstracts_license':'ODC-By-1.0',
              'attribution':'Wadden et al. 2020. Fact or Fiction: Verifying Scientific Claims. EMNLP. https://aclanthology.org/2020.emnlp-main.609/'}
    (output/'source_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def prepare(source, output, split='dev', exclude_inputs=None):
    if split not in {'train', 'dev'}:
        raise ValueError('Only labeled train/dev splits are supported; unlabeled test cases are not negatives.')
    source, output = Path(source).resolve(), Path(output).resolve()
    if output == source or source in output.parents or output in source.parents:
        raise ValueError('Keep prepared tasks outside the source directory.')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Choose a new empty benchmark directory.')
    manifest = json.loads((source / 'source_manifest.json').read_text())
    filenames = ['corpus.jsonl', 'claims_' + split + '.jsonl']
    for filename in filenames:
        if sha(source / filename) != manifest['files'][filename]['sha256']:
            raise ValueError('Downloaded source bytes changed: ' + filename)
    corpus = rows(source / filenames[0]); claims = rows(source / filenames[1])
    documents = {d['doc_id']: d for d in corpus}
    if len(documents) != len(corpus) or len({c['id'] for c in claims}) != len(claims):
        raise ValueError('Duplicate source document or claim identity.')
    selection={'policy':'official_split','source_claims':len(claims),'excluded_claims':0}
    if exclude_inputs is not None:
        exclude_inputs=Path(exclude_inputs).resolve()
        if exclude_inputs.parent==output or exclude_inputs.parent in output.parents:
            raise ValueError('Keep the held-out preparation outside the excluded input directory.')
        seen={r['document_id'] for r in rows(exclude_inputs)}
        selected=[c for c in claims if not seen.intersection(c['cited_doc_ids'])]
        selection.update(policy='exclude_whole_claim_if_any_cited_document_was_seen',
                         excluded_inputs_sha256=sha(exclude_inputs),excluded_claims=len(claims)-len(selected))
        claims=selected
        if not claims:raise ValueError('Document exclusion leaves no claims.')
    inputs, gold, duplicate_citations = [], [], []
    for c in claims:
        if 'evidence' not in c or not isinstance(c['evidence'], dict):
            raise ValueError('Missing expert annotations; do not treat unlabeled inputs as no evidence.')
        cited = list(dict.fromkeys(c['cited_doc_ids']))
        if len(cited)!=len(c['cited_doc_ids']):
            duplicate_citations.append({'claim_id':c['id'],'duplicates_collapsed':len(c['cited_doc_ids'])-len(cited)})
        if not cited or set(c['evidence']) - set(map(str, cited)):
            raise ValueError('Unsupported citation inventory; no oracle document additions are allowed.')
        for doc_id in cited:
            d = documents[doc_id]
            if not isinstance(d['abstract'], list) or any(not isinstance(s, str) for s in d['abstract']):
                raise ValueError('Invalid sentence-indexed abstract.')
            evidence = c['evidence'].get(str(doc_id), [])
            labels = {e['label'] for e in evidence}
            if len(labels) > 1 or labels - {'SUPPORT', 'CONTRADICT'}:
                raise ValueError('Unsupported or conflicting expert labels for one abstract.')
            label = next(iter(labels)) if labels else 'NOT_ENOUGH_INFORMATION'
            rationale_sets = [e['sentences'] for e in evidence]
            if any(not s or len(set(s)) != len(s) or any(type(i) is not int or not 0 <= i < len(d['abstract']) for i in s) for s in rationale_sets):
                raise ValueError('Invalid gold evidence sentence indices.')
            identity = f"SciFact.{split}.{c['id']}.{doc_id}"
            # Only this object may be supplied to the verifier. No rationale or label is included.
            inputs.append({'id': identity, 'claim_id': c['id'], 'document_id': doc_id, 'claim': c['claim'],
                           'document': {'title': d['title'], 'sentences': [
                               {'index': i, 'text': text} for i, text in enumerate(d['abstract'])]}})
            gold.append({'id': identity, 'label': label, 'rationale_sets': rationale_sets,
                         'label_origin': 'SciFact expert evidence annotations for this cited abstract; empty annotation maps to insufficient information within this supplied text.'})
    output.mkdir(parents=True, exist_ok=True)
    for filename, records in [('inputs.jsonl', inputs), ('gold.jsonl', gold)]:
        (output / filename).write_text(''.join(json.dumps(r, ensure_ascii=True) + '\n' for r in records), encoding='utf-8')
    prepared = {'format': 'biograph-steward.provided-document-verification.v1',
                'created_at': datetime.now(timezone.utc).isoformat(), 'dataset': 'SciFact', 'split': split,
                'source_manifest_sha256': sha(source / 'source_manifest.json'), 'source': manifest,
                'claims': len(claims), 'claim_abstract_pairs': len(inputs),
                'selection':selection,
                'duplicate_citations':duplicate_citations,
                'label_counts': dict(Counter(g['label'] for g in gold)),
                'inputs_sha256': sha(output / 'inputs.jsonl'), 'gold_sha256': sha(output / 'gold.jsonl'),
                'protocol': 'Given one claim and one cited abstract; classify source support and cite sentence indices. This supplies citation candidates and does not measure open-corpus retrieval.',
                'limitations': ['Development evaluation only; no independent final test result.',
                                'Do not supply gold.jsonl or this label-count manifest to the verifier.',
                                'Scores on these pairs are not official SciFact full-pipeline leaderboard scores.',
                                'Repeated claims/documents are grouped observations, not independent experiments.',
                                'Published benchmark contamination in foundation-model training cannot be excluded.',
                                'Scientific text entailment does not establish clinical truth or graph link-prediction improvement.'],
                'status': 'prepared_not_evaluated'}
    (output / 'manifest.json').write_text(json.dumps(prepared, indent=2) + '\n', encoding='utf-8')
    return prepared


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--split', choices=['train', 'dev'], default='dev')
    parser.add_argument('--download', action='store_true',help='Download the official release/license into a new source directory.')
    parser.add_argument('--exclude-documents-from',type=Path,help='Prepared input JSONL; exclude whole claims touching any of its documents.')
    args = parser.parse_args()
    if args.download:
        result=download_source(args.out)
        print(json.dumps({'archive_sha256':result['archive_sha256'],'files':result['files']},indent=2))
    else:
        if not args.source:parser.error('--source is required for preparation.')
        result = prepare(args.source, args.out, args.split,args.exclude_documents_from)
        print(json.dumps({k: result[k] for k in ['status', 'claims', 'claim_abstract_pairs', 'label_counts','duplicate_citations']}, indent=2))

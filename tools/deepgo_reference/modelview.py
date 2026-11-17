"""Assemble a new ordinary inference view of qualified publisher members.

The immutable original wrong-CC archive is preserved outside this derived view.
Only its MF/BP models and ontology texts are combined with the maintainer's
explicit CC correction. No model, pickle, annotation or reference is loaded.
"""
import argparse
import json
from pathlib import Path
import shutil

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output
from .archive import fingerprints, need, sealed
from .scores import ENSEMBLES

MAIN_MD5 = '5b5d0c25945cff446056ad4b3cd14b71'
CC_MD5 = '7cd657e30704141360b7bad1ed5b77a3'


def selected_paths(aspects, ontology=False):
    paths = {'go.obo', 'go.norm', 'go-plus.norm'} if ontology else set()
    for aspect in aspects:
        paths.add(f'{aspect}/terms.pkl')
        paths.update(f'{aspect}/deepgozero_esm_plus_{i}.th' for i in ENSEMBLES[aspect])
    return paths


def extraction(path, expected_sha256, expected_md5, expected_paths):
    path = Path(path)
    need(fingerprints(path)['sha256'] == expected_sha256, 'extraction receipt FILE differs.')
    receipt = json.loads(path.read_text())
    need(receipt['format'] == 'biograph-steward.deepgo-selected-extraction.v1'
         and receipt['content_sha256'] == digest({k: v for k, v in receipt.items() if k != 'content_sha256'})
         and receipt['archive']['md5'] == expected_md5,
         'extraction receipt/source archive differs.')
    need(set(receipt['files']) == expected_paths, 'extraction has unexpected/missing inference files.')
    for relative, spec in receipt['files'].items():
        target = path.parent / relative
        need(fingerprints(target) == {key: spec[key] for key in ('bytes', 'sha256', 'md5')},
             'extracted inference source changed.')
    return receipt


def assemble(main, main_sha256, corrected_cc, corrected_cc_sha256, output):
    main, corrected_cc = Path(main), Path(corrected_cc)
    sources = [(main, extraction(main, main_sha256, MAIN_MD5, selected_paths(('mf', 'bp'), True))),
               (corrected_cc, extraction(corrected_cc, corrected_cc_sha256, CC_MD5, selected_paths(('cc',))))]
    out = new_output(output, main, corrected_cc)
    files = {}
    for source, receipt in sources:
        for relative, expected in receipt['files'].items():
            need(relative not in files, 'publisher selection overlaps another source.')
            target = out / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with (source.parent / relative).open('rb') as src, target.open('xb') as dst:
                shutil.copyfileobj(src, dst, 8 * 1024 * 1024)
            actual = fingerprints(target)
            need(actual['sha256'] == expected['sha256'] and actual['bytes'] == expected['bytes'],
                 'derived modelview copy differs.')
            files[relative] = {**actual, 'archive_md5': receipt['archive']['md5'],
                'source_member': expected['source_member']}
    # Upstream issue16 demonstrates that a wrongly packaged CC model can have
    # a BP tensor shape that loads. Provenance and cross-aspect hash identity
    # are checked in addition to the eventual strict load_state_dict check.
    model_hashes = {}
    for aspect, indices in ENSEMBLES.items():
        model_hashes[aspect] = {files[f'{aspect}/deepgozero_esm_plus_{i}.th']['sha256'] for i in indices}
    need(all(not model_hashes[a] & model_hashes[b] for a, b in (('mf', 'bp'), ('mf', 'cc'), ('bp', 'cc'))),
         'cross-namespace byte-identical models require explicit upstream qualification.')
    result = sealed({'format': 'biograph-steward.deepgo-derived-modelview.v1',
        'created_at': utcnow(), 'source_receipt_files': [
            {'file': str(source.resolve()), **fingerprints(source), 'content_sha256': receipt['content_sha256']}
            for source, receipt in sources], 'files': files,
        'CC_source': 'Maintainer issue16 corrected-CC archive; original Zenodo CC weights never used.',
        'model_selection': {key: list(value) for key, value in ENSEMBLES.items()},
        'native_MLP_control': 'not available in either supplied inference archive',
        'models_or_pickles_deserialized': False, 'original_source_modified': False,
        'cross_namespace_model_hash_overlap': False})
    write_json(out / 'modelview.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('main', 'main-sha256', 'corrected-cc', 'corrected-cc-sha256', 'output'):
        parser.add_argument('--' + key, required=True)
    value = assemble(**vars(parser.parse_args()))
    print(json.dumps({'content_sha256': value['content_sha256'], 'files': len(value['files'])}))

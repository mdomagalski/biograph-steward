"""Append a public-reference assessment to an existing verified publication.

Copies aggregate receipts only. Does not fetch sources, fit a model, assign
biological labels, modify a graph or contact a hosted workbench.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from biograph_steward import scientific_assessment as module
from biograph_steward.file_utils import sha


def publish(base, reference, output, *, base_pin, reference_pin, opencell=None, opencell_pin=None):
    base, reference = Path(base), Path(reference)
    module.need(sha(base/'publication.json') == base_pin, 'base publication FILE pin differs.')
    manifest, _, files = module.load_publication(base)
    module.need(manifest['format'] in {module.FORMAT, module.FORMAT_V2, module.FORMAT_V3, module.FORMAT_V4},
                'select the original publication without a public-reference appendix.')
    kwargs = {}
    pins = manifest['operator_source_pins']
    if opencell is not None or opencell_pin is not None:
        kwargs.update(opencell_report=opencell, expected_opencell_pin=opencell_pin)
    if any('coess_'+k in pins for k in module.COESS_NAMES):
        kwargs.update(coessentiality_reports={k:base/name for k,name in module.COESS_NAMES.items()},
                      expected_coessentiality_pins={k:pins['coess_'+k] for k in module.COESS_NAMES})
    for role,filename in [('grounding',module.GROUNDING_FILE),
                          ('function_recovery',module.FUNCTION_FILE),('biored',module.BIORED_FILE)]:
        if role in pins:
            kwargs[role+'_report'] = base/filename
            kwargs['expected_'+role+'_pin'] = pins[role]
    result = module.publish({k:base/name for k,name in module.SOURCE_NAMES.items()}, output,
        expected_source_pins={k:pins[k] for k in module.ROLES},
        public_reference_report=reference, expected_public_reference_pin=reference_pin, **kwargs)
    module.need(sha(base/'publication.json') == base_pin
                and all((base/name).read_bytes() == raw for name,raw in files.items()),
                'original aggregate publication changed.')
    return {'publication':Path(output).name,'format':result['format'],
            'publication_file_sha256':sha(Path(output)/'publication.json'),
            'content_sha256':result['content_sha256'],'files':len(result['files'])+1,
            'source_graph_or_original_publication_modified':False}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--base-sha256',required=True)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--reference-sha256',required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--opencell',type=Path)
    parser.add_argument('--opencell-sha256')
    args=parser.parse_args()
    print(json.dumps(publish(args.base,args.reference,args.out,
                            base_pin=args.base_sha256,reference_pin=args.reference_sha256,
                            opencell=args.opencell,opencell_pin=args.opencell_sha256),indent=2))

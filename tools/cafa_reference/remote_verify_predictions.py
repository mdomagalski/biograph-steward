"""Observe complete remote prediction bytes against already sealed manifests.

Run over SSH on the named existing host. This does not read reference data or
modify any prediction. Its compact receipt can be pinned by local label release.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def observe(config):
    config=Path(config);cfg=json.loads(config.read_text());files={};manifests={}
    for path,expected in cfg['manifests_sha256'].items():
        p=Path(path)
        if p.is_symlink() or sha(p)!=expected:raise ValueError('Sealed producer manifest differs: '+str(p))
        source=json.loads(p.read_text())
        if source['future_GO_labels_read'] is not False:raise ValueError('Prediction producer boundary differs.')
        for name,spec in source['files'].items():
            if Path(name).name!=name:raise ValueError('Unexpected manifest relative name.')
            body=p.parent/name
            if body.is_symlink():raise ValueError('Symlink is not an immutable ordinary prediction.')
            actual=sha(body);size=body.stat().st_size
            if actual!=spec['sha256'] or size!=spec['bytes']:
                raise ValueError('Remote bytes differ from frozen manifest: '+str(body))
            files[str(body)]={'sha256':actual,'bytes':size,'expected_sha256':spec['sha256'],
                              'expected_bytes':spec['bytes'],'manifest_sha256':expected}
        manifests[str(p)]=expected
    return {'format':'biograph-steward.cafa5-remote-file-verification.v1',
        'remote_host':cfg['remote_host'],'observed_at':datetime.now(timezone.utc).isoformat(),
        'observer_code_sha256':sha(__file__),'observation_config_sha256':sha(config),
        'future_GO_labels_read':False,'source_files_changed':False,
        'manifests_sha256':manifests,'files':files}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True)
    print(json.dumps(observe(p.parse_args().config),indent=2,sort_keys=True))

"""Create an immutable AWS source bundle from a selected committed revision.

Only the existing core/container runtime and AWS bootstrap scripts enter the
bundle. Local .env files, credentials, scientific runs and Git metadata do not.
This command never contacts AWS or creates paid resources.
"""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

RUNTIME_PATHS = ('.dockerignore', 'Dockerfile', 'app.py', 'LICENSE', 'requirements-aws.txt',
                 'biograph_steward', 'scripts', 'deploy/aws/bootstrap.sh',
                 'deploy/aws/backup.sh')


def prepare(output, *, ref='HEAD', root=None):
    root = Path(root or Path(__file__).resolve().parents[2]).resolve()
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('Use a new release output directory.')
    commit = subprocess.check_output(['git', 'rev-parse', '--verify', ref + '^{commit}'],
                                     cwd=root, text=True).strip()
    for name in RUNTIME_PATHS:
        subprocess.run(['git', 'cat-file', '-e', commit + ':' + name], cwd=root, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    raw = subprocess.check_output(['git', 'archive', '--format=tar', commit, '--', *RUNTIME_PATHS], cwd=root)
    # Reject anything outside the declared runtime roots before a remote host
    # will extract it. The ordinary commit tree cannot introduce links here.
    with tarfile.open(fileobj=io.BytesIO(raw)) as source:
        for member in source.getmembers():
            name = Path(member.name)
            if (name.is_absolute() or '..' in name.parts or member.issym() or member.islnk()
                    or any(part in {'.git', 'runs', '.pharos_cache'} or part.startswith('.env')
                           for part in name.parts)):
                raise ValueError('Unexpected path or link in runtime archive: ' + member.name)
    output.mkdir(parents=True)
    bundle = output / ('biograph-' + commit + '.tar.gz')
    with bundle.open('xb') as destination:
        with gzip.GzipFile(fileobj=destination, mode='wb', mtime=0, filename='') as compressed:
            compressed.write(raw)
    receipt = {'format': 'biograph-steward.aws-source-release.v1',
               'created_at': datetime.now(timezone.utc).isoformat(), 'git_commit': commit,
               'bundle': bundle.name, 'sha256': hashlib.sha256(bundle.read_bytes()).hexdigest(),
               'bytes': bundle.stat().st_size, 'source_paths': list(RUNTIME_PATHS),
               'cloud_resources_created': False, 'credentials_included': False}
    (output / 'release.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref', default='HEAD')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.out, ref=args.ref), indent=2))


if __name__ == '__main__':
    main()

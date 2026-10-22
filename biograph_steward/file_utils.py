"""Shared file fingerprints and immutable output-directory checks."""
import hashlib
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def new_output(output, *sources):
    output = Path(output).resolve()
    if output.exists() or any(output == Path(s).resolve() or Path(s).resolve() in output.parents or output in Path(s).resolve().parents for s in sources):
        raise ValueError('Choose a new immutable output outside input directories.')
    output.mkdir(parents=True)
    return output

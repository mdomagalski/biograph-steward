"""Read canonical chromosome from unambiguous native HGNC cytoband locations.

This metadata gate does not estimate cancer-cell karyotypes or genomic distances.
HGNC documents location as a cytogenetic location; a range on the same chromosome
retains that explicit chromosome, while ambiguous locations remain unknown.
"""
import re

_LOCATION = re.compile(r"(?P<chrom>[1-9]|1[0-9]|2[0-2]|X|Y)[pq][0-9]+(?:\.[0-9]+)?"
                       r"(?:-(?:(?P=chrom))?[pq][0-9]+(?:\.[0-9]+)?)?\Z")


def canonical_chromosome(location):
    if not isinstance(location, str):
        return None
    match = _LOCATION.fullmatch(location)
    return match.group("chrom") if match else None

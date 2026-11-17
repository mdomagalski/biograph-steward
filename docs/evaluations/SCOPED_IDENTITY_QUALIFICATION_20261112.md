# Source-scoped identity qualification

An optional helper now qualifies stable identifiers explicitly supplied in one
source record, including cases where its symbol is also another gene's alias.
It does not change the frozen gene-only resolver or rescue historical labels
by looking up a plausible current identity.

This follows [HGNC's distinction between stable identifiers, approved symbols
and aliases](https://www.genenames.org/help/symbol-report/index.html). A symbol
can be ambiguous across publications; [HGNC recommends stable IDs](https://hgnc.genenames.org/useful/instructions-to-authors/).
The implementation reuses the captured registry, existing literal-protein
audit and canonical source-row digest rather than introducing another grounder.

## Completed source-only checks

| Source records inspected | Qualified identity context |
| --- | --- |
| Three captured HGNC records | Gene context only |
| Three captured UniProt records | Literal supplied protein and gene context |
| Three SIGNOR records containing a literal UniProt identifier | Literal supplied protein and gene context |

These **nine records cover three genes**. They are not nine independent
experiments, validated catalytic assertions or historical target rescues.

All **13 original historical target rows remain unresolved** under this
explicit-ID contract: they contain bare ATR, PRKACA or RAF1 labels and no native
stable target-ID field. Primary-source review added useful context, but did not
justify copying current registry IDs into those old rows. For example, an
[ATR study](https://doi.org/10.3390/ijms150712007) explicitly identifies the kinase
in its experimental context, whereas the inspected
[platelet study](https://doi.org/10.1182/blood-2013-07-512384) describes PKA-family
signalling without establishing catalytic-alpha specificity. Inaccessible
full texts and unopened supplements remain unknown.

There were **zero automatic rescues**, no reclassification of benchmark labels,
no activity inference or rescoring, and no change to saved graphs or reviews.
The [completed comparison](CURATED_SIGNATURE_RECOVERY_20261112.md) and its
exclusions remain intact. See the [aggregate qualification summary](scoped_identity_qualification_20261112_summary.json).

## Reusing the helper

`tools.kinase_utility.scoped_identity.qualify_scoped_identity` reads supplied
UTF-8 CSV/TSV bytes. The caller declares the native record-ID column, stable-ID
columns and exact unavailable-value markers. Supported namespaces are `HGNC`,
`ENSEMBL` for ENSG identifiers, and `UniProtKB`. It never guesses columns,
splits families, strips versions/isoforms or manufactures missing identifiers.

The binding must name the source and release, full-file SHA-256, native record
ID, positive data-record ordinal and canonical decoded raw-row digest. Example
Python usage in the [optional tool environment](../../tools/kinase_utility/README.md):

```python
import json
from pathlib import Path
from biograph_steward.cohort_mapping import load_registry
from tools.kinase_utility.pilot_methods import parse_sequence_reference
from tools.kinase_utility.scoped_identity import qualify_scoped_identity

_, registry = load_registry("/path/to/captured_registry")
sequences = parse_sequence_reference(Path("/path/to/captured_sequences.tsv").read_bytes())
result = qualify_scoped_identity(
    Path("/path/to/native_source.tsv").read_bytes(),
    binding=json.loads(Path("/path/to/record_binding.json").read_text()),
    delimiter="\t", record_id_field="native_record_id",
    identifier_fields={"HGNC": "reported_hgnc_id"},
    symbol_field="reported_symbol",
    unavailable_values={"reported_hgnc_id": ["", "NA"], "reported_symbol": ["", "NA"]},
    registry=registry, sequence_reference=sequences,
)
```

Replace the example column names and missing markers with the actual source
contract. Do not create an identifier column by resolving its symbol first.
There is no new identity CLI or automatic app import in this increment.

## Boundaries

Stale file/row bindings fail. Conflicting or unresolved present identifiers
prevent qualification and retain their audit details. Gene qualification never
chooses a protein, even if only one product is captured; an explicitly supplied
primary UniProt identifier receives the separate existing protein audit.

Source/release labels are caller declarations tied to exact bytes, not
authenticated publisher metadata. Correspondence does not establish citation
intent, assay constructs, catalytic truth or gene/protein equivalence. The
helper creates local provenance records, not new SSSOM mappings or a broader
standards-conformance claim. Native source rows and primary-review packets
remain private and retain their source rights; software licensing does not
relicense them.

Twelve synthetic contract tests and a separate software-agent review passed.
The private source-only audit accounts for every original exclusion; its
earlier incomplete record filter is preserved beside the corrected audit.
This closes an explicit-ID handling gap while leaving unsupported historical
identities unresolved. No biological accuracy gain was measured by this step.

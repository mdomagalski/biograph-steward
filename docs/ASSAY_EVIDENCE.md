# Qualified assay evidence inspection

The completed Lambourne assessment can now be published as an immutable,
source-qualified observation layer linked to its frozen Pharos lookup. This
implements the [literature reuse decision](literature/ASSAY_EVIDENCE_REUSE_20261025.md).
It is a local evidence publication, not an ordinary Pharos workbench run,
an IMEx-curated import, or a conformant MITAB/KGX export.

## What the publication contains

`evidence.json` preserves every nominated observation, including its original
assay/result/comparator row, complete saved Pharos pair-lookup record, original
AD/DB construct identifiers, branch-specific sequence confirmations, source
locators and file/record hashes. Its `bindings` identify the exact consumed
assessment. The unchanged `source/freeze` and `source/results` directories
preserve the original source tables, author preprocessing, license, audit data,
comparator and result receipts. Original full Pharos retrieval chunks are not
duplicated; their existing hashes and locators remain preserved.

`graph.json` uses the existing protein-ID and qualified-assertion code to
represent eligible observations with the local predicate
`biograph:has_assay_observation_with`. It retains all nominated protein nodes,
including isolates from excluded assays. Detection and nondetection have
different `measurement_qualifier` values. A failed, autoactivating or
sequence-unconfirmed assay remains an observation in the complete evidence
ledger but contributes no graph edge. This is not a positive/negative PPI graph.

Every assertion starts as a candidate; automatic acceptance and pruning counts
are zero. The ordinary guided protein-neighborhood template deliberately excludes
these observations so their context cannot be lost through traversal. There is
no writeback into a primary Pharos graph and no inference of cancer relevance.

Observation identity includes the study, protein pair and exact AD/DB construct
roles. Sorting the protein pair never assigns the first protein to AD. Both
the original constructs and the crosswalk are retained without silently choosing
a protein-to-construct orientation from a potentially one-to-many map.

The confirmed PSI-MI terms annotate the detection method and construct roles:
`MI:0018` two hybrid, DB/bait `MI:0496`, AD/prey `MI:0498`. The authors' human
Y2H-v1 label remains separate. `NCBITaxon:9606` describes the protein participants,
not the experimental host. Host, tissue and exact sequence are not inferred.
No direct-contact term, validated-assay term, curated negative-interaction flag
or confidence score is manufactured.

## Inspect and replay

Open `index.html` in the publication directory. It works offline without a model,
API server or GPU. Search by protein accession, filter by assay outcome or
Pharos lookup state, and select a pair to inspect the two-protein observation
view, original outcome, construct roles and full source records. The shortcut
**Detected + no resolved-profile match** filters the existing population; it
does not define an independently validated new-edge set.

The `publication.json` receipt hashes every included file and the projection
implementation. Verification checks those bytes, reuses the original assay
verifier, reconstructs the projection and compares both graph and HTML. It
requires the exact recorded source implementation and runtime; it does not
require the original input directory to remain in place.

```sh
python3 scripts/publish_lambourne_evidence.py publish \
  --freeze runs/lambourne_corroboration_20261025/freeze \
  --results runs/lambourne_corroboration_20261025/results \
  --out runs/lambourne_assay_evidence_20261025
python3 scripts/publish_lambourne_evidence.py verify \
  --out runs/lambourne_assay_evidence_20261025
```

The recorded publication already exists; use `verify` to check it. Publishing
again requires a new output directory outside the inputs, and remains a
derivative of the same consumed assessment. It is never a fresh scientific
evaluation. `runs/` is ignored by Git, so a fresh clone needs the saved source
packet as well as the code. Upstream source rights continue to apply.

## Scope and stop point

This increment ends at a replayable observation graph and inspection view. It
adds no source search, extraction pipeline, learner, model sweep or experiment.
The actual [publication check](evaluations/ASSAY_EVIDENCE_PUBLICATION_20261025.md)
records population accounting and validation.

The paper reports IMEx deposit IM-30553. The documented public API, with a
successful positive control, returned no matching record for the checked
publication/accession queries. This limits current reuse; it does not prove
that the study was never curated. If records become accessible later, reconcile
them against these source-qualified observations instead of counting them as
new independent evidence.

Preserving and exposing qualified evidence is a measured engineering property.
It does not prove that this layer improves prediction or answers a biomedical
user's question better. This consumed panel cannot independently validate its
own addition. General workbench attachment, broader standards exchange,
user-task evaluation and any independently justified improvement comparison
remain separate tasks; they are not bundled into this publication.

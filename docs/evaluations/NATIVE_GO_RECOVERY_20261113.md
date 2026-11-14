# Native GO annotation recovery — November 13

The existing replacement census has now been applied as a **separate native
GOA source layer**: 24 annotation records add 21 protein–GO concepts across
15 proteins and six previously absent GO nodes. This improves the qualified
annotation coverage available to the graph. It does not measure a gain in
independent biological accuracy or prediction performance. The
[machine-readable summary](native_go_recovery_20261113_summary.json) records the
graph counts, preserved payloads, source pins and actual HTTP/export checks.

## Result and preservation

| Inventory | Previous graph | Published derived graph |
|---|---:|---:|
| Original source evidence plus declared additions | 16,985 | 17,009 |
| Source assertions | 16,980 | 17,001 |
| Nodes | 9,865 | 9,871 |
| Retained evidence after the same exclusions | 16,687 | 16,711 |
| Retained assertions | 16,682 | 16,703 |

All **16,985 existing evidence payloads and decision rows remain unchanged**.
The original snapshot and STRING, MAP-IT and SIGNOR publication bytes are
preserved. Existing assertion IDs, evidence groupings, revisions, lifecycle
states and review histories also remain unchanged. The one explicit envelope
change is `evidence_extension_sha256` on existing extension assertions: it now
binds the combined source container, including GOA. An existing review bound to
the previous extension hash would cause publication to fail; reviews are never
dropped or silently rebound.

The 24 additions receive **abstain**, not automatic acceptance. The resulting
ledger has 5,051 existing keep decisions, 298 existing exclusions and 11,660
abstentions. Keep decisions record the existing source-qualification policy;
they are not independent biological truth labels. No previous decision is
reconsidered by this increment.

## Native annotations remain separate

The [complete 167-proposal census](GO_REPLACEMENT_CENSUS_20261113.md) selects
explicit active replacements supported by qualifying native experimental
annotations and absent as concepts from the retained GO graph. It excludes
unsupported or ambiguous contexts under the existing conservative policy.
Missing matches remain unknown; excluded annotations are not false labels.

The adapter adds `native_go_annotation` records using
`biograph:has_native_go_annotation`. Historical Pharos `go_annotation` rows are
not repaired or overwritten. The new records retain their own literal relation,
reference, evidence code, assigning database, date, raw GAF body, source line and
ontology term metadata. The native relations are `acts_upstream_of` (2 records),
`enables` (7), `involved_in` (8) and `located_in` (7).

This follows the official [GAF2.2 field definitions](https://geneontology.org/docs/go-annotation-file-gaf-format-2.2/).
In particular, relation, reference, evidence, taxon and product form are separate
fields. Multiple reference identifiers on one line can identify one reference;
they are not independent corroborating studies. Exact cohort membership does
not make an annotation colorectal-cancer-specific. For example, a qualified
TTN annotation can concern cardiac development.

In the [local derived workspace](http://127.0.0.1:8796/?run=goa_recovered_workspace_20261113&view=evidence#nativeGoaPanel),
open **Evidence → Recovered native GO annotations**.
Select a protein (TP53 is the default when available), keep **Inspect
candidates**, then click **Show native GO annotations**. Each evidence detail
exposes the recorded relation, evidence code, assigning database and references,
with the raw annotation line and provenance under **Technical source record**.
**Inspect source and recorded conditions**
opens the existing guided source reader. **Accepted only** should show no new
rows: the added assertions remain candidates.

## Provenance and replay

The source publication contains the complete original 4,078-row Pharos GO frame,
the 3,780 retained Pharos GO rows, the full replacement-census outputs, the
pinned ontology and the complete preserved native GO sidecar. This permits
replay of both candidate eligibility and concept overlap; a list containing
only the selected positive rows would not establish those conditions.

The source versions remain explicit: July 26, 2026 ontology and July 28 native
GAF generation, distributed in the August 5 release. They are not relabelled as
November data or asserted to be today's latest release. GO/UniProt GOA source
attribution and CC BY 4.0 terms remain attached, following the
[GO citation and license policy](https://geneontology.org/docs/go-citation-policy/).

Preparation uses existing source adapters, ordinary graph replay, Gold packet
export and full decision replay. It does not retrieve new evidence or run a
model. WikiPathways historical-content support was regenerated against the
**new exact graph bytes** using the same archived captures before publication.
The old history packet was not silently reused or omitted.

Preparation is preserved at `runs/goa_recovery_prepared_20261113/`. The completed
history-bound workspace is `runs/goa_recovered_workspace_20261113/`, with its
finalization receipt at `runs/goa_recovery_finalization_20261113.json` and full
recomputed history at `runs/goa_recovery_history_20261113/`. Final source and
decision replay passed, followed by the local browser walkthrough. The TP53
summary displayed its recorded relation, candidate status and exact PubMed
reference, with technical fields collapsed. The guided source reader preserved
the disease-context and source-reuse limits. This local
increment does not update the separate AWS reviewer workspace or its receipts.

### Delivery boundary — November 14

This remains an optional **complete local workspace**, not an installed shared
reviewer example. Its 412 ordinary files occupy 1,119,168,923 bytes and include
the original mixed-source baseline and history. The native GO publication adds
18 files (75,580,934 bytes), with CC BY 4.0 attribution and preserved local
provenance paths; the whole workspace is not a path-free, GO-only dataset.
The native GO consumers and UI are byte-identical to accepted hosted runtime
`a6a05ff`, so no app-runtime or biological-protocol rewrite is needed. A
November 14 read-only replay passed the complete workspace and GOA publication
checks and reproduced all three recorded answer hashes: TP53 candidates
(six records), ATM candidates (two), and TP53 accepted-only (zero).

The existing deployed reviewer-gateway configuration does not allow
`POST /api/native-go-question`, which the recovered-annotation form uses.
Permitted GET downloads alone would not make that form usable. The current
repository gateway template includes the route, but that does not establish
its deployment. Sharing this separate workspace would require a reviewed data
transfer, gateway update, acceptance and a new checkpoint. That optional
rollout is deferred for this delivery. The already hosted native GO source/QC
inspector and historical function-context inspector are separate capabilities;
neither silently adds these 24 annotations to the hosted 99-target workspace.

The actual HTTP acceptance run is preserved at
`runs/goa_recovery_acceptance_v2_20261113/`: TP53 returns six source records for
three assertions; ATM returns two records for two assertions; the accepted-only
view returns none. The downloaded candidate GAF is byte-identical to the census
export. The downloaded workspace ZIP contains 17,009 baseline evidence records,
16,711 retained records and 17,009 decision rows, including all 24 native
records grouped into 21 candidate assertions. These are delivery and source
fidelity checks, not an independent biological test.

Selected content pins:

| Artifact | Content SHA256 |
|---|---|
| GOA source publication | `e2a3ca8d637ab0777e73f65a2758775cc37b50ce1e4ab14aa05b6807c5168680` |
| Recovery preparation | `07d41865b85542493e6f7f649fd8717e5d8a5aca000c2bbae2c6c67a57874670` |
| Derived raw graph | `7294af86cff1b441daf7bef4d79adf997cefb937929d50088dbbfe5538becf31` |
| Derived retained graph | `fa281e64ce25cb5d4a9700aa5727e25b68410e7c37af36f147985998caf1b1a0` |
| Recomputed WikiPathways history | `bfbf20a40a7cc1f8e9104a0bd33ccfa7680baf46599d8a7bebcedd39186806bf` |
| Qualified workspace publication | `19533fd996d03aaa87b5b0f159ff6df4a084c6896d5ea01e4c74bfb34e66a5b5` |
| Finalization receipt | `9ce8873ad8b06f27eb806a0378011b0cd4e0110776e88c4792f82e18a5bc1706` |

These local hashes detect changes relative to saved receipts. They do not
authenticate the upstream publisher or establish scientific correctness.

## Reproduce with local preserved artifacts

Preparation can reuse the verified source publication, avoiding another source
packaging pass. Choose new output paths rather than overwriting these completed
artifacts:

```sh
python -m tools.go_qualification.publish_recoveries prepare \
  --census runs/go_replacement_census_20261113_v3 \
  --qualification runs/crc_go_ontology_qualification_20261112 \
  --retained-package runs/source_faithful_workspace_20261113/source_retained_package \
  --context runs/crc_go_context_qualification_v3_20261112 \
  --publication runs/goa_source_publication_20261113 \
  --census-sha256 d11a1c12d720e900e15d8169a45742d259594d935a9515bfc43856760700dca1 \
  --output NEW_PREPARATION

python -m tools.go_qualification.publish_recoveries finalize \
  --prepared NEW_PREPARATION --history NEW_BOUND_HISTORY \
  --history-sha256 NEW_HISTORY_CONTENT_SHA256 --output NEW_WORKSPACE
```

`prepare` writes `goa_publication/`, `raw_run/`, `packet/`, `decisions.json`,
`retained/` and `recovery_preparation.json`. It intentionally publishes no app
workspace. `finalize` requires a newly graph-bound history proof and rechecks
the preparation inventory before creating a separate qualified workspace.
Both steps run on CPU with preserved local data; neither requires Brev, a GPU
or an LLM. Source data are separate from the code checkout.

The core regression run passed 2,009 tests with 36 optional skips. Final source
download changes then passed 68 affected tests, including five HTTP tests using
real synthetic GOA publications without patched source readers. All 65 browser
unit tests passed before copy polish; the six native GO UI tests passed again
on the final copy and disclosure layout. The staged-change scope and exact
code pins are recorded in
`runs/goa_integration_review_20261113/software_regression.json`. An isolated
installed-style core package also replayed the actual GOA source without the
research tools package or Biopython. The walkthrough above is an assisted
software check, not independent colleague review.

Nine invented-data orchestration tests exercise full graph/Gold replay,
existing payload and decision preservation, collisions, changed inputs,
extension-bound review refusal, unrelated review preservation and finalization
isolation. The source adapter has its own proof-replay tests. These are software
integrity tests, not biological validation results.

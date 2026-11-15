# Public references in the assessment view

The existing **Compare** view now supports a separately named, read-only v5
assessment. It brings the [public-reference comparison](PUBLIC_GOLD_REFERENCE_RESULTS_20261115.md)
and [OpenCell source-separation check](opencell_localization_20261115/summary.json)
into the app. The previous v1–v4 publications keep their original source bytes,
summaries and HTML. This changes presentation and saved-source access; it does
not assign new biological labels or modify a graph.

## What the results mean

| Task | Captured Pharos | Added/native view | Qualification |
| --- | --- | --- | --- |
| Detailed HOU location labels, 31 matching proteins | 41/51 recovered | 44/51 recovered | HPA provider overlap affects the gained labels; 68/99 proteins have no matching reference. |
| OpenCell imaging comparison categories, 23 matching proteins | 30/40 recovered | 31/40 recovered | Same result after excluding HPA support and explicit OpenCell study references; 76/99 proteins have no library match. |
| Human-reviewed cancer claim/evidence projections | No matching claim layer | Two exact matching evidence records out of 46 | Shared CIViC/study lineage and one human reviewer. All 41 complete clinical assertions remain unassessed. |
| MitoCarta inventory control, 98 gene units | Same result in every arm | Same result in every arm | Two inventory-positive, one explicitly outside the inventory and 95 unknown. |
| STRING functional versus physical networks | Functional source | Separate physical source | Every fixed panel is retained. Physical filtering removes some conflicts and loses supported positives. |

HOU and OpenCell use different categories and denominators; do not pool their
counts. OpenCell is already represented in HOU and earlier project metadata.
The new source-exclusion check addresses explicit provider reuse but is **not a
fresh blind test**. It concerns tagged HEK293T cells; complete tested sequence
identity and hidden historical citation reuse remain unverified. The single
additional recovered OpenCell category has a PINC/TAS annotation dated 2003,
not newly discovered biology.

All positive-only reference results preserve additional output locations as
**truth unknown**. Recovery percentages do not estimate precision, whole-graph
accuracy, drug efficacy or direct physical binding. Interaction AUROC tables
show positive and negative class counts, including the very small canonical
negative denominator. No automatic acceptance or universal pruning follows.

## Reproduction and app use

`scripts/publish_public_reference_assessment.py` reuses the existing verified
publication loader and publisher. Supply an original v1–v4 publication, explicit
SHA256 pins for its manifest and the public aggregate, and optionally the
OpenCell aggregate plus its pin. Use a fresh output folder under `runs/`:

```sh
python3 scripts/publish_public_reference_assessment.py --help
```

Open **Compare**, select the saved public-reference assessment, and read its
location tables. Expand the clinical review/source lineage, every fixed PPI
panel and OpenCell grades for detailed qualifications. Downloadable source
receipts reproduce the displayed aggregates. They contain no individual
reference cases, sequences, clinical passages or model predictions.

The prepared local publication is
`runs/scientific_assessment_public_reference_20261115_v3`. Its final deployment
status and runtime are recorded separately in the delivery receipt. Earlier
local v5 prototypes are retained and are not deployable against the revised
renderer. A code-only checkout does not contain private saved workspaces.

The richer native-location example remains an ordinary question/source/export
workflow, described in [the source profile guide](NATIVE_LOCATION_WORKSPACE_20261115.md).
The separately captured native STRING physical source is an additional named
question profile. Functional evidence and source review states stay available.

These saved-data features require no model, GPU, Brev instance or fresh source
retrieval. Hosted installation, software release and teammate usability feedback
are separate delivery checks.

## GO evidence codes: context, not a confidence hierarchy

GO's [guidelines for external resources](https://geneontology.org/docs/guidelines-external/)
recommend including valid evidence codes when evaluating existing annotations.
They explicitly reject a hierarchy of evidence codes and separately advise
omitting RCA annotations while that code is being retired. An experimental code is not
automatically a correctness verdict; several source rows are not independent
confidence votes.

A direct recount of the saved native-location projection found these **3,309
candidate rows**, with each displayed code agreeing with its preserved native
record:

| Code | Admitted source rows |
| --- | ---: |
| EXP | 136 |
| HDA | 15 |
| HTP | 2 |
| IDA | 448 |
| IMP | 10 |
| IPI | 2 |
| NAS | 9 |
| TAS | 2,687 |
| RCA | **0** |

“All eligible codes” means no additional evidence-code filter within the fixed
identity, relation, taxon and context profile; it does not mean every valid GO
annotation fits that profile. The experimental-only sensitivity discards
support: HOU recovery changes from **44/51 to 42/51**, and OpenCell grades 2+3
from **31/40 to 23/40**. These bounded comparisons do not establish a general
quality ranking between evidence types.

No RCA row is present in this delivered candidate example. Its frozen profile
does not implement a dedicated RCA exception: a future capture containing RCA
needs qualification against the current GO guidance under an explicitly
versioned profile. This check changes no source, graph, frozen policy or score,
and does not constitute a new complete GAF validation.

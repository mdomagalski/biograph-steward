# STRING study independence and confirmation decision

October 27, 2026. **The source audit is complete; independence of the current
12.5 comparison remains unresolved.** No newly reviewed public dataset qualifies
as an immediate independent confirmation of its measured human Y2H endpoint.
The selected follow-up is one older-source temporal control, with its archive
interface verified. That control has not captured the cohort or generated new
performance results.

**Subsequent execution:** the [separately frozen temporal control](STRING_TEMPORAL_CONTROL_20261027.md)
is now complete. This document remains the earlier source/reference decision;
its metadata and capability checks did not themselves generate cohort scores.

The [completed component result](STRING_COMPONENT_COMPARISON_20261027.md)
remains unchanged: full-panel AP 0.172827 → 0.190056, with numeric coverage
88.3% → 72.4%. This audit does not promote that result to a validated biological
or Steward-specific improvement.

## What the source establishes

| Question | Supported finding | Limit |
|---|---|---|
| Does STRING use HuRI? | The [official scoring documentation](https://string-db.org/help/scores/) explicitly names it among experimental inputs. | This does not identify each nominated pair's actual contributing study or quantify its score contribution. |
| Can Complex Portal be an independent physical-score gold set? | The same documentation names it as physical-score calibration data. | A fresh download or database label does not remove calibration dependence. |
| Does the public API expose study-level provenance? | The [supported method inventory](https://string-db.org/help/api/) advertises aggregate network scores, not an experimental-set/publication-lineage endpoint. | A missing publication field cannot establish that a study was absent from scoring. |
| Is the actual release schema richer than the web description? | A bounded prefix of the official 12.5 SQL dump supplies `sets_items.network_type`, `sets_scores` and `proteins_component_scores.component_link`. | The general [web schema](https://string-db.org/help/database/) is not an exhaustive release-specific contract. These are schema capabilities, not retrieved pair-study records. |
| Do collection dates settle the cutoff? | Several complete `collections` rows say August 2022; resource-publication IDs are also recorded. | These comments do not attest the latest included experiments. Resource citations are not a complete study bibliography. |

For identified experimental reuse, the actual schema supports the route
`sets_pubmedrefs → sets → sets_items`, interpreted with release-specific
`network_type` and `sets_scores`. A matched publication/set/pair can demonstrate
overlap in released evidence metadata; it does not alone prove a nonzero
contribution to the captured aggregate score. An absent match would not rule out text mining, transferred
evidence, calibration, missing metadata or restricted source content. Aggregate
channel scores are insufficient to reconstruct a study-removed counterfactual.

The [official manifest](https://version-12-5.string-db.org/cgi/download) offers
the full evidence dump at 53.3 GiB (57,225,579,743 bytes), excluding restricted
data, without advertised small table-specific downloads. We retrieved only its
first 256 KiB and five documentation pages: six requests, 642,003 response
bytes. All 16 table definitions and the complete 12-row collections block were
recovered; later assay/evidence rows were not parsed. Downloading the complete
dump merely to search for absent PMIDs would not close all independence paths.

The existing panel has **285/376 detections with a HuRI overlap flag**. Those
flags are potential pair exposure under the preserved identity mappings, not
proof of construct equivalence. Neither the unflagged stratum nor the current
metadata capture is a newly independent test set. Lambourne/INMC-specific input
inclusion remains unresolved.

## Public reference checks

This was a focused methods/artifact check, not an exhaustive new literature
census. No new pair-outcome files were opened or candidate models installed.

| Candidate | Existing capability worth reusing | Why it is not selected as current independent confirmation |
|---|---|---|
| [Ås: PPI-bias](https://github.com/JoelAAs/PPI-bias), [September 2026 data release](https://zenodo.org/records/22675356) | Study-specific search spaces, inferred tests and detection posteriors; MIT code. | Reanalysis of IntAct observations. Inferred nondetection/search-space assumptions and reuse must be audited; release date does not make the underlying experiments new. Dataset redistribution terms were not established here. |
| [Flock official code/methods](https://github.com/TernaryTx/flock) | Versioned structural/contact processing and explicit leakage rules; MIT repository. | Structural positives, geometry/literature-derived negatives and IntAct-based filtering differ from our complete measured Y2H panel. Its documented April 2026 IntAct access and co-folding cutoff do not exclude STRING 12.5 source reuse. No dataset import is selected. |
| [BioGraphBench-PPI primary abstract](https://pubmed.ncbi.nlm.nih.gov/42889397/) | Explicit random, degree-matched and two-hop sampled-nonedge contracts illustrate evaluation sensitivity. | STRING/BioGRID reconstruction with generated nonedges measures a different endpoint. Cross-resource no-overlap is not independent measured experimental truth. No code/data reuse was selected or license inference made. |
| HuRI, BioGRID/IntAct aggregates and Complex Portal | Useful source-attribution and qualified-evidence resources. | Known STRING input/calibration routes, mixed endpoints and incomplete negatives prevent treating a different database name as an independence certificate. |

No newly checked candidate supplies an immediately qualified independent
replacement. This is a bounded negative finding, not a claim that no suitable
dataset can exist.

## Selected follow-up: one temporal control

The [official version history](https://string-db.org/cgi/access) places STRING
12.0 from July 26, 2023 until 12.5 on September 29, 2026. The
[scoring documentation](https://string-db.org/help/scores/) states that networks
are fixed within a release. The [Lambourne methods](https://www.nature.com/articles/s41467-026-70942-x)
describe selecting human tests from Zhang's 2024 prediction release, then
restricting to its 2025 published set. This supports checking a predictor source
predating that panel's selection. The supplied chronology is stronger than
assuming a newly curated old paper is a new experiment.

**Use archived STRING 12.0 as a temporal development control against the same
consumed assay panel.** This can address whether a similar native-source
ranking difference appears with an earlier source. It does not make the panel
unseen, certify novelty of its pairs, eliminate earlier HuRI evidence or isolate
Steward's contribution. A between-release score change also confounds data and
method updates; it cannot quantify how much came from this study's ingestion.

The archived API capability check completed four small calls on the already
consumed TAS1R2–TAS1R3 pair. The endpoint reports 12.0; exact queries map to two
human representatives, and both functional/physical calls return valid native
13-column rows with score 0.998. Equality on this one pair is not a cohort
result. The [12.0 API contract](https://version-12-0.string-db.org/help/api/)
supports separate `network_type=functional` and `network_type=physical` calls.
It is not the newer 24-column typed overlay; the 12.5 parser must not silently
interpret it. This is the verified remaining adapter difference.

Before cohort access, bind the 12.0 adapter, mapping/duplicate/missingness checks
and actual implementation hashes to a separate executable protocol. Keep all
3,222 nominations and the same 2,676 eligible pairs; preserve constructs,
exclusions, source absence and exposure strata. Reuse the fixed full-panel AP
policy and jointly numeric secondary policy within 12.0, reporting actual
coverage and denominators. Its jointly numeric subset can differ from the
1,938 pairs in 12.5. Do not sweep thresholds or versions. Declare the separate native-network versus
typed-overlay boundary and any runtime incompatibility before scoring.
Retain the original 12.5 packet and result unchanged.

The temporal control is selected **after the consumed 12.5 result** and is a
development sensitivity check. It cannot serve as unseen independent
confirmation. A stronger prediction claim still needs a separately justified
measurement reference and a same-information comparison of Steward's graph
intervention. The four reserved IntAct studies remain a different source-fidelity
task and were not opened to fill this gap.

## Captures and verification

- Metadata: `runs/string_independence_metadata_20261027_attempt_01/`; raw prefix,
  five source pages, receipts, actual DDL and collections. `report.json` SHA-256
  `f8b42b3ed0e5bd365a5bc55b399fa65d8e723aac636093a48ab293b0a1fd1029`.
- Archive capability: `runs/string_temporal_capability_20261027_attempt_01/`;
  four raw API responses, exact parameters/headers and response hashes.
- [Tracked summary](string_reference_independence_20261027_summary.json): exact
  source paths/hashes, reference decisions and completed versus pending checks.

Offline metadata replay validates all six bodies and re-extracts the same
16 definitions and 12 collections. Archive response hashes, exact mappings,
pair/species and scores were independently rechecked locally. Existing frozen
implementation files and the original metric packet remain byte-identical.
No paid compute, model run, new biological scoring or app UI change was made.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  runs/string_independence_metadata_20261027_attempt_01/verify.py
```

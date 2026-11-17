# Scoped CIViC variant–therapy evidence

The v0.6.2 [study and treatment context display](STUDY_CONTEXT.md) adds per-record levels, study titles, original descriptions and shared-source counts beside summaries, with a source-bound context TSV export.

Implemented and live-checked October 15, 2026. This is a deterministic research inspection workflow, with source-specific response annotations and explicit local human review. It is not a treatment recommendation, a source-paper entailment checker or a prediction result.

## Use in the app

1. Open a saved live Pharos cohort containing KRAS (`UniProtKB:P01116`).
2. Choose **KRAS molecular profiles and therapy response — CIViC** under **Research question**.
3. Retrieve the scoped source. This writes a new run, preserving the original Pharos snapshot and review events.
4. Select a complete molecular profile, therapy-containing records, evidence view and display limits. Accepted-only evidence is the default. Candidate exploration never changes a review state.
5. Follow a summary reference to the complete source record, publication, raw response locator and Pharos-overlap report. The existing assertion passport supports persistent human decisions.

A saved URL includes the source run and question ID. Both source hashes and the current graph/review basis must match before an answer is displayed. A review creates a new run and clears the answer; rerun the question to use the new state. Historical question exports remain intact.

### Optional literature discovery

Source details and the evidence passport offer **Explore related literature · Linked Discoveries** beside explicit PubMed references. The link opens NLM's documented paper-neighborhood interface in a new tab. No request occurs until it is selected, and no source records, answer hashes, graph edges or review decisions change. DOI-only or malformed references do not produce a discovery link.

The [October 28 pilot](evaluations/LINKED_DISCOVERIES_PILOT_20261028.md) tested the two PMIDs in the saved G12D example. This supports literature navigation, not automatic scientific verification. Related publications, citation links and different-looking findings require context review before contributing biological assertions. [NLM's guide](https://linkeddiscoveries.ncbi.nlm.nih.gov/userguide/) documents the service; [NIH](https://www.nih.gov/news-events/news-releases/nih-launches-new-pubmed-tool-strengthen-research-replication-reproducibility) states that it does not determine study quality or successful replication.

## Exact source scope

| Item | Policy |
|---|---|
| Gene | CIViC gene resolved through `NCBIGene:3845` (human KRAS); profiles must contain that gene in their variant feature records. |
| Protein join | CIViC `myGeneInfoDetails` Swiss-Prot cross-reference to an exact retrieved Pharos protein ID. No symbol-only fallback. One-to-many mappings remain a list. A missing mapping excludes response items with a reason. |
| Disease | Exact CIViC disease resolved by `DOID:9256`, Colorectal Cancer. It is not merged with Pharos colorectal adenocarcinoma (`MONDO:0005008`). No subtype transfer or disease equivalence is inferred. |
| Therapy | Ingredient identities resolved by NCIt `C1723` (cetuximab) and `C1857` (panitumumab). API queries use the exact CIViC therapy IDs. |
| Evidence | `PREDICTIVE`, source editorial status `ACCEPTED`, molecular-profile name search `KRAS`, followed by identifier-based local checks. Submitted/rejected source items are outside the pull. |
| Bounds | 1–200 items per therapy; default 100, pages up to 50. Counts, pagination exhaustion, caps and inconsistencies are recorded. Duplicate evidence IDs retain every raw response locator. Conflicting versions abort publication. |
| Failures | Partial GraphQL errors, invalid schema, ambiguous resolution and stalled pagination fail explicitly. No synthetic fallback or TLS bypass. |

Named regimen entities that do not contain the selected ingredient therapy IDs are outside this first scope. Other colorectal disease terms are not searched. Count reconciliation describes these filters, not all CIViC content or the literature.

The live API's `variantHgvs` field failed for some items despite its non-null schema declaration. The adapter omits it rather than accepting partial GraphQL data. CIViC variant/profile IDs, names and the complete raw profile expression are retained; genomic allele normalization is not implemented.

## Assertion semantics

One response assertion connects a **complete molecular profile** with a **complete therapy set**. It preserves exact disease, source significance, evidence direction, variant origin, evidence type and therapy interaction type. It does not split a complex profile or combination/sequential/substitute treatment into isolated variant/drug effects. Context in curated statement text remains inspectable; structured assay, cohort and experimental species extraction is not implemented.

Identifiers prefixed `CIViC.molecularprofile:` refer to source profile IDs. `biograph:therapyset:` identifiers hash the sorted CIViC therapy members and interaction type; these are local sets, not chemical-equivalence mappings. `biograph:has_reported_therapy_response` is a project-local source-annotation predicate, not a validated Biolink relation.

Evidence direction is part of assertion identity: **DOES_NOT_SUPPORT sensitivity is not converted to resistance**, and refuted resistance is not converted to sensitivity. Evidence level/rating and publication remain source metadata, not model confidence. Multiple records can support one qualified assertion, without being counted as independent experiments.

Flagged, deprecated/retracted, pending-revision, incomplete, unmapped or unsupported-semantic records are retained in the source snapshot and listed with exclusion reasons. No assertion is automatically accepted because CIViC labels its source record ACCEPTED. Local human decisions use the existing lifecycle and additionally bind to the CIViC snapshot hash.

The answer flags differing response annotations/directions under the same profile, disease, variant origin and therapy set. These are review alerts, not adjudicated contradictions: clinical and preclinical conditions may differ. Alerts inspect the full selected evidence view even when display caps omit the relevant records.

## Overlap with Pharos

`civic_overlap.json` compares qualified identities and explicit PMID references against the retrieved Pharos baseline. Supporting-record references and target-linked discovery references are reported separately. A shared PMID alone does not prove an identical claim. An absent reference does not establish independent evidence, particularly when Pharos has uncited disease summaries or capped publication discovery.

Newly represented variant/therapy detail is labeled **additional qualified detail**, not verified new evidence. Underlying-study independence remains unresolved. This increment does not fetch papers, recover uncited DisGeNET source records or claim that different publications are independent experiments.

## Source and export contract

The primary `snapshot.json` remains unchanged. A new `civic_snapshot.json` sidecar stores the exact scope, raw responses, retrieval times, coverage, source license, flattened evidence records and content hashes. Every flattened record is checked against its raw response pointer. Replay, saved-run reopening and new review runs retain the sidecar. `civic_report.json`, `civic_overlap.json` and `civic_raw_responses/` are included in the source-run ZIP.

The live API exposes no release ID used by this adapter. The manifest explicitly records a null source version; snapshot/response hashes and retrieval times identify this pull. Question exports include `question.json`, `summary.txt`, `paths.tsv` and `report.html`, with both source hashes, current review basis, full cited source records, bounds and limitations. Full source archives remain in the separate source-run ZIP.

## CLI

```bash
# Public live retrieval; writes a new run.
python3 app.py civic --run runs/crc_pharos_01 --max-items 100 --out runs/crc_civic_01

# Replay an already retrieved sidecar without network access.
python3 app.py civic --run runs/crc_pharos_01 \
  --snapshot runs/crc_civic_01/civic_snapshot.json --out runs/crc_civic_replay_01

python3 app.py therapy-question --run runs/crc_civic_01 \
  --profile all --therapy both --view candidates --out runs/therapy_question_01
```

Omitting `--view` selects locally accepted evidence only. An exact profile selector looks like `CIViC.molecularprofile:81`. `replay` also supports `--civic-snapshot` together with the original snapshot and optional review events. A run already containing CIViC cannot be enriched again: source-refresh reconciliation is subsequent work.

HTTP: `POST /api/civic` takes `run_id` and optional `max_items`; `POST /api/therapy-question` takes `run_id`, `profile`, `therapy`, `view`, `max_results` and `max_paths`. Unsupported fields are rejected. Saved answers use the existing question/download routes.

## Live validation

The October 15 source pull returned **46 cetuximab matches and 20 panitumumab matches**, with nine items occurring in both pulls: **57 distinct source items**. Both exact-scope queries reconciled their reported totals. **46 items** passed the conservative inclusion checks; **11** were excluded for pending source revisions. They form **41 qualified response assertions across 20 molecular profiles**, all initially local candidates. Two comparable profile/therapy groups have differing annotations requiring study-context review.

Of the retained items, one shares an explicit PMID with retrieved Pharos publication discovery, and 45 have no matching explicit baseline reference. No item is claimed to be verified independent evidence. These local artifacts are in ignored `runs/`, not bundled with a fresh clone:

- Source: `runs/civic_kras_crc_source_20261015/`
- Enriched run: `runs/crc_civic_final_20261015/`
- Saved example: `runs/civic_g13d_final_20261015/` (focused G13D example)

**149 automated tests passed**, including bounded mock retrieval, completeness/caps, duplicate/conflicting records, raw-source integrity, profile/therapy preservation, direction handling, conservative exclusions, source mapping, overlap, local review, immutable exports, CLI and HTTP. Browser checks verify saved reopening, source/publication passports, review navigation, accepted-empty results and candidate exploration. No live biomedical assertion was accepted during testing.

## References and terms

- [CIViC GraphQL API and anonymous rate limit](https://docs.civicdb.org/en/latest/api.html)
- [Evidence model](https://docs.civicdb.org/en/latest/model/evidence.html) and [molecular-profile conditions](https://docs.civicdb.org/en/latest/about/faq.html)
- [CIViC content license: CC0-1.0](https://docs.civicdb.org/en/latest/about/faq.html); source publication text and linked third-party content have their own terms.

Current development priorities are in the [build plan](BUILD_PLAN.md). The INMC investigation is separate from this scoped CRC inspection workflow; neither source counts nor qualified detail establish predictive improvement.

Local verified example: `http://127.0.0.1:8766/?run=crc_civic_final_20261015&question=civic_g13d_final_20261015`.

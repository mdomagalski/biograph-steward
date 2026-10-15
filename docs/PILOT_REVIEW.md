# Three-case pilot review — October 15, 2026

These are **AI-prepared source-check notes**, separate from the blank human reviewer worksheets. They do not approve scientific claims, change assertion states, or supply evaluation gold labels. The three cases are `g13d-cetuximab`, `g13d-locally-accepted` and `single-drug-only`. Review their actual output, scope plan and underlying sources before completing the source-bound TSVs described in [EVALUATION.md](EVALUATION.md).

## Candidate G13D/cetuximab question

The enriched graph returns qualified candidate annotations with differing directions. Pharos has a source gap for this specific molecular-profile/therapy query. Additional coverage alone does not establish correctness or clinical usefulness. Check that the output preserves complete KRAS G13D profiles, DOID:9256, complete therapy sets, local candidate state and negated annotations.

The ten scoped CIViC items refer to eight publications. Items 145/306 share a publication, as do 6320/6322; they are not independent studies. Two source items (3878 and 3882) were excluded because of pending editorial revisions, not because their scientific findings were disproved.

| CIViC items | Primary-source check | What still needs review |
| --- | --- | --- |
| 1180 | [PMID 26371285](https://pubmed.ncbi.nlm.nih.gov/26371285/) is titled as a phase II single-agent cetuximab study. The retrieved PubMed record has no abstract. | Verify detailed patient counts and outcomes in the underlying paper. Title/metadata and CIViC's statement alone do not establish support. |
| 1181 | [PMID 26812186](https://pubmed.ncbi.nlm.nih.gov/26812186/) combines randomized trials of anti-EGFR antibodies; its abstract reports no differential benefit for G13D versus other KRAS mutations. | Preserve the comparative, pooled anti-EGFR context. It does not isolate cetuximab monotherapy or prove absolute resistance in every G13D context. |
| 145, 306 | [PMID 20978259](https://pubmed.ncbi.nlm.nih.gov/20978259/) includes a retrospective clinical association and preclinical experiments. Its abstract calls for prospective confirmation. | Keep clinical and preclinical evidence distinct, retain comparators, and avoid converting the association into a treatment recommendation. |
| 3881 | [PMID 20619739](https://pubmed.ncbi.nlm.nih.gov/20619739/) describes cetuximab plus chemotherapy in a retrospective consortium. CIViC's description includes several co-treatment regimens. | The abstract does not verify the detailed G13D subgroup claim. A single-drug CIViC therapy list must not imply monotherapy. Full-text review is needed. |
| 6320, 6322 | [PMID 19223544](https://pubmed.ncbi.nlm.nih.gov/19223544/) primarily reports PIK3CA and aggregate KRAS findings in its abstract. CIViC cites individual patient rows for the G13D claims. | Check the supplemental table for patient-specific outcomes. Preserve cetuximab/panitumumab as a substitutes set and the original evidence direction. |
| 806 | [PMID 26623049](https://pubmed.ncbi.nlm.nih.gov/26623049/) describes a small retrospective subgroup; its abstract reports nonsignificant adjusted trends and mentions irinotecan co-treatment. | Do not restate a trend as confirmed benefit or a negated resistance annotation as proven sensitivity. Check treatment context in the [full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC4534836/). |
| 3878, excluded | [PMID 22722830](https://pubmed.ncbi.nlm.nih.gov/22722830/) concerns acquired resistance and KRAS mutations. | Check G13D-specific experimental details in the [full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC3927413/). Judge the revision-based exclusion separately from scientific validity. |
| 3882, excluded | [PMID 25666295](https://pubmed.ncbi.nlm.nih.gov/25666295/) concerns FOLFOX4 plus cetuximab and reports aggregate RAS results in its abstract. | Detailed G13D-specific support needs the paper. Preserve the combination context and distinguish the pending-revision exclusion from a scientific judgment. |

The first practical gap is **treatment and study context in the displayed evidence**. Original descriptions remain available, but a therapy-list filter cannot determine monotherapy or distinguish every co-treatment, study design and subgroup. A reviewer should decide which qualifiers are necessary before a summary is useful. Do not silently add inferred therapy ingredients to source records.

## Locally accepted counterpart

The same scope with `view=accepted` currently yields no locally accepted CIViC evidence. Confirm that the output says this rather than presenting an empty result as biological absence, resistance, or failed treatment. CIViC's editorial acceptance is not local scientific approval. This case checks review-state behavior; it does not independently validate the biological claims above.

## Monotherapy-only question

The current query contract cannot filter for monotherapy-only studies. The expected draft behavior is abstention with an explanation. Check that the live planner also abstains and does not answer a broader question after dropping the required condition. Even an apparent single-drug source list may conceal co-treatment in the underlying study.

## Complete the review

The packet contains only these three cases' rows, retaining the full evaluation's IDs/hashes. Leave identity fields and hashes unchanged. Enter your own name, notes and judgments; record an abstract/full-text locator before marking evidence supported. AI notes have not been copied into judgment fields. `uncertain` is valid when the underlying material is insufficient. Partial worksheets can be scored against their original full evaluation without grading the other cases.

After adjudication, prioritize explicit context display and unsupported-condition handling according to the observed errors. A separate held-out question set and the challenge's controlled prediction experiment are still required before claiming broader improvement.

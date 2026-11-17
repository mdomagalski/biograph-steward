# Expert labeled grounding assessment

BioGraph Steward now has a reproducible check of **entity identity in source
claims**, using released expert annotations rather than AI-authored correctness
labels. Native Gilda context reduces some false alarms but misses other errors.
It remains an optional review aid; no identifier replacement or graph pruning
is enabled by these results.

## Question and existing methods

The task asks whether a mention in a supplied evidence record refers to its
assigned human gene identity. It uses the curated mechanistic extraction corpus
released with [Bachman, Gyori and Sorger (2023)](https://doi.org/10.15252/msb.202211325),
the [official analysis repository](https://github.com/sorgerlab/indra_assembly_paper)
and [Zenodo release 7559353](https://doi.org/10.5281/zenodo.7559353).
The paper describes expert assessment by biomedical researchers. These are
curator-relative judgments about extraction, not independent experimental
confirmation of every biological mechanism.

The implementation reuses [Gilda](https://doi.org/10.1093/bioadv/vbac034) 1.6.1,
INDRA 1.24.0 and Adeft 0.13.0 through their native APIs. Three fixed arms use
the same inputs and resources: lexical matching, source-evidence sentence
context, and exact PubMed title plus abstract. No prompt variations, project
classifier training or fitted threshold were introduced. Both native classifier
stacks passed compatibility probes before the benchmark predictions.

## Source fidelity and evaluation boundary

All 5,709 curated statement/source pairs join to the released JSON corpus.
The primary frame contains 4,294 pairs with one complete payload and explicit
human-gene origin annotations. Other identities, multiple payloads or missing
origins remain outside this frame. The adapter uses per-evidence original
mention/grounding arrays; it does not substitute the assembled statement's
representative names. Native statement/source hashes and large integer IDs
are preserved without floating-point conversion.

The frame, resources, code and three arms were sealed before any curation
category or prediction was inspected. Connected statement, source, publication
and native entity-family groups separate 3,249 development cases from 1,045
reserved cases. Known reviewed-source groups were forced into development.
The exposure audit is not exhaustive, and Gilda/Adeft training-publication
overlap remains unestablished. The reserve is a project holdout, not proven
model-unseen independent biology.

The endpoint admits only unanimous native `correct` versus unanimous native
`grounding` annotations. Mixed labels, missing labels and other error categories
are excluded explicitly; duplicate curation rows are not independent votes.
No case is made negative because it lacks a database match. Unmatched
namespace/granularity, unavailable context and unavailable groundings preserve
their actual unresolved/error states.

Exact numeric citations produced 2,745 available publication contexts out of
2,748 requested. A pre-outcome audit corrected 670 cases where stale internal
reader IDs in `text_refs.PMID` had incorrectly vetoed a valid `Evidence.pmid`.
This follows INDRA's published native reader/disambiguation implementation. Both
original fields remain intact; competing valid numeric PMIDs remain unresolved.

## Reserved result

Of the 1,045 reserved source cases, **678** have eligible endpoint labels:
**80 grounding errors and 598 correctly grounded cases**. The other 367 do not
become negatives. Every arm resolves 575/678 eligible cases (84.8%) and leaves
103 unresolved, with zero runtime model errors.

| Fixed method | Correct error flags | False alarms | Precision of flags | Error recall over all 80 errors | False alarm rate over all 598 correct cases |
|---|---:|---:|---:|---:|---:|
| Native lexical matching | 31 | 25 | 55.4% | 38.8% | 4.18% |
| Native sentence context | 25 | 19 | 56.8% | 31.2% | 3.18% |
| Native publication context | 26 | 18 | 59.1% | 32.5% | 3.01% |

Publication context removes seven false alarms relative to lexical matching,
while losing five correct error flags. Sentence context has net reductions of
six false alarms and six correct flags. Native context disambiguation is available
for only 37 agent mentions across the full reserved frame. More surrounding
text does not supply a context model for every mention.

The full-denominator result above is primary. A separately reported common
resolved intersection does not replace it. No population confidence interval,
significance claim, whole-graph accuracy percentage or automatic pruning
benefit is inferred. Development results are retained separately: 2,226 admitted
cases, with publication flags 92 true/24 false versus lexical 90 true/33 false.
The reserved result was not used to tune or replace the method.

## Use and reproduction

The optional [grounding tools](../../tools/grounding_claims/README.md) preserve
source acquisition, frame preparation, context capture, fixed predictions,
label admission and scoring as separate steps. Core app startup still requires
only ordinary Python; Gilda/INDRA are not application dependencies. Existing
source graphs, reviews and the original reference are unchanged.

The private run directory is `runs/indra_claim_qualification_20261113`.
Its evaluation freeze is
`acb70606b94b90bbde8a2828e835678244a5c7e8ddac5b9533ed45b3a42c0c0a`;
the development and reserved evaluation seals are respectively
`27bada8c75a7f7722f9297cdf59e84e8936bb85321e5c088c8889cf075290204`
and `6c2ca75b6b95f591d115654443f4753d9f87685398c9f00fd072656eb478e2fb`.
Both partitions are now consumed. Their case-level source/label/prediction
files remain private under the dataset's **CC BY-NC-SA 4.0** terms. Aggregate
evaluation data retain that attribution and license; the project's own adapter
code is MIT. No unlicensed author analysis code or pickle was incorporated.

The [sanitized aggregate](expert_grounding_20261113_aggregate.json) contains
the full denominators and paired counts without case IDs, text or native tag
records. [Replay metadata](grounding_replay_20261113/metadata.json) supplies
source/resource hashes and the exact outcome-free reviewed-source token list.
The existing **Compare & assess** view displays the same separate component
when its saved `scientific_assessment_delivery_20261113` publication is supplied.
No raw benchmark data enter that app publication.
The [delivery acceptance summary](grounding_delivery_20261113_summary.json)
records the app, source-replay and regression checks separately from the
scientific result.

The [reproduction check](grounding_replay_20261113/reproduction_check.json)
executed the tracked streaming join and preparation commands against the actual
released corpus. All 4,294 complete prepared cases, source arrays, resolved
citations, component groups and split assignments exactly match the evaluation
frame. This replays source preparation, without reopening labels or rerunning
classification; receipt timestamps and paths differ as expected.

This closes the lack of an executed expert-labeled component evaluation.
Clinical claim truth, exact protein/isoform identity, causal direction and
independent whole-graph biological precision remain separate tasks.

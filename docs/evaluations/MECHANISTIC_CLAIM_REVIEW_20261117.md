# Expert-curated source-claim assessment

We now have a working assessment with public human-curator labels for both
correct and incorrect mechanistic source claims. On 134 evaluated claims, the
prespecified agreement rule between INDRA and Nemotron flagged **three
unsupported claims and no supported claims**, retaining all 64 supported
claims. This is a small, conservative triage result. It does not establish a
broad accuracy gain or justify automatic deletion from the primary Pharos graph.

[Readable aggregate report](mechanistic_claim_review_20261117/report.html) ·
[Aggregate JSON](mechanistic_claim_review_20261117/aggregate.json) ·
[Frozen protocol](mechanistic_claim_review_20261117/protocol.json)

## Reference and established methods

The reference is Bachman, Gyori and Sorger's
[2023 molecular-mechanism assembly study](https://doi.org/10.15252/msb.202211325),
its [official analysis repository](https://github.com/sorgerlab/indra_assembly_paper)
and [released data](https://doi.org/10.5281/zenodo.7559353). Human curators labelled
extracted source statements for errors including wrong relations, grounding,
polarity and negation. An incorrect extraction can concern a relationship that
is true under other conditions. These labels measure faithful representation
of the supplied sources, rather than universal biological truth.

We also checked why a generic noninteraction list cannot substitute for this
task. The original [MLH1/PMS2 study](https://pubmed.ncbi.nlm.nih.gov/10101297/)
distinguishes short PMS2-like products from the binding-competent PMS2 region.
The [AE1/ankyrin study](https://pubmed.ncbi.nlm.nih.gov/7798219/) distinguishes
the truncated kidney AE1 form from erythroid AE1. Removing the canonical
protein association on the basis of those construct-specific negatives would
discard relevant context. The selected benchmark instead preserves the
source claim's native conditions.

We use INDRA 1.24.0's native
[`CountsScorer`](https://indra.readthedocs.io/en/latest/modules/belief/skl_belief.html)
with one fixed logistic regression and its native raw source-count features.
Only the 368 development claims supply labels for fitting. Source vocabulary
is also development-only. The optional `SimpleScorer` uses native bundled
priors. Unavailable priors produce abstentions, with no repaired priors or
fallback predictions. Released statement belief scores are excluded.

The NVIDIA comparison uses the existing application transport and the running
`nvidia/Llama-3.1-Nemotron-Nano-8B-v1` model. One fixed prompt asks for a verdict
on every supplied evidence record. A claim is retained if any source supports
it, flagged only if every source fails, and left unresolved otherwise.
The secondary consensus flags a claim only when both CountsScorer and Nemotron
flag it. This rule was fixed before evaluation.

The model is a source reviewer in this assessment. It is separate from the
delivered agent that chooses source tools and builds question-specific graphs.
These measurements are not agent-caused protein-function prediction gains.

## Inputs and boundaries

The symmetric admission rule requires every original evidence record to be
uniquely bound, present in the existing human-gene extraction frame and reviewed
by curators. It admits 502 claims and 1,177 evidence occurrences:

| Split | Claims | Supported | Unsupported |
|---|---:|---:|---:|
| Development | 368 | 142 | 226 |
| Evaluation | 134 | 64 | 70 |

The evaluation set contains 131 connected source groups and 202 publications.
No development/evaluation group or validated publication identifier overlaps.
However, the underlying corpus and fixed split were previously used for a
grounding assessment. This is **retrospective reuse for a new endpoint**, not
a newly blinded reference. Model pretraining overlap is unknown.

The extraction frame's HGNC assignments do not independently establish human
biological context or correct grounding. Likewise, these curator-selected
examples do not estimate error prevalence in Pharos. Twenty-seven evaluation
claims have an accession cross-reference to at least one current cohort target.
That linkage is not a complete match to an assertion in the primary graph.

Full native statement JSON, n-ary complexes, conditions, sites, source-specific
agent annotations and all original evidence are preserved. Only the released
belief score is removed from model inputs. No curator tags or labels enter
model requests. The native server tokenizer verified every complete prompt:
the maximum was 6,403 tokens against a 16,384-token context window.

## Results

Abstentions remain in the retained reference graph. All methods share the same
134 claims. “Supported” below always means supported under the reference's
curation policy, which includes the author's accepted hypothesis and
activity-versus-amount categories.

| Method | Unsupported flagged / 70 | Supported flagged / 64 | Supported retained / 64 | Unresolved retained | Supported fraction of retained graph |
|---|---:|---:|---:|---:|---:|
| Retain everything | 0 | 0 | 64 | 0 | 64/134 (47.8%) |
| Native CountsScorer | 67 | 53 | 11 | 0 | 11/14 (78.6%) |
| Native fixed-prior SimpleScorer | 0 | 0 | 64 | 42 | 64/134 (47.8%) |
| Nemotron source review | 4 | 1 | 63 | 8 | 63/129 (48.8%) |
| Prespecified consensus | 3 | 0 | 64 | 8 | 64/131 (48.9%) |

The source-count model produces a purer but much smaller retained graph. Its
removal of 53 supported claims makes the default threshold unsuitable as a
general deletion rule. Nemotron is conservative but misses most unsupported
claims. The consensus avoids the model's one supported-claim removal, while
detecting only 3 of 70 unsupported claims. Three correct flags are too few to
claim reliable population-level pruning precision.

Paired whole-group bootstrap intervals use 10,000 resamples and the frozen
seed 20261117. For the supported fraction of the retained graph, the pointwise
95% intervals for improvement over retaining everything are:

| Method | Difference in percentage points | 95% interval |
|---|---:|---:|
| CountsScorer | +30.81 | [+8.04, +51.88] |
| Nemotron | +1.08 | [−0.42, +2.84] |
| Consensus | +1.09 | [0.00, +2.52] |

The model and consensus do not establish a strictly positive precision gain
under the frozen criterion. These are conditional corpus intervals, not
independent biological replication or multiple-comparison-adjusted results.
The full aggregate retains all five arms and their comparisons.

## What is delivered and used

The reproducible adapters are in
[tools/mechanistic_review](../../tools/mechanistic_review/README.md). The run
materializes a complete decision ledger and a typed retained reference graph
for every method. Retained claims keep all original evidence and conditions.
These are separate assessment graphs. No primary Pharos assertion, local
review decision, shared application permission or Neptune graph is changed.

The frozen protocol is SHA256
`fd362356cdde3f594ab221acf7c258dd22250b60b2a90edd3ea5171069120a7a`.
The sealed assessment content digest is
`5b1a7f68ea9113b59e233f79723020fed41a4f7cd650d76ce29023d48bd9d3c8`.
There were 134 model requests and 8,152 output tokens, with no retries, prompt
sweeps, response repair or tool execution. Eight inconsistent verdict/category
outputs abstained. Durable request intents prevent repeating a request after
an uncertain interruption.

The library is BSD-2-Clause and our adapters are MIT. The original reference
data retain **CC BY-NC-SA 4.0** terms. Raw source text, individual reference
labels and predictions remain outside the code archive and aggregate delivery.
Original source files, previous unsuccessful assessments and split boundaries
are preserved.

The practical next step is development-only error diagnosis and evaluation on
another appropriately matched reference. The current production workflow
continues to use source inspection and review proposals, with no broad
automatic biological deletion.

## Diagnosed errors and an existing upstream route

The low error recall is not explained by context truncation or by requiring all
sources to fail. All inputs fit, and the pooling rule matches the reference.
Of the 70 unsupported claims, **41 single-evidence claims were still retained**.
At evidence level, 141 of 189 curator-negative records received a support
verdict. Wrong relations and grounding errors were common among these misses.
The eight inconsistent verdict/category outputs are a separate contract issue,
not the main cause of false acceptance.

Source counts also have a capacity limit: only 32 distinct count-feature vectors
occur in the evaluation set. Ten vectors contain both label classes and cover
88 of 134 claims. A count model cannot distinguish the different sentence
meanings within an identical feature vector.

INDRA's installed
[EnglishAssembler](https://indra.readthedocs.io/en/latest/modules/assemblers/english_assembler.html)
can supply a readable canonical claim alongside the unchanged native record.
It rendered all 134 claims without inference. This makes entity and direction
mismatches easier to inspect. Its wording must remain subordinate to the native
type: its use of “binds” for a Complex must not become a direct-binding claim.
No accuracy benefit from this rendering has yet been measured.

The directly relevant author-maintained
[indra-belief-model project](https://github.com/gyorilab/indra-belief-model/tree/74e0ffe9ea21f6f11e906cee89a2091f45be2f7d)
provides a concrete reuse opportunity: canonical claims, grounding aliases,
contrastive examples and evidence review. It registers newer Bedrock Nemotron
models, but not our served Nano 8B or its calibration. Its correctness-only,
evidence-pair gold policy differs from this assessment's author-derived
complete-source policy. Its reported scores and calibrated thresholds cannot
be substituted for our measurements.

That project's newer human-curation metadata also provides a reference lead.
A label-blind overlap check found 393 of its representative 403 pairs, and
147 of its external 154 pairs, with a publication identifier and no observed
prior publication, statement-hash or source-hash overlap in our exposure
inventory. Entity-family independence and the data licensing remain to be
qualified. The representative set's completion is not proven representative,
and its whole-source recovery is incomplete. These are candidates for a
separate frozen **evidence-pair** assessment, not additional blind cases for
this already consumed full-claim test. Individual new labels were not opened
and no further inference was run.

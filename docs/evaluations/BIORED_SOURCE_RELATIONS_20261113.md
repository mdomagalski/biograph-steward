# Curator-reference literature relation assessment

The published BioREDirect specialist outperformed the tested NVIDIA source-audit
agent. The agent did not pass the frozen promotion rule and is not promoted to
the default decision path. This assessment measures whether an abstract reports
a relation; it does **not** estimate the biological correctness of all Pharos
edges or demonstrate improvement over the original Pharos graph.

## Fixed comparison

Before opening the selected relation labels, we froze the model artifacts,
controller, biological policy, 128 publication/pair selections and all predictions.
The reference is the authors' BioCreative VIII corpus, whose original entity,
relation and source-novelty annotations were doubly curated by NLM annotators.
Gold entity spans/identifiers are supplied inputs. The primary frame selects one
gene-involving pair per publication; the complete specialist assessment below
uses every eligible gene-involving pair.

| Method, same 128 cases | Exact accuracy | Positive precision | Positive recall | Exact positive F1 | Unresolved |
|---|---:|---:|---:|---:|---:|
| Always no reported relation | 65.6% | 0.0% | 0.0% | 0.0% | 0 |
| Typed co-mention control | 27.3% | 27.3% | 79.5% | 40.7% | 0 |
| Published specialist | **78.1%** | **61.0%** | 56.8% | **58.8%** | 0 |
| Specialist with type guard | 78.1% | 61.0% | 56.8% | 58.8% | 0 |
| NVIDIA model, flat context | 56.3% | 37.3% | 63.6% | 47.1% | 4 |
| NVIDIA model, bounded tool agent | 57.8% | 39.4% | 63.6% | 48.7% | 5 |

Unresolved outputs remain in the accuracy and recall denominators. A wrong
positive relation type counts as both a false positive and a missed correct
type. Co-mention is a deliberately weak candidate-generation control, not the
deployed Pharos workflow. The always-negative control exposes class imbalance.

The agent-minus-specialist exact-F1 difference has a paired publication bootstrap
95% interval of **−18.3 to −2.3 percentage points**. The agent-minus-flat interval
is **−3.1 to +6.7 points**, providing no clear benefit from the agent loop here.
The agent made 34 false-support calls on 84 curator-`None` cases, versus nine
for the specialist. These are source-reference disagreements, not proof that a
relationship is biologically false everywhere.

## Complete specialist assessment

Across **16,489 candidate pairs from 374 publications**, the specialist achieved:

| Measure | Result | Publication-cluster 95% interval |
|---|---:|---:|
| Exact relation accuracy | 86.0% | 83.7–88.1% |
| Exact positive relation F1 | 60.0% | 57.0–62.8% |
| Related-pair F1, ignoring relation subtype | 78.8% | 76.6–80.9% |

The 2,313 errors comprise 924 false source supports, 678 missed source supports
and 711 wrong positive relation types. Exact F1 is 65.7% for chemical–gene,
61.8% for disease/phenotype–gene and 50.4% for gene–gene pairs. Native `Bind`
recall is only 30.6% (38/124), with 70.4% precision; its corpus meaning also
includes receptor/complex conventions rather than guaranteed direct binding.

The type guard changed zero predictions. Two native chemical–gene reference
relations are `Cotreatment`, involving protein reagents and chemical stimuli.
This illustrates the documented distinction between entity category and
experimental role; a chemical-only co-treatment assumption is not universal.
The original labels, frozen policy and comparisons were retained without tuning.

The full **28,734-row** native task, covering 399 candidate-bearing publications
in the 400-abstract release, was also scored using the authors' gold-label
and metric helpers. Relation F1 was 56.84%, versus the paper's 56.06% ten-run
mean; all six metric levels were within 0.8 percentage points of their reported
means. This is useful artifact consistency evidence. It is not an exact
reproduction: one released checkpoint is compared with multiple-run means, and
the authors' separate summary decoder differs from their native inference
decoder on one saved relation decision in this complete table.
Added entity-role labels followed a separate annotation process: a 50-article
double-annotation pilot followed by single annotation of the remaining articles.
They are a weaker diagnostic reference than the original doubly curated labels.

## Agent contribution and limits

The real model was `nvidia/Llama-3.1-Nemotron-Nano-8B-v1`, served by the existing
vLLM 0.8.5 V0 deployment. Each case allowed at most three distinct read tools and
four model calls. The tools inspect the unchanged abstract, native entity
mentions and the published specialist output. They cannot retrieve labels or
change the graph. Final source-unit identifiers resolve mechanically to literal
passages; valid identifiers do not establish entailment.

All 128 agent outputs were controller-valid, including five explicit abstentions.
The agent read all three tools in the same order every time: this does not
demonstrate adaptive retrieval. It used 512 model calls and 1,144,926 input tokens;
the flat control used 128 calls and 409,192 input tokens. Latency includes schema
processing and shared compute and is not an isolated throughput benchmark.
A separately preserved initial flat attempt was blocked by the local network
sandbox. Its 128 failed transport traces returned no model outputs; the unchanged
arm was rerun with verified permission before any reference labels were opened.
There were no semantic retries or outcome-based repairs.

The authors' prediction script intends the released specialist for BC8 test use,
but its archive has no training-ID or split manifest independently establishing
the weights' fine-tuning membership. Public model pretraining exposure is also
incompletely auditable. The numbers are therefore **curator-reference agreement
under this provenance limitation**, not a claim of fully audited model-unseen
accuracy. Neither canonical human-protein mapping, species transfer, whole-graph
accuracy nor downstream prediction gains is established by this source task.
The intervals resample whole publications 5,000 times and describe this corpus,
not a whole-Pharos population sample.

The reusable implementation is in [tools/biored_agent](../../tools/biored_agent/README.md).
Author code, weights, source abstracts, case-level outcomes, failed development
versions and complete provenance receipts remain in ignored run storage rather
than the application's MIT package. No live graph was accepted or pruned by this
assessment. Candidate source claims still require identifier/context and source
qualification before graph use.

## Primary sources and seals

- [BioCreative VIII reference curation](https://doi.org/10.1093/database/baae069)
- [BioREDirect paper](https://doi.org/10.1093/bioinformatics/btaf226) and [official artifacts](https://github.com/ncbi-nlp/BioREDirect)
- [BioREx harmonization method](https://doi.org/10.1016/j.jbi.2023.104487)
- [Publication cluster bootstrap](https://doi.org/10.1111/j.1467-9868.2007.00593.x)

Primary prediction seal:
`ffad6df0a0500d06a28d4ca975946d9d3ac391f967efd7e4d3d17f8a9b3d2d2f`.
Aggregate report seals:

- Primary: `1c2880b0b9f586bb00ba65c776fd6eb74384c18f6b5b75ad002eb309400f1a11`
- Complete gene pairs: `89bad14549b8402223c8d8299e9b06d94d09c65a9028d8ee33a9f19c9d0f7bd7`
- Released artifact: `ee33b1841676dc93ca7ad680b3438251c1c52daa7939076d0d042bbd90e12a86`
- Descriptive error audit: `f124b4d6a09a6ce9e3cff09682ada51329ad8f934a6e328bec58d97c92c56f76`

The shared scientific-assessment v4 archive carries the sanitized three-report
capsule at `scientific_assessment_reference_20261114/sources/biored.json`.
Its content seal is
`9c4e8ce2f504d371cc029b805c4a23aa2f3217752cfdd2eb00e7a305db74b161`.
This capsule excludes raw abstracts, individual cases/outcomes, author code,
weights and credentials.

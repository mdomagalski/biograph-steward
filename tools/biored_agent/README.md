# Expert-labeled relation assessment and bounded agent comparison

This optional experiment assesses whether a proposed relation is reported in a
supplied title/abstract, using the authors' BioRED/BioCreative VIII annotations.
It does not treat an absent abstract relation as a biological negative, a
`Novel` flag as independent novelty, or a predicted relation as biological truth.
The concrete use is inspecting/filtering candidate literature edges before they
can become source-supported graph assertions. Original Pharos records are not
rewritten by these tools.

Author implementations and checkpoint files stay in the ignored run directory;
they are not vendored into the project's MIT application package. The official
NCBI repositories do not expose an explicit artifact-wide license in the
inspected tree. Local evaluation is separated from redistribution: no author
weights, abstract corpus or author code should be included in app/repo exports
without recording applicable terms. Cite the primary papers and official data.

## Established implementation

- [BioRED and annotation guidelines](https://github.com/ncbi/BioRED)
- [BioCreative VIII expert curation and evaluation](https://doi.org/10.1093/database/baae069)
- [BioREDirect paper](https://doi.org/10.1093/bioinformatics/btaf226)
- [Official BioREDirect code](https://github.com/ncbi-nlp/BioREDirect)
- [Official model/data directory](https://ftp.ncbi.nlm.nih.gov/pub/lu/BioREDirect/)

The paper/code use the original BioRED train+development 500 abstracts for
training, original 100-test abstracts for development, and 400 new BioCreative
VIII abstracts for final evaluation. Those 400 were published September 2022 to
March 2023 and doubly annotated by NLM curators. Public pretraining/checkpoint
membership is not fully independently auditable; project-unseen and model-unseen
are distinct claims. The released model is a specialist comparator, not an agent.
The official prediction script explicitly uses the downloaded model on BC8 test
data, but the archive has no training-ID, dataset-hash or split manifest tying
its weights to the paper's experiment. The 500/100/400 protocol must therefore
not be asserted as independently verified fine-tuning membership of that archive.
Results from it are curator-reference agreement with that limitation.

## Controlled comparison

The initial frozen proposal is in `runs/agent_contribution_20261113/`. No final
400-abstract relation labels may be opened until the candidate frame, masks,
model artifact, model-tool policy and comparison outputs are sealed. Development
may inspect only original 600 BioRED abstracts; they are exposed/model-development
material and never become a fresh test again.

The fixed primary frame is 128 outcome-blind hash-selected test publications,
with one gene-involving candidate pair per publication. Native curator-provided
entity spans and identifiers are inputs; entity detection and canonical protein
grounding are not being evaluated. The first six native preprocessing fields are
preserved. Relation, novelty and direction outcomes are never supplied to a tool
or language model. This is a source-relative component benchmark, not an estimate
of all Pharos edges' biological accuracy.
There are 374 eligible gene-involving publications in the 400-abstract release.
Publications receive equal weight here; this is not the authors' complete
all-pairs benchmark. Typed co-mention is an explicit weak candidate-generation
control, not a claim that the deployed Pharos workflow accepts all co-mentions.
An improvement against that control is not automatically a gain over Pharos.

Three roles are distinguished explicitly:

1. Outcome-blind typed entity co-mention proposes candidate literature edges.
2. The released BioREDirect model classifies those candidates using unchanged
   native preprocessing/decoding and supplied document text.
3. A bounded read-only model agent may inspect the same document and specialist
   tool output, returning a proposed relation plus source-unit identifiers or an
   explicit unresolved result. The identifiers resolve mechanically to unchanged
   native passages; their validity alone does not establish entailment. It cannot retrieve labels, train,
   edit source text, accept/prune the live Pharos graph, or invent references.

Primary scoring must include entity-pair and exact relation-type precision,
recall and F1; false positive/negative counts, abstention/coverage and full
candidate denominators accompany any precision improvement. Source-relative
unknown is not silently converted to a biological falsehood. Agent and specialist
outputs are compared on the same fixed frame with publication-level paired
uncertainty. A no-gain or failed agent remains a recorded result.

The complete controls include always-`None`, typed co-mention, the native released
specialist, its deterministic type guard, a one-call flat-context language model,
and the bounded tool-using language-model agent. The flat control receives the
same three tool outputs and biological policy. It isolates the effect of the
agent loop from simply adding another model. Tool choices and costs are recorded;
reading every tool in the same order will not be described as adaptive retrieval.

Source-unit identifiers adapt the established [SciFact sentence-rationale
representation](https://github.com/allenai/scifact/blob/master/doc/data.md), using
the BioREDirect authors' own sentence-boundary helper to preserve this corpus's
text. They are algorithmic source units, not gold evidence rationales. The
same-model no-agent ablation is motivated by the authors' [PaperQA2 component
study](https://arxiv.org/abs/2409.13740); this benchmark does not reproduce their
different full-text literature-search task or assume their gains transfer.

## Runtime and preserved development failures

The published specialist is loaded with `weights_only=True`, offline, using the
authors' inference/preprocessing/decoding. An isolated local Python environment
with Torch 2.6.0 and Transformers 4.55.0 executes CPU inference; it does not change
the application's dependencies or train on test cases.
The optional package pins are in `requirements-specialist.txt`; use a separate
Python 3.12 virtual environment, never the existing app or model-server environment.

The agent uses the existing NVIDIA Llama-3.1-Nemotron-Nano-8B-v1 server on Brev:
vLLM 0.8.5 V0, XGrammar 0.1.18, at most three distinct read tools and four calls
per case, with at most 800 output tokens per call. This is a NVIDIA model served
by vLLM, not a claim that a NIM or NVIDIA Agent Toolkit deployment ran it.

Initial development failures are retained under separate run names: repeated
tool choices, nonliteral generated quotations and overlong ID arrays. The last
interface corrections use the installed runtime's documented complete schema
support: native `minItems`/`maxItems` route from XGrammar to its existing Outlines
backend. V4 still allowed empty citations in a positive conclusion at the schema
level, although its existing controller already rejected them. V5 aligns that
same guard through separate positive and no-relation/unresolved branches;
the biological guidance is byte-identical. CPU probes and two unforced live
development requests verified a positive conclusion with a real source ID and a
`None` conclusion without one. No serving dependency or model service was changed.
Remaining unsupported
conclusions, missing citations, invalid actions and abstentions are counted as
failures or unresolved outputs, never silently repaired or scored as negatives.

## Reproduction order

Use `python -m tools.biored_agent.prepare --help` to build masked development and
test frames from pinned official artifacts. Then run `predict` on each frame and
`agent` on the 32 development controls, including `--mode flat`. Use a dedicated
runtime for the specialist. Keep downloaded artifacts under an ignored run path.

Before held-out execution, `evaluate freeze` requires the completed development
agent and flat-control runs and the sanitized live runtime observation. It pins
the code, model artifacts through the frame, model revision, biological policy,
all six arms, full denominators and publication-level paired bootstrap method.
After both 128-case language-model arms and the specialist finish,
`evaluate seal-predictions` seals all three output inventories. Only then may
`evaluate score` open the 128 selected native outcome rows. Never tune the method
against those outcomes or overwrite failed development runs.

The agent is eligible for default promotion only if its paired 95% bootstrap
lower bounds are above zero for both exact accuracy and positive relation F1
against the native specialist, type-guarded specialist **and** flat model. These
fixed-frame intervals are descriptive, not a whole-graph validity guarantee.

`python -m tools.biored_agent.report --source RESULTS/report.json --output
RESULTS/report.html` renders a shareable aggregate page without source abstracts,
individual cases, model weights or credentials.

The separately predeclared full gene-pair specialist assessment has 16,489
candidate rows from 374 publications. It resamples whole publication clusters
for paired intervals, preserving correlated rows within each paper. This follows
[established cluster bootstrap methods](https://doi.org/10.1111/j.1467-9868.2007.00593.x);
its uncertainty describes the benchmark publication frame. It does not turn
every candidate row into an independent biological experiment. The optional
remaining-type run completes all 28,734 native rows for an author-metric artifact
consistency diagnostic, and does not replace the fixed agent comparison.
The frozen native inference decoder differs from the authors' separate summary
script when multiple specific positive classes exceed its threshold; a synthetic
counterexample is retained in the run. The diagnostic uses the authors' gold
tuple reader and metric function without changing the frozen inference decoder.
Paper means therefore provide context, rather than an exact reproduction target.

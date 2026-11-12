# PPI pruning: method and interpretation

**Decision date: 11 November 2026.** This comparison tests whether an established
network-denoising method improves a bounded biological task. It does not assume
that fewer edges mean a more scientifically accurate graph.

The [completed comparison](PPI_PRUNING_COMPARISON_20261111.md) reports the observed
tradeoff and separates secondary ranking gains from the fixed pruning decision.

## What this increment adds

The project already has source-bound Pharos retrieval, evidence qualification,
an edge-disposition ledger, retained-graph export and assay comparison tools.
Those mechanisms support pruning, but do not establish a beneficial automatic
pruning policy. Earlier physical-evidence prioritization changed answer ordering;
it did not alter the saved graph or the learner's inputs.

The existing R-GCN comparison is unsuitable for this intervention:
[`prepare_inmc_graphs.py`](../../scripts/prepare_inmc_graphs.py) explicitly excludes
all direct Pharos PPI from every model arm. Repeating that unchanged learner
cannot measure the effect of removing or reweighting those edges. The present
comparison instead evaluates concrete retained PPI graph projections directly.

## Fixed intervention and comparator

- Use one frozen, source-verified cohort and its native Pharos `Score` values for
  STRINGDB-containing associations. Native STRING scores express upstream
  association confidence; they are not calibrated for this Y2H detection task,
  direct-binding measurements or independent-study counts. The captured Pharos
  inventory does not establish the exact upstream STRING release.
- Compute Network Enhancement (NE) on the same weighted, undirected source
  network. Only original input edges receive exported NE scores; inferred
  nonedges are excluded from this existing-edge pruning task.
- Permit pruning only for resolved pairs whose source bundle is **exactly
  `STRINGDB`**. Each arm retains `floor(0.8 × eligible pairs)`: the comparator ranks
  native scores, and the intervention ranks NE scores. Pair IDs break cutoff
  ties deterministically. Ranking metrics retain score ties.
- Every mixed-source, non-STRING or unresolved edge is protected by an
  **abstain-and-retain** disposition. Preserve the canonical source graph and
  publish separate retained graphs and complete decision ledgers.

The 80% retention budget is a fixed project comparison rule, **not** an optimum
recommended by the literature. The runner does not select it from assay outcomes
or a parameter search. Both arms have the same eligible population and budget.

## Established implementation

Wang et al.'s **Network Enhancement**, published **6 August 2018**, is an
unsupervised method for denoising undirected weighted networks. Its reported
downstream applications support testing network utility; they do not guarantee
improvement on our assay endpoint. [Primary paper](https://www.nature.com/articles/s41467-018-05469-x).

The original biological evaluation predicts gene functions across 22 human
tissue networks; it does not validate binary Y2H detection or provide a dedicated
complex-recovery benchmark. Applying NE here fits its weighted, undirected input
assumptions, but tests a transfer of utility to a different endpoint. STRING's
default combined scores target shared biological function, and even its physical
network can include co-complex relationships without direct contact. NE scores
are not calibrated probabilities. [Author documentation](https://snap.stanford.edu/ne/),
[STRING 2025 paper](https://academic.oup.com/nar/article/53/D1/D730/7903368),
[official score interpretation](https://en.string-db.org/help/scores/).

Reuse the [author implementation](https://github.com/wangboyunze/Network_Enhancement)
at commit `8662284871274b805ed82f725af54ab76dc79e53`, with unchanged defaults:
diffusion order `2`, `alpha=0.9`, and `K=min(20,ceil(node_count/10))`. The author
algorithm is **GPL-3.0** and remains an external, hash-verified code/license
directory; it is not vendored into the MIT application or reimplemented in
Python. The adapter invokes the [official GNU Octave container](https://github.com/gnu-octave/docker)
version **11.3.0**, pinned by immutable image digest, with offline execution,
read-only source/input mounts and CPU/memory limits. The execution manifest binds
source, parameters, input bytes, runtime and original-edge scores. A prepared
adapter or valid output schema alone is not a completed biological evaluation.

## Biological endpoint and limits

Use the **previously consumed Lambourne human Y2H-v1 panel** as a retrospective
development endpoint. Compare detected-observation retention and ranking on the
same eligible, mapped assay population, reporting coverage and missing pairs.
Conditional assay nondetection is not a universal negative PPI label. No new
held-out generalization claim follows from reusing this panel.

The captured Pharos source does not establish the upstream STRING release or
complete study-level reuse. Record that uncertainty alongside any paired result.
It limits independence claims; it does not prevent an explicitly retrospective
utility comparison. Pruning is task-specific graph selection, not a verdict that
discarded functional associations are false or that retained edges prove direct
physical binding. Numerical improvement remains unclaimed until the comparison
has actually executed and been scored.

## Recent literature: adopted principles and deferred methods

**PRING** (NeurIPS 2025; paper v2 **22 October 2025**) motivates evaluating graph
organization and biological utility alongside isolated pair accuracy. Its MIT
author evaluator measures complex-edge precision/recall and connectivity, keeping
missing proteins as isolates. These are useful secondary endpoints, but its
Reactome complex references and STRING/IntAct/UniProt-derived network are not
independent Pharos truth. Its sampled absent pairs must not replace measured
assay nondetections. [Primary paper](https://arxiv.org/html/2507.05101v2),
[official code](https://github.com/SophieSarceau/PRING),
[official dataset card](https://huggingface.co/datasets/piaolaidangqu/PRING).

**Brière et al.**, published **20 August 2026**, demonstrate why duplicate/inverse
relations, feature leakage and the choice of test population affect biomedical
KG evaluation. This comparison therefore keeps unordered pairs unique, binds
source and candidate bytes, uses the same inputs/budget across arms, and states
reference reuse explicitly. It does not claim to reproduce the paper's complete
benchmark or independent validation. [Primary paper](https://doi.org/10.1093/bioinformatics/btag608),
[MIT author code](https://github.com/galadrielbriere/data_leakage_kge_benchmark).

**BioGraphBench-PPI**, published **1 October 2026**, provides a recent contract
for auditing PPI evaluation and strong simple structural baselines. Its MIT code
at `d73bdce981aaeb9bf76ebe68fbcd57eff67eeed8` implements common-neighbor,
Jaccard, Adamic–Adar and degree-product controls. It derives tasks from STRING
12.0 and BioGRID 5.0.260, with sampled unobserved pairs rather than measured
noninteractions. Neither pair subtraction nor a different resource name proves
study independence. Its degree-matched sampler uses complete-positive-graph
degrees, while predictive features use training adjacency; that distinction
needs review before reuse in a held-out task. It supplies no new independent
experimental reference for this comparison. Structural controls may help a
later interpretation assessment, but no arm, split or negative set is added to
the already fixed comparison. [Primary paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC13669192/),
[author code](https://github.com/wvillegas01/biographbench-ppi),
[release metadata](https://zenodo.org/records/22216311).

**scYOU**, published online **9 November 2026**, reports representation-guided
STRING pruning and complex recovery, but requires single-cell protein-expression
and GO-derived inputs absent here. At audited commit
`063bf602f066886df04e877740afbdb51ce45422`, the GitHub source has no license file
and no released STRING-pruning/complex-evaluation code path. Its separate Zenodo
archive declares CC BY 4.0, but that archive was not inspected or verified against
the GitHub revision. It is a future integration candidate, not a reproducible
drop-in baseline for this increment. [Primary paper](https://doi.org/10.1093/bib/bbag626),
[official repository](https://github.com/anchor-hue/scYou),
[author archive](https://zenodo.org/records/18756874).

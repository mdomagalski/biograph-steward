# External perturbation-profile concordance

This optional CPU assessment tests whether graph-neighbour priorities transfer
to an experimental transcriptomic readout. It does **not** estimate edge truth,
pruning precision, binding or a whole-graph accuracy percentage. It fits no model
and changes no production graph.

The November 13 assessment binds the existing source-qualified historical
Pharos/STRING graph, six existing complete rankings, the shared native spanning
forest, approved HGNC mappings, and the official Pathway Commons 12 Reactome
extended SIF. The new candidate uses one binary co-complex-context priority,
then the unchanged organism-native experimental/combined-confidence ranking.
Reactome is already represented in Pharos; this is richer context from that
provider, not an independent evidence vote.

`core.py` reads the released two-table SIF; it does not parse BioPAX or invent
pair-expansion rules. Pure ProteinReference nodes need one matching HGNC symbol.
Ambiguous gene products and nonunique protein-to-gene mappings abstain. The
Paxtools projection can expand protein families and collapses native states:
co-complex support is neither direct binding nor a complete proteoform claim.

The external files are the original Replogle 2022 K562 day-8 and RPE1 day-7
author-normalized pseudobulk matrices. Their CC BY4.0 license and author MD5s
are recorded separately. Use standard AnnData backed reading. The primary
readout is signed Pearson similarity among each query's top ten available graph
neighbours, averaged equally over the same queries across arms. The exact
own-target expression feature is zeroed before Pearson centering, following the
paper. This adapter uses **all author-retained measured genes**, not the paper's
selected strong-perturbation/highly-variable-gene panel. It is a new bounded
assessment using the published similarity principle, not exact figure replay.

Each target needs a unique nominal perturbation row and at least 25 filtered
cells. Constant or nonfinite profiles abstain without imputation; report every
exclusion. A nominal target does not guarantee every guide is on-target. Missing
targets, ambiguous identities and weak responses never become negative truth
labels. Per-query k=1/5, absolute correlation, and equal-budget graph retention
are declared secondary diagnostics. Query bootstrap intervals are descriptive:
genes share partners and the two cell lines come from one study.

Install `requirements.txt` in an optional isolated environment. No Brev model,
GPU or AWS reviewer instance is required. A JSON configuration supplies
`source_dir`, `rankings_dir`, `forest`, `registry`, `context`, `context_metadata`,
and exactly two `references`, named `K562` and `RPE1`, with `file`, author `md5`
and source URL fields. Preserve original provider bytes under their own terms.

```sh
python -m unittest tools.perturbation_transfer.test_core tools.perturbation_transfer.test_contract
python -m tools.perturbation_transfer.run prepare --config CONFIG.json --output FROZEN
# Record the emitted protocol SHA256 separately before reading expression X.
python -m tools.perturbation_transfer.run evaluate --frozen FROZEN --protocol-sha256 RECORDED_SHA256 --output RESULTS
```

The runner verifies all bound source/reference/code hashes before opening X,
records exposure, and refuses to overwrite a results directory. Both cell
contexts run under the same frozen method. Preserve failures and consumed
results; a technical replay after exposure is not another confirmation. Do not
retune weights, features, budgets, mappings or endpoints on this consumed test.

`qc_sensitivity.py` is a separate **post-exposure** diagnostic. It implements
the author framework's existing nonfinite-column removal across the full
population and leaves the first-pass freeze/results intact. It reports signed
k10 correlation and global-budget coverage, with no absolute-correlation QC
result. Synthetic Pandas equivalence is tested in `test_qc_sensitivity.py`.
This recovers profiles lost by complete-row exclusion but discards features and
changes the measured query population. It is not a new confirmation or a
license to tune the feature panel. See the completed
[assessment](../../docs/evaluations/PERTURBATION_TRANSFER_20261113.md).

Sources: [Replogle et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC9380471/),
[author files](https://api.figshare.com/v2/articles/20029387),
[Pathway Commons 12 archive](https://download.baderlab.org/PathwayCommons/PC2/v12/),
[native SIF semantics](https://www.pathwaycommons.org/pc2/formats),
[Paxtools](https://doi.org/10.1371/journal.pcbi.1003194),
[AnnData reading](https://anndata.readthedocs.io/en/stable/generated/anndata.io.read_h5ad.html).

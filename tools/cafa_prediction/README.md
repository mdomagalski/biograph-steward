# Historical network function prediction

This optional adapter runs the **unchanged published** FastSinkSourcePlus,
GeneMANIAPlus/Regularized Laplacian and LocalPlus functions from
[Law, Kale and Murali](https://doi.org/10.1093/bioinformatics/btaa885), using their
[official implementation](https://github.com/Murali-group/multi-species-GOA-prediction)
at commit `c45c21b9c937c3372eae03248f49fb008d4cb0cf`.
The GPL-3.0 source and license remain in a separately verified, ignored runtime
directory. No external implementation is copied into the MIT application.

The current use case is a retrospective CAFA5 partial-knowledge function
prediction on the existing Pharos protein neighborhood. The shared input is the
exact qualified STRING v11 December 2018 weighted graph and the official
CAFA5 annotations known at its 2023 submission deadline. No current GOA2026
annotations, future test GO columns, literature extraction or current Pharos GO
features enter these predictions. The 2023 GO vocabulary is supplied by the
author evaluation archive. Its admitted curator labels include the EXP family,
TAS and IC under the published CAFA5 contract; they are not all direct-assay
truth. Later annotation agreement is a scoped function-reference measurement,
not universal correctness of a graph claim.

FastSinkSourcePlus uses its author defaults `a=.8`, `max_iters=1000`,
`eps=.0001`; LocalPlus is native weighted one-hop transfer; GeneMANIAPlus uses
`alpha=1`, `tol=.00001` and the unchanged SciPy solver default iteration cap.
Only known positive training labels are supplied; unannotated genes are not
asserted biological negatives. Global known-annotation frequency and graph
cohort frequency are additional controls. The official CAFA5 Naive/BLAST
comparators must be qualified separately before any complete positive claim.
FSSplus is the primary candidate; GeneMANIA is a fixed secondary method.

The source code's `cg(..., tol=...)` is supported by SciPy 1.13.1 and removed in
1.14, as stated in [the version-specific official documentation](https://docs.scipy.org/doc/scipy-1.13.1/reference/generated/scipy.sparse.linalg.cg.html).
The isolated numerical runtime is NumPy 1.26.4, SciPy 1.13.1 and tqdm 4.67.1.
The adapter does not monkey-patch that API or alter author scores. Numerical
tests compare native outputs with small independent linear-system solutions.
Run these optional modules from a repository checkout: `tools` is excluded from
the installed application wheel. Use a separate research environment; install
the pinned numerical packages there before running numerical tests. Official
reference scoring additionally needs Pandas 2.2.3, as documented in the
[reference adapter](../cafa_reference/README.md).

The configuration has exactly these keys, each an ordinary local file path
except the external `author_directory`:

```json
{
  "network_nodes": "network_nodes.tsv",
  "weighted_pairs": "weighted_pairs.tsv",
  "network_qualification": "source_qualification.json",
  "known_t0": "known_t0.tsv",
  "ontology": "go-basic.obo",
  "targets": "partial_graph.txt",
  "author_directory": "EXTERNAL_AUTHOR_CODE",
  "author_receipt": "EXTERNAL_AUTHOR_RECEIPT.json"
}
```

The target file contains sorted unique exact accession identities, without
future GO terms or a header. Historical known labels have the author's literal
`EntryID`, `term`, `aspect` header. Source exclusions and the complete graph
universe are preserved; absent source weights are never made zero-valued edges.

```sh
python -m unittest tools.cafa_prediction.test_core -v
python -m tools.cafa_prediction.run prepare --config CONFIG.json --output FROZEN
# Record protocol.json's FILE SHA256 externally before executing predictions.
python -m tools.cafa_prediction.run predict --frozen FROZEN \
  --protocol-sha256 RECORDED_FILE_SHA256 --output PREDICTIONS
```

Both commands refuse existing output directories. Preparation checks historical
source bindings and runtime versions; execution checks every frozen source and
code pin again. Outputs are full-precision positive scores in compressed
three-column TSV files, algorithm convergence diagnostics and a sealed manifest.
No future reference labels are accepted as command arguments. An unsuccessful
comparison must remain preserved; selecting another method after inspecting
CAFA5 outcomes would be development reuse, not another fresh test.

The separate official CAFA evaluator performs ontology propagation, known-label
masking and reference-based scoring. Benchmark Fmax selects a threshold on the
evaluation curve; it is not a deployable confidence threshold. Paired bootstrap
intervals over proteins are descriptive because graph neighbors and source
curations are dependent. Source/version and prior exposure limits must accompany
any reported function-prediction result.

## Fixed secondary score fusion

`fusion.py` supplies four separately frozen secondary arms: equal-weight official
BLAST/FSSPlus, BLAST/LocalPlus, ProtT5 cosine-1/FSSPlus and the matched
ProtT5 cosine-1/LocalPlus control. Missing component predictions enter arithmetic
as zero scores, never as biological-negative labels. The source-qualified
component files must already use [0,1] scores, allowing only the same `1e-10`
upper float64 roundoff tolerance as the native numerical guard. The 579 native
LocalPlus values just above one have maximum `1.000000000000001`; raw scores
remain unchanged, with no clipping. The author threshold grid ends at 0.999.
The adapter rejects other ranges instead of choosing a normalization. Literal duplicate/alias scores use their
maximum, matching the official CAFA reader. Explicit primary/alternative GO
identities come from that unchanged reader's frozen OBO mapping before fusion.

The convex-combination form is established by
[DeepGOPlus](https://doi.org/10.1093/bioinformatics/btz595), but these components
and the fixed half weights are this project's pretest adaptation. In particular,
the current [official `predict.py`](https://github.com/bio-ontology-research-group/deepgoplus/blob/master/predict.py)
declares a CLI alpha of 0.5 but actually combines scores with namespace-specific
weights. This adapter does not claim to execute that model or reproduce its
published scores. It never sweeps fusion weights or promotes a secondary winner
to replace the frozen primary candidate.

`fusion_cosine3.py` retains those original four arms and adds two separately
sealed controls using the author's paper-reported weighted cosine three-neighbor
ProtT5 predictions, with the same fixed half weights. This extension was chosen
before future labels were opened: the one-neighbor file repeats literal known
annotations for 98.68% of its rows, giving little novel coverage in partial
knowledge evaluation. No three-versus-five neighbor performance search occurs.

## Full historical network context

`full_source.py` extends the existing exact STRING v11 weight attestation to all
20,412 proteins in the archived Pharos319 protein table. The existing native
SQL importer supplies reciprocal source rows; the adapter checks native human
STRING IDs, globally injective archived accession mappings, both official 2018
directions and identical integer combined scores. Ambiguous or unmatched pairs
abstain from model adjacency; they are not labeled biologically false.

The full check found 236 previously admitted pairs whose mapping ambiguity was
outside the original 3,172-protein frame. The original conditional experiment is
preserved. A separate globally qualified induced control retains 87,452 original
weights, and the full qualified network contains 986,091 weights. Every original
node and target remains, including isolates.

`full_context.py` freezes four secondary arms before future-term access:

- Globally qualified original induced graph, original seeds, FSSPlus.
- Full qualified graph, original seeds, FSSPlus.
- Full qualified graph, all available historical human seeds, FSSPlus.
- Full qualified graph, all historical human seeds, matched LocalPlus.

The all-seed arms emit both their complete vocabulary and a separately named
original-term sensitivity file. This separates useful network context from
additional labeled neighbors and added prediction heads. The same author
functions, parameters, target IDs and numerical guards apply throughout. A
bounded CPU process pool executes independent terms; it does not alter the
published algorithm. The self-contained packet verifies all source bodies,
author files and adapter/core/runner hashes before remote execution.

The archived accession-to-locus mapping is not a construct, sequence or isoform
identity certificate. Exact temporal weights and known-at-deadline annotations
are the admitted inputs; current GO annotations and future reference GO terms
are never model features. Full-network context is a predeclared secondary
comparison, not a replacement selected after observing the primary result.
The source mapping was read from an April 2024 Pharos dump, even though its
recorded upstream identifier loader is from 2019. A separate exact native
January 2019 alias audit corroborates 18,751 of 18,756 weighted endpoint mappings;
five lack that exact historical alias. Alias provenance is retained literally,
including BLAST-derived rows; this establishes recorded historical identifier
support rather than biological or sequence equivalence.

`reserved_context.py` prepares a separate target-only replication on 4,806 exact
CAFA5 PK proteins outside every original graph node. It copies the sealed full
graph, labels, methods, heads and numerical implementation without refitting.
The old induced control receives isolated padding to the same full node frame;
its expected zero coverage on these proteins is an explicit diagnostic, not a
scientific comparator. Full FSS versus full LocalPlus and official sequence or
annotation-transfer baselines are the meaningful comparisons. Known t0 labels
remain legal inputs: disjoint evaluation genes do not mean label-free zero-shot
prediction. This reserve is from the same CAFA study, not an independent study.

`strict_alias_context.py` is the final pre-outcome source sensitivity: it
abstains from the 228 weights incident to those five temporally unattested
mappings, retains every node, seed and target, and executes the same full-seed
FSS/LocalPlus predictors once for all 6,100 targets. It splits only by exact
primary/reserved accession membership. The original models and outputs remain
preserved; this view is a source-eligibility sensitivity, not a replacement
chosen because it scores better. Two affected nodes are reserved evaluation
targets and remain as isolates rather than disappearing from the denominator.

## Exact query context prototype

`query_context.py` reuses PyG 2.6.1 `k_hop_subgraph` on the same strict historical
network. Complete one-hop neighborhoods preserve the published LocalPlus model
because its score is a row-normalized weighted sum of positive seed neighbors.
The prototype checks every query incident edge, raw weight, weighted degree,
normalized coefficient and all historical GO scores against the full network.
Its `extract_context` helper accepts 1–25 exact source protein IDs, including
isolated nodes; the CLI executes the fixed metadata-only verification below.
It does not
claim that arbitrary neighbor rows have full-network semantics, or that one hop
is sufficient for FSS, GeneMANIA or another model.

The fixed metadata-only check samples 16 connected proteins and 16 isolates by
hash and checks singleton and multi-query contexts. This is execution
equivalence, not a new biological evaluation, pruning verdict or model recipe.
The original source graph and all frozen scientific forecasts remain unchanged.

The saved prototype also provides top-three-per-aspect display examples, with
every contributing positive neighbor, its exact historical STRING pair and raw
weight, the complete query degree denominator, and its known-at-t0 GO triple.
Contribution sums must recover the actual author score. The benchmark training
table has no individual publication identifiers or native GAF relation/context;
none is invented. These are model-input explanations, not direct experimental
evidence for the query, disease-specific claims, curated annotations or current
discoveries. The score is a ranking quantity, not a calibrated probability.

The isolated check reused the existing CPU PyTorch 2.6.0 environment with
NumPy 1.26.4 and SciPy 1.13.1. Only PyG and its small import dependencies were
installed under `/private/tmp/biograph_query_pyg_deps`; the application and model
server environments were unchanged. Source and runtime receipts accompany the
result under `runs/prediction_next_20261113/query_context_equivalence_v1/` and
`query_context_runtime_receipt.json`.

To reproduce this optional prototype or `test_query_context`, also install
**`torch==2.6.0` and `torch-geometric==2.6.1`** in that isolated environment;
NumPy/SciPy alone are insufficient. Use the supported CPU wheel for your platform
from [PyTorch's version-specific installation guide](https://pytorch.org/get-started/previous-versions/#v260).
The operation is the existing
[PyG 2.6.1 `k_hop_subgraph`](https://pytorch-geometric.readthedocs.io/en/2.6.1/modules/utils.html#torch_geometric.utils.k_hop_subgraph),
not a new sampler or another prediction method. Saved-query inspection in the
application requires neither package.

## Read-only application inspector

`query_publication.py` publishes 1–25 exact archived accession queries, including
isolates, with the complete source graph, training triples, contributor lists,
source qualification and execution-equivalence receipt. Future reference labels
are not accepted as inputs. The saved six-protein example is for usability; it
is not another validation cohort. Its queries keep every source contribution,
while the interface initially shows the largest three for readability.

The core application reads these publications with standard libraries only.
Place each ordinary publication directory directly inside the configured runs
directory and explicitly register its `publication.json` **file** SHA256:

```json
{
  "format": "biograph-steward.function-context-index.v1",
  "publications": [{
    "id": "YOUR_PUBLICATION_DIRECTORY",
    "manifest_sha256": "EXACT_64_CHARACTER_SHA256"
  }]
}
```

Save this as `function_context_index.json` in that runs directory. The app does
not discover arbitrary prediction files. Open **Compare & assess → Trace a
historical function prediction**, choose an accession and open its saved
context. The reader verifies file hashes, exact query identity and contribution
arithmetic. It does not rerun PyG or establish factual accuracy. Authentication
uses the existing workspace policy; these GET routes perform no source fetch,
model call, acceptance decision or graph edit.

A separate optional annotation-overlap note can be registered on the same row
as `"display_notes": {"id": "NOTES_DIRECTORY", "file_sha256": "EXACT_SHA256"}`.
That directory contains `notes.json`, bound to the exact publication file/content
and every displayed query/term/score. It records overlap with the broader
pre-deadline annotation baseline and a dated later GOA/ontology comparison.
Terms already represented elsewhere and terms obsolete in the later ontology
are labeled beside the unchanged historical ranking. Missing matches remain
unknown; later coverage is not an independent accuracy label. Native relations,
references, ancestor paths and product-form fields remain explicit. A populated
GAF product-form field equal to the query accession does not indicate a different
isoform. The original forecast download and the separate comparison download
remain distinct.

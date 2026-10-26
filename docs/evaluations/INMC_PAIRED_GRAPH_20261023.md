# Restricted Pharos/GO evaluation graph

October 23, 2026. **Preparation and freeze record. The paired graphs were frozen
before assay outcomes or the author-positive reference were opened.**
This is a supporting, retrospective PPI component study. It is separate from the
organizers' unavailable Pharos gold set and from the workbench's cancer answers.
The later [completed comparison](INMC_COMPARISON_20261023.md) records the measured
result and first outcome access; this document preserves the preparation rules.

## Question and actual artifacts

Does adding official GO `is_a` structure improve recovery of recorded Y2H
detection on the fixed INMC nominated panel, compared with the same learner using
the same restricted Pharos annotation listings without that hierarchy?

The immutable prepared packet is
`runs/inmc_paired_graphs_20261023/qualified_v2/`. Its `report.json` binds source,
implementation and member hashes. It contains the graph tables, original gene
identities, candidate inventory, development split, exclusion ledgers and the
proposed protocol. That preparation artifact remains `fully_frozen: false`.
After the CPU resource check passed, a separate fully frozen packet was created
at `runs/inmc_paired_graphs_20261023/frozen_cpu/`, at 14:54:38 UTC on October 23.
The [compact receipt](inmc_paired_graph_20261023_summary.json) binds its exact
files and runtime. Earlier preparation attempts remain preserved.

| Property | Actual count |
|---|---:|
| Shared node vocabulary | 10,350 |
| Original gene nodes / reviewed product nodes / GO nodes | 8,272 / 1,797 / 281 |
| HuRI original unordered pairs | 52,548 |
| Training unordered pairs / directed supervision triples | 49,937 / 99,394 |
| Separate development pairs | 2,611 |
| Reserved candidate pairs, including self-pairs | 3,276 |
| Reserved self-pairs, excluded from the primary endpoint | 495 |
| Gene-to-reviewed-product context links | 1,804 |
| Retained product–GO pairs | 2,570 |
| Scaffold / baseline / hierarchy-arm triples | 99,394 / 103,768 / 104,083 |
| The sole baseline-to-hierarchy difference | 315 official `is_a` edges |

These are learner projections. Reviewed-product links do not establish the
experiment's assayed isoform or construct. No disease membership was invented.
Shared products group pairs for exclusion only; original genes remain separate.

## Qualifications and leakage controls

The rationale follows the [source reuse review](../literature/PHAROS_GO_QUALIFICATION_REUSE_20261022.md)
and the documented risk of [GO/PPI circularity](https://pmc.ncbi.nlm.nih.gov/articles/PMC3570208/).
The selected scope is cellular-component annotations with IDA/HDA codes, outside
the protein-complex subtree; obsolete and unrecognized terms are excluded.
This is a task-specific risk reduction, not an evidence-code quality ranking.

The builder reproduced the prior 2,607 eligible product–GO pairs, then excluded
37 source rows from **both** graph arms using conservative current-GOA diagnostics.
Flags overlap: 35 have annotation extensions, four have a distinct product form,
and one has possible negation. The [official GAF specification](https://geneontology.org/docs/go-annotation-file-gaf-format-2.2/)
defines these contextual fields. It does not prescribe our exclusion policy.
An exact current-GOA projection match is not proof of historical annotation
identity; therefore these flags do not establish that a Pharos record is wrong.
Canonical accessions in the product-form column are not automatically treated
as distinct isoforms. IDA rows with nonempty With/From, literal masked-pair
exposure, and the blocked study reference are also checked.

All 23,968 retained Pharos PPI source views are outside **every** learner arm,
including all previously found reserved-pair exposures. Other Pharos context
families and all current-GOA protein annotations are also excluded. The source
records remain available in the audit; the evaluation does not delete them from
the workbench or declare them false.

Every candidate identity is reserved before outcome decoding. Development pairs
are selected by a fixed hash of shared-product-connected pair groups. Masks
expand through transitive shared products, including equivalent pairs absent
from the training scaffold. There are 5,894 masked original gene pairs and 3,876
masked product pairs. Both orientations are excluded from positive training and
accepted negative corruptions. Corruptions are unlabeled training examples,
not measured biological negatives.

The development removal leaves 16 panel genes with no scaffold training edges.
They stay in the graph and evaluation; no coverage repair changes the split.
Missing Pharos or qualified GO context likewise does not remove test pairs.
Of the retained annotation listings, 1,924 lack a compatible current-GOA row;
their source polarity and supporting references remain unknown. Together with
source releases newer than the assay, this prevents a claim of complete
derivative-evidence removal or independent temporal validation.

## Established learner and reproduced integration checks

Use native PyKEEN 1.11.1 with torch 2.6.0. The primary comparison uses R-GCN on
the restricted baseline and hierarchy graphs; R-GCN and ComplEx on the scaffold
are controls. All share vocabulary, supervised pairs, masks and update budgets.
The three R-GCN arms additionally require identical initial parameter hashes and
positive minibatch schedules for each seed.

The fixed settings are 32-dimensional embeddings, three R-GCN layers, four
bases, ReLU, disabled edge/self-loop dropout, SoftplusLoss, Adam at 0.001,
20 epochs, batches of 4,096, 16 typed negative proposals per positive, and seeds
17, 43 and 101. There is no hyperparameter search or early stopping. Native
`PseudoTypedNegativeSampler` and `PythonSetFilterer` enforce the declared masks.
Resource smoke runs one epoch on the two primary arms and scores development
pairs only. The full runner produces unlabelled fixed-candidate predictions;
it has no assay-input argument.

Before using real labels we reproduced three integration details:

1. The [native hierarchy smoke](../../scripts/smoke_pykeen_hierarchy.py) shows
   that a fixed-weight parent-only signal reaches a gene through
   GO parent → GO child → product → gene in three layers. Native inverse
   messages provide transport; they do not change biological edge semantics.
   Three layers cover this immediate-parent path, not every ancestor in the
   closure. The saved result is
   `runs/inmc_hierarchy_smoke_20261023/attempt2/report.json`.
2. The [pinned implementation](https://raw.githubusercontent.com/pykeen/pykeen/v1.11.1/src/pykeen/nn/message_passing.py)
   draws unused random masks even when `edge_dropout=0.0`. The runner uses its
   native disabled branch (`representation.edge_dropout=None`) after constructing
   zero-probability self-loop dropout. This avoids graph-size-dependent RNG
   consumption; it does not patch PyKEEN or introduce a custom trainer.
3. The [pinned graph sampler](https://raw.githubusercontent.com/pykeen/pykeen/v1.11.1/src/pykeen/triples/instances.py)
   can select a zero-degree node and fail. A synthetic fixture reproduced this.
   Supported `sampler=None` uses ordinary shuffled `BatchedSLCWAInstances`,
   preserving isolated nodes and exactly one pass over supervision per epoch.

The early direction-assertion failure and preparation attempts are retained.
OBO Graphs includes PROPERTY declarations as well as CLASS nodes; the builder
now handles these [standard node types](https://github.com/geneontology/obographs)
without admitting relation declarations into the GO term vocabulary.

## Freeze, execute, then score

The final freeze binds the exact graph files, assay interpretation,
prediction runner, outcome adapter, hierarchy smoke, actual-device resource
receipt and runtime. Both real graph arms passed one CPU epoch (25 updates,
approximately three seconds per arm), with matching initialization and positive
batch hashes. The fixed full comparison therefore runs locally; Brev is not
required. A changed device or runtime requires a new resource check.
The [scripts guide](../../scripts/README.md) contains reproduction commands.

Only after that freeze and prediction run may the outcome adapter decode the
panel. It verifies the entire nominated pair population first and enforces the
[declared assay contract](inmc_assay_contract_20261022.json): all three codes
must be Positive/Negative; any positive is recorded detection, all negative is
nondetection in these assays. Any failed/unscored result excludes the pair from
the primary endpoint. Self-pairs remain a separate report. `freq` is opaque.
Eligible positives and negatives must reconcile with the author reference;
the complement of author positives is never used as a negative reference.

Primary scoring is scikit-learn average precision, with ROC-AUC secondary, on
identical eligible off-diagonal pairs. Scores average both directions.
Missing/nonfinite scores block headline results. Report all paired seed changes,
context coverage and leave-one-original-gene-out influence descriptively.
Shared genes make dyads dependent; three seeds do not supply a population
confidence interval. No naive pair bootstrap or significance claim is planned.

A positive result would support this particular representation and selected
assay task. A null or negative result remains useful and will not trigger
post-outcome changes to scope, split, eligibility or model settings.

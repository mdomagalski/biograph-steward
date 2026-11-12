# Current investigation scripts

For delivery, [prepare_judge_demo.py](prepare_judge_demo.py) reuses the committed
runtime and verified gold-packet APIs to create separate software-only and local
full-CRC archives. It preserves the original workspace and an all-abstain edge
ledger, checks extracted byte inventories and records hashes. It neither
retrieves data nor clears redistribution rights. See [delivery instructions](../docs/DELIVERY.md).

This directory contains preparation tools for the active measured-link investigation. The workbench CLI is `python3 app.py --help`.

| Script | Purpose |
|---|---|
| [verify_submission_demo.py](verify_submission_demo.py) | Export an existing real assay-attached cohort with a retained graph, all-undecided ledger and complete sources; verify an extracted ZIP and source preservation. No inference, new source retrieval or biological scoring. |
| [evaluate_construction_planner.py](evaluate_construction_planner.py) | Freeze twelve development scope/tool-selection cases, then explicitly run one model call per case with incremental traces and results. No source retrieval or scientific-accuracy claim. |
| [probe_nemotron_tool_interface.py](probe_nemotron_tool_interface.py) | Bounded, explicitly invoked NVIDIA interface diagnostic. The experimental tool adapters are comparison-only and cannot execute production construction. |
| [prepare_intact_fidelity_reference.py](prepare_intact_fidelity_reference.py) / [verify_intact_fidelity_preparation.py](verify_intact_fidelity_preparation.py) | Prepare the metadata-selected, opaque IntAct panel and replay its frozen contract plus mandatory semantic amendment. No source-body decoding. |
| [validate_intact_reader_controls.py](validate_intact_reader_controls.py) / [inspect_intact_development.py](inspect_intact_development.py) | Validate the official PSI-JAMI reader on invented controls, then inspect only the four explicitly authorized development studies. Reserved studies are forbidden. |
| [publish_intact_development.py](publish_intact_development.py) | Publish the consumed development records, complete source ledger and readable offline viewer using verified official-reader output. No model calls or reserved-source access. |
| [evaluate_intact_evidence_fidelity.py](evaluate_intact_evidence_fidelity.py) | Compare the development-only source publication or real attached run, readable answer and full gold packet against original raw/official-reader evidence. This is source fidelity, not biological accuracy. |
| [replay_intact_consumed_flow.py](replay_intact_consumed_flow.py) | Freeze and replay the four already-opened studies after the standards-supported identity-comparator correction. Uses explicit consumed labels, captured official-reader streams and capped native Pharos retrieval. Preserves the original stopped assessment; cannot execute the new unopened panel. |
| [check_intact_final_readiness.py](check_intact_final_readiness.py) | Prepare-only final-rules and safe metadata preflight. Current expected exit 1 means full-flow execution is not ready; exit 2 means invalid metadata. Never opens, hashes or authorizes reserved reference bodies and does not run a score. |
| [audit_inmc_inputs.py](audit_inmc_inputs.py) | Verify the pinned INMC archive, input schema and identifier coverage using the existing frozen HGNC/UniProt registry. Export a deduplicated context-retrieval inventory while retaining shared products and all original genes. Does not derive binary assay labels, select a final cohort or train a model. |
| [retrieve_pharos_inventory.py](retrieve_pharos_inventory.py) | Retrieve the audited accession inventory in resumable, integrity-checked chunks. Preserve cross-chunk interaction links, all tissue labels, unresolved identities and original gene mappings. Stages raw Pharos records; does not approve features or load assay outcomes. |
| [audit_pharos_inventory.py](audit_pharos_inventory.py) | Verify a completed retrieval and inventory direct candidate-pair overlaps in raw and retained interaction rows. Reads only original pair identities from the pinned experimental archive; does not remove graph edges or decode outcomes. |
| [audit_go_qualification.py](audit_go_qualification.py) | Use the pinned upstream GAF parser to inventory qualified GO annotations, compare compatible Pharos projection groups and flag reserved-pair exposure. Requires a separate Biopython environment. No features or scientific labels are produced. |
| [smoke_pykeen_reuse.py](smoke_pykeen_reuse.py) | Exercise upstream PyKEEN R-GCN and ComplEx on non-biomedical Nations data, evaluating validation only. Uses the isolated [pinned smoke environment](../requirements-graph-ml-smoke.txt). |
| [smoke_pykeen_context.py](smoke_pykeen_context.py) | Test native R-GCN context adjacency with identical supervision, reserved-pair negative filtering and fixed-pair scoring on a tiny invented graph. CPU only; no biomedical inputs. |
| [smoke_pykeen_hierarchy.py](smoke_pykeen_hierarchy.py) | Verify native three-hop message transport, cache invalidation and common-supervision wiring on invented data. No biological outcomes. |
| [prepare_inmc_graphs.py](prepare_inmc_graphs.py) | Build the fixed, restricted Pharos/GO graph pair, preserve original identities and record symmetric qualifications/exclusions. Reads the HuRI training member only, never assay outcomes. |
| [run_inmc_comparison.py](run_inmc_comparison.py) | Run the actual-graph resource smoke or, after a bound full freeze, the fixed native R-GCN/ComplEx comparison. Produces unlabelled scores, never assay metrics. |
| [freeze_inmc_comparison.py](freeze_inmc_comparison.py) | Create a new immutable comparison packet bound to graph files, passing checks, runtime, runner, scorer and assay interpretation. Preserves the prepared packet. |
| [score_inmc_comparison.py](score_inmc_comparison.py) | Authenticate the full frozen prediction population before opening the pinned assay/author sources. Reconcile the reference and use the frozen pure outcome/metric adapter; record any holdout exposure or failure. |
| [assess_lambourne_corroboration.py](assess_lambourne_corroboration.py) | Freeze the full-panel Pharos comparator and author-consistent assay contract, execute once with a durable first-access receipt, or explicitly replay the saved descriptive result. No model or GPU required. |
| [publish_lambourne_evidence.py](publish_lambourne_evidence.py) | Reuse the completed assessment to publish an immutable qualified observation graph and offline inspection view, preserving all excluded/nondetected records and copied source receipts. No new assay scoring, automatic pruning or IMEx-conformance claim. |
| [prepare_ppi_pruning_graph.py](prepare_ppi_pruning_graph.py) / [run_network_enhancement.py](run_network_enhancement.py) / [assess_ppi_pruning.py](assess_ppi_pruning.py) | Optional fixed-budget PPI pruning comparison: publish the audited source graph, invoke external GPL author NE code, freeze separate retained views, then explicitly score consumed assays. See the [CLI guide](../docs/PPI_PRUNING.md); no model/GPU or automatic app-default changes. |
| [publish_pruning_preview.py](publish_pruning_preview.py) | Publish a verified, compact saved assessment for the app's Compare & assess tab, with per-pair policy choices and assay context. Does not rerun scoring, apply pruning or export full retained graphs. |

Read the [reuse decision](../docs/literature/MEASURED_LINK_BENCHMARK_REUSE_20261022.md) and [input-readiness report](../docs/evaluations/INMC_INPUT_READINESS_20261022.md) before running these tools. Use new output directories and preserve source receipts. A runtime smoke does not show biological improvement.

The [follow-up decision](../docs/evaluations/INMC_READINESS_FOLLOWUP_20261022.md) explains the v2 mapping categories and declared assay task. `context_targets.json` is an outcome-blind request inventory, not a selected evaluation population or proof of assayed isoform identity.

Retrieve the prepared inventory with the core Python environment:

```sh
python3 scripts/retrieve_pharos_inventory.py \
  --inventory runs/inmc_mapping_followup_20261022/input_audit_v2/context_targets.json \
  --output-dir runs/inmc_pharos_uniform_20261022/retrieval
```

After an interruption, repeat the command with `--resume`. The inventory,
implementation, scope and chunk size must be unchanged; completed chunks are
verified before further requests. `--stop-after-chunks 1` permits a small live
transport check without selecting a smaller evaluation population. The default
chunk size is 25; both scope and source omissions are recorded in `plan.json`.
`progress.json` records completed work during a pull; `summary.json` is refreshed
at normal completion or a handled failure. A finished pull may still contain
unresolved targets or capped/inconsistent families. No feature use is approved
by retrieval completion. These packets are not disease-workbench snapshots.

The [GO reuse review](../docs/literature/PHAROS_GO_QUALIFICATION_REUSE_20261022.md)
records the official source release, parser, interpretation boundaries and
reproduction commands. The [context learner smoke](../docs/evaluations/PYKEEN_CONTEXT_SMOKE_20261022.md)
records the supported library wiring and its limitations. Neither is the frozen
biological comparison.

The [completed uniform-source audit](../docs/evaluations/INMC_PHAROS_UNIFORM_20261022.md)
records actual coverage, caps and reserved-pair exposures. To reproduce the local
audit after retrieval, use new output directories:

```sh
python3 scripts/audit_pharos_inventory.py \
  --retrieval-dir runs/inmc_pharos_uniform_20261022/retrieval \
  --archive runs/link_prediction_reuse_audit_20261022/inmc_release_v1.zip \
  --output-dir runs/inmc_pharos_uniform_20261022/audit
runs/inmc_go_feasibility_20261022/venv/bin/python scripts/audit_go_qualification.py \
  --gaf runs/inmc_go_feasibility_20261022/HUMAN-uniprot.gaf.gz \
  --inventory runs/inmc_mapping_followup_20261022/input_audit_v2/context_targets.json \
  --pharos-chunks runs/inmc_pharos_uniform_20261022/retrieval/chunks \
  --pair-mask runs/inmc_pharos_uniform_20261022/audit/overlaps.json \
  --output runs/inmc_go_feasibility_20261022/pharos_join
```

The GO tool uses [requirements-go-audit.txt](../requirements-go-audit.txt) in a
separate environment; it adds no dependency to the core application. Its real
parser test runs there, while the core suite skips that optional integration
test if Biopython 1.88 is absent. The remaining audit/provenance tests run in the
core environment.

Completed growth, extraction, verifier and context-QA study tools have left the active branch. Their exact implementations, protocols and outcomes are preserved at the commit listed in [EXPERIMENT_HISTORY](../docs/EXPERIMENT_HISTORY.md). Reproduce them from that separate checkout with their original packets; do not weaken source-hash checks or reseal an old study to run it against current code.

## Prepared restricted Pharos/GO comparison

Read the [graph and protocol report](../docs/evaluations/INMC_PAIRED_GRAPH_20261023.md).
Use the isolated [evaluation dependencies](../requirements-inmc-evaluation.txt),
which extend the original PyKEEN smoke runtime. The existing `qualified_v2` packet is
immutable; change the output directory to reproduce it:

```sh
runs/link_prediction_reuse_audit_20261022/venv/bin/python scripts/prepare_inmc_graphs.py \
  --retrieval runs/inmc_pharos_uniform_20261022/retrieval \
  --audit runs/inmc_pharos_uniform_20261022/audit \
  --goa-audit runs/inmc_go_feasibility_20261022/pharos_join \
  --ontology runs/inmc_go_feasibility_20261022/go-basic.json.gz \
  --archive runs/link_prediction_reuse_audit_20261022/inmc_release_v1.zip \
  --out runs/inmc_paired_graphs_20261023/qualified_v2
```

The resource smoke uses the actual input graph, one epoch and seed 17, and
scores only development pairs. It must pass on the intended execution device;
CPU completion does not authorize an unchecked CUDA run. The language-model
server is unnecessary. Example on a prepared GPU runtime:

```sh
python scripts/run_inmc_comparison.py \
  --graph runs/inmc_paired_graphs_20261023/qualified_v2 \
  --output-dir runs/inmc_resource_smoke_20261023/cuda \
  --device cuda --resource-smoke
```

Preserve failures. A full run omits `--resource-smoke` and requires the new
fully frozen packet produced by `freeze_inmc_comparison.py`; passing a merely
prepared graph fails before training. The pure `biograph_steward.inmc_outcomes`
adapter is tested on synthetic records only until the final freeze. Its caller
must authenticate source hashes and the complete prediction population before
opening assay labels. No comparison score follows from a successful smoke.

The October 23 full comparison used CPU after the actual-graph resource check
showed it was practical. These are the recorded freeze and prediction commands;
use new output destinations when reproducing them:

```sh
python scripts/freeze_inmc_comparison.py \
  --graph runs/inmc_paired_graphs_20261023/qualified_v2 \
  --hierarchy-smoke runs/inmc_hierarchy_smoke_20261023/attempt2/report.json \
  --resource-smoke runs/inmc_resource_smoke_20261023/cpu/report.json \
  --output-dir runs/inmc_paired_graphs_20261023/frozen_cpu
python scripts/run_inmc_comparison.py \
  --graph runs/inmc_paired_graphs_20261023/frozen_cpu \
  --output-dir runs/inmc_comparison_20261023/cpu \
  --device cpu
```

Only after the complete sealed prediction run passes, use the authenticated
scoring gate. This opens the reserved labels and consumes the unseen holdout:

```sh
python scripts/score_inmc_comparison.py \
  --graph runs/inmc_paired_graphs_20261023/frozen_cpu \
  --predictions runs/inmc_comparison_20261023/cpu \
  --archive runs/link_prediction_reuse_audit_20261022/inmc_release_v1.zip \
  --workbook runs/inmc_readiness_20261022/author_sources/41467_2023_37079_MOESM4_ESM.xlsx \
  --output-dir runs/inmc_comparison_20261023/scored
```

The gate records the native openpyxl version and source hashes. It validates
the full nomination population and the author reference, never fills missing
labels from the complement of positive pairs, and leaves a failure/exposure
receipt if parsing or reconciliation fails. A consumed holdout remains usable
for fixed-protocol reproduction, not an unseen test for subsequent tuning.

## External human PPI identity audit

The [Lambourne reference audit](../docs/evaluations/LAMBOURNE_REFERENCE_AUDIT_20261023.md)
checks the author's identities and nomination metadata against existing HuRI,
INMC and raw Pharos inputs. It does not decode the new assay result column or
select valid tests using outcomes. It requires the pinned source files and
retrieval receipts already saved locally. Use a new output directory:

```sh
python3 scripts/audit_lambourne_reference.py \
  --sources runs/lambourne_reference_audit_20261023/sources \
  --receipts runs/lambourne_reference_audit_20261023/source_receipts.json \
  --pharos runs/inmc_pharos_uniform_20261022/retrieval \
  --archive runs/link_prediction_reuse_audit_20261022/inmc_release_v1.zip \
  --registry runs/crc_adjudication_mapping_20261020/registry \
  --output-dir runs/lambourne_reference_audit_20261023/identity_audit_reproduction
python3 -m unittest discover -s tests -p 'test_lambourne_reference_audit.py' -v
```

The source acquisition is pinned to author commit
`fb05ab3ca2cc0fcaf402bb0df568e95a5158178b`; receipt URLs, byte hashes and Git blob
hashes are checked. The historical preprocessing excerpt is explanatory source,
not executable project code: it has private-database dependencies. An absent
pair in the scoped Pharos archive is never classified as a biological negative.

### Focused Pharos PPI lookup

The [completed snapshot report](../docs/evaluations/LAMBOURNE_PHAROS_LOOKUP_20261023.md)
records coverage, overlap and the remaining source-lineage limitations.

The existing inventory retriever now accepts the audited author-accession
inventory with `--profile ppi`. It resolves each accession exactly and retrieves
only PPI rows; other families' count metadata can still appear. It preserves raw
neighbors outside the cohort and retains within-cohort neighbors across chunk
boundaries. An identity redirect is recorded, not silently substituted. This is
source retrieval, without assay outcomes, a language model or GPU.

Use a new destination for a fresh snapshot; `--resume` requires the identical
inventory, options and implementation. The code hashes in older context packets
remain binding. Do not reseal them to accept a newer retriever.

```sh
python3 scripts/retrieve_pharos_inventory.py \
  --inventory runs/lambourne_reference_audit_20261023/next_lookup_inventory.json \
  --output-dir runs/lambourne_pharos_lookup_20261023/retrieval_reproduction \
  --profile ppi --chunk-size 50
python3 scripts/audit_lambourne_pharos_lookup.py \
  --pharos runs/lambourne_pharos_lookup_20261023/retrieval_reproduction \
  --identity-audit runs/lambourne_reference_audit_20261023/identity_audit_v3 \
  --identity-report-sha256 f4bd5e51a28935e9cf5d673f7c0e17c5b0492760eba2e8d15f2d07c938148cbd \
  --output-dir runs/lambourne_pharos_lookup_20261023/audit_reproduction
```

The audit requires a completed, count-reconciled retrieval and authenticates the
prior identity audit, source responses and saved chunks. It preserves all
published pairs, unresolved identities, prior exposure and separate provider
properties. A missing match applies only to this API profile; it is not a
measured negative or evidence of study independence. New live responses can
differ from the saved snapshot.

```sh
python3 -m unittest discover -s tests -p 'test_pharos_inventory.py' -v
python3 -m unittest discover -s tests -p 'test_lambourne_pharos_lookup.py' -v
```

### Completed frozen Lambourne corroboration

Read the [result and qualifications](../docs/evaluations/LAMBOURNE_CORROBORATION_20261025.md).
The October 25 packet has already been executed and its outcomes are consumed.
To reproduce that result, use **`verify`**, with Python 3.14.0, the pinned code
and the original saved packet:

```sh
python3 scripts/assess_lambourne_corroboration.py verify \
  --freeze runs/lambourne_corroboration_20261025/freeze \
  --out runs/lambourne_corroboration_20261025/results
```

For provenance, the following are the original freeze and first execution
commands. **Do not rerun them to present this consumed panel as a new test.**
`freeze` requires new output, the reviewed exact sources and the synthetic
author-version replay receipt. `run` refuses a previously opened freeze even
when given a different output directory.

```sh
python3 scripts/assess_lambourne_corroboration.py freeze \
  --pharos runs/lambourne_pharos_lookup_20261023/retrieval \
  --identity-audit runs/lambourne_reference_audit_20261023/identity_audit_v3 \
  --lookup-audit runs/lambourne_pharos_lookup_20261023/audit \
  --sources runs/lambourne_reference_audit_20261023/sources \
  --source-receipts runs/lambourne_reference_audit_20261023/source_receipts.json \
  --preparation runs/lambourne_corroboration_preparation_20261025/source \
  --out runs/lambourne_corroboration_20261025/freeze
python3 scripts/assess_lambourne_corroboration.py run \
  --freeze runs/lambourne_corroboration_20261025/freeze \
  --out runs/lambourne_corroboration_20261025/results
```

The runner reuses `biograph_steward.lambourne_outcomes`, preserves failures and
unresolved comparator states, and reports detection fractions with the fixed
provider/exposure strata. The raw author transformation is checked against the
published supplement; any inconsistency stops assessment. No classifier,
biological-truth label, graph-improvement effect or independent-reference claim
is produced. An opening receipt is written before parsing actual outcomes,
including for attempts that subsequently fail.

The production runner needs no new core dependency or GPU. Optional author
semantics checks require the exact pandas 1.4.3 / NumPy 1.23.0 environment;
the saved passing receipt precedes the outcome freeze. Core tests use synthetic
data and skip those optional version-specific checks when unavailable:

```sh
python3 -m unittest discover -s tests -p 'test_lambourne*.py' -v
```

Ignored source/run files are not part of a Git clone. Outcome source bytes,
comparator evidence and locators are in the frozen packet; original Pharos
chunks are hash-bound but not copied. A full retrieval-audit replay requires
those original chunks. Do not edit frozen receipts to admit different code,
runtime or source bytes.

### Publish the qualified observation layer

The [literature gate](../docs/literature/ASSAY_EVIDENCE_REUSE_20261025.md)
documents the existing IMEx/PSI-MI approach and the unavailable public deposition
records. The [assay evidence guide](../docs/ASSAY_EVIDENCE.md) defines this bounded
local projection. It consumes the already verified assessment, without changing
its outcomes or source bytes:

```sh
python3 scripts/publish_lambourne_evidence.py publish \
  --freeze runs/lambourne_corroboration_20261025/freeze \
  --results runs/lambourne_corroboration_20261025/results \
  --out runs/lambourne_assay_evidence_20261025
python3 scripts/publish_lambourne_evidence.py verify \
  --out runs/lambourne_assay_evidence_20261025
```

Use `verify` for the existing publication; `publish` refuses an existing output.
Open its `index.html` to inspect source-qualified observations, including the
42 detected pairs without a resolved-profile Pharos match. They are not a new
independent accuracy benchmark. This publication has its own local contract and
must not be passed off as an ordinary Pharos run or the validated KGX subset.

The [biological source enrichment workflow](../docs/BIOLOGICAL_SOURCE_UPDATE.md) is available through the core `string-source-publish`, `mapit-source-publish` and `biological-update` commands. It reuses complete saved source artifacts and preserves the original graph.

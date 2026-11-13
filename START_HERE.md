# Start here

BioGraph Steward builds a scoped Pharos-based evidence graph, answers supported questions, and lets you trace each claim to its source, conditions and review history. The core workflow runs locally without an account, API key, GPU, Brev, PaperQA3 or AWS.

## Run locally

From the repository directory, using Python 3.10 or newer:

```sh
python3 app.py
```

Open [the workbench](http://127.0.0.1:8765/). Keep the terminal running; Ctrl+C stops it. No pip installation is needed for the core app.

## Reviewer walkthrough

The [three-page review packet](output/pdf/BioGraph_Steward_Final_Review_20261113.pdf)
summarizes the working product, measured scientific results and delivery routes.
The [release index](docs/releases/20261113/README.md) identifies the tested
software, current hosted demonstration and preserved older private bundle.

The five tabs retain your current graph and selections as you switch tasks.

1. **Data & saved work:** choose **Offline demonstration**, then **Build synthetic demonstration**. This uses invented records to demonstrate the software. No source retrieval or model call is needed.
2. **Ask & explore:** in **Ask a scoped question**, select a protein, set **Evidence for the answer** to **Explore candidates and accepted evidence**, and click **Find evidence paths**. Follow **Question → Graph → Answer → Sources** to inspect the cited summary. An empty accepted-only view is expected before any assertions have been accepted locally.
3. In the same tab, try **Explore paths in this saved graph**. Select the start and end entities, or leave the end open, then click **Explore saved paths**. The search follows up to three connections and preserves direction, conditions and review states. **Inspect source** opens the exact claim used by a path.
4. **Evidence & sources:** choose a claim and click **Guide me through this source**. Inspect what the record reports, where its support can be found, missing context and evidence-reuse limits. A database label alone is not a supporting publication. The synthetic example has no genuine biomedical references.
5. **Compare & assess:** inspect benchmark readiness or compare saved evidence snapshots when available. A fresh checkout has no real comparison history. The literature-comparator preparation is optional and does not run a hosted search when opened.
6. **Export:** use **Export graph with undecided ledger**, or download the graph JSON and complete run ZIP. The answer diagram shows a question-specific selection; the workspace export covers the full saved graph. Undecided records remain retained and are not biologically accepted.

For a review demonstration, use the synthetic data: open **Inspect all source data, assertions and review decisions** in **Evidence & sources**, select **Inspect candidates**, and open an assertion passport. Saving a reviewer, decision and reason creates a new run while preserving the earlier one. Source editorial status and local human review remain distinct.

## Open a real example

A small [offline Reactome source example](examples/reactome_context_20261113/index.html)
is included in the checkout, with exact native records, source links and a
standalone ZIP. It needs no server or account. Its CC0 publisher data and MIT
viewer have separate notices. It demonstrates current source inspection;
it is not the full Pharos graph or an independent correctness reference.

A [portable delivery guide](docs/DELIVERY.md) now designates the complete CRC
workspace and separates the software-only archive from locally verified source
data. Follow its launch instructions when you have authorized access to that
packet. The [five-minute demonstration](docs/DEMO_SCRIPT.md) is the presentation
route; local run IDs alone are not a distribution mechanism.

A fresh checkout includes synthetic fixtures, not retrieved Pharos or assay snapshots. If a real demonstration packet is supplied separately, keep its complete workspace/source folders together and follow the packet's placement instructions. Copying only `graph.json` loses the source and replay context.

With complete saved workspaces available, open **Data & saved work → Saved graphs and answers** or **Open a saved real example**. The shortcut prefers the latest real qualified workspace with a native-supported saved question. A saved question URL reopens its graph and answer. Use the saved example for an offline presentation; live retrieval is optional.

For a supplied **source-faithful qualified workspace**, choose **Ask & explore
→ Qualified WikiPathways source context**. Native support is required by default
when its historical packet is attached. Follow a protein → cited model ← protein
path, then inspect the exact archived GPML and gene/protein matching scope in
its passport. Shared source context is not a new protein interaction. The
workspace is read-only: unresolved evidence is retained, and the full workspace
ZIP includes its original baseline and decision package. See the
[source-faithful workspace guide](docs/evaluations/SOURCE_FAITHFUL_WORKSPACE_20261113.md).

A [separate local 128-gene demonstration](docs/evaluations/SCIENTIFIC_DELIVERY_20261113.md#separate-local-cohort-demonstration)
reuses that workflow on a different saved pathway cohort, retaining all 1,470
records with zero prunes. It requires its complete private packet; the guide
documents the large proof payload and the negative same-study biological
comparison separately from this working application example.

The [November 13 delivery polish](docs/DELIVERY_POLISH_20261113.md) reduces HTTP
response bytes for large saved answers while preserving their original hashes,
source files and exports. Complete proof payloads can still be large.

With that same supplied local packet, the
[B3GALNT2 shared-pathway example](http://127.0.0.1:8794/?run=transfer_pathway_workspace_20261113&question=question_b3galnt2_reactome_20261113)
uses Reactome annotations already present in Pharos even though this protein
has no Wiki rows. Its candidate paths and current-record guide illustrate
broader source inspection, with no new biological-validation result.

For a qualified assay example, **Evidence & sources → Qualified assay evidence** preserves the method, detected or nondetected outcome, experimental roles, original identifiers and excluded observations. The guided inspector exposes source links and unresolved reuse without treating repeated database records as independent experiments. See [assay attachment](docs/ASSAY_WORKBENCH.md) and [IntAct source evidence](docs/INTACT_EVIDENCE_WORKBENCH.md).

For the saved SIGNOR layer, choose **Regulation and experimental context → Sites
& context**. The BRAF example separates phosphate addition at S614 from the
reported decrease in protein activity. Exact cell/tissue filters preserve
missing context and source citations. This [read-only view](docs/SITE_CONTEXT_INSPECTION.md)
adds no graph assertion or automatic acceptance.

## Retrieve a new scoped graph

In **Data & saved work → Data source and retrieval**, select **Build from a protein cohort**. Enter 1–25 exact UniProt accessions, select a focus protein and source profile, then build. The graph and a cited candidate answer are saved together. Use the explicit form for the reliable construction path; the optional model planner remains experimental.

For disease-based retrieval, select **Pharos disease cohort**, search for `colorectal`, and select the exact returned disease. Related disease names are not automatically equivalent. After retrieval, inspect **Retrieval coverage** in **Evidence & sources** for caps, omitted families and failures. Network errors do not silently become synthetic evidence.

See [construction and replay](docs/CONSTRUCTION.md), [scoped retrieval](docs/SCOPED_RETRIEVAL.md), and [CIViC evidence](docs/CIVIC_EVIDENCE.md). CIViC queries retain complete molecular profiles, therapy sets and disease context; a multi-drug annotation does not establish a single-drug effect.

## What the results establish

The [expert-labeled grounding assessment](docs/evaluations/EXPERT_GROUNDING_20261113.md)
measures source-identity error triage using published curator labels. It remains
an assisted-review component: publication context reduces false alarms but
also misses some errors. It performs no automatic identifier replacement or
biological pruning.

The [November 13 delivery and scientific assessment](docs/evaluations/SCIENTIFIC_DELIVERY_20261113.md)
collects the current graph changes, public-label coverage, hosted deployment and
completed controls. The [128-gene prospective transfer](docs/evaluations/PROSPECTIVE_GENE_TRANSFER_20261113.md)
did not reproduce the exploratory pathway-weighting advantage. Whole-graph
precision and transferable pruning gains remain unestablished.

- The [native pathway assessment](docs/evaluations/SOURCE_FAITHFUL_WORKSPACE_20261113.md)
  recovers 253/308 exact cited revisions and preserves all UNKNOWNs. Experimental
  GO curation matches 373/4,078 GO assertions; the declared CRC genomic cohort
  supports 32/100 disease assertions. These separate positive-support axes
  cannot establish whole-graph accuracy. The fixed R-GCN comparisons find no
  reliable pathway-filter improvement over count and degree controls.
- The [curated-signature comparison](docs/evaluations/CURATED_SIGNATURE_RECOVERY_20261112.md)
  increases scored perturbation-target cases from **31 to 39 of 105**, with
  study-weighted normalized rank **0.680898 → 0.576408**. This is mainly a
  coverage gain; shared-target ranking is mixed. It is a corrected technical
  replay with unresolved source reuse, not whole-graph accuracy, automatic
  pruning or a new default app signature source.
- The [fixed STRING comparison](docs/evaluations/STRING_COMPONENT_COMPARISON_20261027.md) found higher average precision for native physical scores than functional scores on 2,676 eligible assay pairs: **0.190056 versus 0.172827**, with lower numeric coverage (**72.4% versus 88.3%**). The [older-release control](docs/evaluations/STRING_TEMPORAL_CONTROL_20261027.md) supports a modest task-specific ranking benefit. These are retrospective source-component results; they do not establish independent validation or a Steward-versus-Pharos graph improvement.
- The [GO hierarchy comparison](docs/evaluations/INMC_COMPARISON_20261023.md) and [Reactome-context comparison](docs/evaluations/REACTOME_CONTEXT_COMPARISON_20261026.md) found **no consistent prediction benefit**. Their evaluated panels remain consumed development material.
- The [Lambourne assay corroboration](docs/evaluations/LAMBOURNE_CORROBORATION_20261025.md) found detection in **17.0%** of Pharos-represented eligible pairs versus **5.9%** of resolved no-matches. This is conditional assay concordance; source/study independence remains unresolved. The [qualified publication](docs/ASSAY_EVIDENCE.md) preserves all 3,222 nominations, assay conditions, nondetections and exclusions.

The app exposes evidence and supports traceable decisions. Local acceptance, source preservation and software checks do not establish biological truth. A missing record in a scoped graph does not establish absence elsewhere.

The complete [graph-plus-decision export](docs/GOLD_SET_INTERFACE.md) works for the demonstrated source profiles. The [KGX standards audit](docs/STANDARD_EXPORT.md) covers a bounded subset and reports unresolved mappings; full Biolink conformance is not claimed. The official scoring contract and independent biological improvement remain open. Earlier approaches and their outcomes are preserved in the [experiment ledger](docs/EXPERIMENT_HISTORY.md).

For optional model configuration or shared hosting, see [planner configuration](docs/PLANNER_PROTOCOL.md) and [portability](docs/PORTABILITY.md). These services are not required for the walkthrough above.

# Five-minute judge walkthrough

**Question:** Which proteins connect to KRAS in this colorectal-cancer protein
cohort, what do those links mean, and what changed when the graph was qualified?

BioGraph Steward turns a supported question into a small graph, a cited answer
and an inspectable source trail. The example uses **99 primary protein targets**;
it is a focused research workspace, not the whole Pharos database or a clinical
recommendation. No graph-query language or biological adjudication is required.

[Open the reviewer site](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/)
and sign in with the token supplied privately. Allow the saved graph to load.
You need only a browser. This protected session reads completed real-data work;
it does not start a model, retrieve new data or edit review decisions.

## 1. Read the answer | about one minute

In **Start here**, choose **Open the real-data example**. If it is already
loaded, choose **Read the cited answer**. In **Question & graph**, expand the
first answer.

You should find **14 proteins connected to KRAS by the selected STRING physical
source**. The first result connects KRAS and AKT1 and includes a citation such
as `[E001]`. Here a citation identifies preserved database evidence, not
necessarily an assay paper. Read the sentence before interpreting the drawing: the record
predicts physical proximity or membership in a shared complex. It does not
establish direct binding or a colorectal-cancer mechanism.

**What this demonstrates:** a bounded question, a readable answer and the graph
path behind that answer. **Candidate** means awaiting local review; a source
record is not automatically accepted because an assistant found it.

## 2. Check why one link exists | about one minute

Select `[E001]`, then **Inspect this source claim**. Alternatively, use
**Inspect its source** from the start card. Read the explanation in
**Inspect sources** and expand **Native STRING physical association**.

Find the provider and release, the preserved score and the identifier/sequence
matching explanation. The KRAS–AKT1 example preserves the native score **459**
on STRING's 0–1000 scale. It is not a 459/1000 probability that the biological
claim is true. Both protein identities passed the declared alias and complete
sequence checks; historical assay constructs remain a separate question.

**What this demonstrates:** why the link is present, where it came from and
what the evidence leaves unresolved. STRING already contributes to Pharos;
another versioned row does not count as another independent experiment.

## 3. See an actual applied qualification | about one minute

Return to **Start here** and select **Review applied graph qualifications**.
This opens the TP53 pathway example from the same 99-target study, with its
saved qualification decisions already applied. It has a different input-source
collection from the enrichment example; their totals are not a before/after
comparison with one another.

The saved answer displays eight results from 54 inspectable proteins, under
its recorded display limit. Follow a TP53→pathway←AKT1 or ATM path and its source. The annotations join
through the cited pathway model, not a direct binding claim. The passport
distinguishes a literal protein reference from a compatible gene-level match;
these are different identity claims. An archived model can preserve context
that a current flat list omits.

Open **What changed** and find **Applied qualifications in the selected
workspace**. The recorded qualification reduces **16,985 evidence records to
16,687**:
**298 records use obsolete GO identifiers** in the pinned ontology. Their
originals and reasons remain in the baseline and decision ledger. Unresolved
records stay retained. These are applied identifier-currency exclusions,
not 298 experimentally disproved biological relationships. GO is a standard
biological vocabulary; an obsolete identifier has been retired, which does
not itself disprove the underlying biology.

**What this demonstrates:** real, reversible filtering with an explicit reason,
and restraint where missing source evidence does not justify removal.

## 4. Read the measured benefit | about one minute

Open **What changed** and the featured public-reference comparison. Start with
the protein-location result, not the research-history list.

Among **31 proteins with matching reference labels**, the original Pharos view
recovers **41 of 51 known location labels**; the qualified native GO source view
recovers **44 of 51**. These are fixed source-view comparisons, rather than a
newly scored union of the complete integrated graph. A separate OpenCell comparison recovers **30 of 40 to 31
of 40** labels among 23 matching proteins; the gain remains after the stated
HPA/OpenCell source exclusions. Unmatched proteins and unreported locations
remain unknown. Both are already-exposed development references; the exclusions
do not establish a new blind validation.

This location comparison assesses source views separately from the 298
identifier exclusions. Raw and retained Pharos both recover 41 of 51 labels;
the native GO source view recovers the additional labels.

**What this demonstrates:** measured recovery of additional known annotations,
with coverage and source-reuse limits visible. These positive-label tasks do
not measure the fraction of the entire graph that is correct. The separate
same-learner graph-prediction comparisons did not establish consistent
superiority over Pharos and the strongest controls.

## 5. Show what a researcher can take away | about one minute

In the applied-qualification example, open **Export** and download the saved
workspace ZIP. After extracting it, open **source_retained_package** inside
the workspace folder. Its three parts are:

- `retained_graph.json`: the graph after the recorded decisions;
- `edge_dispositions.jsonl`: one keep/prune/abstain disposition for every input
  evidence record, with its reason;
- `baseline_packet`: the preserved input and sources, including excluded rows.

An **abstain** decision retains the record. The small answer diagram is a view
of this workspace; the answer ZIP and full workspace ZIP have different scopes.
In `retained_graph.json`, a protein has a UniProt identifier and the explicit
`biolink:Protein` category. These identifiers and categories make the graph
reusable alongside its source trail. The bounded standard projections and their limitations are
documented in [Standard export](STANDARD_EXPORT.md) and
[Mapping and overlap](EVIDENCE_OVERLAP.md).

**What this demonstrates:** a reproducible result with its baseline and
decisions, rather than an unexplained graph image.

## Where the agents fit

The implemented Nemotron planning and source-audit components have recorded
model/tool evaluations. The dependable demonstration uses explicit choices and
source-bound execution. The shared site replays saved outputs with the model
off; it is not a live autonomous build. The tested audit agent is not promoted
to automatic biological acceptance or pruning. See the
[NVIDIA integration record](NVIDIA_INTEGRATION_STATUS_20261113.md) for that
separate evidence.

## Watch the narrated screen tour

[Watch the narrated walkthrough](../output/walkthrough/BioGraph_Steward_Walkthrough.mp4)
(**3 minutes 42 seconds**), read the
[transcript](../output/walkthrough/BioGraph_Steward_Walkthrough.txt), or use the
[caption file](../output/walkthrough/BioGraph_Steward_Walkthrough.vtt).
The [seven-slide overview](../output/presentations/BioGraph_Steward_Overview.pptx)
provides a short presentation of the same product and measured results.

The video is a narrated screen tour assembled from actual hosted-app captures
using saved real data. It combines captured interface states and focused crops
for readability; it is not a continuous interaction recording. Authentication
is off camera and loading waits are omitted. It makes no live model calls,
new retrieval or review edits.

| Chapter | What it shows |
|---|---|
| 0:00 | Start with real research data |
| 0:25 | Read the KRAS answer and one selected path |
| 0:56 | Inspect a citation, source score and preserved identity proof |
| 1:29 | Read the measured source-view comparison and its coverage limits |
| 2:08 | Inspect the separate TP53 qualification and its retained decision package |
| 2:55 | Distinguish the focused answer from the complete candidate workspace export |

For feedback, ask only: Could you find the answer? Could you explain one link?
Could you identify what was actually removed and why? Could you distinguish the
measured result from a claim of whole-graph truth? Could you find the reusable
graph and its baseline?

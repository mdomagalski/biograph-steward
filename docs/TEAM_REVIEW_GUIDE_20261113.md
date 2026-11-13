# BioGraph Steward
## Team review guide | November 13, 2026

**Please review over the weekend and send feedback by Monday, November 16.**
Allow 25-35 minutes, plus loading and downloads. Biological expertise is welcome
but is not required. We need to learn whether the app's answers, evidence,
qualifications and exports are understandable. You are not being asked to certify
the biology.

### What the application does

BioGraph Steward is a Pharos-based research evidence workbench. It helps a user
ask a supported question, explore the resulting graph, read a cited answer,
inspect the original records and share a reproducible workspace. A link between
two entities is presented with its source and conditions rather than treated
as an automatically verified fact.

**The working route:** choose saved data > ask a guided question > explore the
graph and answer > inspect sources and warnings > export.

### What is integrated

| Component | What it contributes |
|---|---|
| Pharos backbone | Protein-target annotations, including disease, expression, GO, pathways and aggregated interaction data. GO, Reactome, WikiPathways and older STRING information are already represented here. |
| Original-source context | Exact archived WikiPathways models, preserved native GO annotations and recorded quality checks, plus current Reactome record links. These clarify existing annotations; they are not extra independent studies. |
| Direct CIViC layer | Separately retrieved cancer molecular-profile and therapy-response records, joined to exact Pharos protein identifiers. Complete variant and treatment combinations remain together. |
| Versioned extensions | Newer STRING associations, MAP-IT observations of nearby proteins in tissue, and SIGNOR activation/inhibition records, with separate provenance and context. Their presence does not establish independence from Pharos's underlying evidence. |
| Storage and optional planning | AWS hosts the app. Neptune is Amazon's graph database and holds a private mirror of the demonstration graph. NVIDIA/Nemotron planning is optional and experimental; the guided workflow needs no model or GPU. |

### Scope of the main demonstration

The main saved example contains **99 primary protein targets, 9,865 entities
and 16,687 retained evidence records**. A record count is not a count of
independent experiments. The Pharos backbone comes from a frozen Pharos319
capture on October 14, 2026; separate extensions and publisher context retain
their own dates. The exported baseline includes those extensions.

Qualified Lambourne/IntAct assay inspection is also supported in separate
examples. Those attached assay observations are **not** part of this main
99-target demonstration. Available features and data depend on the selected
workspace.

<!-- page -->

## 1. Get into the right example

### Access: choose the route supplied by Marcin

| Route | What you can review |
|---|---|
| Authorized AWS workbench | The full current saved example and native GO inspector. The present deployment uses private access. A shared browser-only HTTPS address is planned, not yet verified or supplied in this guide. |
| Repository checkout | The synthetic app demonstration and the small real Reactome annex. Repository access alone does not provide the complete Pharos workspace or native GO packet. |
| Separately arranged saved-data access | Real examples can be reopened with their complete authorized source packets and current software. A graph JSON file alone is insufficient. The preserved older combined bundle does not include the latest GO attachment. |

**An address beginning `127.0.0.1` or `localhost` refers to your own computer.**
Marcin's local URL will not open his app on yours. A private AWS tunnel requires
your own authorized AWS access; GitHub membership does not grant it. Sign-in
information is supplied separately, never in this guide. After a service restart
you may need to sign in again; saved links remain usable.

If full-demo access is unavailable, complete the repository-only tasks below
and mark the others **not attempted - data/access unavailable**. Please do not
spend the review setting up AWS or Brev.

### Repository-only start

Use the [review branch](https://github.com/mdomagalski/biograph-steward/tree/codex/scientific-accuracy-round2)
and follow [START_HERE](../START_HERE.md). From the repository directory:

```sh
python3 app.py
```

Python 3.10 or newer is sufficient for the core app; no pip install, model or
cloud account is needed. Keep the terminal open and visit
`http://127.0.0.1:8765/`. Choose **Data & saved work > Offline demonstration >
Build synthetic demonstration**. These are invented records, suitable for
testing navigation and exports, not for assessing biological evidence.

For a small real-data task, open
`examples/reactome_context_20261113/index.html` from the checkout. It works
offline without the app server.

**Repository-only assignment:** follow the synthetic question, source and export
steps in START_HERE, then the optional Reactome task on the next page. Mark the
real TP53/native GPML, NRAS GO and real-assessment tasks unavailable. You can
still report navigation, terminology and export-scope problems.

### Full-demo start and navigation

Choose **Data & saved work > Open a saved real example**. Confirm the workspace
is `source_faithful_workspace_20261113`. Its supplied TP53 answer has eight
result proteins. If another workspace opens, record its name and ask for the
intended example before testing its GO features.

The five tabs are **Data & saved work**, **Ask & explore**, **Evidence & sources**,
**Compare & assess**, and **Export**. Start with the saved answer; new retrieval
is unnecessary. The main cold load can take around 1-2 minutes, and native GO
inspection around 20 seconds on the tested host. Record waiting separately from
task difficulty; if an error persists, note it and move on.

<!-- page -->

## 2. Follow the testing route

Try each task before reading the glossary and interpretation notes. Using those
notes is fine: mark the task **with help**. If stuck for about three minutes,
record the obstacle and continue. An empty or unavailable result is useful
feedback; do not invent a result to finish the task.

### T1. Find the answer | 3 minutes

Open the supplied TP53 question in **Ask & explore**. Follow
**1. Question > 2. Graph > 3. Answer > 4. Sources**. Find the written answer and one citation.
In your notes, describe what question the app answered and whether it was
obvious where the answer was. Did a candidate or review label change how you
read it?

### T2. Follow a claim to its source | 6 minutes

Select a TP53 path involving AKT1 or ATM. Open a citation/passport and find
**Archived native source check** and **Download cited native GPML**. Open or
download one native record. Describe what connects the proteins, where the
support came from, and whether the app distinguishes the cited historical
model from today's publisher page. Was a database name enough to locate the
underlying support?

### T3. Inspect a GO warning | 7 minutes

In **Evidence & sources > Find a saved claim**, search `GO:0005794` by itself.
Choose NRAS under **Claim to inspect**, then **Guide me through this source >
Inspect preserved native GO annotations**. Find the original relation, its
recorded normalization and a reference. Repeat with `GO:0070062` and NRAS.
Explain what the warning appears to mean, and what remains uncertain. If a
button or packet is unavailable, record your access route and stop this task.
Do not decide whether NRAS biology is correct.

### T4. Understand and export the workspace | 5 minutes, plus download

In **Export > Saved workspace files**, use **Download run ZIP**. The main
qualified workspace disables **Export graph with undecided ledger** because
its retained graph and decisions already exist. Return to **Ask & explore** and
try **Download summary, paths and evidence ZIP** beside the saved answer.
After extraction of the workspace ZIP, locate
`source_retained_package/retained_graph.json`, `edge_dispositions.jsonl` beside
it, and `baseline_packet/source/graph.json` inside that package. Explain how
the complete workspace differs from the answer diagram. Mark download and
file-interpretation problems separately.

### T5. Read the assessment and try another question | 5 minutes

In **Compare & assess**, find one reported result and its stated limitation.
Can you tell what was measured and what was not? If time permits, return to
**Ask & explore**, choose ATM or AKT1 with **Qualified WikiPathways source
context**, explore candidates and accepted evidence, and keep archived native
references required. Find evidence paths. Report whether scope and any empty
result are understandable; this is a supported template, not unrestricted chat.

### Optional: a second real source | 5 minutes

Use the repository's offline Reactome annex. Find B3GALNT2, its catalytic role,
a bundled source record and the recorded release. Can you distinguish a source
statement from independent confirmation? This task needs no full graph, account
or model. The separate 128-gene B3GALNT2 app workspace is not in the hosted
99-target demonstration.

<!-- page -->

## 3. Terms and interpretation notes

Use this page when a label is unfamiliar. Tell us which definitions should have
appeared inside the app instead.

| Term | Meaning in this application |
|---|---|
| Knowledge graph; node; edge | A network of entities and recorded relationships. A node can be a protein or pathway; an edge records a relationship and its source. An edge is not automatically a proven mechanism. |
| Annotation; assertion; evidence record | An annotation is a source's recorded assignment. An assertion is a qualified claim; evidence records are the attached source items. Several records may describe the same underlying study. |
| Provenance; native record | Provenance records where information came from, its identifiers, version and retrieval history. A native record preserves the publisher's own fields rather than only our graph summary. |
| Snapshot; historical version | A saved, dated capture. A current website can differ from the model cited by an older snapshot. A redirect is not proof of historical content. |
| Candidate; accepted | Candidate means available for inspection, not locally accepted. Accepted records a local review decision. A publisher's own ACCEPTED status is separate; neither is a universal truth guarantee. |
| Keep; prune; abstain | Decisions about a declared graph view: retain, exclude, or withhold a verdict. Abstained/undecided records remain retained. The original baseline is preserved. |
| UNKNOWN; no match | Insufficient information within the selected scope. Neither means that a biological relationship is absent everywhere. |
| GO; qualifier; NOT | Gene Ontology supplies function, process and location terms. Qualifiers specify the relationship. NOT negates that specific annotation; it is not general evidence that a protein has no function. |
| Normalization; QC warning | Normalization produces a separately recorded standardized form. A quality-control warning identifies a rule/context issue; it does not automatically refute the underlying biology. |
| Pathway; GPML | A curated biological-process model; GPML is a native WikiPathways file format. Shared membership can explain graph proximity without establishing direct protein binding. |
| Molecular profile; therapy set | The complete variant combination and complete treatment combination in a CIViC claim. A combination record cannot be split into separate single-variant or single-drug effects. |
| Entity resolution; grounding | Matching a name or mention to the intended biological identifier. The same symbol can have several meanings; a plausible name match can still identify the wrong entity. |
| Source overlap; independent evidence | Different databases can reuse a paper, record or experiment. More database labels do not necessarily mean more independent support. Missing overlap details leave independence unresolved. |
| Coverage; accuracy; prediction | Coverage asks how much a reference can support or assess. Accuracy requires credible correctness labels. Prediction evaluates a specified task against controls. These are different measurements. |

### Three examples to keep distinct

- **TP53 and AKT1:** their displayed shared model context is not a new claim of
  direct physical binding.
- **NRAS / GO:0005794:** the preserved native `part_of` value and the recorded
  `located_in` derivative are both visible. A compatible current row still does
  not establish the exact identity of the older Pharos source row.
- **NRAS / GO:0070062:** a related native record has a context warning, but no
  native row matches all five available Pharos fields. The warning cannot be
  used to declare the historical annotation or base association false.

<!-- page -->

## 4. Improvements, unsuccessful approaches and limits

### What has improved

- **Evidence can be followed:** guided questions connect the answer diagram,
  cited records, native files, source versions and exports.
- **Original data remain available:** the baseline and all keep/prune/abstain
  decisions are preserved. The active view excludes 298 obsolete-GO-ID records;
  those are vocabulary-currentness exclusions, not 298 disproved relationships.
- **Context is richer:** the workflow preserves clinical combinations, native
  GO qualifiers, pathway versions, regulatory effects and source-reuse caveats.
  We recovered 253 of 308 exact cited WikiPathways revisions; the rest stay
  explicitly unresolved.
- **Delivery is reproducible:** the private AWS app, Neptune mirror, saved
  answers, exports and service restart have been checked. Software and data
  remain separately packaged; the earlier backup recovery has a limited scope.

### What did not work reliably, and what we use now

| Approach explored | Outcome and current decision |
|---|---|
| Large language model (LLM) planning and literature extraction | Outputs could have valid structure yet select the wrong entity, miss support, confuse context or decline a supported task. Use the guided route with fixed rules for this review; optional model planning remains experimental. |
| BioMedBERT and text-support checks | Biomedical language models and natural-language-inference (NLI) methods tested whether text supports a claim. Some task-specific results improved, but false support and context errors remained. These are not automatic truth gates for the delivered graph. |
| Extra hierarchy/pathway context and automatic biological pruning | No reliable general predictive improvement was established. A fixed transfer to 128 new genes and 7,648 pairs was negative against the baseline and controls. No such pruning or ranking policy was promoted. |
| Expert-labeled source-identity checking | On 678 eligible cases, publication context reduced false alarms from 25 to 18 but detected 26 rather than 31 errors. This is a review trade-off, not automatic identifier correction or whole-graph accuracy. |

### What remains limited

The app supports source inspection and qualified decisions. **Independent
whole-graph biological accuracy, validated automatic biological pruning and
transferable prediction gains remain unproved.** Public reference matches often
measure positive support or coverage, not correctness of every edge; missing
matches are not reliable negative labels. Potential source/training overlap
limits independence.

The demonstration is a scoped frozen capture, not all of Pharos or the latest
complete release. Current publisher links and native GO context do not recreate
missing historical metadata. Evidence types differ: tissue proximity,
functional association, pathway membership and physical binding are not
interchangeable. Complete drug/variant normalization and every source's assay
context are not implemented. Schema and integrity checks establish neither
clinical validity nor a treatment recommendation.

The independent teammate walkthrough is still to be done. Your feedback will
test usability and explanation, not establish a biological-accuracy percentage.

<!-- page -->

## 5. Send feedback by Monday, November 16

Reply in the team channel or send notes to Marcin. You can use the linked
text template; editing the PDF is unnecessary. A short description of where you got
stuck is more useful than a general rating. Screenshots are helpful when they
show the selected example and confusing control; do not include access tokens.

### Record each task

Use **I = independent**, **H = with help**, **N = not completed**, or
**A = not attempted**. Record hands-on time separately from waiting/downloads.
Unattempted or access-blocked tasks are not failures of biological understanding.

| Task | I / H / N / A | Time / waiting | Exact obstacle or unclear wording |
|---|---|---|---|
| T1: Find the answer |  |  |  |
| T2: Inspect the original source |  |  |  |
| T3: Explain GO source/QC differences |  |  |  |
| T4: Download and understand exports |  |  |  |
| T5: Assessment / another question |  |  |  |
| Optional Reactome annex |  |  |  |

### Questions worth answering

1. What did you think the app would do, and did the result match that expectation?
2. Could you distinguish an imported claim, a local review decision and a
   quality warning? Did anything look more certain than its evidence justified?
3. Were any terms, warnings, missing references or repeated records misleading?
4. Could you locate the same answer again and understand what the exported
   package includes? Was anything important missing?
5. What are the **three most important changes** before submission? Which is
   blocking, and which is a useful polish item?
6. If relevant to your work: what research question would you try next, and
   what evidence would make its answer useful?

### Copy-and-reply template

Use the [ready feedback template](TEAM_REVIEW_FEEDBACK_20261113.txt). Include
your name/date, access route, workspace, browser and operating system. For each
task, write `T1: status | hands-on time | waiting | note`, then list your three
priority changes. A plain Teams reply is sufficient.

### More detail, if useful

[Start and setup](../START_HERE.md) |
[GO inspection](NATIVE_GO_CONTEXT_WORKBENCH.md) |
[Scientific assessment](evaluations/SCIENTIFIC_DELIVERY_20261113.md) |
[Experiment history](EXPERIMENT_HISTORY.md) |
[Delivery and data access](DELIVERY.md)

Prepared for the November 13 review checkpoint. The current tested hosted code
is `ea5752e`; subsequent guide edits do not replace the runtime or source
packets. Current AWS access is private. A shared HTTPS reviewer link will be
communicated only after it is configured and checked.

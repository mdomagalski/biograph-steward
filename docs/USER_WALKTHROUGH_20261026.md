# Team usability pilot — October 26, 2026

**Purpose:** a 15–20 minute walkthrough with a colleague who did not implement
the feature. Check whether they can find an answer, inspect its evidence and
understand the export. No biological expertise or scientific verdict is needed.
**Three assisted steps have participant responses, recorded below. The full
walkthrough and independent usability assessment remain incomplete.**

## Setup

Facilitator: supply the working workspace URL and private access instructions;
never record tokens here. Confirm the links first. Use the saved example without
a model or Brev. Let the participant think aloud and attempt each goal before
offering help. After three minutes without progress, record the obstacle and
move on. Record network/download waiting separately.

| Session field | Fill in |
|---|---|
| Participant ID / role | |
| Facilitator / date / app commit | |
| Workspace base URL | |
| Starting graph | `<WORKSPACE_BASE>/?run=assay_workbench_v2_20261026` |
| Entry route chosen beforehand | Saved graph / optional construction |
| Browser / device | |

The real example contains **P22674 and P38936**, both resolved: one Pharos
interaction annotation and one qualified assay observation. This is a complete
example within its declared scope, not all of Pharos. The construction source is
`runs/assay_cohort_source_20261026`; the standalone export demonstration is
`runs/submission_demo_v2_20261026/index.html`. Supply working links as needed.

## Five tasks — participant prompts

1. **Open the graph and identify its scope.** Find the requested proteins,
   whether they resolved, and the sources represented. Optional construction
   route: choose **Build from a protein cohort**, enter `P22674, P38936`, explore
   `P22674`, select **Reported interactions**, leave fresh retrieval unchecked,
   and click **Build graph and answer**. Record construction separately, then
   open the prepared combined graph; assay attachment is a separate step.

2. **Find an answer and its citation.** Ask which other cohort protein has a
   reported interaction annotation with P22674 / CCNO. Locate the written
   answer, graph connection and supporting citation. Explain which evidence
   the answer includes. If a hint is necessary: choose **Reported interactions**,
   **Explore candidates and accepted evidence**, then **Find evidence paths**.

3. **Follow the source and its context.** Open the answer's citation and find
   its source record. Then inspect the separate record under **Qualified assay
   evidence**. Find the assay name, an original source table/document, and one
   qualification such as a condition or construct identity. Point to them;
   there is no need to judge whether the biological claim is true.

4. **Explain the meaning in your own words.** Read the information beside the
   graph, assay record and **Graph and decision export**. Explain what an
   undecided edge means, what the assay observation claims, and what you infer
   if an edge or protein lies outside this cohort. Is an explicit prune decision
   different? Record the participant's explanation before supplying an answer.

5. **Export and reopen.** Click **Export graph with undecided ledger**, then
   download **graph, decisions and complete sources**. Extract the ZIP. Locate
   and open `retained_graph.json`, `edge_dispositions.jsonl` and
   `baseline_packet/source/graph.json` in a browser/text viewer. Find how many
   decisions there are and whether the original evidence remains available.
   Which files would you share? Reimporting the derived graph into the app is
   not part of this task; the facilitator can run the verifier afterward.

## Record results

Outcome: **independent / with help / not completed / not attempted**.
No scientific acceptance, rejection or pruning is requested.

| Task | Outcome | Time / waiting | Error or confusing wording | Help supplied | Participant interpretation / quotation |
|---|---|---|---|---|---|
| 1. Open or construct / scope | | | | | |
| 2. Answer and citation | | | | | |
| 3. Source and qualification | | | | | |
| 4. Status and scope meaning | | | | | |
| 5. Export and reopen | | | | | |

Finish by asking: **Where did you hesitate most?** and **What would you need to
understand or share this result confidently?**

| Observation to act on | Why it hindered the task | Proposed change | Owner / retest |
|---|---|---|---|
| | | | |
| | | | |

## Facilitator cues — do not give these before the attempt

- The Pharos candidate answer connects CCNO / P22674 to CDKN1A / P38936 and has
  a citation. The qualified assay stays separate from the generic interaction
  answer. Empty **Accepted evidence only** results do not mean no data exists.
- The participant should find **Y2H-v1**, source material and qualifications.
  Finding a citation is not itself a scientific support audit.
- **Abstain/undecided** means no keep/prune decision; the edge remains. An assay
  detection is conditional on that assay, not proof of clinical usefulness.
  Out-of-scope evidence is neither a negative nor an explicit prune.
- Pruning removes an edge from the retained view while preserving its original
  record and decision trail. Here, both evidence edges remain undecided.
- Difficulty understanding these distinctions is an interface finding, not a
  failure of the participant's biological knowledge.

Developer-only follow-up after extraction:

```sh
python3 app.py gold-decisions-verify --run /absolute/path/to/extracted/package
```

Record this separately. Automated integrity checks and a developer browser
walkthrough do not establish intended-user success. Report actual participant
count, roles, entry routes, independent/assisted completion and obstacles.
This formative pilot does not estimate population usability, scientific accuracy
or biological improvement and is not a new scientific benchmark.

See [the verified submission example](evaluations/SUBMISSION_DEMO_20261026.md),
[the export contract](GOLD_SET_INTERFACE.md) and
[qualified assay evidence](ASSAY_WORKBENCH.md).

## Assisted walkthrough — ready-to-open example

Use this mode when the participant wants guidance. Record **assisted** completion;
do not use the supplied hints or answers to claim independent task success.
No model, Brev instance or new source retrieval is required.

[Open the saved graph and candidate answer](http://127.0.0.1:8778/?run=assay_workbench_v2_20261026&question=assisted_walkthrough_question_20261026).
This localhost link requires the existing workspace server on port 8778. For
another deployment replace the base URL, retaining both run IDs. An offline
answer is available at
`runs/assisted_walkthrough_question_20261026/report.html`; it does not provide
all of the app's assay and export controls.

| Step | Where to explore | Question for the participant |
|---|---|---|
| 1. Find the claim | **3. Answer**, written summary and evidence graph | Which protein is connected to CCNO? Is the evidence candidate or accepted? |
| 2. Trace its source | Click **[E001]** or its graph edge; inspect the evidence passport | Does this record name a database, a paper, or both? Is any missing information clear? |
| 3. Inspect the experiment | **Qualified assay evidence**, select the pair; expand **Assay context and source locators** | Can you find the assay, detected/nondetected outcome, and construct identifiers? |
| 4. Locate original records | In that assay inspector, **Author assay table** and **Construct crosswalk** | Can you trace the displayed observation to its original rows? Which link or label is confusing? |
| 5. Understand the export | **Graph and decision export** → **Export graph with undecided ledger** | Does “undecided” keep the evidence available? Can you locate both the decisions and original records? |

Facilitator/source-audit findings, not participant results:

- Step 1: CDKN1A / P38936; candidate evidence. The selected cohort is only CCNO
  / P22674 and CDKN1A / P38936. An empty accepted-only view would not mean no
  evidence exists.
- Step 2: STRINGDB through Pharos. This source record has no explicit publication
  reference (`publications=[]`, `reference_raw=null`). Do not imply that a paper
  is one click away. Two reciprocal source rows are one normalized annotation,
  not two independent experiments.
- Steps 3–4: Y2H-v1, detected; AD construct `100063977`, DB construct `3192`.
  Participants are human proteins; assay host is unspecified in the qualified
  record. Sorted protein order does not assign construct roles. The observation
  remains separate from the generic Pharos annotation and is not an unconditional
  physical-binding or clinical claim.
- Step 5: both edges remain undecided; only an explicit prune removes an edge
  from the retained view, while preserving its source and decision trail.

Preparation verified the saved answer's content hash and graph/review binding,
and HTTP 200 responses for the app, run and question endpoints. This is source
and endpoint verification, not a completed visual or human usability test.
The assisted session record below is separate from the independent pilot table.

### Assisted session record — October 26, 2026

Participant: project user in this conversation; role, browser and device not
recorded. Facilitator: assistant. Entry route: the saved graph and answer linked
above. Timing was not measured. Source-audit findings and navigation instructions
were provided before the response, so this does not establish unaided discovery
or correct biological interpretation.

| Assisted step | Outcome / evidence | Help supplied | Remaining uncertainty |
|---|---|---|---|
| 1. Find the claim | With help, self-reported: “I can find both” in response to locating the connected protein and candidate/accepted status. | Direct saved-answer URL, **3. Answer** location and prior explanation of the expected finding. | Participant has not restated the protein or status; comprehension was not independently checked. No timing or obstacle report. |
| 2. Trace its source | With help: “It provides source db: STRINGDB, but the reference is not supplied”. This matches the saved record's database and absent publication reference. | Instruction to click **[E001]** and distinguish a database from a paper; the source-audit finding had already been disclosed. | No timing or obstacle report. This is assisted identification of provenance, not independent scientific validation. |
| 3. Inspect the experiment | Partial with help: “human Y2H-v1, outcome: detected I see the constructs in JSON, but it is not that clear to me”, followed by the AD/DB fields. Assay/outcome located correctly; construct meaning unclear. | Instruction to select the pair and expand **Assay context and source locators**. Plain-language explanation supplied afterward. | Initial observation; see the partial explanation recheck below. No timing recorded. |
| 3. Assay explanation recheck | Partial with help: “I would guess that bait is a protein used to find the interacting partners.” This captures the broad experimental concept of bait. | Prior plain-language explanation and a request to explain prey/bait and identify the link for construct `100063977`. | No prey definition or construct-mapping link was supplied. Use of the revised display was not confirmed. This does not complete the recheck or establish improved comprehension. |

Steps 4–5 have no participant results yet. Do not count step 1 as completion of
the broader answer-and-citation task in the independent pilot.

Action from step 3: the assay inspector now presents a readable construct table,
expands AD/DB, explains prey/bait as experimental roles, and links the mapping
table next to the explanation. JSON remains available for traceability. This
addresses a reported clarity problem. A partial assisted explanation recheck is
recorded above; improvement and complete understanding remain unestablished.

Separate source audit for this saved example: `orf_map.tsv` maps AD `100063977`
uniquely to CCNO / P22674 (line 9846), and DB `3192` uniquely to CDKN1A / P38936
(line 2959). The assay and raw tables confirm AD/DB IDs at line 3527. The mapping
file hash matches the freeze:
`b03bc31f4c0880697fd7a2d1bfe7a34889773e9317858986825910ffa77849d5`.
This audit explains the specific example; the general JSON projection still does
not assign protein-to-construct orientation and the UI does not infer it from
pair order. Definitions follow the [official PSI-MI vocabulary](https://github.com/HUPO-PSI/psi-mi-CV/blob/master/psi-mi.owl)
and the existing [assay literature review](literature/ASSAY_EVIDENCE_REUSE_20261025.md).

### Source/export recheck — October 26, 2026

A separate read-only developer audit confirmed that the saved app, run, question
and four assay-source links return HTTP 200. All five observation locator files
match their recorded hashes and the exported copies. The existing
`submission_demo_v2_20261026` handoff passes the decision verifier and ZIP
integrity check: 57 files, two abstain decisions with null confidence, and both
original evidence records retained. No source run or historical export changed.

The source links download complete TSV files; they do not highlight the relevant
row. The construct-crosswalk locator still records `row_resolved=false`. These
are access/integrity checks, not participant completion of steps 4–5. The assisted
recheck received a broadly correct description of bait, recorded above. Prey,
construct mapping and the effect of the revised display remain unverified.

### Developer browser and guided-selection check — October 26, 2026

A separate [developer walkthrough](../runs/guided_selection_walkthrough_20261026/index.html)
now exercises the rendered assay inspector, source downloads and export in an
isolated Chrome session. All four visible source links returned their original
records. The downloaded real-example ZIP reopens with 36 authoritative source
files matching the saved run, two abstain decisions and both edges retained.
The assay-role table and mapping-link explanation were visually inspected.

The new guided form sends its complete explicit selection, displays chosen and
proposed settings, and requires plan review before building. Injected model
responses confirmed that matching choices require review and omitted pathways
remain visibly blocked. Backend fixtures also verify mismatches, changed choices
and absent review stop before source access, and that the guarded trace survives
publication, source export, review, replay and assay attachment. These fixtures
do not establish live model performance or biological correctness.

The desktop browser connection and native-control fallback failed to initialize;
an existing isolated Playwright/Chrome installation was used instead. Earlier
developer attempts are preserved: one attempted new construction from a saved
read view, where those controls are intentionally hidden; another assertion
expected an internal key instead of the readable “Shared pathways” label. The
corrected developer check passed without changing application behavior for those
two test issues. See the [tracked receipt](evaluations/guided_selection_walkthrough_20261026_summary.json).

This completes a developer source-to-export check. Participant steps 4–5 and
comprehension of prey/construct mapping remain unmeasured. Exact-choice matching
and the review checkbox do not verify arbitrary free-text assay conditions or
substitute for scientific review. No new model inference or source retrieval ran.

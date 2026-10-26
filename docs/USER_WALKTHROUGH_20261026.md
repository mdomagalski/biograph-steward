# Team usability pilot — October 26, 2026

**Purpose:** a 15–20 minute walkthrough with a colleague who did not implement
the feature. Check whether they can find an answer, inspect its evidence and
understand the export. No biological expertise or scientific verdict is needed.
**No participant results have been recorded.**

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

# Finish the assisted source-to-export walkthrough

This continues the project user's existing assisted session. It does not replace
the planned colleague pilot, and it does not assess biological accuracy. No
model, Brev instance or new source retrieval is needed.

## Current starting point

[Open the saved two-protein example and answer](http://127.0.0.1:8783/?run=assay_workbench_v2_20261026&question=assisted_walkthrough_question_20261026).

The app, saved run, answer and the two source downloads were checked directly on
port 8783. The graph contains two proteins, two evidence edges and one qualified
assay observation. The `Construct crosswalk` and `Author assay table` downloads
match the saved source bytes. These are endpoint and integrity checks, not a new
visual inspection or participant result. The original
[assisted session record](USER_WALKTHROUGH_20261026.md#assisted-session-record--october-26-2026)
is preserved.

Port 8778 still serves an older process: its page responds, but the current
IntAct graph cannot be reopened there. Use 8783 for this session. A system proxy
initially returned 503; direct loopback requests succeeded. Record an actual
participant access problem separately rather than attributing it to the app.

## Next participant prompt

Select the observation under **Qualified assay evidence**. You will see
**Construct crosswalk** and **Author assay table**. Which link would you use to
identify the protein for construct `100063977`? Try to find its row. Describe what
you found, or say where you became stuck.

Do not provide the expected link, protein or row in advance. Both the construct
mapping and the link distinction were previously explained, so any successful
response is still **assisted**. Record separately whether the participant chose
a link, opened the file and found the matching row. The TSV download does not
highlight the relevant row. Correctly choosing a link alone does not establish
successful record lookup or understanding of prey/bait.

## Then complete the export task

Ask the participant to use **Graph and decision export**, select **Export graph
with undecided ledger**, and download **graph, decisions and complete sources**.
The export creates a new package; it does not change the saved graph or make a
scientific decision.

After extraction, ask them to locate `edge_dispositions.jsonl`,
`retained_graph.json` and `baseline_packet/source/graph.json`. Ask what
“undecided” means and whether the original evidence is still available. Do not
supply the interpretation until their first attempt has been recorded. Record
download/extraction difficulties separately from interpretation difficulties.

Successful task completion requires locating the decisions and retained graph,
pointing to the original source graph, and explaining the effect of an
undecided decision. A ZIP integrity check alone cannot establish this outcome.
The developer can run the existing verifier afterward:

```sh
python3 app.py gold-decisions-verify --run /absolute/path/to/extracted/package
```

## Record only observed results

| Remaining step | Current state | What would complete it |
|---|---|---|
| Locate the construct-mapping source | Assisted: selected Construct crosswalk and supplied P22674 for construct100063977 | Correct self-reported source/accession lookup; no timing or observed browser action |
| Explain prey/bait and construct orientation | Assisted: prior broadly correct bait definition; now proposed prey as protein fused to activation domain | Correct prey definition for this two-hybrid record; construct orientation was source-checked separately |
| Export, extract and locate records | Assisted self-report: found the package and named files; their relationship to app graph was unclear | File navigation reported; downloaded/extracted bytes not independently inspected |
| Explain undecided and out-of-scope evidence | No participant result | Participant explains these before receiving the facilitator cue |
| Independent colleague pilot | Not started | Separate participant follows the five tasks in the original worksheet; outcomes and help recorded |

For each attempt, record **independent / with help / not completed / not
attempted**, time and download waiting, the exact obstacle, and help supplied.
Leave pending results blank; do not infer success from a developer replay.

## Separate IntAct demonstration

[Open the current IntAct evidence answer](http://127.0.0.1:8783/?run=intact_workbench_20261026&question=intact_answer_20261026)
when a separate source-qualified example is useful. Its current run and answer
endpoints reopen successfully: four proteins, five evidence edges and four
qualified source records. The existing answer distinguishes source curation,
experimental outcome and local review. This is not a replacement for finishing
the known two-protein task above, and the source-record count is not a count of
independent experiments.

## Biological improvement proceeds separately

The user walkthrough should not delay a frozen biological comparison. Its role
is to test whether people can inspect and share evidence. Biological gain needs
an independent, overlap-qualified reference and a fixed comparison against the
same Pharos baseline. Source preservation, readable answers and a usable export
are useful prerequisites; passing them does not prove an improvement in biology.

## Continuation observed in this chat

The project user selected **Construct crosswalk** in response to the source-link
question, then supplied **P22674** after being asked to open the crosswalk and
search for `100063977`. Both answers match the previously verified source mapping.
This records assisted link selection and self-reported successful accession
lookup; it does not record timing, confirm a particular browser action or test
unaided discovery. The protein and mapping had been explained earlier in the
session. No new explanation of prey/bait was supplied.

The next prompt asks the user to export, download, extract and locate
`retained_graph.json`, `edge_dispositions.jsonl` and
`baseline_packet/source/graph.json`. That question includes a suggested answer
that states undecided edges remain, so selecting it cannot establish an unaided
understanding of decision semantics. The user then reported finding the package but not understanding its contents,
and clarified that the named files were found but their relationship to the app
graph was unclear. The original session record is unchanged.

### Export-scope finding and assisted recheck

The user reported **“Found the package, but its contents are unclear”**, then
**“I found them, but their relationship to the app graph is unclear.”** The issue
was scope, rather than an observed inability to read JSON or locate the files.
Source inspection confirms the saved workspace has two evidence records between
CCNO/P22674 and CDKN1A/P38936: a Pharos/STRING annotation and a separate Y2H
assay observation. The current question's answer selects only the Pharos record.
The export retains the full workspace, including both records and both decisions.

The facilitator supplied that distinction and the three-file map. The app's
export panel now explains whole-workspace scope, separate evidence records for
one pair, undecided versus biological acceptance, and the roles of the retained
graph, decision ledger and original workspace graph. No export format, source
record, scientific decision or frozen evaluation implementation was changed.
The actual served page contains this guidance, and the edited JavaScript passes
a syntax check. This is not a new developer visual-browser assessment.

After being asked to refresh and expand **How the package relates to this
workspace**, the user replied **“Clear now.”** Record this as a positive assisted
clarity recheck for the reported scope confusion, not independent task success or
a population usability effect. The subsequent free-response check is recorded below. No participant timing
was recorded.

### Final role response and scope limitation

The user proposed **“Is the protein fused to the activation domain in a two-hybrid
assay”** for prey. That is correct for this recorded AD/prey two-hybrid context;
the facilitator confirmed it and distinguished DB/bait. This is a correct assisted
response after the earlier role explanation, not evidence of unaided discovery.

The user did not answer the separate question about a protein missing from the
two-protein workspace. The facilitator explained that it is outside this scope
and may have evidence elsewhere. Leave that comprehension check unscored. No
independent explanation of undecided semantics was elicited after the supplied
cue. The assisted session found and corrected one export-scope explanation
problem; a full independent colleague/biomedical-user pilot is still incomplete.

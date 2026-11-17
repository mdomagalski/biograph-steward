# Team review: question → plan → evidence → proposals

**Current public-demo instructions: November 17, 2026.** Allow about 15 minutes, plus loading or downloads. No biological
adjudication or graph expertise is required: we need to know what is clear,
what is misleading and where you get stuck.

Open the [reviewer site](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/)
directly. No sign-in or AWS account is required. The recorded-agent workflow
is installed and checked after a real restart; see
[delivery status](DELIVERY_STATUS_20261115.json). A
[two-page PDF](../output/pdf/BioGraph_Steward_Team_Review_Guide.pdf) provides
the same review tasks.

Direct examples: [recorded KRAS agent](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/?run=native_evidence_workspace_20261115&question=native_physical_KRAS_question_v3_20261115&agent_job=source_agent_eval_dc7b597201da_S01&view=data) and
[qualified TP53 graph](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/?run=source_faithful_workspace_20261113&question=question_20261113T075313Z_1a76b00f&view=ask).
The second is the saved server-side workspace sometimes named
`source_faithful_workspace_20261113` in technical records. You do not need to
find a folder with that name. For this review, use the hosted examples; a code
checkout does not automatically include their complete source data.

Open **Agent workflow** on **Start here**, expand **Open a
recorded agent run**, choose the recorded KRAS example and select **Replay the
recorded run**. The featured record is `source_agent_eval_dc7b597201da_S01`.
This is real saved evidence from the 99-target cohort. Replay checks the saved
sources without calling a model or changing the graph. You need only a browser,
not an AWS account, repository setup, Brev instance or running model.

## Five things to try

Try each before opening an explanation. If stuck for about two minutes, record
where and continue. Separate waiting/loading time from hands-on time. A screenshot of the exact step is useful.
The loading message and spinner identify source checks in progress. Please
report any indicator that is unclear or remains after a result or error appears.

| Task | What to try | What to tell us |
|---|---|---|
| **T1. Follow the question and plan** | Open the verified recorded agent run. Find the original question, chosen tool and arguments. | What did the agent plan to inspect? Was a new model call made during replay? |
| **T2. Read and trace one answer** | Read one cited statement and its focused graph; open that citation's source passport. | Could you find the provider and source meaning? Does physical association establish direct binding? What does candidate mean here? |
| **T3. Understand the proposed review** | Find **Retain candidate context** or **Needs review**, its reason and inspected source assertions. | Does this proposal accept a claim or remove it from the graph? Could you distinguish a source fact from an agent choice? |
| **T4. Find what actually changed** | Open the separate **Review applied graph qualifications** example, then **What changed**. Compare its exclusion explanation with the featured location-reference result. | Which number describes applied filtering and which describes known-label recovery? Could you explain the difference without judging the biology? |
| **T5. Understand the reusable files** | Download the verified recorded-agent JSON. Find its focused graph, source inspections and trace. In the applied-qualification example, read **Export** and its package explanation. | Can you distinguish the focused answer/agent record from the full retained graph, decision ledger and original baseline? Full source packets are supplied separately for final submission or operator use. |

Use the [step-by-step user guide](../HOW_TO_USE.md) or
[agent guide](SOURCE_AGENT.md) if needed, and mark the
task **with help**. The recorded agent uses an eight-result cap; the separate
manual KRAS answer displays all 14 matching partners. This is a difference in
display limits, not evidence that source claims disappeared.

**What changed** remains a product comparison. Its **Graph changes and
assessment** heading introduces applied qualifications and the complete current
scientific assessment, including controls and limits. Development dashboards
and experiment-history menus are excluded from the shared production review.

The native-evidence and retained examples use different source collections in
the same captured cohort. Their total record counts are not a before/after
comparison with one another. Candidate/accepted are local review states. A
source score is not a truth probability, and a missing annotation is not proof
that the biology is false.

## Return feedback

Use the [short reply template](TEAM_REVIEW_FEEDBACK_20261113.txt), or plain text.
For each task, record **independent / with help / not completed / not attempted**,
time spent, waiting time and the exact obstacle. List your **three most
important changes**, marking any blocker. Tell us if a term or display made a
claim seem more certain than the cited evidence supports.

The [product summary](FINAL_SUBMISSION.md) explains the tools, measured outcomes
and their limits. A fresh repository checkout contains code and an explicit
invented fixture; the public real-data demonstration is separate. Full source packets are supplied separately for final submission or operator use. Operator checks
and this prepared guide do not replace independent teammate feedback.

[Earlier instructions](TEAM_REVIEW_GUIDE_ARCHIVED_20261114.md) remain preserved.
Use the current tasks above.

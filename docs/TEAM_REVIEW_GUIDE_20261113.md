# Team review: question → plan → evidence → proposals

**Current instructions: November 16, 2026.** Please send feedback by Monday,
November 16. Allow about 15 minutes, plus loading or downloads. No biological
adjudication or graph expertise is required: we need to know what is clear,
what is misleading and where you get stuck.

Open the [reviewer site](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/)
and use the token supplied privately. The current recorded-agent workflow
is installed and checked after a real restart; see
[delivery status](DELIVERY_STATUS_20261115.json). A
[two-page PDF](../output/pdf/BioGraph_Steward_Team_Review_Guide.pdf) provides
the same review tasks.

Open **Agent workflow** on **Start here**, expand **Open a
recorded agent run**, choose the recorded KRAS example and select **Replay the
recorded run**. The featured record is `source_agent_eval_dc7b597201da_S01`.
This is real saved evidence from the 99-target cohort. Replay checks the saved
sources without calling a model or changing the graph. You need only a browser,
not an AWS account, repository setup, Brev instance or running model.

## Five things to try

Try each before opening an explanation. If stuck for about two minutes, record
where and continue. Separate waiting/loading time from hands-on time. Keep
access tokens out of screenshots.

| Task | What to try | What to tell us |
|---|---|---|
| **T1. Follow the question and plan** | Open the verified recorded agent run. Find the original question, chosen tool and arguments. | What did the agent plan to inspect? Was a new model call made during replay? |
| **T2. Read and trace one answer** | Read one cited statement and its focused graph; open that citation's source passport. | Could you find the provider and source meaning? Does physical association establish direct binding? What does candidate mean here? |
| **T3. Understand the proposed review** | Find **Retain candidate context** or **Needs review**, its reason and inspected source assertions. | Does this proposal accept a claim or remove it from the graph? Could you distinguish a source fact from an agent choice? |
| **T4. Find what actually changed** | Open the separate **Review applied graph qualifications** example, then **What changed**. Compare its exclusion explanation with the featured location-reference result. | Which number describes applied filtering and which describes known-label recovery? Could you explain the difference without judging the biology? |
| **T5. Understand the reusable files** | Find the agent-record download. In the applied-qualification example, open **Export** and its package explanation; download the saved workspace if practical. | Can you distinguish the focused answer/agent graph, full retained graph, decision ledger and original baseline? |

Use the [agent guide](SOURCE_AGENT.md) or
[five-minute source walkthrough](JUDGE_WALKTHROUGH.md) if needed, and mark the
task **with help**. The recorded agent uses an eight-result cap; the separate
manual KRAS answer displays all 14 matching partners. This is a difference in
display limits, not evidence that source claims disappeared.

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
invented fixture; the authorized real-data route is separate. Operator checks
and this prepared guide do not replace independent teammate feedback.

[Earlier instructions](TEAM_REVIEW_GUIDE_ARCHIVED_20261114.md) remain preserved.
Use the current tasks above.

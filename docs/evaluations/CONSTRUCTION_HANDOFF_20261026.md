# Construction and submission checkpoint — October 26, 2026

The bounded question planner is connected to deterministic graph construction,
and the retained graph plus full decision ledger can be downloaded with the
complete retrieved baseline and qualified assay sources. This checkpoint closes
delivery and provenance gaps. It does not establish biological improvement,
correct scientific pruning or successful intended-user tasks.

## Completed and verified

- Exact-scope planning, plan preview, deterministic execution and persistent
  planner provenance through publication, assay attachment, review, replay and
  source-packet export. Invalid or abstained plans cannot execute. A valid plan
  can still misunderstand a question; schema validity is not intent accuracy.
- Retained graph materialization removes only explicit prune decisions, retains
  abstentions and isolated nodes, and recalculates assertion support. Original
  source records and reviews remain available. Changed support cannot silently
  inherit an earlier review verdict.
- Offline verification re-derives the retained graph from the unchanged baseline
  and decisions. Qualified assay publications, exclusions, conditions, reviews
  and licenses travel with the packet. Unsupported KGX mappings still fail
  explicitly rather than flattening those qualifications.
- The [real saved example](SUBMISSION_DEMO_20261026.md) passed export, extraction
  and offline verification: two proteins, two evidence edges, both undecided.
  All 62 source-run files remained unchanged. This already-consumed example is
  an integration check, not a new biological holdout.

The adapter reuses the existing model transport and constructor. Its
[capability note](../CONSTRUCTION_AGENT.md) cites the deployed vLLM version's
official structured-output documentation and NVIDIA model card, and distinguishes
documented capability from local integration checks and unresolved live behavior.

## Engineering verification

The full core suite completed with **756 tests, 26 optional skips, no failures**.
The optional dependencies covered by skipped tests were not verified by this
run. Contract tests include injected model responses, authenticated HTTP routes,
source/trace tampering, immutable outputs, explicit pruning, partial assertion
support, and failures before atomic publication. These are engineering checks;
injected model responses do not measure live model performance.

The suite's local HTTP checks require direct loopback access. An initial run
encountered environment-proxy errors; the final run explicitly bypassed the
proxy for loopback hosts:

```sh
NO_PROXY=127.0.0.1,localhost,::1 no_proxy=127.0.0.1,localhost,::1 \
  python3 -m unittest discover -s tests
```

The combined workbench JavaScript passed the bundled Node syntax check, changed
Python files compiled, and whitespace/local documentation links were checked.
Final review identified a late planning-response race when navigating to another
graph. A generation check now discards stale success and error responses; all
three focused Node state-transition checks pass (`node --test
tests/construction_ui.test.cjs`). No backend code changed after the full suite.
Neither a syntax check nor HTTP contract tests establish visual usability. The
desktop browser bridges were unavailable, so visual browser acceptance and a
colleague walkthrough remain unperformed.

## Prepared, not yet executed

`runs/construction_planner_development_20261026/` freezes twelve development
requests, expected scope/tool choices, code hashes and sanitized model settings.
Preparation made **zero inference calls**. The cases cover supported plans,
cohort/focus selection, ambiguous requests and unsupported operations. Expected
answers are excluded from model input. This is a small development capability
check, not a held-out scientific benchmark.

The declared configuration is NVIDIA Llama-3.1-Nemotron-Nano-8B-v1 with the
existing reasoning-off profile on vLLM 0.8.5. Runtime attestation and the live
comparison remain pending: the read-only SSH probe reported that the local
Brev CLI was not logged in. The user has been asked to restore login and start
the existing instance/model. No paid compute was started automatically.

After access is restored, check the runtime, execute the frozen twelve requests
once, preserve all outcomes, and record one real-cohort plan plus a same-snapshot
deterministic comparison. Do not tune on these outcomes and call the result an
independent evaluation. Tell the user when compute is no longer needed.

The [team walkthrough worksheet](../USER_WALKTHROUGH_20261026.md) is ready but
contains no participant results. The midpoint report remains an unsent working
draft and uses “tested code” rather than implementation test counts.

## Remaining boundaries

Independent biological benefit and reliable scientific pruning are unproven.
Public IntAct/IMEx curation remains the selected next reference-suitability and
source-overlap audit, not an automatically independent gold set. Controlled
source-update checks, broader qualified standards mappings, actual user
assessment and the organizer's exact scoring/format contract still require work.
AWS deployment is optional; receipt of credits does not by itself require a new
service or establish that deployment is verified.

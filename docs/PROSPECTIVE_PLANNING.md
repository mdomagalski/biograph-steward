# Fresh planning cases and the next comparison

This increment prepares the next experiment without Brev, a GPU, source retrieval or live model calls. The served `tool_shapes_v3` planner is unchanged. Earlier successful and failed reports remain historical records.

The [saved October 20 preparation](evaluations/PLANNING_CHALLENGE_PREP_20261020.md) includes the local deterministic results, six pending reference/constraint conflicts and verified artifact identities. No live model score exists for this new set.

The package includes `biograph_steward/planning_challenge_cases.json`: **32 AI-prepared scope questions in 16 paired families**, using the same frozen Pharos/CIViC catalogue. There are 23 draft query references and nine draft abstentions. Each family stays wholly in the `test` split. That split means prospective model evaluation; it does **not** establish an independent biomedical benchmark. The author saw the earlier development questions. Source entities and some capabilities overlap, and semantic independence has not been established.

| Family | Boundary to review |
|---|---|
| Symbol / identifier forms | Exact TP53 symbol and UniProt identifier, including case variation. |
| Alias boundary | A listed symbol versus an unlisted nickname; no external alias guessing. |
| Evidence-view negation | Include candidates versus explicitly exclude them. |
| Double negation | Retain candidate evidence versus use accepted evidence only. |
| Relation negation | Request one relation while explicitly excluding the other. |
| Relation conjunction | Both supported relations versus a single relation. |
| Profile identifiers | A whole known profile ID versus an unknown longer ID. |
| Whole OR profile | Preserve one complete disjunctive profile across spelling/case variations. |
| Compound completion | A known simple profile versus an unavailable negated profile containing it. |
| Lowercase compounds | Unknown complete AND/OR expressions must not become a contained known profile. |
| Background therapy mentions | Distinguish the requested therapy from another drug mentioned as background. |
| All-profile negation | Explicit all profiles versus a named profile after negating “all profiles.” |
| Source disease | Exact CIViC disease versus an unsupported Pharos subtype transfer. |
| Direction scope | Preserve all directions versus an unsupported direction-only filter. |
| Tool conjunction | A single tool versus a question requiring two tools. |
| Intent negation | A research query that disclaims recommendations versus actual treatment advice. |

Pairs are diagnostic contrasts, not independent observations. Summaries report every case and whether an entire family matched. Renaming a group is not proof of a new semantic family.

## Prepare locally

Use the exact control suite from the last v3 experiment. These paths refer to existing local ignored artifacts:

```bash
python3 app.py planning-prepare \
  --baseline runs/brev_tool_shapes_20261020/final_suite/sources/pharos \
  --enriched runs/brev_tool_shapes_20261020/final_suite/sources/enriched \
  --prior-suite runs/brev_tool_shapes_20261020/final_suite \
  --out runs/planning_challenge_20261020

python3 app.py planning-compare \
  --packet runs/planning_challenge_20261020 \
  --out runs/planning_challenge_offline_20261020
```

The second command defaults to `--planner none`. It runs deterministic tools with the supplied draft plans, produces cited outputs and worksheets, and explicitly reports the planner as **not run**. Draft agreement and biological accuracy are not inferred from the deterministic reference arm.

Preparation rejects reused IDs, group labels, normalized prior questions, duplicate normalized new questions and mixed splits. It checks exact source/review file bytes, budgets and the six frozen planning/transport implementation files against the prior control. The full package fingerprint changes because the new preparation runner is part of the software; preparation therefore freezes a new suite. The planner's prompt, resolver, scope rules, validators and transport remain unchanged.

| Prepared artifact | Purpose |
|---|---|
| `packet.json` | Hash-bound controls, case identity, artifact inventory and limitations. |
| `suite/` | Current implementation, questions, fixed budgets and copied source/review bytes. |
| `review.html` | Questions, draft plans, catalogue, tool contracts and scope rubric before inference. |
| `case_reviews.tsv` | Blank scope judgments; edit a copy rather than the immutable original. |
| `catalogue_and_tools.json` | Source identities and actual tool capabilities. |
| `scope_audit.json` | Offline constraint diagnostics; no generated plans or model-performance score. |

The audit separately checks whether a draft reference passes post-generation validation and fits the constrained generation schema. These can differ. A blocked draft reference reveals a constraint/reference conflict requiring review. An abstention not forced by the schema is not evidence that a model will fail; the model can still choose to abstain. Do not adjust reference plans to match the parser.

## Review the scope before model inference

Scope review is an engineering task grounded in the catalogue and tool contract. It does not require deciding whether a biological claim is true. Start with `review.html`, then use the audit as a diagnostic rather than as the answer key.

1. Confirm the question has one clear interpretation and the intended action is implemented.
2. Check the complete identity, including profile AND/OR/NOT, and distinguish background or negated mentions from requested targets.
3. Check exact source disease, therapy scope, candidate/accepted view and requested relations. Preserve full therapy sets.
4. Check every requested qualifier. Require abstention if the necessary filter, prediction, clinical advice, graph write or second query is unsupported.
5. In a **copy** of `case_reviews.tsv`, set `reference_plan_correct` to `yes`, `no` or `uncertain`, and supply `reviewer` and `notes`. Leave uncertain scope unapproved. Do not edit questions, references, identifiers or hashes.

A rejected reference requires a corrected question/reference in a **new packet**; retain the old packet. If review or diagnostics are used to tune the planner, treat these cases as development and obtain another prospective set for later claims. Software records reviewer attribution but cannot verify their independence or expertise. No judgments are automatically filled in for the supplied real-source packet.

## Run the model comparison when Brev returns

`planning-compare --planner live` requires every scope approved in a separate worksheet before constructing the configured model client. Missing model configuration or a protocol mismatch fails before inference; there is no fallback to a replay, heuristic or unexecuted success. The historical generic `evaluation-run` command remains available for other experiments; this review gate belongs to the new prospective runner.

After the evaluated source revision and frozen packet have been transferred to the VM's persistent volume, with Brev running:

```bash
docker compose -f compose.yaml -f compose.brev-local-model.yaml exec -T steward \
  python app.py planning-compare \
  --packet /data/runs/planning_challenge_20261020 \
  --scope-reviews /data/runs/planning_challenge_scope_reviewed.tsv \
  --planner live \
  --out /data/runs/planning_challenge_live_01
```

Check the pinned model revision, vLLM image, generation settings and health against the [local-model deployment](LOCAL_MODEL.md) before inference. The runner verifies the frozen code/data/protocol; it cannot independently attest which weights an HTTP server loaded. No compute is started by the runner, and this preparation does not restart Brev.

Each question receives one model request and at most one validated read-only query. The model receives the question and application contracts, not case IDs, draft references, review notes, source statements or expected answers. Invalid plans, inappropriate abstentions and errors remain visible. A failed first run must remain saved; fixes require a new controlled experiment.

## Judge the result

The result includes the existing evaluation report/worksheets plus `comparison.json`: per-case draft matches, per-family all-matched flags, statuses, call counts, scope-review attribution and exact query-output comparisons with the enriched deterministic arm. Output equality excludes only `source_run` and the answer hash derived from that arm label. The submitted scope worksheet is hashed and snapshotted before inference; its saved copy is scored separately from scientific evidence judgments.

Inspect false declines of supported queries, unsupported requests allowed into queries, identity/profile simplification, unwanted therapy or evidence-view broadening, and failures concentrated in a family. Do not rank versions by answer count alone. Retain all cases and disclose application-enforced abstentions and constraints.

Agreement with reviewed scope references is still a planning result. Citation-support accuracy remains unknown without publication review: check the abstract/full text, complete profile, disease, therapy set, direction and study conditions, and record a locator/span in the evidence worksheet. The controlled prediction experiment needed to test biological graph improvement remains separate.

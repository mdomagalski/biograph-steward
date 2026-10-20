# CRC evidence-quality pilot

This increment connects the existing source verifier to an inspectable comparison and to original assertion passports. It asks whether checks identify source-contract errors while preserving source-supported text. It does not establish biological truth, clinical validity, general pruning accuracy or predictive improvement.

## Panel and reference scope

The fixed panel reuses six saved CRC publications from the October 20 evidence-value pilot. Each publication supplies one exact-excerpt control, three binding/citation edits, two semantic edits and one complete, unmodified CIViC annotation: 42 cases in total. The six controls and 30 edits have explicit source-contract references; the six original annotations have no reference support label. Exact-excerpt controls retain their source wording and the complete supplied abstract. Edits cover protein identity, citation identity, quotation fidelity, disease, variant, regimen, model/population, treatment setting, statistical qualification and negation.

These references are AI-authored and inspectable, not independent biomedical gold. A changed claim is flagged relative to the supplied text/identity contract, not declared false everywhere. The controls are deliberately easy extractive checks, not a representative collection of scientifically valid graph edges. Related cases share publications. All sources are reused development material; this is not an unseen or confirmatory evaluation. Human scientific label count stays zero and scientific accuracy stays null. Public benchmark model-pretraining overlap remains unknown.

The experiment freezes original source records, complete saved paper records, passage locators, literature/source manifests, case changes, references, implementation hashes and decision rules before inference. It verifies historical source bytes without re-executing or relaxing the old experiment's frozen-engine check. The new experiment records its own engine. All references, change descriptions, case kinds and original/control/edit names are withheld from model inputs; task identifiers are opaque hashes.

## Three views and decisions

All views use the same case inventory:

1. Original: retain every assertion as unverified in a sandbox preview.
2. Deterministic: propose quarantine for a mismatched frozen KRAS protein binding, publication identity or altered attributed quotation. Structural validity does not establish source support.
3. Assisted: reuse those checks, then request one bounded source assessment for each structurally usable case. Valid SUPPORT retains the claim as source-supported in the preview. CONTRADICT proposes quarantine. NOT_ENOUGH_INFORMATION, invalid output, timeouts and model errors request review. None changes a lifecycle state.

This yields 18 blocked integrity cases and at most 24 requested verification turns. Inputs contain only a claim and the numbered source text. The existing tool-disabled verifier contract applies: one turn, no repair, retry, fallback or additional retrieval; decisive outputs require up to three exact supplied quotations. Exact quotations establish reference fidelity, not entailment. Execution settings and traces are retained. Errors remain in the denominator. An offline run reports the assisted arm as not run; abstaining on everything cannot be presented as a successful verifier run.

The initial `free_string.v1` execution is preserved separately. The model dropped the `task-` prefix when returning opaque task identifiers, so otherwise well-formed responses failed identity validation. Follow-up packets explicitly freeze `guided_enum.v2`: each request constrains the output schema's `task_id` to the exact supplied identifier. This changes routing metadata, not permissible verdicts, passages, references or inference budgets. Wrong identifiers still fail validation; no completed output is repaired. The two executions remain distinct development comparisons, not independent scientific replications. Existing frozen packets and saved results retain their original contract and remain replayable.

Report flag precision/recall on the 36 scored source-contract cases, unsupported test cases retained, supported controls retained, false-flag rate and false-quarantine rate. A review request counts as a flag but not as a quarantine proposal; those rates remain separate. Empty precision denominators are null. Original annotations are displayed and assessed but excluded from these metrics. Model failures, verdict counts and exact-quotation validation accompany the metrics. No model or graph policy is promoted automatically.

## Commands

Use new output directories; previous packets and results are immutable:

```sh
python3 app.py quality-prepare \
  --packet runs/crc_evidence_value_20261020/final_packet \
  --literature runs/crc_evidence_value_20261020/literature \
  --out runs/crc_evidence_quality_20261020/packet

# Source inspection and deterministic comparison only; no inference.
python3 app.py quality-run \
  --packet runs/crc_evidence_quality_20261020/packet \
  --out runs/crc_evidence_quality_20261020/offline

# Explicit separately configured verifier; no question-planning calls.
python3 app.py quality-run \
  --packet runs/crc_evidence_quality_20261020/packet \
  --verifier configured \
  --out runs/crc_evidence_quality_20261020/live

# Recompute decisions, scores and citation checks without model calls.
python3 app.py quality-verify --result runs/crc_evidence_quality_20261020/live
```

The Brev model can be selected explicitly for this runner without changing the app's planner settings or enabling a live-verification button:

```sh
BIOGRAPH_VERIFIER_PROVIDER=api \
BIOGRAPH_VERIFIER_MODEL=nvidia/Llama-3.1-Nemotron-Nano-8B-v1 \
BIOGRAPH_VERIFIER_ENDPOINT=http://127.0.0.1:8000/v1/chat/completions \
BIOGRAPH_VERIFIER_API=nim_chat \
BIOGRAPH_VERIFIER_PROMPT_PROFILE=nemotron_nano_v1 \
BIOGRAPH_VERIFIER_MAX_OUTPUT_TOKENS=3000 \
BIOGRAPH_VERIFIER_TIMEOUT=120 \
python3 app.py quality-run --packet PATH_TO_FROZEN_PACKET \
  --verifier configured --out NEW_RESULT_DIRECTORY
```

This uses the existing local vLLM model, not a NIM deployment or AWS service. No new account or key is required. Freeze the packet before executing this command. A changed engine requires a new packet; do not rewrite the packet or discard a poor result.

## App and review

The app's **Evidence-quality comparison** section lists verified completed results and their reports/ZIPs. Reports provide three retained-preview filters, the complete findings, exact source passages, explicit before/after edits, source identities and unscored originals. Hidden preview cases remain in the export.

For real CIViC edges, the existing evidence passport shows only the unmodified-annotation assessment, bound to the exact Pharos snapshot, CIViC snapshot and assertion revision. Synthetic edits never attach to real graph edges. A mismatched snapshot/revision yields no assessment, not implied support. Invalid saved results are withheld. The protected read-only endpoint is `/api/evidence-quality`; scoped passports use `?run=RUN_ID&assertion=ASSERTION_ID`. Existing authentication/origin rules apply.

The general assertion table also includes molecular-profile assertions through their protein crosswalks. Previously its final row filter required the subject itself to be a protein, hiding CIViC profile edges even after selecting that family. The dedicated therapy-question workflow and the source records are unchanged.

Use the existing human-review form to approve any actual state transition. It records reviewer, reason and time in a new run and preserves the original. Model recommendations cannot invoke that form or create human identities. `reviewer_worksheet.json` in the export is blank; edit a copy for independent adjudication. Importing it does not yet apply reviews or create gold labels.

The next scientific validation needs independently reviewed source-support cases, non-extractive positive controls and more independent publications. The challenge's same-model measured graph-link task remains separate. The consumed DepMap gene holdout is not opened or retuned by this workflow.

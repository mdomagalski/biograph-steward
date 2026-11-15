# Public-reference delivery update

This addendum prepares the November 15 public-reference results for final
delivery. It does not record an AWS rollout, change the existing private draft
release, or supersede any earlier checksums. The reviewed code checkpoint,
hosted runtime, source workspace and research report each retain their own
identity.

## What reviewers should see

Use three concrete outcomes, each with its denominator and meaning:

| Assessment | Result | Explanation to retain |
|---|---|---|
| Positive localization-label recovery | Captured Pharos **41/51**; qualified native GO **44/51**, across 31 matched primary proteins | Two proteins improve and 29 stay unchanged. The gained labels have shared HPA provider exposure. This measures labelled location coverage, without estimating whole-graph accuracy. |
| Exact clinical claim–evidence matching | **2/46** source evidence items match explicit human-reviewed supporting labels | The complete five-field projection and evidence paragraph match. Other source items stay unmatched; this does not adjudicate the richer complete assertion or accept its candidate state. |
| Same-release interaction-source qualification | Negative-reference conflicts **492 → 330**; positive hits **4,889 → 4,300** | Physical versus functional presence on the same mapped known units. The loss of supported positives remains visible. Physical association can include co-complex evidence. |

The [full report](../../evaluations/public_gold_20261115/report.html) retains
all predefined comparisons, alternative references, unavailable cases and
source-overlap qualifications. The earlier function-prediction result remains
a separate task with its own controls and intervals.

The [native-location workspace guide](../../evaluations/NATIVE_LOCATION_WORKSPACE_20261115.md)
puts additional source annotations into the ordinary answer → source inspection
→ export workflow. Its **3,309 source rows / 429 protein–term concepts / 94 of
99 primary targets** are counts of records and concepts, not independent
experiments. All annotations remain candidates. The other five targets have
explicit empty answers whose meaning is unknown coverage. This is a separate
Pharos-plus-native workspace, without replacing the enriched default.

## Hosted delivery

The existing reviewer app and login remain the access route. Add a separately
named saved example and the aggregate scientific report through the established
private source-packet installation process. Preserve the earlier workspace and
runtime for rollback. Keep the shared reviewer ingress limited to saved-data
inspection and exports.

Before describing the new example as live, record the installed code/source
identities and verify these operations through the actual authenticated route:

1. Open a saved native-location question and read its written answer.
2. Inspect a cited native annotation, its source reference and candidate state.
3. Open the accepted-only view and distinguish an unaccepted candidate from
   missing biological evidence.
4. Download the answer and complete workspace exports. Confirm the source
   records, original Pharos baseline and exhaustive decisions remain present.
5. Reopen the earlier TP53 example and the separate scientific assessment.

Publish only the aggregate assessment material in an unrestricted release.
Raw reference cases, source sequences, model weights, credentials and the
uncleared mixed-source demonstration graph remain outside it. Public source
availability does not itself grant redistribution permission.

## Final software checkpoint

The older tested core ZIP is pinned to `9bf202f`; it does not acquire later
capabilities when a branch is pushed. Rebuild only after the intended code
changes have been reviewed and committed. The existing source-release builder
reads a committed allowlist and creates no cloud resources:

```sh
python3 deploy/aws/prepare_release.py --ref HEAD --out runs/final_runtime_release_20261115
```

Use a new output directory if that name already exists. The full runtime tar
and the standalone core ZIP have different scopes. Reuse the demonstrated
standalone acceptance process: create the core subset with `app.py`,
`biograph_steward/`, `LICENSE` and its own launch instructions; extract it into
a fresh folder; construct the synthetic example; ask a cited question; download
the actual graph/decision and answer ZIPs; restart and reopen the saved answer.
The source-release builder is in
[`deploy/aws/prepare_release.py`](../../../deploy/aws/prepare_release.py), and
the original private core acceptance operator is
`runs/software_delivery_core_20261115/verify_core_release.py`. Its fixed commit,
output directory and dated launch text require deliberate updates for a new
checkpoint. Do not rerun it unchanged and label the old archive current.

Create new checksums and a receipt tying the final source commit to the software,
aggregate-report packet and presentation. Update the review index only after
those bytes are verified. A draft release and a private branch remain distinct
from the eventual public MIT repository/release and organizer submission.

## Presentation and final reviewer feedback

The presentation update preserves the existing six main slides and three
appendices, adding one editable public-reference appendix. Its visible
qualifications keep positive recovery, exact projection support and the
interaction trade-off separate. Saved app screenshots remain dated captures,
without asserting that they show the newest source profile.

Teammate review remains due Monday, November 16. Prioritize access failures,
unclear terms, misleading biological interpretations and export confusion.
Operator/API checks do not replace that feedback. The supplied submission
deadline is November 17, 2026; no hidden organizer labels are required to finish
this reproducible handoff.

No model server or GPU is needed for these saved-data delivery steps. Keep the
AWS reviewer service available while the team reviews it.

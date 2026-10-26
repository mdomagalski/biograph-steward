# Frozen Lambourne assay corroboration

October 25, 2026 (America/New_York). **The bounded assessment is complete.**
The adapter reproduces all 3,222 published nomination statuses from the authors'
raw human assay export, with no consistency errors. In this selected panel,
Pharos-represented pairs have a higher assay detection fraction than resolved
pairs with no match under the declared lookup. This measures retrospective
assay corroboration; it does **not** establish independent Pharos accuracy or
an improvement from Steward.

The [pre-outcome decision](../literature/REFERENCE_COMPARATOR_DECISION_20261025.md),
[identity audit](LAMBOURNE_REFERENCE_AUDIT_20261023.md) and
[Pharos lookup](LAMBOURNE_PHAROS_LOOKUP_20261023.md) fix the task and comparator.
The [aggregate JSON](lambourne_corroboration_20261025_summary.json) records the
result and source hashes. Full local artifacts, including every nominated pair
and its source locators, are under
`runs/lambourne_corroboration_20261025/`; the readable result is
`results/report.html`. These run files are ignored by Git.

## Result and denominators

| Frozen Pharos lookup state | All nominations | Detected | Not detected | Assay excluded | Detected / assay eligible |
|---|---:|---:|---:|---:|---:|
| Represented | 2,325 | 334 | 1,632 | 359 | 334 / 1,966 = **17.0%** |
| No match, both endpoints resolved | 895 | 42 | 666 | 187 | 42 / 708 = **5.9%** |
| One endpoint unresolved | 2 | 0 | 2 | 0 | No comparator score |
| Total | **3,222** | **376** | **2,300** | **546** | 2,676 assay eligible; 2,674 comparator eligible |

The 546 excluded nominations comprise 478 failed sequence confirmations,
41 autoactivators and 27 failed tests. They are retained in the audit and are
not counted as negative assays. There are no ambiguous confirmations,
unexpected states, inconsistent nominations or repeated raw rows in the actual
selected population. The two unresolved pairs retain their assay outcomes but
have no Pharos comparator score.

Exclusion fractions differ between represented and resolved no-match groups:
359/2,325 (15.4%) versus 187/895 (20.9%). Reported detection fractions therefore
condition on assay eligibility; they are not yields for the entire nominated
population.

The predeclared exposure strata materially qualify the aggregate comparison:

| Prior pair-overlap flags | Represented: detected / eligible | Resolved no-match: detected / eligible |
|---|---:|---:|
| Neither HuRI nor INMC flag | **74 / 1,619 = 4.6%** | **16 / 650 = 2.5%** |
| HuRI flag only | 259 / 343 = 75.5% | 26 / 56 = 46.4% |
| INMC flag only | 1 / 4 = 25.0% | 0 / 2 = 0.0% |
| Both flags | No observations | No observations |

The two unresolved pairs are in the neither-flag stratum. Across the full
panel, **285 of 376 detections (75.8%) have a HuRI-overlap flag**. These flags
combine the prespecified registry and author-crosswalk checks. Absence of both
flags does not establish independence from every Pharos source or study. The
no-flag stratum is descriptive, not a newly selected independent test set.

Exact source-provider bundles are also reported in JSON/HTML. Their differing
composition and evidence types prevent a causal ranking of provider quality.
The fixed report contains no accuracy, F1, AUROC, p-value or pair-independent
confidence interval.

## What was reused and verified

The endpoint is detection in the authors' reported human Y2H-v1 assessment.
[Lambourne et al.](https://www.nature.com/articles/s41467-026-70942-x) describe
the experimental methods; the [official repository](https://github.com/CCSB-DFCI/ai-interactome-experimental-assessment)
supplies the source tables and historical preprocessing. The paper's human
figure-caption assay label differs from the Methods/files; this discrepancy
remains disclosed rather than silently resolved.

The verified implementation gap was local, reproducible adaptation of that
released transformation and a comparator sealed before pair-level outcome
access. No new biological labeling rule or model was invented. The adapter:

- Reads the duplicated `source_dataset` headers by position, preserving the
  original nomination population. The full supplement has 4,775 rows; 1,553
  control/nonnomination rows are outside this assessment.
- Preserves exact AD/DB construct orientation while checking the authors'
  sorted protein identities against the released ORF crosswalk.
- Reproduces the authors' status logic, then separately requires explicit
  applicable sequence confirmation for an evaluable assay. Missing
  confirmation is not silently accepted.
- Stops the assessment if any nomination's raw status, identity or construct
  fails reconciliation with the published supplement. The processed intermediate
  absent from the pinned repository and the private control mapping are not
  reconstructed.

Before opening real outcomes, 24 synthetic tests passed in Python 3.10.20 with
the authors' pandas 1.4.3 / NumPy 1.23.0 versions. These include all 36
confirmation truth-table combinations (30 valid transformations and six
author-rejected inconsistencies), CSV boolean encodings and that pandas
version's missing-value tokens. The production adapter itself uses only the
standard library. The repository's MIT license and full preprocessing source
are preserved in the freeze; this does not replace the separate rights review
needed for redistributing upstream Pharos data.

The comparator preserves all 3,222 nominations, their three lookup states,
provider bundles and prior-exposure flags. It refers to the saved Pharos319
PPI retrieval with confidence 400 and a 5,000-neighbor cap per accession. All
resolved-target source counts reconciled in the existing audit. A no-match is
specific to this profile and snapshot, not proof of global absence from Pharos.

## Freeze, first access and replay

The runner replayed the complete original Pharos lookup before sealing the
comparator. It pinned the sources, source receipts, synthetic author replay,
full nomination inventory, eligibility rules, descriptive summaries,
implementation hashes and Python 3.14.0 runtime.

| Receipt | Value |
|---|---|
| Protocol sealed (UTC) | `2026-10-26T00:28:42.393036+00:00` |
| First pair-level outcome access recorded (UTC) | `2026-10-26T00:28:58.551026+00:00` |
| Protocol content SHA-256 | `f3601f4e96393a2d1d2352e655ba0745000b5e4d209a83656a3cba08b0598351` |
| Result content SHA-256 | `1738a688ad8709eb270a6a7fec6458c64add4ec9768e4f2526f1f35474be1aee` |
| Source-table commit | `fb05ab3ca2cc0fcaf402bb0df568e95a5158178b` |
| Historical preprocessing commit | `ec477f7043195c46ce1787cbd7e09fd407d21b97` |

Both timestamps are October 25 locally. Public paper aggregates and nomination
metadata were already inspected before this freeze, as disclosed in the
specification. The panel is retrospective and public, not a prospective hidden
test. **Its pair-level outcomes are now consumed for future development.**

An exclusive opening receipt is written before semantic outcome decoding;
failed attempts also consume the packet. A second `run` against the same freeze
is rejected even with a different results directory. `verify` is an explicit
replay, not a fresh assessment:

```sh
python3 scripts/assess_lambourne_corroboration.py verify \
  --freeze runs/lambourne_corroboration_20261025/freeze \
  --out runs/lambourne_corroboration_20261025/results
```

Replay passed after completion. It requires the exact pinned implementation,
runtime and saved packet. Outcome source bytes, comparator evidence and source
locators are included in the freeze. The original Pharos chunks were verified
during freezing but were not duplicated; repeating the full retrieval audit
requires those original chunks. A fresh Git clone alone does not contain the
ignored study packet. Do not reseal an old packet to admit newer code.

The full core regression completed **649 tests, with 26 optional tests skipped**
and no failures. The 24-test legacy pandas replay passed separately without
skips. A separate post-access positional CSV join independently reproduced
every nominated raw/published status, applicable confirmation, exact AD/DB
construct match and the reported counts. This is an independent software
cross-check, not independent biological validation or expert adjudication.

## Interpretation and next decision

This closes the author-adapter and baseline-corroboration execution gaps. It
does not close Pharos imported-study lineage, establish cancer relevance,
provide official challenge gold, or show a Steward improvement. No learner or
graph change was evaluated in this increment. The earlier INMC result remains
unchanged: no consistent hierarchy benefit was demonstrated.

The **42 detected pairs with no resolved-profile Pharos match** are candidates
for a qualified assay evidence layer. Only 16 lack both prespecified overlap
flags; none should be labeled globally novel or independently validated from
this lookup alone. If integrated, retain study, assay, constructs, original
source locators and overlap/lookup qualifications. Preserve all detected,
nondetected and failed observations in the evidence audit; a Y2H nondetection
does not automatically invalidate a functional or co-complex Pharos edge.

Such an overlay can be assessed for information coverage, faithful context and
traceability. Its own imported observations cannot simultaneously be its
independent accuracy test. A later predictive benefit claim still requires a
justified change, separate reference eligibility and a fixed comparison against
Pharos plus a simple-addition control. No new source search or model sweep is
authorized merely to obtain a larger score. Brev was not needed for this run;
any later model/GPU step should be announced before compute is started.

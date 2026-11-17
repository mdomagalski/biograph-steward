# Shared-record flags in the workbench

The workbench can display a verified provider trace beside the original assay
context. This answers whether an attached curated record was observed in a
particular aggregator release. It does not turn matching pairs, papers or
methods into matching experiments.

## Use the existing trace

The command reads saved local inputs only. It copies the original workspace
byte for byte into a new directory and adds a separate supplement:

```sh
python3 app.py assay-source-reuse \
  --run runs/intact_consumed_flow_20261027_attempt_01/execution/batch_0001/attached \
  --trace runs/provider_pair_lineage_20261027_attempt_01 \
  --out runs/source_reuse_workbench_20261027
python3 app.py assay-source-reuse-verify --run runs/source_reuse_workbench_20261027
```

These real-data inputs are local artifacts, not bundled with a clean checkout.
Synthetic tests exercise the same publication/attachment pipeline without
retrieving sources. Neither a model nor Brev is needed.

Open the new run in the live workbench. The assay table, selected observation
and guided source answer show a **Source reuse** field. The report and complete
workspace ZIP are linked beside it.

| Flag | Meaning |
|---|---|
| Shared record in current STRING 12.5, user-assisted | The user copied an exact source-record link from STRING. The preserved typed IntAct source verifies that record's aliases and experiment/publication context. |
| Current STRING reuse unresolved | The record was not identified in the observed, truncated view. It may still be reused. |
| No verified source-reuse annotation | This workspace has no supplement; no reuse conclusion is inferred. |
| Source-reuse audit could not be verified | The supplement or its bindings failed verification. The underlying assay context remains inspectable. |

For TAS1R2–TAS1R3, `IM-30398-1` / `EBI-67107463` is shared with current STRING;
`IM-30398-5` remains unresolved. **Both records' inclusion in the original
Pharos319 import remains unknown.** The current STRING finding must not be
presented as proof of the historical Pharos build inputs. Reactome resource
reuse is documented in the provider report, but no exact Reactome record flag
is manufactured from matching names.

## What travels in the workspace ZIP

| Artifact | Relationship to the workspace |
|---|---|
| Original graph, attachment, observations, source files and reviews | Preserved unchanged; the supplement makes no graph or review decisions. |
| `source_reuse.json`, `source_reuse_records.jsonl` | Separate classifications bound to exact source hashes and observation identities. |
| `source_reuse.html` | Readable qualifications and limits. |
| `source_reuse_source/` | Copied trace report/ledger/manifest, preparation scope and user-copied source-link observation. |
| `source_reuse_manifest.json` | File inventory and implementation fingerprints for offline verification. |

The copied proof and the workspace's existing `assay_source/` are sufficient
for verification after moving the package and removing the original trace
directories. Absolute source paths in that proof are provenance labels; the
verifier does not reopen them. It never executes the trace's publication script.
Hash checks establish integrity and replay, not independent authentication of
the user's browser observation.

**Download run ZIP** includes this supplement. The graph/decision export and
saved answer payload keep their existing formats; they do not acquire a reuse
verdict or a new confidence value. The live app displays the supplement beside
the answer. A new reviewed or reconstructed run requires a newly bound
supplement rather than inheriting this one's display status automatically.

## Existing methods used

The project already reads IntAct through the official
[PSI-MI JAMI implementation](https://link.springer.com/article/10.1186/s12859-018-2119-0).
This increment uses that captured typed output and the existing overlap audit.
The [PSI-MI vocabulary](https://github.com/HUPO-PSI/psi-mi-CV/blob/master/psi-mi.obo)
and [IntAct validator](https://www.ebi.ac.uk/intact/validator/help.xhtml)
distinguish interaction identities, IMEx registration, experiments and primary
publication references. Generic cross-references are not promoted to record
identity, and an experiment's IMEx study registration is not an experiment ID.

[MImerge/MIscore](https://academic.oup.com/database/article/doi/10.1093/database/bau131/2433131)
already address interaction evidence redundancy and scoring;
[IMEx](https://www.nature.com/articles/s41467-020-19942-z) documents reuse by
aggregators. We add the missing display and portable binding to those existing
evidence distinctions. We do not implement a new deduplication algorithm,
independence estimator or confidence score.

The remaining scientific gap is unchanged: useful assay detail and verified
source reuse do not demonstrate biological improvement. Historical provider
imports remain untraced. A later comparison needs a task-specific intervention,
a control receiving the same information and a separately frozen evaluation.
The fresh four-study reference remains unopened.

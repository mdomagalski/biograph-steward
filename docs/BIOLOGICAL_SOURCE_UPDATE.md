# Versioned biological source enrichment

The workbench can publish a separate graph with a newer STRING source layer,
qualified MAP-IT tissue observations and source-reported SIGNOR regulation. The Pharos snapshot, original records,
assertions and review history remain intact. These additions improve inspectable
source coverage; independent biological accuracy and pruning benefit remain
unproven.

The current three-source example is **`crc_biological_workspace_20261112`**:
9,865 entities, 16,985 evidence records and the same 99 primary Pharos targets.
It adds 290 SIGNOR records to the two-source example below. In **Evidence &
sources**, select **Regulation and experimental context**. Presets show MCC in
colorectal cell models, inhibitory BRAF phosphorylation and a citation-context
limitation. Source direction, effect, site, experimental organism and exact
cell/tissue labels remain distinct from local review and literature notes.
Twenty-four records have agent-assisted source checks; the remaining 266 are
explicitly unexamined. No note automatically validates or prunes an assertion.

SIGNOR's TAX_ID describes the supporting experimental organism. Its manual
documents remapping some animal-model relations onto human orthologue proteins;
the app preserves both meanings. The Oct2026 release's actual 27-column schema
and `t`/`f` directness values differ from the checked upstream importers, so a
small release-bound standard-library reader retains the literal fields.
Unknown assay hosts and missing context are not inferred. The source is CC BY
4.0; exact source material and required attribution travel with the workspace.

The MCC example supplies added mechanistic context for a pair already present
in saved STRING at 0.292, below the workspace cutoff. It is not labeled a novel
relationship or independent new study. See the [biological assessment and its
limits](evaluations/BIOLOGICAL_IMPROVEMENT_20261112.md).

To publish that source and include it in an update, use the saved release,
snapshot and optional saved PubMed metadata:

```sh
python -m biograph_steward signor-source-publish \
  --source /path/to/Oct2026_release.txt \
  --snapshot runs/crc_civic_final_20261015/snapshot.json \
  --pubmed-xml /path/to/pubmed.xml \
  --out runs/my_signor_publication
python -m biograph_steward biological-update \
  --run runs/crc_civic_final_20261015 \
  --string-publication runs/my_string_publication \
  --mapit-publication runs/my_mapit_publication \
  --signor-publication runs/my_signor_publication \
  --out runs/my_biological_workspace
python -m biograph_steward regulatory-question \
  --run runs/my_biological_workspace --protein UniProtKB:P23508 \
  --direction incoming --out runs/my_mcc_answer
```

The new three-source packet and all-abstain graph/decision export both passed
offline replay, with every original Pharos entity, evidence record and assertion
unchanged. The following section preserves the earlier two-source delivery.

The completed colorectal-cancer example is `crc_evidence_enriched_20261111`.
In **Evidence & sources**, select **Show EGFR tissue evidence**. Search the 120
partner observations, inspect source and assay context, and download the displayed
answer JSON. The question is deterministic and reads saved evidence; it makes no
model call or source request. The ordinary graph explorer can also traverse the
additional evidence and participant proteins.

## What changed

| Property | Original workspace | Enriched workspace |
| --- | ---: | ---: |
| Primary Pharos targets | 99 | 99 |
| All graph entities | 9,746 | 9,865 |
| Evidence records | 15,717 | 16,695 |
| Distinct PPI annotation endpoint pairs | 718 | 956 |
| Qualified MAP-IT partner observations | 0 | 120 |

All original node, evidence and assertion records are unchanged. All new
assertions remain candidates. Neither automatic acceptance nor pruning is
performed.

**STRING 12.5** supplies 858 additional versioned functional-association records
at the fixed native score threshold of 0.4. They cover 238 pairs absent from the
original workspace and 620 already represented pairs. Native physical scores
remain annotations, not direct-binding claims. The capture accounts for all
4,851 possible pairs among the 99 requested accessions; one accession has no
provider mapping. Missing rows and subthreshold scores are preserved as coverage
states. No assay outcomes select STRING records.

This actual 99-target graph update is distinct from the earlier 3,222-nomination
coverage diagnostic. The larger diagnostic suggested that newer scores could
cover 20 of 42 old-graph-absent detections at 0.4; those figures are not results
of this CRC graph update or independent validation.

**MAP-IT** supplies 120 exact-accession EGFR partner observations from the
completed source-key-corrected reanalysis. There are 119 additional participant
proteins; they are not silently added to the primary Pharos target cohort.
Enrichment is qualified as pooled colorectal tumour/adjacent-tissue proximity,
with the method, full-family adjusted statistics, identity lineage, sampling and
source citations retained. It does not establish direct binding or
tumour-specific rewiring. The full 5,378-group model ledger preserves conditional
noncalls, unresolved identities and the bait self-observation exclusion.

The full April 2024 Pharos PPI archive contains 33 of these pairs under its public
resolver policy, another 40 as raw records below the public score threshold, and
no nonmock pair record for the remaining 47. All 120 partner accessions resolve
in that archive. These are historical overlap states, not proof that 47 pairs
are absent from current Pharos or new scientific discoveries. Additional source
records and cited publications are never treated as independent experiment counts.

The source-selection gap is real: the existing assay attachment supports
Lambourne/IntAct records inside small primary cohorts, and physical priority only
orders existing paths. This extension reuses the existing typed STRING parsers,
immutable publication capture, source replay, assertion review and gold packet
mechanics. It keeps that existing assay contract unchanged and adds explicit
adapters for these two different sources.

## Reproduce from saved source artifacts

Core use needs Python 3.10+ and no model, GPU or additional dependency. Complete
saved source packets are supplied separately from Git; source data keep their
own licenses.

```sh
python -m biograph_steward string-source-publish \
  --capture runs/historical_pharos_mapit_20261112/current_release_fingerprint \
  --out runs/my_string_publication
python -m biograph_steward mapit-source-publish \
  --analysis runs/historical_pharos_mapit_20261112 \
  --out runs/my_mapit_publication
python -m biograph_steward biological-update \
  --run runs/crc_civic_final_20261015 \
  --string-publication runs/my_string_publication \
  --mapit-publication runs/my_mapit_publication \
  --out runs/my_enriched_workspace
```

The STRING publisher accepts the saved whole-cohort capture contract, not
arbitrary network rows or a nominated-pair capture presented as a complete
network. The MAP-IT publisher packages the completed frozen analysis and checks
the full archive with the previously verified SQL cache. It does not fit a model
or search for new biological outcomes. A fresh clone needs those analysis/source
artifacts and the documented archive extraction before republishing; it can
reopen an already published portable workspace without the SQL cache or R.

To replay the enriched graph, preserve the source extension explicitly:

```sh
python -m biograph_steward replay \
  --snapshot runs/my_enriched_workspace/snapshot.json \
  --extension-run runs/my_enriched_workspace \
  --out runs/my_enriched_replay
python -m biograph_steward gold-export \
  --run runs/my_enriched_workspace --out runs/my_enriched_packet
```

The complete export preserves `evidence_extension.json`, the observation ledger,
both publications, raw source material, licenses and projection bindings.
Missing or altered source material fails replay. Review decisions are carried to
a new immutable workspace. Pruning exports preserve the complete source packet
and explicitly mark observation-edge retention.

The bounded KGX export profile still omits unsupported PPI/proximity records and
reports those omissions. The complete graph/decision packet preserves them;
this feature does not claim a new Biolink predicate mapping or full conformance.

## Scientific and delivery boundary

The previous MAP-IT pruning endpoint remains unscorable and the earlier Lambourne
superiority gate remains failed. Imported observations cannot independently
validate their own integration. The verified contribution here is faithful,
traceable biological evidence enrichment and explicit reuse accounting.

[Completed source/coverage assessment](../runs/biological_enrichment_20261111/coverage_assessment.json),
[temporal reference assessment](evaluations/PHAROS_TEMPORAL_BASELINE_20261112.md),
[STRING score meanings](https://string-db.org/help/scores/),
[MAP-IT study](https://doi.org/10.1038/s41467-026-79134-z).

## Verification record

The final regression run passed in the existing Python 3.12.4 evaluation
environment with localhost excluded from the system proxy. The initial system
Python attempt lacked optional evaluation packages; a subsequent proxy-routed
attempt received HTTP 503s on local test URLs. These environment failures were
resolved without changing application authentication or source rules.

The real enriched packet and undecided decision bundle passed replay. The
browser walkthrough verified the 120-record question, an ENG source trace and
the displayed-answer JSON saved on disk; the browser tool's download-event wait
stalled after the file had already been saved. No model or new remote compute
was used for this increment.

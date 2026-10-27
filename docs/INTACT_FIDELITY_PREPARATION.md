# IntAct evidence-fidelity preparation

Prepared October 26, 2026. **The official reader is now validated and the four
development studies have been inspected: four eligible human-protein evidence
rows across two publications.** The four reserved studies remain unopened.
A complete real Pharos-attached import/answer/export comparison now passes
source fidelity on all four eligible development rows. See the
[workbench result](INTACT_EVIDENCE_WORKBENCH.md) and
[tracked summary](evaluations/intact_evidence_flow_20261026_summary.json).
This work implements the assessment selected in the
[public-reference review](literature/PUBLIC_REFERENCE_OPTIONS_20261026.md).
It does not report biological accuracy, independent link prediction, graph
improvement, PSI-MI export conformance or an organizer score.

The [reader/development record](evaluations/INTACT_READER_DEVELOPMENT_20261026.md)
and [tracked result](evaluations/intact_reader_development_20261026_summary.json)
describe the earlier reader increment. The original protocol, panel, opaque
retrieval receipts and semantic amendment remain unchanged. Statements below
about unopened files describe the original preparation boundary, before the
separately recorded development exposure.

An independent source review corrected one semantic rule **before any reference
rows were opened**. The original frozen protocol remains unchanged as history;
the linked [semantic amendment](evaluations/intact_fidelity_20261026_semantic_amendment.json)
is mandatory for later interpretation and scoring. An absent expansion annotation
means that none was supplied. It does not establish true-binary experimental
origin. The specification's instruction that true binary records use `-` does
not license that converse inference, and the pinned JAMI initializer adds no
affirmative origin flag when expansion terms are absent. This correction changes
no selected file, eligibility rule, split or metric denominator.

The question is concrete: when Steward is supplied with curated interaction
evidence, does its import, answer and export preserve the participants, source,
experiment and qualifications? The existing Lambourne observations remain
author-table observations. They are not relabeled as IntAct/IMEx curation, and
their previously consumed results remain unchanged.

## Reuse decision and verified gap

The [IntAct resource paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC8728211/)
and [IMEx curation paper](https://www.nature.com/articles/s41467-020-19942-z)
describe a detailed evidence model that already addresses participant identity,
experimental context and qualified interaction observations. The
[official MITAB 2.7 specification](https://github.com/HUPO-PSI/miTab/blob/301904541d716b767d02a67f3413907952844ea1/PSI-MITAB27Format.md)
supplies the 42-column exchange format. We use these concepts rather than
creating another biological annotation system.

[PSI-JAMI](https://github.com/MICommunity/psi-jami/tree/b66f63654d5878b918aad74af60054b1be0437a8)
provides an existing Java MITAB evidence reader. Its pinned parent POM declares
version **3.9.4** and Apache-2.0; its README's older release badge is not treated
as the runtime version. The repository's Python package has no MITAB parser.
At original preparation JAMI had only been inspected at source level. The next
increment built the official published reader in an isolated environment and
validated it on 30 unchanged synthetic controls plus two recovery controls.
Its full official field-parser collections are retained separately from its
potentially lossy evidence objects. The remaining implementation is the
evidence-to-answer/export projection, with reader diagnostics retained.

Source review also found limitations that must be handled before claiming a
lossless import. JAMI's evidence objects can retain only the first of some
multi-valued roles, types, methods, hosts and expansion terms, with listener
events. The reader can infer interactor type from identifiers when type is
absent. Therefore every raw cell must remain available, and lossy or inferred
structured mappings must be flagged rather than silently becoming reference
truth. The future adapter must capture all listener diagnostics and prove its
behavior on synthetic controls before opening reserved reference rows. A custom
biological parser has not been introduced to work around this issue.

One important format rule differs from a generic missing-value policy: MITAB27
defines `-` in the **negative** column as false, or positive evidence, by default.
The raw `-` and the fact that the value came from a format default must both be
retained. Other absent experimental context remains not supplied. Neither a
positive record nor a binary representation alone establishes direct binding;
negative evidence remains qualified by the source experiment.

## Actual source selection and exposure boundary

The official
[named release directory](https://ftp.ebi.ac.uk/pub/databases/intact/2026-10-17/psimitab/pmid/2025/)
contains 56 numeric publication filenames. Metadata access disclosed their
names, rounded sizes and timestamps; it did not expose their interaction rows,
publication abstracts or pair outcomes. The 2025 publication directory was
chosen as a finite recent panel, not as a temporal or independent holdout.

Selection uses a technical size band of 4–64 KiB from the directory display,
then ascending SHA-256 of `biograph-intact-fidelity-v1\n` plus filename. It takes
the first eight files: four for development and four reserved for a later final
assessment. Twelve files satisfy that metadata band. Size selection can correlate
with study size, so the panel does not represent all IntAct evidence. No source
was selected for absence from Pharos, its positive/negative outcome, method,
protein identity or model performance.

| Development publications | Reserved publications |
| --- | --- |
| 40075158 | 39833857 |
| 40404733 | 40211762 |
| 40071126 | 39972491 |
| 40739265 | 40555359 |

The machine-readable [protocol](evaluations/intact_fidelity_20261026_protocol.json)
and panel receipt were frozen **before source-body retrieval**. Eight exact
release URLs were then fetched as opaque bytes with a strict 64 KiB per-file
bound, SHA-256 hashes and HTTP receipts. At that preparation stage no reference
file was decoded, parsed or displayed. The later reader increment opened only
the four development files, after passing controls and writing exposure receipts.
The selected bytes are saved in the ignored run directory. A
[tracked preparation receipt](evaluations/intact_fidelity_20261026_preparation.json)
preserves their identifiers, URLs, hashes and access status.

Each publication stays in one split. Before any final scoring, explicitly shared
primary/secondary study provenance must be audited; a reserved study connected to
development or consumed material is excluded without replacement. Pair and
participant overlap must be reported. Database separation and publication year
do not establish independence from Pharos, STRING or unknown model pretraining.
Reserved rows must remain unopened during development; any exposure is recorded
as consumed rather than hidden by reselection.

## Frozen scope of the later assessment

Primary eligibility requires an unambiguous UniProtKB participant on each side,
explicit human participant taxonomy and explicitly protein-typed interactors,
plus traceable publication, source and interaction identifiers. Isoform suffixes,
orientation and construct/feature strings remain exact. Missing or inferred
primary identity/type is excluded with a reason. All source rows remain accounted
for, including malformed, nonhuman, ambiguous and unsupported cases. Negative,
expanded and optional-context-missing rows are retained as separate strata when
otherwise eligible; empty strata are reported as unevaluated.

The protocol fixes field groups before any reference values are inspected:

- Participant identity, taxonomy, exact accession, alternatives and orientation.
- Source database, evidence and publication identifiers, original record links,
  artifact fingerprint and row locator.
- Interaction and participant detection methods and interaction type, without
  unsupported directness claims.
- Biological and experimental roles, host and literal experimental annotations.
- Complex expansion and original interaction grouping.
- Negative/positive/default semantics, missing values, features and stoichiometry.

Direct source access is the reference-access baseline. The deterministic import,
answer and export must use the same eligible rows. An agent-assisted arm requires
its own later frozen contract and is not run by this preparation. For lossless
import the curated representation intentionally enters the importer; this is
source-fidelity testing, not concealed-answer scientific verification.

Coverage and strict fidelity use **all eligible rows** as the denominator, so
abstention cannot look like success. Report conditional correctness alongside
coverage, per-field errors, critical unsupported assertions, micro counts and
per-publication macro averages. Preserve development and final results separately.
No source-pruning or edge-deletion rule follows from this assessment.

## Reproduction and next executable work

[The preparation script](../scripts/prepare_intact_fidelity_reference.py) handles
only directory metadata and opaque source bytes. It rejects changed frozen inputs,
redirects, duplicate filenames, missing panels and output replacement. Its offline
controls use synthetic metadata, not reference rows. It contains no MITAB parser,
model call, graph write or scoring function.

Before any later reference interpretation, use the
[amendment-aware replay guard](../scripts/verify_intact_fidelity_preparation.py):

```sh
python3 scripts/verify_intact_fidelity_preparation.py \
  --panel runs/intact_fidelity_preparation_20261026/panel.json \
  --expected-panel-sha256 38c0b5929bc0c02213ffd66f6c4e7d68924351c3651273a78ce851b5f873de89 \
  --amendment docs/evaluations/intact_fidelity_20261026_semantic_amendment.json \
  --expected-amendment-sha256 2cd2cb485836228ce71dd9d62201c61dd5de45d18563894ac883f188f245e98c
```

This verifies the original preparation, pinned format/parser evidence and the
explicitly acknowledged correction. It produces the effective field rule in
memory and opens no reference source blob. The old preparer's artifact-only
check verifies historical integrity; it does not authorize the superseded
semantic interpretation. Later evaluator outputs must bind both original
protocol and amendment hashes.

The completed run is `runs/intact_fidelity_preparation_20261026/`. Its preparation
receipt binds the protocol, script, directory metadata, panel and source bytes.
Re-fetching the current release URL is not a substitute for verifying those
saved bytes; the observed named path and content hashes are both required.

That reader increment is complete: all 32 synthetic cases passed, followed by
18 accounted development-file lines (four headers and 14 evidence rows).
Four evidence rows qualify; eight excluded rows involve RNA and two are mouse
protein rows. These exclusions describe task scope, not wrong source evidence.
The eligible rows concern two protein pairs and all supply positive
co-immunoprecipitation evidence, with no expansion annotation. Real negative
and expansion strata are therefore unevaluated in this development subset.
The source's physical-association type is preserved without a direct-binding
claim. No file was replaced because of its eligibility or outcome.

The deterministic qualified import, readable answer and complete export are now
implemented and tested against those four rows and synthetic edge cases. The
full real comparison passed 4/4 source fidelity; it does not add a biological
accuracy or independent-prediction result. The reserved subset remains untouched
until the adapter and scoring projection are committed and frozen, followed by
the required provenance/overlap audit. Final-study suitability remains unknown.

Data reuse follows the dedicated
[IntAct CC BY 4.0 statement](https://raw.githubusercontent.com/intact-portal/intact-portal-documentation/b5d5bb35365739d4942e9ca250a2cf4fbaa14c62/about/license-privacy.md),
with attribution to IntAct/IMEx and the original publications. The download guide's
broader Apache statement is not used to relicense MITAB data. No GPU or Brev model
is required for this preparation or the ordinary reader/import work.

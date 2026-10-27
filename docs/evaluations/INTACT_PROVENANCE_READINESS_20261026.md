# IntAct provenance audit and reserved-assessment readiness

October 26, 2026. The tested implementation is committed locally. The bounded
bibliographic audit is complete, but **shared-study provenance and reserved
participant/pair overlap remain unresolved**. No reserved interaction file was
opened or hashed in this increment. No final score or biological improvement is
claimed. The [tracked summary](intact_provenance_readiness_20261026_summary.json)
binds the implementation, retrievals and preserved failures.

## Frozen implementation

| Commit | Scope |
|---|---|
| `7aa13c3` | Execution-free NVIDIA interface comparisons, diagnostic, tests and original results; both adapters remain outside production execution |
| `dabbffb` | Official PSI-JAMI reader, invented controls, fixed preparation and development inspection |
| `bca13a7` | Qualified evidence attachment/answer/export, complete source-fidelity result and exact-selection construction guard |

The working tree was clean before bibliographic access. All 16 original
pre-comparison implementation/input hashes still match, as do the saved
[4/4 development source-fidelity result](../INTACT_EVIDENCE_WORKBENCH.md)
bindings. No new model or GPU run was needed. These commits have not been pushed
to GitHub. Downloaded data, model/environment files, credentials and compiled
reader output remain outside Git.

## What the metadata check establishes

NCBI ESummary resolved all eight fixed publication IDs. Europe PMC's **lite**
search resolved the exact DOI references for INMC, HuRI, Choi's assay benchmark
and Lambourne. No selected publications share a DOI with each other, and no
selected PMID/DOI matches those four anchor references.

This is an exact bibliographic-identity check against a declared small inventory,
not an exhaustive inventory of every previously consumed reference. Different
PMIDs and DOIs do not establish different experiments. No abstracts, full texts
or reserved interaction records were retrieved. Titles, identifier aliases and
publication-status metadata for the reserved publications are now exposed; do
not call those publications wholly unseen.

The PubMed database metadata did not list a qualifying correction/retraction/
republication link type for the planned bounded check. No article-level
correction relationship check was executed. The returned ESummary fields are
not clearance from corrections, retraction or shared data.

The first sandbox retrieval failed with DNS errors and is preserved separately.
The successful attempt saved the script and pre-access receipt before fetching,
then retained all four raw metadata/schema responses, URLs, byte hashes and HTTP
receipts. No file or publication was replaced.

## Existing source model and verified gap

[IntAct's pinned curation manual, section 10.6](https://github.com/intact-portal/intact-portal-documentation/blob/b5d5bb35365739d4942e9ca250a2cf4fbaa14c62/docs/curation-manual/special-cases.md)
already describes shared primary/subsidiary datasets using qualified publication
cross-references and experiment comments/annotations. Reuse that model.
A generic `see-also` reference or `uniprot-dr-export: No` flag alone is ambiguous;
neither establishes shared study data. `imex-primary` identifies accession
registration, not an independent primary experiment.

Our existing bridge preserves publication identifiers and full MITAB source
fields, but does not export all publication and experiment cross-references and
annotations. Column 9 does not contain the complete publication/experiment
model. Therefore perfect MITAB fidelity does not close the study-provenance gate.
This does not invalidate the tested preservation of all supplied MITAB fields.

The [official Graph API schema](https://www.ebi.ac.uk/intact/ws/graph/v3/api-docs)
documents established richer representations:

| Route | Documented scope | Audit consequence |
|---|---|---|
| `/interaction/details/{ac}` | Publication cross-references/annotations, abbreviated experimental context | Insufficient to assume full experiment provenance |
| `/interaction/detailsOld?ac=…&depth=2` | Full experiment/publication objects with cross-references and annotations | Candidate source; record-level availability must be verified |
| `/export/interaction/{ac}?format=miXML30` | PSI-MI XML exchange representation | Candidate for the official JAMI XML reader; not implemented or verified here |

These routes also return biological observations. They are not metadata-only
shortcuts for opening reserved records. The inspected schema exposes no
standalone publication-only route. This is a finding about this schema, not a
claim that all IntAct services lack such a capability.

## Development-only availability check

Only the four already-consumed eligible development evidence IDs were requested.
The first detail-route attempt produced JSON decode errors and retained its
error report. That first helper did not preserve undecodable raw responses, so
it cannot support HTTP/body claims for those requests.

A follow-up preserved raw bytes and headers before parsing. For the consumed
record `EBI-70852459`, **both documented detail routes returned HTTP 200 with an
empty body**. No publication or experiment annotation values were obtained.
This is a narrow observed access result, not evidence that curation is absent,
that the whole service is unavailable, or that a particular release/index lag
caused it. The cause remains unresolved. The original frozen MITAB files and
source-fidelity comparison were not changed or rescored.

## Decision and next bounded work

Reserved scoring is not ready. Preserve the existing development-only guards;
do not widen their allowlists and call that a final evaluation. The inspector,
publisher, catalog validation and evaluator intentionally bind the development
reference, including its fixed row accounting.

1. Verify an existing richer publication/experiment provenance route on consumed
   development material or synthetic controls. The official named release has
   [PSI-MI XML 2.5 per-publication files](https://ftp.ebi.ac.uk/pub/databases/intact/2026-10-17/psi25/pmid/)
   and [PSI-MI XML 3.0 per-publication files](https://ftp.ebi.ac.uk/pub/databases/intact/2026-10-17/psi30/pmid/).
   Its READMEs specify 2.5.4 and 3.0.0. Check the actual official JAMI XML
   dependency/version and reconcile development evidence IDs and qualifiers
   before using that metadata. Export timestamps differ, so a shared named
   release does not establish identical records across formats. No selected XML
   file was downloaded here. Do not create a new biological annotation system
   or infer missing lineage.
2. Prepare a separate final execution path using the unchanged eligibility,
   semantic amendment, source-fidelity metrics and no-replacement rule. Freeze
   and test it before any reserved interaction access.
3. Have that fixed path audit explicit shared-study components and exact
   participant/pair overlap before scoring. Missing/ambiguous provenance stays
   unresolved; shared proteins, pairs or citations alone do not prove duplicate
   experiments. Exposure and exclusions must remain visible.

This closes the finite readiness review with an explicit unresolved gate. It
does not start another benchmark/model sweep, certify study independence or
measure scientific accuracy. Brev remains unnecessary for this work.

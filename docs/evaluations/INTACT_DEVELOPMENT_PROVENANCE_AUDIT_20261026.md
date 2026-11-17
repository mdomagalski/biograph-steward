# IntAct development provenance and overlap audit

The bounded development audit is complete. It identifies the experiment and
publication groupings needed for the final source-fidelity assessment, but does
**not** establish study independence or biological improvement. The four eligible
rows represent two protein pairs, three curated experiment records and two
publications. The reserved interaction bodies remain unopened and unhashed.

The [bound inventory](intact_development_provenance_audit_20261026_summary.json)
records source hashes, exact evidence and experiment identifiers, annotation
locators, participant identity groups and limits. It follows the
[XML development check](INTACT_XML_PROVENANCE_20261026.md); it does not amend any
frozen input, eligibility mask or historical result. The date is October 26 local
time, October 27 UTC.

## Reused methodology and what it permits

The pinned official IntAct manual already specifies the relevant units. A curated
experiment groups a protocol; changing host, interaction detection or participant
identification can require a new experiment. Multiple observations from one paper
can be represented under the same experiment. Consequently an experiment AC is
not a biological replicate identifier, and a new AC is not proof of an independent
study. We preserve evidence, experiment and publication groupings rather than
inventing an independence score. [Experiment manual](https://github.com/intact-portal/intact-portal-documentation/blob/b5d5bb35365739d4942e9ca250a2cf4fbaa14c62/docs/curation-manual/experiment.md),
[interaction manual](https://github.com/intact-portal/intact-portal-documentation/blob/b5d5bb35365739d4942e9ca250a2cf4fbaa14c62/docs/curation-manual/interaction.md).

The IMEx resource paper documents shared curation and redistribution through
aggregators including STRING, plus context-sensitive evidence and richer XML
representations. Database names therefore cannot establish independent evidence.
This supports our source-lineage and overlap checks, not a claim that any specific
STRING record came from these IntAct observations. [Porras et al., 2020](https://www.nature.com/articles/s41467-020-19942-z).

The public manual pages were retrieved at the already-pinned documentation commit;
HTTP receipts and copies are retained under
`runs/intact_development_provenance_audit_20261026/method_sources/`. No additional
interaction data, original-paper abstract or original-paper full text was fetched.

## Observed groupings

| PMID | MITAB evidence rows | XML evidence objects | Curated experiments | Eligible human protein rows |
|---|---:|---:|---:|---:|
| 40075158 | 2 | 2 | 2 | 0 |
| 40404733 | 5 | 4 | 3 | 2 |
| 40071126 | 4 | 4 | 3 | 2 |
| 40739265 | 3 | 3 | 2 | 0 |
| Total | 14 | 13 | 10 | 4 |

The eligible METTL14–DGCR8 observations, EBI-70852459 and EBI-70852463,
reference **the same experiment**, EBI-70852453, in PMID 40404733. They retain
separate figure annotations, 3f and 3g, and the Hep3B host. They are distinct source
records, not two studies and not two experiment ACs.

The eligible MAD2L2–POGZ observations, EBI-70836068 and EBI-70836438,
reference EBI-70836062 and EBI-70836432 in PMID 40071126. Their hosts are
KTC-1 and CAL-62; both cite figure 1f. These are two qualified contexts within one
publication. The export does not establish statistical or study independence.

All four eligible rows explicitly encode positive anti-bait co-IP / physical
association. None establishes direct binding. The broader development set has no
curated negative observation, so it cannot estimate rejection specificity or
performance on negative evidence. The ten excluded rows remain eight
RNA-containing rows and two mouse-protein rows; exclusion is a task-scope
decision, not a finding that their biology is wrong.

The n-ary finding remains explicit: EBI-70852445 / IM-30672-3 has three
participants; PMID 40404733 MITAB lines 3 and 4 are its two source-annotated
MI:1060 spoke views. They stay together as one evidence group. They are neither
duplicate rows to delete nor independent experiments to count. Both were already
outside the eligible protein-only subset.

## Explicit lineage and exact overlap

The retained official-reader models contain only the selected study PMID as a
publication reference; no external PubMed/DOI reference or explicit cross-study
provenance link appears in the inspected interaction/experiment/publication
collections. That is an observed absence of exported links, **not proof that the
studies share no samples, assays, source data or earlier experiments**. No
connected-component independence decision is justified from missing annotations.

The original MITAB primary identifiers yield 17 unique exact participants and 11
unique undirected pair views across the development rows. No exact primary-ID
participant or pair is shared between different development publications. These
counts use the literal database plus accession, with no synonym, isoform, gene or
cross-species collapse. They do not establish biological disjointness.

Earlier bibliographic-only metadata for all eight selected studies found no
PMID/DOI alias match between selected publications, or against the four recorded
consumed publication anchors (41935050, 36949045, 32296183, 31467278). This is
identifier nonidentity only. Historical dataset/participant overlap and language
model pretraining exposure remain unverified.

For the frozen four-protein Pharos319 cohort, one of the two eligible IntAct pairs
(MAD2L2–POGZ) already appears as a STRINGDB annotation. Its two reciprocal source
views are one graph edge, with no supplied publication reference. The other pair
is absent from that particular cohort graph. Thus IntAct adds qualified assay and
publication information; the first pair's study lineage remains unknown, and the
second pair's absence is not proof of novelty across all Pharos/TCRD/STRING.

Reserved pair and participant overlap cannot be assessed without opening reserved
values. That operation belongs to a separately frozen evaluator, not this
development audit.

## Source caution: preserve the unresolved state

PMID 40071126 has a MI:0618 caution on experiment XML ID 5691196 /
EBI-70836442. Its Italian text says a LINC01355 relation was not annotated because
the curator could not resolve the sequence. Both RNA observations EBI-70836448
and EBI-70837425 reference that experiment. The latter currently retains a
`lncrna_linc01355` participant with identity-qualified ENST00000670871.

These facts must be shown together. The export supplies no annotation timestamp
or resolution state: we cannot decide whether the comment is historical, refers
to a different relation/sequence, or describes an outstanding mapping problem.
It does not establish that LINC01355 is currently absent, that the mapping was
resolved, or that the separate protein co-IP observations are invalid. The warning
is not attached to their two curated experiments.

The manual defines caution as a user warning about possible errors, confusion or
sequence/method ambiguity. Its editorial lifecycle describes review before
release but does not give this annotation a resolution status. The verified gap
is missing annotation history/status in the inspected export, not a missing
custom confidence formula. Preserve the warning and abstain from a biological
judgment. [Annotation manual](https://github.com/intact-portal/intact-portal-documentation/blob/b5d5bb35365739d4942e9ca250a2cf4fbaa14c62/docs/curation-manual/introduction.md),
[lifecycle manual](https://github.com/intact-portal/intact-portal-documentation/blob/b5d5bb35365739d4942e9ca250a2cf4fbaa14c62/docs/curation-manual/life-cycle.md).

## Gate recommendation

A separate final execution contract can now reuse the verified reader and these
observed groupings. It must freeze code, inputs, artifact access, lineage and
exclusion rules before reserved decoding; retain uncertainty; quarantine explicit
reuse with consumed studies or unresolved source projection; preserve n-ary
objects and exact identifiers; and prohibit replacement or tuning after outcomes.
The final report must disclose exact pair/participant overlap and unknown study
independence, with publication-level and evidence-row denominators. This audit
alone authorizes no reserved access or final score.

These source-fidelity rules make the integration assessable. They do not test
whether the graph improves biological prediction. That requires a separately
fixed scientific endpoint, measured-outcome reference, baseline comparison and
leakage exclusions. The consumed rows support engineering checks of species/type
qualification and context/directness preservation. Comparing them against an
invented weak baseline would not demonstrate independent biological improvement.
No model, GPU, graph change, pruning or new biological validation was performed.

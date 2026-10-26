# Public evaluation references without the organizer's hidden labels

October 26, 2026 (America/New_York).

**Decision:** use public expert curation to establish a bounded reference for
evidence interpretation and source fidelity. IntAct/IMEx is the preferred next
reference for that task. Do not wait for the organizer's secret test labels,
and do not describe another public interaction collection as an independently
validated replacement for them. An independent prediction claim still needs
source and study separation appropriate to its specific endpoint.

This was a finite review of three resources. It inspected primary papers,
official documentation, schemas, licensing statements and directory metadata.
No candidate interaction table or per-pair outcome file was downloaded or
decoded, no new reference labels were materialized, and no model or cloud
compute ran. Published aggregate descriptions and method examples were visible.
The consumed INMC and Lambourne panels and their results remain unchanged.

## What we should ask organizers for

Our request should concern **the evaluation contract**, not the hidden answers:
accepted graph format and identifiers, baseline version, relation/task scope,
label meanings, allowed evidence cutoff, scoring metrics, and how to submit a
graph or predictions for organizer-run scoring. A tiny synthetic example or a
separate development example can clarify the interface without revealing the
final test. No message was sent during this review.

The existing [gold-set interface](../GOLD_SET_INTERFACE.md) supports a portable
handoff. Our own public-reference assessments can proceed independently of
access to official labels. They must remain named local assessments rather
than an estimate of an unspecified official score.

## Three resources and their actual fit

| Resource | Public material verified | Appropriate use here | Limitation and decision |
|---|---|---|---|
| **IntAct / IMEx** | Official download directories, per-publication MITAB export documentation, PSI-MI formats, curation model and data license | Expert-curated reference for participants, interaction type, experiment/publication context, and qualified positive/negative observations; potential study-grouped reference for a separately specified assay endpoint | Preferred for evidence-fidelity evaluation. A database or publication holdout alone does not establish absence from Pharos or model pretraining. It is not a ready-made generic prune/keep gold set. |
| **BioGRID** | Current and archived releases, TAB 3 schema, experimental-system definitions, multi-validation criteria and MIT data terms | Alternative reference for source attribution and relation qualification; versioned snapshots could support a separately specified update/retraction task | Keep as a secondary option, not another parallel ingestion project. Physical associations include different experimental endpoints. Multi-validation does not guarantee truth or independent studies. |
| **Negatome 2.0** | Primary paper and its distinctions between manually curated and structure-derived noninteraction sets | A possible narrowly contextual negative-reference resource if its actual files, provenance and reuse terms can be verified | Do not adopt now. The original site did not load in this audit; downloadable artifact and data license were not established. Structural noncontact, assay nondetection and universal noninteraction are different claims. |

### Why IntAct / IMEx is the first choice

IntAct's primary paper describes detailed experimental curation and explains
that interaction observations depend on experimental and biological conditions.
It also distinguishes original multi-participant experiments from binary
expansions. These distinctions match the workbench's existing qualified
observation layer and avoid inventing another annotation system.
[IntAct paper, 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC8728211/)

The official annotation guide separates direct interaction, physical association
and association. In particular, a binary displayed association is not proof of
direct binding. A correct local reference must preserve these distinctions and
avoid converting missing fields into contrary evidence.
[IntAct annotation practices](https://raw.githubusercontent.com/intact-portal/intact-portal-documentation/master/documentation/user-guide/data_sources.md)

Public retrieval is real, not just promised in a paper: the
[current download directory](https://ftp.ebi.ac.uk/pub/databases/intact/current/)
and [MITAB README](https://ftp.ebi.ac.uk/pub/databases/intact/current/psimitab/README)
were accessible. The README identifies evidence-level rows and the official
MITAB specification. The [download guide](https://raw.githubusercontent.com/intact-portal/intact-portal-documentation/master/download/ftp/ftp.md)
documents per-publication MITAB files and textual-evidence downloads. The
text-mining subdirectory was not accessible in this check, so a sentence-level
benchmark has **not** been established. Directory timestamps are observed
metadata, not proof of completeness or a validated latest release. A selected
artifact must be pinned and checked before use.

The [dedicated license page](https://raw.githubusercontent.com/intact-portal/intact-portal-documentation/master/about/license-privacy.md)
and the paper explicitly identify **CC BY 4.0 for interaction data**, with
Apache 2.0 for software and specified other assets. The download guide contains
a broader Apache statement that conflicts with that distinction. Use the
specific data-license statement and preserve attribution and any artifact-level
terms; do not infer that the software license covers exported interaction data.

### Why the alternatives do not solve independence automatically

BioGRID's [TAB 3 schema](https://wiki.thebiogrid.org/doku.php/biogrid_tab_version_3.0)
retains experimental system, publication, organism, qualifications and source.
Its [release repository](https://downloads.thebiogrid.org/BioGRID) provides
current, previous and archived releases under MIT terms. Archives can preserve
a declared historical snapshot but are explicitly not the current consensus.

The [experimental-system documentation](https://wiki.thebiogrid.org/doku.php/experimental_systems)
warns that a recorded interaction need not be direct and that curation does
not guarantee truth or present consensus. The
[multi-validation definition](https://wiki.thebiogrid.org/doku.php/biogrid_mv)
can be satisfied by a different method in the same publication or a different
publication using the same method. We must inspect actual study dependencies
instead of turning that label into an independence certificate.

The [Negatome 2.0 paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC3965096/)
distinguishes literature-curated noninteractions from pairs that share a
structural complex but lack direct contact. Its stringent subsets were filtered
against IntAct, and Negatome 1.0 was itself incorporated into IntAct. Thus these
sets have explicit ascertainment and database relationships; they cannot label
every absent Pharos edge false. The paper's open-access status is not a verified
license for an uninspected separate data artifact. The original
[Negatome endpoint](https://mips.helmholtz-muenchen.de/proj/ppi/negatome/)
timed out in this audit; this is an access result, not proof that the data no
longer exists.

## The bounded reference contract to prepare

The first contract should answer: **Does the workbench preserve and correctly
communicate the curated interaction evidence supplied to it?** This evaluates
qualified integration, not the truth of every possible biological interaction.
It supports the agreed product work without changing to another prediction
endpoint merely to obtain a better result.

Before any selected reference values are inspected:

1. Fix the exact task and eligible evidence: human protein participants,
   publication and evidence identifiers, declared interaction-type/method
   vocabulary, and explicit handling of isoforms, constructs, missing context,
   negative evidence and multi-participant expansion. Reuse PSI-MI concepts and
   the source's curation rules. Do not select only Pharos-absent pairs.
2. Pin one release/artifact, license and receipt. Select development and final
   cases by a declared outcome-independent rule, grouping repeated reports from
   the same study and preserving related pair/participant exposure flags.
   Auditing eligibility may reveal metadata; record that access rather than
   calling the panel wholly unseen.
3. Fix expected fields, coverage denominators and error types before execution:
   wrong identity, lost qualification, unsupported directness, missing source,
   unsupported negative/positive conversion, and appropriate abstention.
   Compare direct source access, deterministic integration and any agent-assisted
   path on the same cases. Record coverage alongside correctness so abstaining
   on everything cannot look successful.
4. Keep the curator's reference representation outside an evaluated extraction
   or interpretation agent's inputs. If the evaluated action is lossless import
   of that same representation, call it **source-fidelity testing**, not
   independent scientific verification. No concealed-answer claim is made for
   a pretrained model whose training corpus is unknown.
5. Preserve all results and consumed-status receipts. Do not switch references,
   change label definitions or tune prompts on the final subset after seeing
   performance. Use development material for corrections.

This is a **selection and preparation decision**, not an executed freeze, a
downloaded benchmark, an implemented adapter or a new score. The tested existing
assay attachment and bounded construction workflow remain the immediate product
deliverables. A new reference adapter should use official format tooling where
it fits, after inspecting its version and semantic coverage.

## Conditions for a later biological prediction or pruning claim

Public outcomes are acceptable scientific references; secrecy is not what
makes an evaluation independent. What matters here is whether the endpoint
matches the claim and whether test evidence or its derivatives entered inputs,
selection or tuning. Recent biomedical KG work finds materially different
generalization under an external reference compared with customary splits and
provides reusable checks for redundant and reverse relations.
[Brière et al., 2026](https://academic.oup.com/bioinformatics/article/42/8/btag608/8767164),
[official code](https://github.com/galadrielbriere/data_leakage_kge_benchmark)

Our [closed Pharos lineage audit](REFERENCE_COMPARATOR_DECISION_20261025.md)
still applies: deployed provider releases and study provenance are not bound to
all current Pharos rows. Selecting a different public database does not repair
that. Study and pair exclusions reduce demonstrated overlap but cannot certify
unknown derivative overlap. A prospective temporal assessment would require
freezing all inputs and predictions before genuinely later evidence becomes
available; a recently curated old publication is not new independent evidence.

A fair later improvement comparison must fix a biologically justified change
before opening its final outcomes and compare Pharos, addition of the same
information, and Steward's qualification under matched inputs and budget.
Measured nondetections are conditional on their assays; missing interactions
are unlabeled. Broad pruning precision needs actual context-compatible error
labels. Curated positives alone can measure agreement or retention on that
reference, but cannot estimate all false-positive removals. An injected-error
test remains an engineering test with a stated corruption model.

**Stopping point:** IntAct/IMEx is the recommended public reference for bounded
evidence-fidelity preparation. BioGRID is a documented fallback; Negatome is
not selected. No broad additional source search or new model run is needed to
complete this decision. We can improve and evaluate source interpretation now,
while keeping independent biological prediction and the organizer's final
evaluation as distinct claims.

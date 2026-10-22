# Evidence workbench data contract — v0.6

Raw snapshots remain `biograph-steward.pharos.v1`. Derived graphs now use `biograph-steward.evidence-graph.v3`. Old snapshots are verified and transformed with current rules without modification. Old derived graphs are not silently rewritten. Replaying the same snapshot with a newer transformer can intentionally change disease-context mapping and audit counts.

## A node

`id`, `name`, `category`, `data_kind`, `identifier_mapped`, and optional `sym`, `tdl`, `family`, `source_identifier`, `url`.

- Proteins use `UniProtKB:` plus the returned accession, never a gene symbol promoted into a protein identifier.
- A supplied MONDO ID is normalized without guessing equivalence from names.
- A missing disease ontology ID is represented with a clearly local `pharos.disease:` identifier and causes associated edges to need review.
- A source record naming a different disease gets a separate local disease node with that exact label; it is never attached to the selected disease. The application has not resolved that label to an ontology. A source record with no disease name is retained in input quarantine and creates no association edge.
- Explicit Reactome pathway source IDs are preserved as `REACT:` identifiers. Other pathway records retain local `pharos.pathway:` IDs pending a verified crosswalk.
- Demo nodes use `demo:` identifiers and cannot pass the normal live identifier parser.

## An evidence edge

`id`, `subject`, `predicate`, `object`, `status`, `review_reasons`, `record_kind`, `aggregator`, `primary_source_raw`, `reference_raw`, `publications`, `evidence_raw`, `source_scores_raw`, `evidence_record`, `record_locators`, `snapshot_sha256`, `data_kind`, `biologically_validated`.

There can be multiple edges for one protein-disease pair because different records carry different evidence. A later modeling pipeline must group these before splitting pairs; otherwise the same pair may leak into both training and test sets.

Each edge now also contains `assertion_id` and `qualifiers`. Edge IDs identify transformed source records; they do not identify independent experiments.

A raw locator such as `snapshot.json#/targets/0/diseaseAssociationDetails/1` identifies the precise transformed input. The snapshot contains query variables and raw successful API responses. A hash alone is not sufficient evidence provenance; it is paired with those records.

`primary_source_raw` retains the upstream string unchanged. `Pharos` is the aggregator, not an automatically substituted primary source. No claim of source independence is made.

## Status semantics

- `passed_structural_checks`: identifiers and implemented minimal record rules passed; **not** scientific validation.
- `needs_review`: an inspectable edge remains, with explicit reasons for caution.
- Quarantine log: a malformed or exact duplicate input is excluded from the graph, but preserved in the raw snapshot and log.

## Qualified assertion

`assertions.json` groups edges by normalized subject, predicate, object, record kind and qualifiers. The qualified-claim ID is independent of citation, source score and evidence text. Its `revision` hashes the contributing evidence IDs and changes when those records change. Different qualifier values or membership/evidence kinds produce different assertions.

The qualifier slots are `disease`, `variant`, `therapy`, `species`, `tissue`, `cell_line` and `response`. This adapter only supplies the disease qualifier on associations/memberships. Other qualifiers remain null; missing context is not inferred from the selected research question. These are project-local fields, not a claim of complete Biolink qualifier validation.

An assertion preserves contributing evidence IDs, distinct source names, explicit PMIDs, structural validation results, snapshot identity and review history. `independent_evidence_count` is null: different sources or publications alone do not establish independent experiments. Unresolved local pathway IDs are not merged by name; a broader pathway crosswalk remains future work.

## Human review lifecycle

Every new assertion starts as `candidate`, regardless of structural validation. The allowed transitions are:

| From | To |
|---|---|
| candidate | accepted, provisional, quarantined, rejected |
| provisional | accepted, quarantined, rejected, obsolete |
| accepted | provisional, quarantined, rejected, obsolete |
| quarantined | candidate, rejected |
| rejected | candidate |
| obsolete | candidate |

Acceptance requires at least one structurally usable source record and an explicit human decision; disease-filtered membership alone cannot be accepted. Human acceptance is not automatic biological validation, clinical truth, a confidence score or an experimental benchmark label. The `biologically_validated` field remains false. The application does not check textual entailment or validate a reviewer's expertise.

Each event records sequence, assertion ID/revision, exact snapshot hash, previous/new state, reviewer, reason and a timezone-qualified timestamp. Replaying events checks those identities and the transition sequence. Events from another snapshot are rejected rather than carried forward automatically. The reviewer is a local name field, not authenticated identity, and these local files are not cryptographically signed.

The separate [snapshot-comparison workflow](SNAPSHOT_REFRESH.md) can create new, target-bound inherited review events after conservative compatibility checks. These record the tool as actor and preserve the original event, source/target hashes and comparison ancestry; they are not fresh human adjudications. Legacy cross-snapshot replay remains prohibited. This first version accepts ordinary parents only and does not chain inherited histories.

Browser and CLI reviews create a new run directory, retaining the same raw snapshot and appending the decision to a copy of the prior history. The original run remains unchanged. `review_parent.json` records the parent run name. Multiple decisions from the same original run create separate branches; there is no multi-user merge service.

`review_events.json` can be supplied to `replay --reviews` to preserve decisions. Replaying only a snapshot intentionally starts all assertions as candidates. A saved `?run=...` URL reopens the snapshot and review history in the local app. Offline HTML reports are read-only.

The accepted UI view is the default. Inspection mode exposes candidates and all other states. Graph lines group by qualified assertion and open all contributing records. Input quarantine and assertion lifecycle quarantine are separate: the first preserves records that could not be transformed, while the second records a review decision about an existing assertion.

## Question scope and audit boundary

`question_scope.json` records the Pharos disease-inspection template, exact disease, relation families and configured limits. This file is a deterministic scope description; the optional planner is described below. Pathways remain general protein context. The separate CIViC question template supports qualified molecular-profile/therapy source annotations, as described below; neither template establishes causal effects or recommends treatment.

Benchmark audit v2 counts only associations to the selected disease in its pair worksheet. Other-disease records are listed separately, and proteins without selected-disease evidence remain unlabeled. Historical v1 counts can differ because v1 attached mismatched records to the selected disease. Human review states are not automatically converted to prediction labels.

## Not model inputs yet

Do not train on all exported columns. Disease-association text, references, source scores, labels and inverse/equivalent edges may expose held-out answers. A future benchmark must deliberately select permissible features after pair-level splitting and leakage review.

The display order is alphabetical by symbol/identifier, not scientific priority. The source API order governs the bounded retrieval, not a model score. Scores on an evidence card are original source values, not output from this prototype.

## Scoped retrieval extension

Snapshot v1 optionally includes `retrieval.context` and `targets[].pharos_context`. Older snapshots remain readable. The scoped profile replaces preview pathways with paginated source rows; GO, PPI, drug, expression and publication records are exported as `context_records` and link to normalized candidate assertions for GO, PPI, drug listings and expression observations. Publications remain discovery-only. Exact duplicate context records share an entry with multiple snapshot locators; reciprocal PPIs remain source records, not independent experiments. Source response envelopes are copied before enriching target rows and their hashes are verified on replay. See [the scoped contract](SCOPED_RETRIEVAL.md) for filters, limits, completion statuses and intentionally unrequested collections.

## Qualified source context

See [context normalization v0.3](CONTEXT_NORMALIZATION.md) for the local predicate semantics, optional qualifier slots, reciprocal grouping, measurement context, provenance pointers, review boundaries and migration behavior. Existing disease/pathway claim IDs and evidence revisions remain stable. `source_record_count` counts raw source views, while `evidence_edge_ids` identifies evidence groups; `independent_evidence_count` remains null. No expression units, GO relation/polarity, species, treatment response or disease-specific support are inferred.

## Guided question results

`biograph-steward.guided-question.v1` binds a deterministic question to the exact source snapshot, graph/review basis and guided parameters. Each returned path lists its nodes, assertion IDs, review states and evidence references; every summary statement cites the complete path. Only exact-term disease associations and structurally usable context qualify. Accepted paths require all assertions to be accepted. See [the question contract](GUIDED_QUESTIONS.md) for limits, citation semantics, output files and persistence. This adds a graph-basis hash without changing existing claim identity or raw snapshots.

## CIViC source sidecar and response assertions

Version 0.5 preserves the primary Pharos snapshot and adds a separately hashed `civic_snapshot.json` sidecar. `read_run`, replay and review runs normalize both sources, with source-specific locators and licenses. Existing Pharos assertion IDs, evidence revisions and decisions are unchanged. The graph's additive `civic_snapshot_sha256` enters the question basis when present. CIViC review events bind to this hash in addition to the primary snapshot and assertion revision.

New optional qualifiers `evidence_direction`, `variant_origin`, `therapy_interaction` and `evidence_type` enter identity only when supplied. A `variant_therapy_response` assertion connects a complete CIViC molecular profile to an exact local therapy set; disease, response significance and direction remain separate. Source status and level are evidence metadata. Local candidates are not accepted by CIViC editorial acceptance. Project-local predicates/categories are not full Biolink validation.

The `civic_variant_therapy.v1` question template uses profile results, complete qualified response paths, source citations and both snapshot hashes. It shares immutable question/ZIP persistence with the protein-neighborhood template while keeping the biological scope separate. See [the full adapter contract and validation](CIVIC_EVIDENCE.md).

## Bounded planning

The planner catalogue omits reference plans, source statements and reviewer judgments. One strict JSON proposal selects an existing protein-neighborhood query, a complete-profile CIViC query or abstention. Validated application code executes at most one read-only local query. Invalid/incomplete/refused/unavailable model outputs remain explicit, with no model fallback. Request/schema/catalogue hashes and returned usage are traced; credentials are not persisted. See [the current planner contract](PLANNER_PROTOCOL.md).

The retired frozen-source evaluation suites and their review worksheets remain source-bound historical artifacts in the [research archive](EXPERIMENT_HISTORY.md). They are not part of the current application command surface. Their labels and model judgments do not become local assertion acceptance or fresh prediction labels after consolidation.

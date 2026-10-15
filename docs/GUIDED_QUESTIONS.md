# Guided question → evidence graph → traceable summary — v0.4

The primary app flow now asks a supported question over a saved, verified cohort. The initial template is:

> Which other proteins associated with the exact selected disease have reported interaction annotations or shared pathway annotations with the selected protein?

This is a deterministic graph query with a bounded, cited summary. Free-form question interpretation, variant–therapy response and causal inference remain outside this template.

## Use the app

Build or reopen a source run. **Ask a scoped question** appears first; retrieval controls and the full data/review workbench remain expandable.

1. Choose an exact protein identifier from the cohort. KRAS is selected when available; duplicate symbols remain separate UniProt choices.
2. Choose reported interactions, shared pathways or both. Review the exact disease, source cohort, retrieval limits, evidence policy and output limits.
3. Run **Accepted evidence only**, or explicitly choose **Explore candidates and accepted evidence**. If the accepted view is empty, the app reports how many proteins have inspectable paths and offers candidate exploration.
4. Inspect the selected result's compact evidence graph and cited summary. Expanding another result changes the graph. Teal lines represent accepted assertions; dashed amber lines require review.
5. Select a reference or graph line to open its evidence. **Open full assertion and review** leads to the existing source passport and human decision form.

Every assertion in an accepted path must be accepted. A candidate or provisional assertion makes the path require review. Rejected, quarantined and obsolete assertions are excluded from both views. Candidate exploration never changes lifecycle states.

## Exact scope and path rules

An interaction path requires a result protein's structurally usable association with the exact selected disease plus a normalized interaction annotation linking that protein with the focal protein. A shared-pathway path requires the same disease association plus both proteins' memberships in the same mapped pathway identifier. Both PPI orientations are supported. Membership in a disease-filtered list alone is insufficient.

The focal protein is a selected cohort member and is not itself returned as a result. An accepted disease association for the focal protein is not required: the question only asserts the result protein's disease link. Differently named diseases, unresolved pathway mappings and context-qualified statements that would need additional interpretation do not establish generic paths. A context connection never creates another disease association.

Outputs default to eight proteins and two paths per protein, with maximums of 30 and five. Proteins are ordered alphabetically by symbol/ID. Path order puts interactions first, then sorts pathway labels. Omitted proteins and paths are counted explicitly. Counts and ordering are not confidence scores or rankings of biological relevance. Broad shared pathways can appear; they do not establish a disease mechanism.

Scope includes the target cap, relevant per-family retrieval coverage and original source settings. A preview lacks count-reconciled context coverage; unknown counts and capped/inconsistent/unrequested families remain explicit. Absence of a result is not evidence of a biological negative. Source records without supporting publication references still need citation recovery; target-linked publication discovery is not attached to these claims automatically.

## Traceability and persistence

Every summary sentence names a returned evidence path and cites each assertion along it. References identify assertion IDs/revisions, current review state, structurally usable evidence records, source names, original scores, snapshot locators and response provenance where present. The remaining evidence can be inspected in the full source passport.

A question records its source run, snapshot hash/time, Pharos database version, graph/review basis hash, review-event hash, template/parameters and answer checksum. Its content is deterministic for the same source and parameters. Saved URLs contain both `run` and `question`; the browser checks that the source and review basis still match before displaying an answer.

Question outputs are written to a new directory, preserving source runs. The ZIP contains:

| Artifact | Contents |
|---|---|
| `question.json` | Scope, bounded paths, results, complete cited evidence, coverage gaps and trace hashes. |
| `summary.txt` | Plain-text summary, evidence references, limitations and source/review hashes. |
| `paths.tsv` | One row per returned path, with protein, nodes, assertions, citations and review status. |
| `report.html` | Standalone read-only summary with expandable evidence and reproducible scope. |

A human decision creates a new source run and clears the displayed answer. Re-run the question to use that review state; old question artifacts remain historical. No biomedical assertion is accepted by running a question. The full graph's `question_basis_sha256` is additive metadata; raw snapshots and existing claim IDs/revisions are preserved.

The running app performs guided queries locally. A standalone full graph report retains data inspection and directs users to the app for new questions. The separate question report is portable and read-only.

## CLI and HTTP

```bash
python3 app.py question --run runs/crc_normalized_verified_20261014 \
  --protein UniProtKB:P01116 --view candidates \
  --relations interactions shared_pathways --max-results 8 --max-paths 2 \
  --out runs/kras_question_01
```

Omitting `--view` uses accepted-only evidence. An unambiguous symbol is accepted by the CLI; ambiguous symbols require an explicit protein ID. `POST /api/question` accepts a saved run ID and guided parameters, saves a new result and returns its ID. `GET /api/question/<id>` verifies the saved answer checksum. The existing download route exports its ZIP. The API rejects unsupported question fields and relationship types.

## Validation

The full test suite passes: **126 tests**. A verified CLI example is saved in `runs/kras_guided_question_verified_20261014/`; reopen it in the running app at `http://127.0.0.1:8766/?run=crc_normalized_verified_20261014&question=kras_guided_question_verified_20261014`.

The saved 99-protein colorectal adenocarcinoma cohort yields **76 inspectable proteins and 1,065 eligible paths around KRAS** using both relationships. Accepted-only results are empty because that live cohort has no accepted path assertions. Default candidate output returns the first eight proteins with up to two paths each; the complete match count remains visible. These are source-annotation paths, not independent experiments or a discovery result.

Tests cover exact disease scope, rejection of membership-only/context-generalized paths, acceptance of every path assertion, reverse PPI lookup, shared-path witnesses, bounded ordering, citation resolution, ambiguity, unknown coverage, snapshot/review trace changes, immutable exports, HTML escaping, API validation and saved-answer integrity. Browser QA verifies candidate exploration, compact summaries, citation-to-passport navigation and saved-question reopening. An explicitly synthetic reviewed path verifies accepted-only output; changing one assertion to provisional clears the answer and removes the path from the accepted result. No live biomedical assertion was accepted by these checks.

The next product increment is the proposed variant–therapy evidence adapter and a question template that preserves those conditions, followed by measured source-overlap and evaluation work.

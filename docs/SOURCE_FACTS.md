# Source-first fact records

This experimental tool compiles a small set of explicitly stated study results
into structured records before comparing a claim. It uses source patterns and
application checks, not a model's support verdict. It makes no LLM requests,
retrieves no new papers, and needs no GPU or larger dataset.

The first version supports two narrow families: response percentages with an
evaluable-patient count for a reported treatment group, and an author's reported
significance/P value for one identified endpoint. Unknown wording, ambiguous
associations, or unavailable context require review. The records are
`pattern_extracted_unreviewed`; compilation is not scientific adjudication.

## Source compilation

The core APIs are:

```python
from biograph_steward.source_facts import compile_source
from biograph_steward.fact_comparison import compare_claim

dossier = compile_source(paper)
assessment = compare_claim(claim, dossier)
```

`paper` is a parsed PubMed record with exact PMID, title, and abstract blocks
containing `text`, `section`, and `locator`. The compiler receives no claim,
expected label, evaluator reference, or before/after context edit. It scans the
abstract, not full text or supplements, even if the saved record contains them.

The `source-facts.v1` dossier contains `source_id` (`PubMed:<PMID>`),
`source_sha256` of the complete parsed paper, an embedded copy of `paper`,
`records`, `coverage_gaps`, and compiler policy/limitations. Record fields include
the kind, complete named regimen, comparator when stated, molecular scope,
endpoint, and response percentage/evaluable count or author significance/P value.
Survival records additionally preserve an unambiguous explicitly reported effect
direction. Fields unavailable to the pattern remain unavailable; a record may
coexist with an explicit scope or direction gap. The compiler does not fill them
from outside knowledge.

Provenance is a map of field names to source spans, including `source_unit` and
separate value/context spans. Each span records the abstract `passage_index`,
`locator`, `[start, end)` Unicode-codepoint offsets, exact `text`, and SHA-256 of
that fragment's UTF-8 bytes. Decimal normalization is explicit; original spelling
remains in the source span. Displayed evidence uses stored text, not a newly
generated quotation.

`validate_dossier(dossier, paper=None)` recompiles the source and requires exact
dossier equality, rejecting altered values, swapped associations, added fields,
and changed spans. Supplying the original `paper` additionally binds the dossier
to that expected record. Replay of an embedded record alone is not independent
attestation of the journal's or PubMed's current contents. This detects edits
after extraction; it does not prove that a source pattern originally assigned
every association correctly.

The source alone must establish which group, regimen, molecular scope, and
endpoint belong to a result. A percentage appearing somewhere in an abstract
does not establish an association with every drug mentioned there. Likewise, a
significant PFS result cannot supply the qualification for an OS result.
Recognized regimens use a disclosed finite therapy vocabulary. FOLFOX4 and
FOLFIRI are atomic named regimens, not inferred monotherapies. Supported AND
connectors combine members of an arm; alternative OR arms must not be merged.
Response counts must be explicitly evaluable counts, not treated-group totals.

Survival extraction requires one endpoint, one explicit author qualification,
one equality P value, and an explicit treatment comparison in a supported source
unit. Molecular scope uses the nearest explicit stratum marker within a paragraph;
response extraction can use a single unambiguous METHODS KRAS variant. More
complex variant profiles, disease context, treatment line, and patient/preclinical
population distinctions are outside these initial record fields.

The compiler preserves reported statistical language. It does not calculate a
new significance decision, infer no effect from nonsignificance, infer clinical
benefit from a P value, or generalize across variants, populations, or regimens.
An explicit improved/increase or reduced/decrease phrase can provide reported
direction; this does not establish a causal treatment benefit. A claim asserting
an increase cannot become compatible merely because its significance agrees
when the source direction is unknown or different.
Unsupported patterns and ambiguous scope remain coverage gaps rather than
invented fields. The first version is deliberately incomplete.

### Bounded language and binding guards

- Recognized denial, conditional, or hypothetical wording produces
  `unsupported_negated_or_uncertain_report` before either result family is
  extracted. An author's reported nonsignificant finding is distinct from denial
  that a finding was observed.
- Negated arm definitions are not used. A variant in a recognized exclusion or
  hypothetical METHODS statement is not inherited. An excluded or otherwise
  unsupported nearest stratum marker blocks fallback to an older marker or the
  generic METHODS variant; molecular scope stays unresolved.
- An adjacent additional or alternative agent outside the therapy vocabulary
  makes a recognized arm expression ambiguous. The compiler must not truncate
  that arm to its known drugs and treat the subset as complete.
- Survival statements with unsupported top-level semicolons or conjunctions
  receive `unsupported_multiple_result_clauses`. Supported numeric parentheticals
  containing medians, hazard ratios, confidence intervals, and semicolons remain
  allowed. Punctuation alone is not treated as a new scientific result.
- A significance qualifier must bind locally to the same endpoint or its
  explicit named-arm comparison predicate. Unbound qualification yields
  `unsupported_survival_qualification_binding`. A direction term must also bind
  locally to that endpoint; otherwise direction stays unavailable with
  `effect_direction_unresolved`, even if other fields compile.

These are finite language guards, not a general negation, scope, or clinical
interpretation engine. Unfamiliar wording can fall outside them. Every extracted
record remains unreviewed, including records whose exact spans replay correctly.

## Limited claim comparison

The comparison step recognizes two explicit claim templates and requires a full
match. It does not silently classify a recognized fragment while ignoring the
rest of a claim. Its outcomes describe the limited comparison:

The supported forms are deliberately explicit:

```text
The [complete regimen] combination group had a reported response rate of [number]% in evaluable patients.
[Drug] monotherapy had a reported response rate of [number]% in evaluable patients.
In the [molecular] stratum, the increase in [overall survival / progression-free survival] with [complete regimen] compared with [comparator] was [nonsignificant / statistically significant].
```

Case differences and the declared normalization rules are supported; arbitrary
paraphrases or appended qualifiers are not. A single named drug does not identify
a combination with an omitted partner. The comparison uses one source record at
a time, preserving tuple associations rather than joining matching words from
different rows.

| Status | Meaning |
|---|---|
| `limited_context_compatible` | Recognized fields agree with a compiled record; this is not scientific support or acceptance. |
| `review_context_difference` | A material context differs and requires review; a different context is not automatically a biological contradiction. |
| `review_report_difference` | A reported value or qualification differs within the recognized comparison. |
| `review_unresolved` | The claim, source pattern, scope, or required information is not resolved by this tool. |

Every outcome remains experimental and subject to review. Agreement on recognized
fields does not authorize acceptance of the complete relationship. Neither compilation
nor comparison changes a graph lifecycle state, deletes evidence, approves an
assertion, or replaces a human decision.

The comparison payload preserves parsed claim spans, normalization rules,
candidates, field checks, and matched record IDs. `action` remains
`request_review`; `auto_approval` and `entailment_established` are false, and
`graph_mutations` is zero. Conflicting same-context source records cannot be
resolved by selecting only a favorable match; their disagreement requires review.

## Save and inspect artifacts

These commands use an existing verified literature collection and create new
output directories. They run entirely offline:

```sh
python3 -m biograph_steward source-facts \
  --literature runs/crc_context_verification_20261020/literature_live \
  --pmid 36546659 \
  --out runs/source_facts_krystal_001

python3 -m biograph_steward source-facts-verify \
  --result runs/source_facts_krystal_001

python3 -m biograph_steward fact-check \
  --facts runs/source_facts_krystal_001 \
  --claim 'Cetuximab monotherapy had a reported response rate of 46% in evaluable patients.' \
  --out runs/source_fact_check_001

python3 -m biograph_steward source-facts-verify \
  --result runs/source_fact_check_001
```

A fact artifact contains `source_facts.json`, `report.html`, and
`source_fact_manifest.json`. A comparison contains `comparison.json`, an HTML
report, and the same manifest filename. The comparison JSON embeds its dossier
and the original source-artifact manifest. Replay checks that the embedded
dossier and its rendered report match that original manifest's file hashes.
Manifests bind file hashes, identify zero model
requests and graph mutations, and declare no automatic approval.

Artifact loading verifies the inventory, hashes, deterministic compilation,
comparison replay where applicable, and regenerated HTML. Existing directories
are not overwritten. The Python workflow functions are `build_source_facts`,
`save_fact_check`, and `load_fact_artifact` in `source_fact_workflow.py`.

In the authenticated workspace, `GET /api/source-facts` lists saved dossiers and
`GET /api/source-facts/<id>/` opens a report with exact spans and coverage gaps.
Its form sends `POST /api/fact-check` with `facts_id` and `claim`, saving a new
review-only comparison. `GET /api/fact-check/<id>/` opens that comparison. The form
does not submit a human review or change an assertion's state. Local HTML remains
inspectable, but checking a new claim from the form requires its protected saved
workspace route.

## Development checks

The initial source fixtures reuse two observed CRC publications and the four
earlier full/focused source-only questions. They are development material with
AI-authored source references, not an independent biomedical benchmark.
Independent human scientific labels remain zero.

Report these measurements separately:

- Field and provenance validity, including exact source/offset binding.
- Requested-field coverage, with a fixed reference-field denominator.
- Complete association agreement: regimen/group/response/count or
  molecular scope/arm/comparator/endpoint/qualification/P value, plus any explicitly
  compiled effect direction.
- Unrequested content and unsupported additions.
- Cases requiring review because the tool does not cover their source or wording.

Field coverage cannot substitute for association correctness. Swapping two arms'
percentages or counts can preserve every number while producing false tuples.
The same applies to swapping PFS/OS qualifications. Offline checks should reject
wrong source bindings, altered spans, wrong group/endpoint associations, and
unrequested grade-5 or total-patient additions. Do not silently remove an extra
field and score the original output as a clean record.

The earlier model answers can provide a descriptive comparison of requested
coverage and unsupported additions. They were not asked to follow this new
schema, so do not score their plaintext format as a schema failure. If two
complete source dossiers are reused to answer four full/focused question
instances, disclose that duplication and the different source windows; these
are not four independently compiled studies.

The existing 18 claims can stress coverage and review routing offline. Keep all
claims visible, including papers and fact families the tool does not cover.
Unavailable source facts remain unresolved, not successful error detection.
Do not compare overall flag recall with a broader-source workflow as though
coverage were identical, or call agreement on these templates biological accuracy.

## Limits

Exact provenance proves where text came from; it does not prove scientific
truth, independence of studies, completeness of a paper review, or generality
of a pattern. Source-pattern success on two publications does not establish
de novo model extraction, reliable interpretation of other trial reports, or
improved graph prediction. Broader source support requires separately frozen
examples, declared coverage, and appropriate review.

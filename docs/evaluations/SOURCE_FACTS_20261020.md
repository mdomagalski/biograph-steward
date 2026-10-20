# Source-first facts: recorded development exercise

The new tool preserves four explicit result tuples from two previously inspected
publications and routes the known regimen and significance edits to different
review reasons. This demonstrates a narrow, reproducible source-pattern workflow;
it does not establish scientific accuracy, independent extraction performance,
or improvement to the biological graph.

## Source records

Compilation receives each saved paper alone, before any candidate claim. It uses
complete saved abstract blocks, not a claim-selected window. The two papers were
chosen because the preceding model probe found the requested associations but
added unsupported or unrequested narrative. These are observed development
sources, with zero independent human scientific labels.

| Source | Complete result association | Compiled record |
|---|---|---|
| KRYSTAL, PMID 36546659 | Adagrasib monotherapy, KRAS G12C | Response 19%; 43 evaluable patients |
| KRYSTAL, PMID 36546659 | Adagrasib plus cetuximab, KRAS G12C | Response 46%; 28 evaluable patients |
| PRIME, PMID 20921465 | WT KRAS; panitumumab-FOLFOX4 versus FOLFOX4; PFS increase | Author-stated significant result; P=.02 |
| PRIME, PMID 20921465 | Same WT comparison; OS increase | Author-stated nonsignificant result; P=.072 |

All four records pass exact span/hash and deterministic association replay, and
agree with the earlier AI-assisted source references. The checks reject
post-extraction field swaps; they do not prove that every source pattern was
interpreted correctly. Every record remains `pattern_extracted_unreviewed`.

The compiler also exposes seven flagged gaps across these abstracts, including
unsupported result language and combined endpoint/clause units. This is a
pattern-scope inventory, not seven biological errors or a complete paper review.
FOLFOX4 is an atomic named regimen. The tool does not expand it into ingredients,
calculate statistical significance, equate nonsignificance with no effect, or
infer treatment benefit.

## Known-claim exercise

All 18 existing development claims remain visible. Source facts exist for two
papers; six claims concern the third paper, which this increment does not compile.
Eight other claims use unsupported wording or fact families. Those fourteen
cases remain unresolved and are not counted as errors detected.

| Result | Claims | Interpretation |
|---|---:|---|
| `limited_context_compatible` | 2 | KRYSTAL combination response and PRIME nonsignificant OS have agreeing recognized fields. Review still required. |
| `review_context_difference` | 1 | Cetuximab monotherapy differs from the source treatment arms; this is not an opposing biological result. |
| `review_report_difference` | 1 | The PRIME OS significance edit conflicts with the source's explicit qualification in the same recognized context. |
| `review_unresolved` | 14 | Six lack a compiled source; eight fall outside the complete claim grammar. |

Every outcome has `action=request_review`, `auto_approval=false`,
`entailment_established=false`, and zero graph mutations. Disease, population,
treatment line, design, general activity and arbitrary paraphrases are not
verified by this increment. Added qualifiers cannot be silently dropped by a
partial claim match.

## Comparison with the earlier probe

The previous model probe made four requests across two papers, using full and
focused windows. Prior AI review found the requested core associations in all
four answers, unrequested narrative in all four, and an explicit extra error or
scope error in two. The new compiler makes zero model requests, produces four
structured tuples across two unique papers, and has no free-form biological
commentary field. It excludes the earlier invented missing-grade-5 and unscoped
patient-total assertions from its records. Original source text remains retained.

These output and source-window differences prevent an equal-window superiority
claim. Plaintext model answers were not asked to satisfy the new JSON schema and
are not retroactively scored as format failures. Agreement with known tuples is
not an independent benchmark or a new scientific holdout result.

## Product and verification

The protected app lists the dossiers under **Source facts and claim checks**.
Each report shows the source, record fields, exact source spans, coverage gaps,
and a claim form. A submitted claim creates a separate immutable comparison;
it does not record a human decision or alter graph states. The CLI provides
`source-facts`, `fact-check`, and `source-facts-verify`; see the
[tool documentation](../SOURCE_FACTS.md).

The development exercise is saved under
`runs/source_facts_increment_20261020/`, with a frozen code snapshot, stripped
claim inputs, protocol, result and a one-off recording script. The fourteen
replayable artifacts are the two dossiers and twelve comparisons for claims
with a compiled source. The six missing-source observations remain in the
aggregate record. Source material and raw run artifacts stay out of Git.

Final software verification ran 459 tests with one optional integration skipped,
zero failures and zero errors. Invented fixtures cover wrong-arm/value swaps,
cross-endpoint qualifications, excluded and unspecified molecular contexts,
unknown extra therapies, negative/hypothetical language, Unicode offsets,
rehashed semantic/report tampering, parent-artifact binding, HTML escaping,
sign-in, origin checks and protected downloads. Chrome verification submitted
the regimen edit through the form and opened the saved comparison.

The app was deployed on the existing Brev instance from the frozen working-tree
snapshot, without a Git commit or model restart. Fourteen artifacts were imported
and replayed there. A protected live API check confirmed sign-in requirements,
the two dossier links, report/download access and the review-only regimen result.
The deployment receipt binds seven app files to the frozen protocol. This
increment makes zero model requests; the model service remains unchanged.

- Protocol hash: `30c787acb5243ebc42826d22cd786a1ddb62d0cb172121dbdf46c952f9f59078`
- Result hash: `28a86aaad59f7f4c273d61f6751abcfe75ac51153fcc1372527e97d359ef018f`
- Original 18-case context result replays unchanged:
  `11c29c521832605eb9c2ad4a50689707cb1843377ee7179e62b384c34d005acd`.

The next evaluation should use a separately selected set of source paragraphs,
with declared coverage and reviewed arm/endpoint associations, before broadening
the patterns or allowing an agent to propose draft records. Reusing these known
cases for further tuning cannot establish generality or scientific improvement.

# Scientific qualification and pruning

The qualification commands create separate, reproducible artifacts. They do
not accept evidence, rewrite the source workspace, or calculate whole-graph
biological accuracy. Use a complete verified Gold source packet and new output
directories. Keep the original graph and its exhaustive decision ledgers.

For exact current-source inspection and the optional executed ontobio/GAFeRence
checks, see [native GO quality control](GO_NATIVE_QUALITY.md). That follow-up
does not transfer current qualifiers into unknown historical records.

## Recover native GO context

Pharos exposes the GO term, aspect, evidence/ECO code and assigning database.
Its inspected GraphQL model and historical TCRD loader do not preserve the full
GAF relation, negation, references, extensions or gene-product form. A matching
protein/term/evidence tuple cannot reconstruct those lost fields.

`qualify-go-context` uses the existing Biopython 1.88 GAF parser to preserve
native GAF 2.2 records alongside the verified source graph. It inventories all
GO evidence edges and records every compatible native candidate using exact
accession, GO ID, evidence code, assigning database and aspect. It does not
collapse isoforms or use names to force a match. Even a unique compatible row
does not establish historical source-record identity. Missing matches stay
unknown; the original edge's qualifiers remain unchanged.

The [official GAF 2.2 specification](https://geneontology.org/docs/go-annotation-file-gaf-format-2.2/)
defines explicit NOT, relation, reference, With/From, annotation extension and
product-form fields. AND/OR groupings and native literals must remain intact.
Multiple reference identifiers on one annotation can identify the same
reference; neither rows nor identifier counts are independent study counts.
Native GOA is an upstream annotation source, not an independent truth reference
for a Pharos GO annotation. Compatibility links must not become additional
votes supporting the original claim.

Use the existing optional source-audit environment; the application core has
no added dependencies:

```sh
python3.12 -m venv .venv-go-audit
.venv-go-audit/bin/python -m pip install -r requirements-go-audit.txt
.venv-go-audit/bin/python app.py qualify-go-context \
  --packet runs/my_source_packet \
  --gaf /path/to/HUMAN-uniprot.gaf.gz --gaf-sha256 VERIFIED_SHA256 \
  --source-url https://release.geneontology.org/RELEASE/annotations/gaf/HUMAN-uniprot.gaf.gz \
  --out runs/my_go_context
```

Hashes bind the supplied bytes; they do not authenticate an arbitrary declared
publisher URL. Verify release metadata and preserve source terms separately.

## Apply ontology currency checks

`qualify-go-ontology` checks exact primary GO IDs against a pinned OBO Graphs
JSON ontology. Active primary IDs qualify for a strict active-ID view. Explicitly
obsolete IDs are excluded from that view, and unavailable IDs remain undecided.
All other evidence families abstain and remain retained. The command reuses
the Gold interface to preserve the baseline, apply the complete decision ledger
and rebuild surviving assertion support.

[GORULE:0000020](https://github.com/geneontology/go-site/blob/master/metadata/rules/gorule-0000020.md)
already defines how the GO pipeline repairs merged/obsolete IDs when an explicit
replacement exists and filters annotations without one. This adapter reads the
same explicit ontology metadata; it is **not** execution of the full GO pipeline.
Pharos's lossy annotation-existence edges are not complete native GAF records.
Single, active `replaced_by` targets are therefore emitted as separate proposals,
without automatically changing the source edge or inheriting its review state.
`consider` suggestions never become automatic replacements. With/From and
extension ontology validation are outside this primary-ID check.

```sh
python3 app.py qualify-go-ontology --packet runs/my_source_packet \
  --ontology /path/to/go-basic.json.gz --ontology-sha256 VERIFIED_SHA256 \
  --out runs/my_active_go_view
```

An obsolete term is a demonstrated vocabulary-currency problem. It is not proof
that the underlying experiment or biological relationship was false. Conversely,
an active identifier is not proof of experimental support. Never delete a
`has_go_annotation` existence record merely because a compatible native GAF row
is negated: an annotation can exist and express NOT.

## Requirements for an independent biological comparison

A suitable reference must match the claim predicate, organism, assayed protein
sequence/form and experimental context. It must have a documented study origin
and separation from all inputs used to make the decisions. Existing consumed
panels remain development/sensitivity data. Missing references are not negative
labels, and designed or altered-construct negatives cannot refute generic
canonical-protein associations.

The [existing task filter](AUTOMATIC_TASK_QUALIFICATION.md), GO source recovery
and ontology currency check answer distinct questions. They do not jointly
become a calibrated false-edge classifier. A whole-graph accuracy percentage
would require suitable evidence across its different claim families and a
declared evaluation unit; a PPI-only reference cannot supply it.

The executed source/release checks, outcomes and remaining validation limits
are recorded in the evaluation report linked from the build plan.

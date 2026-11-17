# Native location records in the working question flow

The richer native GO context is now usable through the existing source,
question and export features. This is a **separate local Pharos + native-location
workspace**, not a replacement for the retained/enriched reviewer graph or an
AWS deployment. The [aggregate application receipt](public_gold_20261115/native_location_application.json)
records the exact source and graph hashes.

All **15,671 original Pharos records** are preserved. The profile adds **3,309
candidate source records**, grouped into **429 protein–location concepts across
94 of the 99 primary targets**. Of those concepts, 361 already occur as
protein/GO pairs in historical Pharos and 68 are absent there. The repeated pairs
provide explicit native relation, evidence and reference context; they are not
counted as independent corroboration. Reactome supplies 2,644 records and TAS
accounts for 2,687 annotations. Neither a row nor a reference identifier is
necessarily a distinct study.

## Open the example

On the operator checkout containing the saved source bundle, start the current
code from the repository root:

```sh
python3 app.py serve --host 127.0.0.1 --port 8797 --runs-dir runs --no-browser
```

Open
[the native-location workspace](http://127.0.0.1:8797/?run=native_location_workspace_20261115&view=evidence).
A code-only checkout does not contain this mixed-source dataset; the existing
hosted reviewer example continues to use its separately verified default.

1. In **Evidence & sources**, expand **Native GO locations**.
2. Choose a protein and keep **Inspect candidates** selected. Click
   **Show native GO annotations**.
3. Read the literal `located_in` relationship and evidence code. Expand a
   source record to inspect its references and full GAF fields. Use
   **Inspect source and recorded conditions** for the evidence passport.
4. Try **Accepted only**. It is empty because no source record has been
   automatically approved. Switch back to inspect the candidates.
5. Use **Download this answer** for the displayed page. The ordinary workspace
   ZIP separately preserves the complete graph, source publication and review
   state. A focused answer and a full workspace have different scopes.

The saved-data workflow needs **no Brev instance, GPU, model or fresh retrieval**.

## Qualification and verification

The versioned profile admits literal positive, active cellular-component
`located_in` rows with one human taxon, no distinct product form, no annotation
extension and empty With/From. This last condition is a conservative profile
boundary, not a claim that other GAF contexts are invalid. Original evidence
codes remain visible; an electronic annotation is not described as manually
reviewed. ND/root records do not supply a specific location and cannot become
supported-location claims, following
[GO's published ND semantics](https://geneontology.org/GO_REF/0000015.html).

The complete native GAF and existing source proof are replayed. No HOU labels,
benchmark mappings, model predictions or clinical conclusions enter this graph.
The frozen [reference comparison](PUBLIC_GOLD_REFERENCE_RESULTS_20261115.md)
remains a separate assessment, with its source-overlap and coverage limits.
No source compatibility check establishes universal biological truth or full GO
pipeline conformance. The older obsolete-term recovery profile is unchanged.

The [independent all-target question census](public_gold_20261115/native_location_question_census.json)
checks all 99 targets through 135 candidate-page requests and 99 accepted-view
requests. Their union exactly equals all 3,309 source records and 429 concepts;
29 targets exercise multiple pages. The five empty answers retain the
non-absence explanation, and all accepted views are empty. Actual authenticated
HTTP answer, source inspection, exact full-GAF download and 199-file on-demand
ZIP checks also passed. Source/default graphs and code remained unchanged during
the census.

Recreate a separate workspace from pinned local sources with
`python -m tools.go_qualification.publish_locations --help`. It requires the
exact original complete snapshot, native context and ontology. Output must be a
fresh destination; original/default workspaces and historical records are not
rewritten. The core application and source-profile path use the standard
library; optional scientific packages are needed only for their separate
reference-preparation tasks.

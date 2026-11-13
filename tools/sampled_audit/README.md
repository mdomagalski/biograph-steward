# Fixed sampled evidence audit

This optional adapter summarizes a frozen **stratified simple random sample
without replacement** of qualified assertions. It keeps the source-relative
and primary-evidence audit outcomes separate from independent scientific
correctness. It does not label biological claims, change a graph or turn
AI-assisted review into independent truth.

## Established method and verified fit

[Gao et al., PVLDB 2019](https://www.vldb.org/pvldb/vol12/p1679-gao.pdf),
section 5.1, defines simple random sampling without replacement for KG accuracy
evaluation. The [University of Michigan survey-design guidance](https://ccsg.isr.umich.edu/chapters/sample-design/appendix-c/)
documents the finite-population correction and sample-variance estimator.
For independent stratum draws, the ordinary population-weighted mean and
estimated design variance are:

```text
W_h = N_h / sum(N_h)
p_h = positive audit outcomes in stratum h / n_h
estimate = sum_h W_h * p_h
estimated variance = sum_h W_h² * (1 - n_h/N_h) * p_h*(1-p_h)/(n_h-1)
```

The implementation is a small project adapter for these standard equations,
not a reproduction of the authors' complete iterative/cluster algorithms.
Exhaustive tests enumerate every possible draw from two small finite
populations: their average estimated mean and variance must equal the known
population mean and exact randomization variance. Additional controls cover
unequal allocation, missing outcomes, census strata and paired removal.

The [SIGMOD 2025 author implementation](https://github.com/KGAccuracyEval/credible-intervals4kg-estimation)
was inspected at commit `05f85e810c8339dd999a9a99e33da0724a635150`.
Its MIT-licensed `framework/samplingStrategies.py` has SHA256
`e0143b9d4e49187fa5e037dfff1a87b2534a42bf8cad7c624e0eafc41afd2782`.
The actual `SRSSampler.run` draws with `random.choices` (replacement), accesses
already supplied binary `groundTruth` and does not implement UNKNOWN or the
fixed stratified design used here. Its Wilson/Beta/HPD functions cannot simply
be pooled across our strata into one valid accuracy interval. No author code
or labels are copied, no labels are invented, and no complete-paper replication
is claimed.

The [2026 author manuscript on LLM stratification](https://www.dei.unipd.it/~marches1/papers/mcs-vldb-2026.pdf)
similarly separates LLM sampling signals from human ground-truth annotation.
Sampling uncertainty does not quantify annotation mistakes or shared LLM errors.

Existing survey libraries were also checked: `samplics` is now superseded by
the [official `svy` project](https://github.com/samplics-org/svy), which provides
general design-based estimation. This small optional adapter needs only the
standard-library equations above; no new general survey framework or runtime
dependency is added to the application.

## Statistics API

First prepare a new immutable sample from a verified existing Gold packet. The
allocation file maps **every exact assertion kind** to its fixed sample size.
Freeze this allocation/seed before examining sampled outcomes.

```sh
python3 tools/sampled_audit/prepare.py \
  --packet runs/my_source_packet --allocation /path/to/allocation.json \
  --seed 2026111201 --out runs/my_frozen_audit
```

Preparation writes the sealed protocol before drawing IDs, then complete
assertion/evidence dossiers, `sample.jsonl`, a blank review template and a
sealed file inventory. It uses the existing source inspector; it does not
retrieve primary evidence, generate review outcomes or modify graph records.

After the source/primary-evidence audit, score a complete explicit review file:

```sh
python3 tools/sampled_audit/score.py \
  --audit runs/my_frozen_audit --packet runs/my_source_packet \
  --reviews /path/to/completed_reviews.jsonl --out runs/my_audit_results
```

The scorer replays the sample selection, inclusion probabilities and complete
dossier contents from the verified original Gold packet. Every review must
match its exact case, assertion, sample and dossier hash, with a stated actor,
both reasons and a nonempty evidence basis. Unavailable evidence needs an
explicit unresolved outcome and reason. The scorer checks source/review bytes
before and after export. It cannot authenticate reviewer expertise, assess the
truth of an arbitrary supplied reason, or independently calibrate an AI judge.

For the fixed preexisting GO-currentness comparison, also supply the complete
qualification directory, its independently recorded report-file SHA256 and
the separate sample-bound intervention receipt:

```sh
python3 tools/sampled_audit/score.py \
  --audit runs/my_frozen_audit --packet runs/my_source_packet \
  --reviews /path/to/completed_reviews.jsonl \
  --go-qualification runs/my_existing_go_qualification \
  --go-qualification-report-sha256 VERIFIED_REPORT_FILE_SHA256 \
  --intervention-binding /path/to/intervention_binding.json \
  --out runs/my_paired_audit_results
```

This uses `go_ontology_qualification.load_ontology`/`classify_term` to reproduce
the exact lifecycle decisions and `gold_packet.load_decisions` to verify the
complete retained graph/ledger. It checks the original source/policy binding
and derives retained assertions from surviving evidence, preserving alternate
support. It does not accept a merely labelled, arbitrary “pruned graph.”
The executed receipt explicitly records when its binding was added after sample
selection; it binds an unchanged policy/output from the previous assessment
and does not claim to precede every reviewer inspecting a case.

The result includes the preserved review bytes, weighted statistics, optional
paired case dispositions and a sealed provenance report. Original source
graphs and human review states are unchanged.

```python
from tools.sampled_audit.audit_statistics import summarize

report = summarize(
    strata={"some_family": {"population_size": 100, "sample_size": 10}},
    sample_rows=sample_rows,
    review_rows=review_rows,
    retained_assertion_ids=retained_ids,  # optional frozen intervention
)
```

Each sample row supplies `case_id`, `assertion_id` and `stratum`. Review rows
must match every sampled case exactly once and provide:

- `source_relative_support`: supported / contradicted / unresolved;
- `primary_evidence_support`: supported / contradicted / unresolved;
- `independent_scientific_correctness`: unreviewed.

Additional row metadata is checked/preserved by the preparation and audit
workflow. This module checks complete case/stratum alignment, outcome vocabulary
and fixed population/sample sizes. It does not authenticate an arbitrary
supplied evidence dossier or sampling claim. The caller supplies the verified
frozen source population and intervention; retained assertion membership must
be derived from surviving evidence edges, rather than loss of any one record.

For each axis, all three status fractions use the **original population**
weights and sampled denominator. Their design-based standard errors describe
sampling variation of the declared audit procedure only. No biological
confidence interval is produced. A non-census stratum with one sampled unit
cannot estimate variance; the standard error is unavailable. No observed
variation can give a zero estimated standard error even with a small sample;
the report flags this and does not call it certainty.

The `weighted_sample_completion_range` assigns all sampled unresolved outcomes
first to contradicted and then to supported. It is a sensitivity range for
unresolved **sampled** outcomes, not a confidence interval or guaranteed bound
on population biological accuracy. Unresolved cases are never dropped from
the denominator or automatically treated as false.

The optional paired intervention reports the original-population weighted
fractions of supported, contradicted and unresolved audit outcomes removed,
plus retained coverage. These describe the supplied source/primary-evidence
review procedure. They are not calibrated estimates of biological errors
removed or scientifically valid claims lost. Independent scientific labels
are explicitly unreviewed; this adapter rejects attempts to inject or score
them as if the necessary validation were already implemented.

```sh
PYTHONPATH=.:tests python3 -m unittest \
  test_sampled_audit_preparation test_sampled_audit_statistics test_sampled_audit_scoring -v
```

Raw source and dossier data retain provider terms. The software license does
not clear redistribution of the full underlying graph package.

## Project exact source-version pathway context

`wiki_version_projection.py` applies the existing plain JSONL plus mapping-ledger
exchange pattern to a **verified Gold retained package**. It groups only exact
provider/full `WP_rREV` identifiers whose complete native metadata agrees and
whose source-supplied version URL matches literally. That URL stays verbatim;
there is no URI identity conversion, namespace guessing or revision collapse.

```sh
python3 tools/sampled_audit/wiki_version_projection.py export \
  --retained runs/my_current_wiki_view/retained \
  --retained-report-sha256 VERIFIED_REPORT_FILE_SHA256 \
  --out runs/my_wiki_version_projection
python3 tools/sampled_audit/wiki_version_projection.py verify \
  --projection runs/my_wiki_version_projection
```

The projection keeps every represented evidence ID, directed predicate and
original assertion/review reference. Parallel triples are not merged or
independent experimental votes. Node, edge, assertion and source-resource
ledgers account for all inputs; the complete original retained package is
preserved. Unsupported identities, conflicting metadata and qualified records
outside this flat profile remain in that source with explicit reasons.

Shared `protein → source version ← protein` context is not a newly inferred
PPI or a directed two-hop protein path. A source-reported version locator does
not validate historical content or membership. This is a separate source
projection, with no full KGX/Biolink validation claim; it changes neither the
app normalizer nor existing standards/SSSOM identity contracts. See the
[executed normalization record](../../docs/evaluations/WIKIPATHWAYS_VERSION_NORMALIZATION_20261112.md).

```sh
PYTHONPATH=.:tests python3 -m unittest test_wiki_version_projection -v
```

## Build a cohort-independent WikiPathways reference packet

`prepare_wiki_reference.py` packages provided native files and proof metadata;
it does not need an earlier cohort analysis, sampled labels or a network call.
The existing author reader and `wiki_current_view.load_reference` replay the
native GMT before any completed reference packet is published.

```sh
python3 tools/sampled_audit/prepare_wiki_reference.py \
  --metadata /path/to/native_reference_inputs.json --out runs/my_wiki_reference
```

The strict metadata JSON has exactly these top-level fields:

```json
{
  "format": "biograph-steward.wikipathways-reference-inputs.v1",
  "source_release": "20261110",
  "source_url": "https://data.wikipathways.org/current/gmt/wikipathways-20261110-gmt-Homo_sapiens.gmt",
  "version_proof": {"Version": "WP4566_r104315", "canonical_WPID": "WP4566"},
  "files": {}
}
```

Populate `files` with all eight entries below. Each value has only `path` and
`sha256`; relative paths resolve against the metadata file's directory. The
empty `files` above is an illustration, not a runnable completed configuration.

| File key | Provided bytes |
|---|---|
| `gmt` | Dated native human GMT from the [official monthly catalog](https://data.wikipathways.org/current/gmt/) |
| `read_gmt`, `read_pathway_gmt` | The two unmodified Python reader sources at [author commit 2e77a566](https://github.com/wikipathways/pywikipathways/tree/2e77a5665f8261b56e2ef61d8b0106c220193ac5/pywikipathways) |
| `reader_license` | That Python repository's full MIT `LICENSE` |
| `r_reader_documentation` | The [author's GMT identifier documentation](https://github.com/wikipathways/rWikiPathways/blob/edca798edb99fc3c8461dbf34b5eb86c6c477b82/R/readPathwayGMT.R) |
| `r_reader_license` | That R repository's separate [MIT license text](https://github.com/wikipathways/rWikiPathways/blob/edca798edb99fc3c8461dbf34b5eb86c6c477b82/LICENSE) |
| `primary_paper_bioc` | [NCBI's official machine-readable copy](https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_xml/PMC10767877/unicode) of the WikiPathways 2024 paper |
| `gpml_version_proof` | A native GPML whose literal `Version` matches the supplied proof, e.g. [the pinned official historical example](https://raw.githubusercontent.com/wikipathways/wikipathways-database/25baea66eedf264287585a92517f14400f9c8157/pathways/WP4566/WP4566.gpml) |

All input SHA256 values are explicit. The reader, both MIT license texts and R
documentation pins must also match the reviewed allowlist in
`wiki_current_view.py`. Unknown executable reader code is rejected. The native
reference verifier checks actual release/species, row coverage, identifiers
and the literal GPML version relation. This is an encoded gene-membership
reference, with no claim of equal pathway contents across releases.

Output `reference.json` and its reported file SHA256 can be passed directly to
the current-Wiki view CLI below, with **any separately verified source cohort**.
`reference_manifest.json` records the native replay, complete copied input
inventory and provenance. Neither file contains the prior 99-target cohort's
diagnostic decisions. Input changes or failed native replay do not publish a
completed packet. Optional pandas is needed for the real author reader; the
core application's dependencies remain unchanged.

Use an isolated Python 3.12 environment for the pinned native reader:

```sh
python3.12 -m venv /path/to/reader-venv
/path/to/reader-venv/bin/python -m pip install -r tools/sampled_audit/requirements-pathway-quality.txt
PYTHONPATH=.:tests /path/to/reader-venv/bin/python -m unittest evaluation_wiki_author_reader -v
```

## Optional current WikiPathways membership view

`wiki_current_view.py` is a separate **exploratory source-eligibility view**.
It does not change the frozen audit, its intervention or the default app graph.
It executes the reviewed unmodified `pywikipathways` GMT reader at author commit
`2e77a5665f8261b56e2ef61d8b0106c220193ac5`, using the supplied pinned native
human GMT and existing frozen human HGNC/UniProt registry. The optional runtime
needs Pandas; the core application still has no additional dependency.
The native [rWikiPathways reader documentation](https://github.com/wikipathways/rWikiPathways/blob/edca798edb99fc3c8461dbf34b5eb86c6c477b82/R/readPathwayGMT.R)
identifies the GMT entries as NCBI Entrez Gene IDs. The
[WikiPathways 2024 paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC10767877/)
and pinned native GPML version metadata supply the reviewed version semantics.

```sh
python tools/sampled_audit/wiki_current_view.py \
  --packet runs/my_source_packet \
  --reference-report /path/to/reviewed_current_membership_reference.json \
  --reference-sha256 VERIFIED_REFERENCE_REPORT_FILE_SHA256 \
  --registry /path/to/frozen_human_registry \
  --registry-sha256 VERIFIED_REGISTRY_CONTENT_SEAL \
  --out runs/my_current_WikiPathways_view
```

The reference report format is
`biograph-steward.exploratory-current-wikipathways-membership.v1`. Its self-seal,
native GMT release/URL/hash, two reviewed author source files, version proof and
Entrez namespace documentation are checked. Diagnostic cohort labels in the
report are ignored; every graph edge is assessed from the native source and
full registry. The reference is retained with the result. No source fetching,
model inference or name/symbol matching occurs.

For exact native WikiPathways membership edges only, a unique explicit
UniProt GeneID cross-reference must agree with an approved HGNC record's
Entrez and exact UniProt links. This is a gene-to-protein relationship, not
protein/isoform identity. Recognized `WP..._r...` records retain an explicit
`dcterms:isVersionOf` relationship and their original revision. When the current
pathway is present, an encoded GeneID is kept and an unlisted GeneID is excluded
**only from this current-source view**. Missing pathways, ambiguous/missing
identifiers and every non-WikiPathways edge remain unknown and retained.

The complete Gold decision ledger, retained graph and original baseline packet
are exported through the existing Gold machinery. `source_groups.json` groups
by exact subject, provider/type and **full sourceID including revision**, while
preserving every local `pwid`, edge, assertion and decision. No native rows are
merged or counted as independent evidence. Unknowns and previous review states
are preserved. A pruned row is not a false biological assertion, and a current
membership is not independent experimental validation. This post-sample view
cannot be presented as the frozen confirmatory comparison or biological gain.

```sh
PYTHONPATH=.:tests python3 -m unittest test_wiki_current_view -v
```

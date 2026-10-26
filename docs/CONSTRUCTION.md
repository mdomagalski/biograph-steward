# Construct and publish an explicit protein cohort

The construction flow connects an exact accession request to bounded Pharos retrieval, normalization, a saved evidence graph and a cited neighborhood answer. It uses the existing Pharos adapter and graph transformer. A deterministic plan selects the fixed retrieval profile; no language model, GPU, Brev instance or AWS account is required.

This increment is deterministic construction and publication, not an autonomous construction agent. The user selects the cohort and supported profile. Agent-selected source retrieval remains a separate future step requiring its own constrained tool contract and evaluation.

The product milestone is a reproducible graph publication. It does not establish improved predictions, scientific accuracy, independent experimental evidence or accepted biological claims.

## Run a construction

From the repository root, choose a new output directory. This example requests Pharos interaction annotations for three exact accessions and inspects connections to `P04637`:

```bash
python3 app.py construct \
  --accessions P04637 P00533 P01116 \
  --focus-uniprot P04637 \
  --profile ppi \
  --relations interactions \
  --out runs/protein_cohort_example
```

The request accepts 1–25 distinct exact UniProt accessions, including explicit isoform suffixes. The focus must be one of them. Symbols, ambiguous synonyms, implicit disease selection and additional source URLs are unsupported. A returned accession must exactly match the requested accession; syntactic validity does not imply Pharos can resolve it. Missing and mismatched identities remain in the scope report; they are not silently replaced or removed from the request denominator.

Use `--profile context --relations interactions shared_pathways` to also retrieve the supported annotation context. The two fixed profiles have these per-protein limits:

| Source family | `ppi` | `context` |
|---|---:|---:|
| Interaction neighbors scanned | 5,000 | 5,000 |
| Pathway annotations | 0 | 2,000 |
| GO annotations | 0 | 500 |
| Drug listings | 0 | 100 |
| Publication discovery records | 0 | 20 |
| Expression observations | 0 | 0 |

The whole retrieval is bounded by 200,000 context rows. Interactions retain partners within the declared cohort; untouched raw responses preserve out-of-cohort neighbors. The existing Pharos query uses `ppiConfidence: 400`; this is not a common probability cutoff across all contributing providers. Metadata counts may be retrieved for families whose annotation rows were not requested.

Coverage reports distinguish retrieved, retained and excluded rows, known counts, caps and inconsistent counts. A complete API count means completion of this bounded source query, not complete biological knowledge. Missing interaction records are not negative experimental results. API version checks and saved timestamps do not establish an atomic database snapshot or an upstream study's independence.

Live retrieval honors the existing `--endpoint`, `--cache-dir`, `--timeout` and `--refresh` options. Cached source envelopes retain their original retrieval timestamps. A live failure never falls back to synthetic data.

## Inspect the saved graph and answer

Start the workbench with the parent directory containing the construction run:

```bash
python3 app.py serve --runs-dir runs --port 8765 --no-browser
```

Open `http://127.0.0.1:8765/?run=protein_cohort_example&question=protein_cohort_example` in a browser. The saved graph has no invented disease node or disease-membership edges. Original source properties and reciprocal interaction views remain traceable through normalized candidate assertions.

The construction answer inspects candidate annotations. It does not automatically accept them. Interaction annotations can represent functional associations or co-complex evidence; the answer does not infer direct binding, mechanism or causality. Shared pathways are general annotation context. GO relations and polarity are not inferred from the limited Pharos fields; drug listings do not establish binding or clinical response. Publication discovery is not claim-specific citation support.

If the selected focus cannot resolve exactly, the graph and identity gaps are still published, with `answer_status: anchor_unresolved` and no fabricated answer. Other proteins' annotations remain inspectable.

Use the existing deterministic question command for another saved-cohort question:

```bash
python3 app.py question \
  --run runs/protein_cohort_example \
  --protein P00533 \
  --relations interactions \
  --view candidates \
  --out runs/protein_cohort_followup
```

The existing model planner and the narrow CIViC enrichment adapter remain disease-scoped. They reject explicit-cohort runs before calling a model or an external source. The optional NeMo wrapper still exposes that existing fixed-source question workflow; it is not a construction agent. Cohort refresh comparison is also outside this increment; publish a separate run and retain both snapshots.

## Verify and reproduce a publication

Verify the saved publication and its source/answer bindings without network access:

```bash
python3 app.py construction-verify --run runs/protein_cohort_example
python3 app.py gold-verify --packet runs/protein_cohort_example/gold_packet
```

Reproduce construction from its preserved snapshot into another new directory:

```bash
python3 app.py construct \
  --snapshot runs/protein_cohort_example/snapshot.json \
  --out runs/protein_cohort_replay
```

Offline publication preserves the snapshot's original request, source responses and retrieval timestamps. It uses the current deterministic transformer and records a new publication receipt. Output directories are immutable: choose a new directory instead of overwriting an earlier publication. Changing the selected proteins or profile requires a new live request.

The run contains the ordinary graph, assertions, context and coverage exports, untouched source responses, the construction request/plan trace and a sealed publication receipt. When an answer is available, `question.json` sits at the run root and its readable exports are in `answer/`. The nested `gold_packet/` directory supports separate offline handoff and integrity verification through the existing gold-interface implementation. That packet is a project-local exchange interface, not an organizer-supplied gold standard or a claim of full KGX/Biolink conformance. Software and retrieved data retain separate license terms.

The receipt records hashes of the construction, retrieval, normalization and question implementations. Strict replay requires that recorded runtime; when code changes, preserve the old publication and republish its snapshot into a new directory. Static reports and the separately verified gold packet preserve the old evidence independently. Hashes detect changes relative to saved receipts; they do not authenticate the upstream publisher or establish factual truth. Ordinary graph publication and source provenance should be evaluated separately from predictive or biological improvement.

## Reused contracts and the remaining gap

The [official Pharos schema](https://github.com/ncats/pharos-graphql-server/blob/master/src/schema.graphql) already supports exact `ITarget.uniprot` queries and the context fields used here. The implementation reuses `retrieve_context`, `build_graph`, the existing question engine and source-bound packet exporter. The missing application capability was a disease-free cohort scope plus an atomic publication boundary, not a new biological extraction method. Verification replays recorded responses through the same adapter; it detects transformation inconsistencies but is not an independent audit of upstream data.

The [Biolink definition of `interacts_with`](https://biolink.github.io/biolink-model/interacts_with/) includes physical and functional relationships. This flow retains that broad interpretation because the supplied annotations do not uniformly justify a stricter binding predicate. Full standard conformance, study independence and measured biological benefit remain separate work.

For a synthetic software demonstration without network access:

```bash
python3 app.py construct --demo --out runs/construction_demo
python3 app.py construction-verify --run runs/construction_demo
```

The demonstration remains explicitly labeled `synthetic_demo`; it is not retrieved Pharos evidence.

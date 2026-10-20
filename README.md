# BioGraph Steward: Pharos evidence workbench

A runnable starting point for **CRC Target Scout**, the first BioGraph Steward use case.

Instead of asking separate people to design disconnected components, start with one shared flow:

```text
Select an exact disease -> retrieve a scoped cohort -> ask a guided question
-> inspect evidence paths and cited summaries -> review assertions and export
```

## Quick start

Python 3.10+; **no third-party dependencies, API keys, cloud account, graph database or LLM required**.

```bash
cd biograph-steward-pharos
python3 app.py
```

Open `http://127.0.0.1:8765` if a browser does not open automatically. Use `py` instead of `python3` on Windows where appropriate.

Read [START_HERE.md](START_HERE.md) for the team walkthrough.

Version **0.8.0** adds [Brev/Docker deployment and shared model-provider configuration](docs/PORTABILITY.md): persistent run/cache paths, protected shared hosting, NVIDIA NIM support for both planner and verifier, and an optional NeMo Agent Toolkit workflow. The core still needs no extra Python packages. [Core deployment on Brev](docs/BREV_DEPLOYMENT.md) passed the Linux tests and authenticated Docker restart checks on October 19, 2026 (EDT). Live NIM inference and AWS integration remain unverified.

Use `python3 app.py deployment-smoke --base-url http://127.0.0.1:8766 --out runs/deployment_smoke_01` against a running service to check synthetic data, cited answers and access controls without model calls. See the deployment guide for post-restart receipt checks and the explicit `--with-planner` model test.

The **fuller scoped Pharos profile is implemented**: paginated pathways and GO, bounded interaction neighborhoods restricted to the selected cohort, drug listings, selected tissue-expression records and publication discovery. Every family has a per-protein coverage report. See [scoped retrieval and live validation](docs/SCOPED_RETRIEVAL.md). These remain Pharos baseline data; GO, interaction, drug and expression context now forms qualified candidate assertions with source crosswalks and reciprocal deduplication; see [normalization and validation](docs/CONTEXT_NORMALIZATION.md). The [guided question workflow](docs/GUIDED_QUESTIONS.md) now finds scoped interaction/shared-pathway evidence and produces cited summaries. A [bounded CIViC integration](docs/CIVIC_EVIDENCE.md) now adds whole molecular-profile/therapy response annotations, source/publication passports and overlap accounting.

### What was actually tested

The offline workflow, mocked API pagination, normalization, evidence preservation, caching, exports, local HTTP endpoints and browser interactions were tested. The package includes a synthetic demonstration with explicit labels throughout. **It does not include a real Pharos snapshot.**

On October 14, 2026, `doctor` successfully checked the live Pharos API (`pharos319`), and a paginated colorectal adenocarcinoma retrieval returned all 99 reported targets. Earlier packaged validation notes describe an older environment with DNS failures. The live run is saved locally under `runs/`, not distributed as an example dataset. Run `python3 app.py doctor` to check current availability. No failure silently falls back to synthetic data.

The [evaluation runner and reviewer worksheets](docs/EVALUATION.md) compare frozen Pharos/enriched sources and an optional bounded question-planning model. Scientific judgments stay pending until reviewed; live model calls require local configuration.

The optional planner supports an API endpoint or an explicitly selected, already authenticated Codex CLI. See [configuration and isolation](docs/EVALUATION.md#optional-signed-in-codex-cli) and the [three-case source-review notes](docs/PILOT_REVIEW.md). Those AI-prepared notes leave human judgments pending.

[Study and treatment context](docs/STUDY_CONTEXT.md) now appears alongside CIViC summaries: per-record levels and study titles, original descriptions, treatment-list limits and shared citations. The same details are exported without inferring monotherapy or changing graph review states.

The proposed [source-verifier contract](docs/VERIFIER_PROTOCOL.md) now has an [external benchmark plan and SciFact preparation command](docs/VERIFICATION_BENCHMARKS.md). Expert labels are kept separate from model inputs; the prepared data has not yet been used to evaluate a verifier.

## What the prototype does now

- Freezes source snapshots and implementation hashes, runs grouped pilot questions, exports three source-bound review sheets, and scores partial human judgments without treating unknowns as negatives.
- Provides one structured question-planning model interface that calls the existing read-only engines, with explicit unavailable/replay/test modes.
- Supports a scoped CIViC KRAS/Colorectal Cancer therapy-response question, preserving complete profiles, therapy sets, evidence directions and separate source/local review states. See [scope, use and validation](docs/CIVIC_EVIDENCE.md).
- Guides a supported protein-neighborhood question through explicit scope, a compact evidence graph, cited summaries and saved/exportable results. Accepted paths require every assertion to be accepted; candidate exploration is explicit.

- Finds candidate disease names through Pharos and requires an explicit choice.
- Retrieves target records with UniProt identifiers, symbols, target-development level, family and disease-specific association details.
- Offers a quick pathway preview or fuller scoped retrieval with per-family caps and a global row budget. This retrieval profile remains a **Pharos-only extract**; CIViC is an explicit separate enrichment step.
- Reports scanned, retained, capped, inconsistent and unrequested data separately. Filters interaction partners to the selected cohort and expression records to explicitly entered tissue words.
- Provides a paginated source-context browser linked to qualified candidate assertions, with raw-response provenance, reciprocal interaction grouping and explicit tissue/assay observations. Human decisions control acceptance; publication discovery is kept separate.
- Preserves source names, references, raw evidence and source-specific scores without combining them into a confidence value.
- Maps explicit MONDO identifiers, UniProt identifiers and recognizable Reactome pathway identifiers. Other pathways retain clearly local Pharos IDs; no name-based ontology mapping is invented.
- Writes a small graph using Biolink category/predicate labels, plus provenance-bearing evidence records. This is a minimal alignment, not a claim of full KGX/Biolink validation.
- Flags incomplete evidence or disease-name mismatches for review. Invalid identifiers and exact duplicate target records go into a quarantine log, and original data remain in the snapshot.
- Presents a graph, target table, development-level filter, evidence inspector and review queue.
- Groups supporting records into qualified assertions with stable claim IDs and evidence revisions. Unknown qualifiers remain null; no variant/therapy context is inferred.
- Records human decisions separately from structural validation, with reviewer, reason and timestamp. Each decision creates a new run; earlier runs and snapshots remain intact.
- Starts the graph in an accepted-assertions view. Use **Inspect candidates** for raw/unreviewed evidence. Saved run URLs reopen review history.
- Connects records naming another disease to a separate local disease node. Records with no explicit disease context are retained in quarantine rather than assigned to the selected disease.
- Saves an offline HTML report and machine-readable artifacts; any saved snapshot can be replayed without network calls.

## Commands

```bash
# Local browser application
python3 app.py

# Explicit synthetic demo: no scientific results
python3 app.py demo --out runs/demo

# Test endpoint and required schema fields
python3 app.py doctor

# List actual disease names and identifiers
python3 app.py search colorectal

# Build using an EXACT NAME returned by the search
python3 app.py build --disease "EXACT DISEASE NAME FROM SEARCH" \
  --max-targets 25 --page-size 25 --pathways 5 --out runs/pharos_crc_01

# Fuller scoped pull of the audited 99-protein cohort (expression scope is explicit)
python3 app.py build --disease "colorectal adenocarcinoma" --max-targets 100 \
  --profile scoped --tissue-term "colon rectum" --out runs/crc_scoped_01

# Recreate output from a previously saved snapshot, without internet
python3 app.py replay --snapshot runs/pharos_crc_01/snapshot.json --out runs/replayed_01

# Export the actual GraphQL requests for inspection
python3 app.py queries --out queries

# Ask a guided question of a saved source run (default view: accepted only)
python3 app.py question --run runs/crc_scoped_01 --protein UniProtKB:P01116 \
  --view candidates --out runs/question_01

# Audit a saved snapshot and prepare one review row per protein-disease pair
python3 app.py audit --snapshot runs/pharos_crc_01/snapshot.json --out runs/audit_01

# Record a decision using an actual ID from assertions.json
python3 app.py review --run runs/pharos_crc_01 --assertion 'assertion:ACTUAL_ID' \
  --state provisional --reviewer 'Reviewer name' --reason 'Evidence reviewed and rationale' \
  --out runs/reviewed_01

# Replay the exact snapshot AND its review history
python3 app.py replay --snapshot runs/reviewed_01/snapshot.json \
  --reviews runs/reviewed_01/review_events.json --out runs/reviewed_replay

# Run the test suite without installing pytest
python3 -m unittest discover -s tests -v
```

The CLI refuses to overwrite a nonempty output directory. Choose a new output name for every run.

The query parameter is a disease name, not unrestricted natural language. A general question planner belongs in a later increment.

## Data modes

| Mode | Meaning |
|---|---|
| `synthetic_demo` | Invented fixture used to test software; fake entities use `demo:` identifiers. No scientific conclusions permitted. |
| `live_pharos` | Retrieved from the configured GraphQL service, possibly using an explicitly recorded API cache. Original retrieval times are retained. |
| Replay | Reads a previously saved snapshot; preserves its original data-kind label and hash. Replay does not turn synthetic data into real data. |

A SHA-256 digest detects accidental snapshot edits; it is not a digital signature or independent proof of origin.

## Output contract

| Artifact | What it contains |
|---|---|
| `report.html` | Standalone, interactive inspection view. No external JavaScript/CDN required. |
| `graph.json` | Full node/evidence-edge representation, summary, review reasons and caveats. |
| `retrieval_coverage.json`, `retrieval_coverage.tsv` | Scoped-profile counts, status, limits, exclusions and response-page pointers per protein/family. |
| `context_records.json`, `context_records.tsv` | Inspectable source context, exact-duplicate grouping and original snapshot locators; separate from assertions. |
| `normalization_report.json` | Per-family source rows, evidence groups, assertions, reciprocal views, statuses and normalization policy. |
| `context_metadata.json` | Per-protein source inventory and affiliate links; links do not imply external data retrieval. |
| `assertions.json`, `assertions.tsv` | Qualified claims, contributing evidence IDs, lifecycle states and evidence revisions. |
| `review_events.json` | Ordered human decisions bound to the exact snapshot and assertion revision. |
| `question_scope.json` | Supported disease-inspection question, relation families, configured limits and unsupported requirements. |
| `review_parent.json` | For review runs, identifies the original run and preceding event count. |
| `nodes.tsv` | Stable identifiers, labels, Biolink categories, target-development levels and mapping status. |
| `edges.tsv` | One row per distinct source-evidence record, with assertion ID, source, references and raw-source locator. |
| `targets.tsv` | One row per retrieved unique protein, in display order; not a prediction ranking. |
| `snapshot.json` | Disease, target records, query settings, retrieval limits, request envelopes and integrity hash. |
| `raw_responses/*.json` | Successful GraphQL request/response envelopes with UTC retrieval times and response hashes. |
| `quarantine.jsonl` | Malformed records and duplicates excluded from graph construction, with reason codes. |
| `run_manifest.json` | Parameters, version information when returned, cache use, checks and explicit model/LLM-not-run flags. |
| `pipeline_trace.json` | Human-readable workflow steps. |
| `source_licenses.json` | Source-license metadata as returned by Pharos, when available. Missing metadata is not permission to redistribute. |
| `benchmark_readiness.json` | Pair/evidence counts, citation coverage and missing prerequisites for model comparison. |
| `review_candidates.tsv` | One row per reported protein–disease pair with evidence IDs and blank reviewer fields. Review candidates are not training labels. Worksheet import is not yet implemented. |

The JSON outputs are canonical for downstream programming. TSV cells beginning with spreadsheet-formula characters are escaped for safer manual opening.

Every new build or replay includes the benchmark audit. It does not train a model or assign positive/negative labels. Summaries such as `2 PubMed IDs` are not counted as explicit citations; an explicit PMID or reference URL is only a presence check, not verification of support. An excluded or absent association is never converted into a negative label.

Version 0.6 writes graph format v3 while retaining raw snapshot format v1. The seven legacy qualifier slots preserve existing claim IDs; optional observation qualifiers qualify the new statements. See [the normalization contract](docs/CONTEXT_NORMALIZATION.md). Replaying older snapshots applies the current context rules, so derived graphs and pair counts may change; original snapshots are never rewritten. Without `--reviews`, replay creates candidate assertions. With `--reviews`, decisions must match the exact snapshot and evidence revision. The local reviewer field is a recorded name, not authenticated identity. See [the data contract](docs/DATA_CONTRACT.md).

## Scientific interpretation

**This is an inspection graph, not a discovery result.** A database-reported disease association can come from different evidence types; it is not automatically an experimentally established relationship.

- `passed_structural_checks` means usable identifiers and minimal provenance passed the implemented rules. It does not mean correct biology.
- `needs_review` means a record is inspectable but has a stated issue, such as missing source information, an unresolved identifier mapping or a disease-name mismatch.
- Input quarantine handles malformed/duplicate records and records missing disease context. It does not implement an LLM hallucination detector or determine whether a biological relationship is false.
- Development-level labels are retained as supplied. Do not treat Tbio and Tdark as interchangeable, or assume every Tbio protein is poorly studied.
- The graph shows known retrieved links, not new target hypotheses. Source-score values retain their original scale and must not be compared as calibrated probabilities across sources.
- Two source names or references do not prove independent evidence.
- A protein's pathway annotation is general context; it does not prove a colorectal-cancer mechanism.
- Pharos may return related disease labels in association details. Such records are flagged for review rather than silently relabeled as exact-disease evidence.
- Query limits and pathway caps are displayed. This graph is not the complete Pharos knowledge graph.

## How it becomes the challenge prototype

The organizer brief requires an agent-built, contextualized graph and a fair held-out-link comparison with the same ML method on a baseline graph. This starter deliberately stops before that comparison.

After one live run is understood, add one change at a time:

1. Complete bounded Pharos retrieval and normalize overlapping evidence. Then define the cohort and evidence policy; split unique protein-disease pairs before training.
2. Review the implemented CIViC qualified-evidence example, then add selected CPTAC measurements with record- and study-level overlap checks. Pharos already includes pathways, PPIs and links to many candidate sources; a new connector is not proof of new evidence.
3. Compare the same model and split on Pharos-only and externally enriched variants. Block held-out labels, duplicates, inverse links and disease-equivalent leakage from model inputs.
4. Add an agent planner that chooses and invokes these existing tools. Avoid giving an LLM unrestricted graph-write access.

CPTAC/PDC measurements, ROBOKOP, GNNs and link prediction remain unimplemented. The optional model plans scope; scientific answer statements continue to come from deterministic source-query tools. Neither is continuous source monitoring. Explicit refresh and snapshot replay provide a reproducible foundation, not a claim of automatic maintenance.

## Code map

This is one local application, not microservices.

```text
app.py                         Entry point; run this first
biograph_steward/client.py      Read-only requests, pagination, cache and schema checks
biograph_steward/graph.py       Normalization, evidence graph, checks and exports
biograph_steward/assertions.py  Qualified claims and review-state validation
biograph_steward/reviews.py     Immutable review runs and history replay
biograph_steward/webapp.py      Local HTTP endpoints and standalone report generator
biograph_steward/ui.html        Browser interface, no build step
biograph_steward/demo.py        Clearly synthetic software fixture
tests/test_starter.py           Offline tests and local endpoint tests
examples/synthetic_demo/        Prebuilt demo outputs
queries/                       Actual GraphQL queries used by the program
```

## Network and operational notes

Live mode uses `https://pharos-api.ncats.io/graphql` with read-only POST queries. Public queries do not include an API credential. Availability, access policy and deployment schema can change.

The client supports HTTPS proxies through standard environment variables. For an approved enterprise certificate bundle, use `SSL_CERT_FILE`. Do not disable certificate verification.

```bash
# Adjust only to values approved for your environment
export HTTPS_PROXY="http://your-approved-proxy:port"
export SSL_CERT_FILE="/path/to/approved-ca-bundle.pem"
python3 app.py doctor
```

Successful responses are cached for 24 hours in `.pharos_cache/`. Choose **Refresh API cache** or pass `--refresh` to retrieve again. The original response time is preserved when a cache entry is used.

The client retries only transient HTTP/network failures, with bounded waits. It rejects GraphQL partial-error responses. A schema mismatch stops a live build. The `--skip-schema-check` option exists for endpoints where introspection is disabled; use it only after reviewing the published schema. It does not suppress errors in the actual data queries.

The UI defaults to `127.0.0.1`. Protected shared hosting requires an access token and explicit HTTPS browser origins; see [the deployment guide](docs/PORTABILITY.md). This remains a single-workspace prototype, without individual reviewer authentication. Stop it with Ctrl+C. Public-data inspection needs no company/client data.

## Source basis and licensing

See [docs/SOURCE_NOTES.md](docs/SOURCE_NOTES.md) for official source links and the distinction between source-supported API behavior, implementation choices and unverified live integration.

The included software is offered under the MIT license. That does **not** relicense Pharos or its constituent source datasets. Review upstream terms before redistributing cached real data. Demo fixtures are authored synthetic examples, not copies of the Pharos database.

## Evaluate the workbench and planner

```bash
python3 app.py evaluation-init --baseline runs/crc_pharos_01 --enriched runs/crc_civic_01 --out runs/eval_suite_01
python3 app.py evaluation-run --suite runs/eval_suite_01 --out runs/eval_results_01
```

Open the generated `report.html` and complete its scope, answer and evidence review worksheets. Configure a model locally and use `--planner live` for a separate result against the same frozen sources. See [configuration, reviewer instructions and metric limits](docs/EVALUATION.md). The supplied 24 questions are draft development scenarios, not biomedical gold answers or a held-out test.

## Evaluate the source verifier

The source verifier judges one claim against one supplied abstract, independently of the question planner. It cites exact numbered sentences and has no graph-write authority. SciFact expert annotations supply its answer key; the project owner does not need to invent biomedical labels.

```bash
# Offline baselines; use a new output directory each time.
python3 app.py verification-run \
  --benchmark runs/scifact_verification_document_holdout_20261015 \
  --out runs/verifier_baselines_02
```

See [run commands for the live verifier and saved reports](docs/RUNNING_VERIFIER.md), the [verification contract](docs/VERIFIER_PROTOCOL.md) and [dataset preparation/licensing](docs/VERIFICATION_BENCHMARKS.md). Source-interpretation scores do not establish clinical truth or improved graph prediction.

The [initial document-disjoint development evaluation](docs/VERIFIER_RESULTS_20261015.md) matched 94/119 expert labels (79.0%), versus 62/119 (52.1%) for the fixed lexical baseline. Support recall was 72.0%, so assessments remain advisory.

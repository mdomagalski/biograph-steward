# Qualified IntAct evidence in the existing workbench

The IntAct development adapter uses the existing assay attachment, assertion
review, immutable run and complete source-export framework. It does not replace
Pharos or build a new graph store. Interpretation follows the pinned
[PSI-MITAB/IMEx source contract](INTACT_FIDELITY_PREPARATION.md), mandatory
expansion amendment and validated PSI-JAMI 3.9.4 reader.

## Implemented scope

Four qualified source rows, covering two human protein pairs in two publications,
are available from the four consumed development studies. All 18 physical rows
(four headers and 14 evidence records) remain preserved; eight RNA-containing
rows and two mouse PPIs are outside the declared primary task. No study was
replaced. Four reserved studies remain unopened.

Each qualified observation retains its exact source A/B identifiers and roles,
MINT attribution, IntAct and IMEx identifiers, publication, full host labels,
methods/type, negative/default provenance, expansion missingness and all 42 raw
columns. Full official field collections remain separate from the reader's
abbreviated interaction objects. A unique observation qualifier prevents records
for the same protein pair from being merged.

The dedicated question asks **what source-qualified evidence is recorded for
the selected protein or cohort**. It returns all selected source outcomes and
local review states, clearly labeled. It does not add these observations to the
ordinary unqualified interaction-path question. Co-IP/physical association does
not establish direct binding, disease mechanism or independent confirmation.

The app provides an IntAct inspector and saved traceable summary with eight
readable field groups, source references and a source-row graph view. Its answer
ZIP includes the full qualified records. The existing full-run ZIP and gold
packet preserve the attachment and entire source publication, including excluded
rows and source license. Saved-answer reopening and download recheck the source
run and graph/review basis. Changed source bytes cannot silently inherit an old
answer. Ordinary review states remain separate from source curation.

The restricted standards export still rejects assay attachments. This increment
does not claim PSI-MI/Biolink/KGX conformance for the local qualified graph or
measure biological accuracy.

## Available real source publication

`runs/intact_evidence_publication_verified_20261026/index.html` is a readable
offline view of the real development records. It includes four qualified graph
edges, source documents, roles, full Hep3B/KTC-1/CAL-62 host labels and artifact
downloads. It is explicitly a **source publication**, not a Pharos-attached run.
It can be inspected without network, Java, Brev or a model.

The producer copies only the explicit four development files, never the entire
opaque preparation directory. It checks the original source, reader, inspection
and ledger hashes before decoding. Publication reopening verifies its complete
file inventory, nested reader-control/runtime bindings and deterministic
projection. These unsigned hashes establish consistency with the receipts;
they do not authenticate a publisher or establish biological truth.

```sh
python3 scripts/publish_intact_development.py \
  --out runs/NEW_INTACT_PUBLICATION
```

Real data remain outside Git. A fresh clone requires the complete pinned source
preparation and validated development inspection, or an authorized reproducible
retrieval. Do not regenerate this reference from a current mutable release URL
and describe it as the same frozen bytes.

## Pharos-attached demonstration and full comparison

The real four-protein cohort was retrieved after network access was restored.
All four accessions resolved exactly. The attached run preserves the four Pharos
nodes and original STRINGDB POGZ–MAD2L2 edge, and adds four separately qualified
observations. All five assertions remain candidates; all five gold decisions
remain abstentions. These are four evidence records across two pairs, not four
new interactions or independent biological confirmations.

The full import → readable answer → answer JSONL → gold packet comparison
passed coverage and strict source fidelity on **4/4 eligible development rows**.
All eight field groups and all 42 source columns were preserved. The full
18-line source material, including the ten excluded evidence rows, remains
available in the source publication and exported packet. Real HTTP checks also
verified saved-run/answer reopening, source downloads and both ZIP downloads.
The [tracked result](evaluations/intact_evidence_flow_20261026_summary.json)
binds the reports, pre-comparison implementation/input hashes and HTTP checks.

The completed run used this sequence. Use new output directories for a repeat;
fresh retrieval produces a new snapshot rather than reproducing the saved bytes:

```sh
python3 app.py construct \
  --accessions Q9HCE5 Q8WYQ5 Q9UI95 Q7Z3K3 \
  --focus-uniprot Q9HCE5 --profile ppi --relations interactions \
  --out runs/intact_cohort_source_20261026

python3 app.py assay-attach \
  --run runs/intact_cohort_source_20261026 \
  --publication runs/intact_evidence_publication_verified_20261026 \
  --out runs/intact_workbench_20261026

python3 app.py assay-question \
  --run runs/intact_workbench_20261026 \
  --out runs/intact_answer_20261026

python3 app.py gold-export \
  --run runs/intact_workbench_20261026 \
  --out runs/intact_gold_packet_20261026

python3 scripts/evaluate_intact_evidence_fidelity.py \
  --inspection runs/intact_development_inspection_20261026 \
  --run runs/intact_workbench_20261026 \
  --answer runs/intact_answer_20261026 \
  --packet runs/intact_gold_packet_20261026 \
  --out runs/intact_workbench_fidelity_20261026_attempt_01
```

In the app, attach the saved publication under **Qualified assay evidence**.
Choose a protein or all cohort proteins and select **Read qualified evidence
summary**. Saved answers also reopen through the existing workspace picker.
The source list initially shows receipt metadata; attachment performs complete
verification.

The saved answer is `runs/intact_answer_20261026/report.html`. In the running
local app it can also reopen at
`http://127.0.0.1:8783/?run=intact_workbench_20261026&question=intact_answer_20261026`.
The code path is additionally tested on wholly invented source fixtures through
review, CLI/API, source-change guards and portable exports. Browser visual
verification could not run because the available browser-control backends failed
locally. Frontend state checks and HTTP integration checks passed; intended-user
usability and browser layout remain unverified.

## Evaluation boundary

The evaluator uses the original pinned raw source, official-reader JSONL and
frozen eligibility ledger, independently of the importer. Coverage and strict
fidelity keep all four eligible rows in the denominator. Checks include the
eight field groups, actual readable HTML tables, complete identifiers and source
links, critical negative/expansion/directness semantics, graph endpoints, record
identity and source preservation. JSON-only or hidden output cannot earn readable
coverage. Mutation tests cover missing records, wrong roles/hosts, lost references,
merged evidence and unsupported qualifications.

Two separately saved assessments passed on the same consumed development rows:

| Assessment | Saved report | Coverage / strict fidelity |
|---|---|---|
| Source publication only | `runs/intact_source_publication_fidelity_20261026_attempt_01/report.json` | 4/4 / 4/4 |
| Real Pharos-attached run, answer and gold packet | `runs/intact_workbench_fidelity_20261026_attempt_01/report.json` | 4/4 / 4/4 |

The earlier publication-only report retains its original scope and recorded
unrun stages. It is not a second independent validation. Publication mode can be
reproduced separately:

```sh
python3 scripts/evaluate_intact_evidence_fidelity.py \
  --inspection runs/intact_development_inspection_20261026 \
  --publication runs/intact_evidence_publication_verified_20261026 \
  --out runs/NEW_INTACT_PUBLICATION_FIDELITY
```

This is a consumed, small development panel, entirely explicit-positive co-IP
evidence. Real negative evidence, default-flag and supplied-expansion strata are empty;
synthetic controls do not fill them. No statistical generalization, scientific
accuracy, source novelty or gain over Pharos follows. Commit/freeze the adapter
and evaluator and complete the required provenance/overlap audit before any
reserved-study scoring. Brev can remain off.

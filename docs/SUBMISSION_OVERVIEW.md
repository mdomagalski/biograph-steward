# BioGraph Steward submission overview

BioGraph Steward uses a bounded NVIDIA Nemotron agent to guide a research
question through supported source tools. It returns a focused Pharos evidence
graph, a cited answer, inspected source records and grounded review proposals.
A researcher can trace a connection, inspect qualifications and reuse the
graph with its source context.

The common application workflow is **open or construct a source workspace →
ask a supported question → inspect the graph, cited answer and sources → save
an evidence review in a new run → export**. A workspace is its saved input and
review state. The two demonstrations illustrate different capabilities of this
same product. Reference comparisons and the historical prediction study verify
parts of the approach rather than form separate products or required user steps.

## Improvements over the captured Pharos baseline

| Improvement | Demonstrated result | What it gives a researcher |
|---|---|---|
| Additional qualified connections | **87 physical-association pairs** and **68 protein–location concepts** absent from the captured annotations | More candidate connections to investigate, with source and identity checks preserved. Overlapping connections remain identified separately. |
| More known locations recovered | **41/51 → 44/51** positive labels across 31 matched proteins, using the same ontology-qualified mapping | Additional reference-supported location context. The OpenCell source-exclusion check also improves **30/40 → 31/40** across 23 proteins. |
| Better additional biological-process prediction | Primary timepoint-ontology ordinary micro-Fmax: retained LocalPlus **0.055**, refreshed LocalPlus **0.059**, context model **0.073**. Fixed-starting-ontology sensitivity: **0.172, 0.183 and 0.210**. | A measured gain over retained LocalPlus from an established context-aware method. The extra gain over the refreshed control remains uncertain. This separate historical study uses a 20,412-protein graph. |
| Applied identifier qualification | **298 records with obsolete GO identifiers excluded**, with originals and every decision retained | A current-identifier view that scientists can inspect, export and revise. |

**See an actual addition:** in the recorded KRAS agent run, inspect citation
**E002, KRAS–CDC42BPB**. Its existing source passport reports **baseline pair
present: false** and **integration state: new workspace pair**, alongside native
STRING 12.5 score 203 and sequence-identity checks. This is one of the 87 pairs
absent from the captured graph. The [saved-artifact audit](evaluations/source_agent_20261116/demonstrated_additions.json)
also verifies that the complete KRAS result has three such pairs among 14;
the agent's fixed eight-result answer contains one.

These results measure different improvements, with their scopes preserved:
added source context, positive-label recovery, a separate function-prediction
benchmark and identifier qualification. Source additions compare exact captured
protein pairs or protein–GO-term concepts; the location assessment compares
mapped reference categories. These endpoints are not pooled into a graph-wide
accuracy score. The location references retain shared-source/prior-use limits;
the prediction study includes a stronger annotation-refreshed baseline. Full
controls and qualifications remain in the linked reports below.

**[Open the public browser demo](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/?run=native_evidence_workspace_20261115&question=native_physical_KRAS_question_v3_20261115&agent_job=source_agent_eval_dc7b597201da_S01&view=data)**
and follow **[How to use BioGraph Steward](../HOW_TO_USE.md)**.
Open it directly, with no sign-in. Saved replay needs only a browser; no AWS
account, local setup, Brev instance or model server is required. Exact accepted
deployment and release identities are recorded in the
[delivery status](DELIVERY_STATUS_20261115.json).

## What to try

One application offers **Added source context workspace** and **Qualified
Pharos workspace**. They share a **99-target colorectal-cancer cohort** and show
different operations with their own preserved inputs, rather than interchangeable
graph versions. The historical prediction study is a separate research
assessment, not another saved version of the app graph.

- **Follow the recorded agent:** inspect its question, validated tool plan,
  cited results, complete selected-source inspections and proposed review
  decisions. The primary KRAS agent run displays eight of 14 matching proteins
  under its fixed cap, while the manual answer displays all 14. Proposals
  retain candidate context or request review; they apply no graph decisions.
  Four sequential tabs separate the plan, evidence graph, inspections and proposals.
- **Added source context workspace:** read the KRAS answer, follow one of its 14
  candidate protein connections and inspect its native STRING source. Start
  with CDC42BPB to see an actual connection absent from the captured baseline.
  Of 330 physical pairs, 243 already share a pair with the baseline and 87 do
  not. Native GO supplies 3,309 rows representing 429 protein–location concepts
  across 94 targets; 361 concepts overlap the captured annotations and 68 are
  additional. These are pair/concept counts, not independent-study counts.
- **Qualified Pharos workspace:** choose **Review applied graph qualifications**
  to inspect the TP53 pathway example
  after explicit qualification decisions. Its 16,985 input evidence records
  become 16,687 retained records; 298 obsolete-GO-identifier exclusions have
  reasons, while uncertain records remain available. This is applied identifier
  qualification, not 298 proven biological errors.
- **Read the measured result and export:** inspect the featured comparison,
  then distinguish the focused answer from the retained graph, complete
  decision ledger and original baseline/source packet.

Matching all **99 cohort proteins** to the published human location reference
finds labels for **31 proteins**, supplying **51 positive protein-location pairs**
for comparing the same proteins across both source views. The captured Pharos view
recovers 41 of 51 and qualified native annotations recover 44 of 51. These are
fixed source views, not a newly scored union of the full graph. The benchmark
has no matching labels for the other 68 proteins, so this comparison cannot
assess them. They may still have location annotations in Pharos or native GO.
Some native GOA location records and the benchmark reuse Human Protein Atlas
(HPA) observations. Agreement can repeat the same underlying experiment rather
than provide independent experimental confirmation. A source-exclusion sensitivity check recovers
30 of 40 to 31 of 40 labels among 23 OpenCell-matched proteins. OpenCell is a
published HEK293T imaging reference previously used during development. This
is a saved research sensitivity check, not a fresh blind test or a step executed
for every app question. Known-label recovery does not measure whole-graph accuracy.

The challenge's same-learner link-prediction panels did not show a reliable
enriched-graph advantage. The separate historical function study compares
three parallel fixed arms for additional biological-process annotations in
proteins with prior functions. LocalPlus transfers known GO labels from direct
weighted neighbors, using the published positive-only implementation
([Law, Kale and Murali, 2021](https://doi.org/10.1093/bioinformatics/btaa885)).
The retained arm uses 2023 annotations; the refreshed arm uses eligible April
2026 annotations. The ProtBoost context arm combines graph and sequence
forecasts with GO context. Ordinary micro-Fmax pools protein–GO decisions and
reports the best precision–recall balance across the declared thresholds,
rather than percentage accuracy.

The primary frame scores **1,954 proteins with 3,254 positive protein–GO pairs**:
322 proteins have new positive labels after masks, while 1,632 have none and
can still contribute unmatched predictions. The sensitivity frame scores
**319 proteins with 3,243 positive pairs** under the starting ontology held fixed.
These differing populations prevent direct comparison of their absolute scores.
The context model gains **0.019 [0.002, 0.035]** over retained LocalPlus in the
primary view and **0.039 [0.008, 0.069]** in sensitivity, using paired 95%
intervals from 2,000 whole-protein resamples. Its extra benefit over refreshed
LocalPlus remains uncertain in both views. These [learned-model results](evaluations/CONTEXTUAL_COMBINATION_RESULTS_20261115.md)
retain their own endpoints and controls; the current agent check does not
claim their gains. The [forecast coverage note](evaluations/final_delivery_20261117/prediction_coverage_feasibility.md)
explains the complete 3,300-protein temporal-gainer frame: 3,297 in the historical
graph and three retained outside it. Further temporal testing requires later labels.

The [current-source agent comparison](evaluations/SOURCE_AGENT_RESULTS_20261116.md)
completed all eight fixed behavioral checks: four nonempty queries and one
valid accepted-only empty query matched the deterministic query, cited answer
and focused graph exactly. Three unsupported or unresolved requests stopped at
preflight without calling a model. These results demonstrate bounded execution
and source fidelity. Most requests already fixed one tool and protein; only
the TP53 location case offered two tool choices. The agent changed no source
graph or learner input and therefore supplies no new prediction-gain result.

## What is delivered

The working tools cover bounded construction, explicit identifier checks,
versioned assertions, source passports, guided multihop inspection, guarded
snapshot comparison and reproducible graph/decision exports. Stable identifiers,
Biolink references and bounded KGX/SSSOM profiles have recorded limits. AWS hosts
the public saved-demo workbench; Neptune supplies a separate private
mirror/inspection route.
The Nemotron agent orchestrates these existing tools and source inspections.
Its adapter-grounded proposals remain for human decision. A separate local
constructor builds Pharos graphs from explicit lists of 1–25 proteins per
request without a model. This is the interactive request limit, not a limit on
saved-graph size. A new agent question uses the source tools attached to its workspace
and requires a configured model endpoint. The separate literature auditor did
not outperform its specialist control. The
[research appendix](RESEARCH_APPENDIX_20261115.md) retains this and other method
comparisons. No model result automatically accepts or biologically prunes evidence.
The public demo replays saved work. Live construction, retrieval,
model calls and review edits are disabled there. Public downloads include the
recorded-agent JSON and a prepared complete KRAS app/source copy for personal
local reviews saved as new runs. Bulk graph/ledger inspection exports remain
part of the private submission handoff under source terms.

The judge-facing [final handoff](DELIVERY.md#final-submission-folder), prepared
locally at `output/final_submission/`, has only five files:
**START_HERE.txt**, **BioGraph_Steward_Project_Report.pdf**,
**BioGraph_Steward_Demonstration.mp4**, **BioGraph_Steward_Overview.pptx** and
**BioGraph_Steward_App_Data_and_Exports.zip**. The data ZIP combines the complete
native KRAS app/source copy with graph, decision-ledger and matched-baseline
inspection exports for both named workspaces, an index and source terms. The
full Qualified Pharos source-recovery packet remains a separate optional replay
asset. Historical media, research adjuncts and internal guides are outside the
front folder. MIT licensing covers the software, not a blanket public license
for these source datasets.

A separate [APP/PSEN worked example](evaluations/GENERALIZATION_EXAMPLE_20261117.md)
uses three proteins outside the original 99. The supplied
`BioGraph_Steward_APP_PSEN_Example.zip` includes a local runtime, complete
captured sources and the actual recorded APP location-agent job. Its
**OPEN_EXAMPLE.txt** provides the direct launch route. The same source-view
comparators execute on this cohort without changing their scientific rules.
HOU recovers 2/2 labels in its one matched protein in every arm, while OpenCell
has no admissible matches. This supports workflow reuse, not an added accuracy
gain or broad disease-transfer claim.

The **[final submission summary](FINAL_SUBMISSION.md)** maps these outcomes to
the organizer's 40% usability, 30% accuracy/pruning, 20% explainability and 10%
standards criteria. It links complete results and clearly separates the
preserved research appendix. The
[narrated screen tour](../output/walkthrough/BioGraph_Steward_Walkthrough.mp4)
shows actual browser views using verified saved real data, with
synthetic narration, captions and edited screenshot states; the
[seven-slide overview](../output/presentations/BioGraph_Steward_Overview.pptx)
provides a separate project overview. [Hosted deployment](evaluations/public_demo_20261117/hosted_acceptance.json)
and [artifact identities](DELIVERY_STATUS_20261115.json) are recorded separately
from the tour's local capture provenance. Preserved media remain in the
[dated media history](../output/history/20261115_guided_review/README.md).

The [project report PDF](../output/pdf/BioGraph_Steward_Final_Report.pdf)
([Word copy](../output/docx/BioGraph_Steward_Final_Report.docx)) connects
the scientific motivation, accessible agent workflow, methods, results and
opportunities for broader validation. The separate
[source-verifier comparison](evaluations/SOURCE_VERIFIER_COMPARISON_20261117.md)
reports adverse supported-claim exclusions under its partial Evidence-input
view. The verified input-completeness gap and any corrected-input diagnostic
remain separate. Current app assertions lack the complete native INDRA inputs,
so this benchmark verifier does not automatically prune Pharos.

The `BioGraph_Steward_Source_Verifier_Code.zip` adjunct supplies the research
code and **README_REPRODUCTION.txt**. A matching checkout, optional runtime and
separately licensed pinned author/reference inputs are required. It is distinct
from the portable app and the self-contained APP/PSEN example.

For code or separate operator execution, use [START_HERE](../START_HERE.md) and
[delivery instructions](DELIVERY.md). The code-only synthetic fixture is labeled
as invented data and is separate from the hosted real examples. MIT software
licensing does not relicense source datasets.
Project repository: [github.com/mdomagalski/biograph-steward](https://github.com/mdomagalski/biograph-steward).

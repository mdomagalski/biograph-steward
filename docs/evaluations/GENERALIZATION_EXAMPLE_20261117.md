# A real-source workflow reused on a new protein cohort

The unchanged constructor and current-source agent successfully handled **APP (P05067), PSEN1 (P49768) and PSEN2 (P49810)**. None is a primary target in the original 99-protein example. The cohort and APP location question were fixed before retrieval. Exact reviewed human identifiers were checked in [UniProt](https://www.uniprot.org/uniprotkb/P05067/entry), [PSEN1](https://www.uniprot.org/uniprotkb/P49768/entry) and [PSEN2](https://www.uniprot.org/uniprotkb/P49810/entry). No disease-membership assertion was inferred.

This provides an additional worked example of reusable graph construction and source inspection. It is separate from the original 99-target graph, its Pharos comparator and its qualified companion. It does not add a new accuracy benchmark.

## What ran

The existing explicit-cohort constructor retrieved the three proteins on November 17 UTC. The API reported **pharos319**. It preserved 12 source exchanges and published a graph with 460 entities and 549 evidence records. The declared GO, pathway, interaction and drug queries reported complete coverage. Publication discovery remained capped at 20 per protein and expression was not requested.

The existing source publishers then replayed the complete captured HUMAN-uniprot GAF and STRING 12.5 bulk inputs for the new cohort. No adapter, model prompt, identity rule or source profile was changed.

| Component | Executed result |
|---|---|
| Native GO location profile |144 candidate records across 57 protein–location concepts. 47 concepts already occur in the new Pharos capture and 10 are absent. |
| Native physical profile |All three proteins pass reciprocal-alias and full-sequence checks. Three source-listed pairs are present, and all three already occur as pairs in the new Pharos capture. |
| Combined example |466 entities, 696 evidence records and 609 assertions. Every original Pharos record and assertion remains unchanged. |
| Complete APP location answer |24 concepts supported by 75 source rows, preserved in full. The agent uses its predeclared 10-concept display cap. |

The GO profile admits positive, active cellular-component `located_in` annotations with the existing context restrictions. Evidence codes and references remain literal. The GAF was generated July 28, 2026, the ontology is dated July 26, 2026, and the separate physical source is STRING 12.5 with the captured UniProt 2026_04 canonical reference. Source versions are explicit. Additional rows or database names are not counted as independent studies.

## The agent execution

The actual Nemotron run completed in **three calls and 244 completion tokens**, within the fixed 3-call/3,600-output-token budget. It used the caller-constrained APP native-location tool. This checks execution on the new cohort, rather than unrestricted natural-language routing.

The complete query, cited answer and focused graph exactly match execution by the deterministic source engine with the same limits. The focused graph has 11 entities and 21 evidence records. The model selected three citation groups. Every source assertion under those citations was inspected, and three candidate-retention proposals were recorded without applying them. Sources, graph data and review states were unchanged.

The existing constructor performed retrieval. The agent organized a question, source query, evidence graph, source inspections and review proposals on that saved workspace. It did not perform arbitrary autonomous ingestion. Candidate retention does not mean biological acceptance.

## Reopen and reproduce

The separate organizer asset is **`BioGraph_Steward_APP_PSEN_Example.zip`** (61,170,245 bytes, SHA-256 `51053bb481806733a8311aac2ee8b8cb3a2c8445ea0b20396c110acf3fedfad4`). It is intentionally excluded from Git and has not been uploaded publicly. It contains the runtime, complete pinned source files and terms, saved queries and the actual recorded agent job. **`OPEN_EXAMPLE.txt`** inside the packet gives the direct APP-location launch link. Opening the saved example requires Python 3.10 or newer and makes no model call or fresh retrieval.

Construction replay, original and combined graph-packet verification, clean packaged Python execution with site packages disabled, and the existing `source-agent-verify` command passed. The archive was extracted and every member matched its staged inventory. These checks establish faithful replay and portability. The added location concepts measure source representation coverage, not independent biological accuracy or prediction gain.

See the [aggregate result and source/profile pins](final_delivery_20261117/generalization_example.json), [existing construction flow](../CONSTRUCTION.md), [current-source agent](../SOURCE_AGENT.md) and [native physical-source contract](../NATIVE_PHYSICAL_SOURCE.md). The original 99-target public demo remains unchanged. Provider terms apply separately from the software license.

## The same localization comparison on the new cohort

The cohort-specific operator gap was also closed. A reusable source-eligibility
entry takes explicit baseline/current workspaces and the complete declared
cohort. Before scoring the new example, it reproduced every original 99-target
source-eligibility semantic field and all 218 protein rows. The original
preparer, mappings, scoring code, frozen contracts and results remain unchanged.
All three new proteins meet the unchanged source-eligibility rules.

The cohort, source views, 107-entry map, separate 160-entry coarse control and
all original arms were fixed before reference outcomes were joined. The
historically named retained arm reads the Pharos component actually preserved
in the combined workspace. No new pruning or decision packet is implied.

HOU matches **one of the three proteins**. Its two released positive labels
are recovered by every arm at all three levels. The other two proteins remain
reference-unavailable.

| Fixed arm | Detailed labels | Middle labels | Broad labels | Extra detailed outputs, truth unknown |
|---|---:|---:|---:|---:|
| Captured Pharos, qualified map |2/2|2/2|2/2|4|
| Pharos component retained in current view |2/2|2/2|2/2|4|
| Native location, all admitted codes |2/2|2/2|2/2|5|
| Native location, experimental codes |2/2|2/2|2/2|5|
| Original coarse-map control |2/2|2/2|2/2|6|

This is a **neutral recovery result**, not a new gain. Extra outputs are unknown,
not false biological labels. OpenCell has **zero of three** admissible reciprocal
library identities. All five arms and both original grade profiles therefore
remain unevaluable, with null recovery rather than invented negative outcomes.

These previously used references share possible HPA, UniProt or study lineage.
The new result supports reuse of the comparison workflow while retaining its
coverage and context limits. It is not a fresh blind validation or a population
accuracy estimate. The [full aggregate](final_delivery_20261117/generalization_localization.json)
preserves all controls, levels, source exclusions and null outcomes. The
[reusable source-binding helper](../../tools/reference_accuracy/reproduction/prepare_cohort_source_eligibility.py)
and [reproduction instructions](../../tools/reference_accuracy/reproduction/README.md)
record how another fixed complete cohort can be bound without changing the
scientific rules. The four organizer archives remain unchanged.

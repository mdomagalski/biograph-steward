# Worked source inspection: B3GALNT2

Current Reactome records identify an explicit catalytic role for B3GALNT2,
with primary biochemical evidence and distinct experimental-context limits.
This is one worked interpretation of an already represented source. It does
not establish whole-graph accuracy, prediction gain or a new independent study.
The original graph, candidate reviews and frozen comparisons remain unchanged.

## Start from the saved question

Open the [local B3GALNT2 question](http://127.0.0.1:8794/?run=transfer_pathway_workspace_20261113&question=question_b3galnt2_reactome_20261113)
with its complete separately supplied 128-gene workspace. It is outside the
99-target offline demonstration bundle. The protein has no Wiki rows in this
capture but three Reactome annotations. The ordinary question shows eight of
17 matching proteins, using existing Pharos records and candidate paths.

1. Open **3. Answer** and the CDCA8 references. The shared annotations concern
   broad protein metabolism and post-translational modification. They do not
   supply a physical-interaction or specific reaction-role claim.
2. In **Evidence & sources**, search `B3GALNT2` and inspect the more specific
   **O-linked glycosylation** annotation. Its exact source ID is
   `R-HSA-5173105`. No other sampled protein shares this annotation in the
   captured graph; that is a cohort result, not absence elsewhere.
3. Use **Guide me through this source** and its current Reactome lookup. The
   original imported source link and current lookup remain separate. The
   [current reaction detail](https://reactome.org/content/detail/R-HSA-8931648)
   is a narrower record found through the publisher's documented identifier
   mapping and hierarchy APIs.
4. Check the catalyst identity, then read the cited studies for the tested
   construct and experimental host. A curator's human model and inference flag
   describe different facts from the species of the cells used in an assay.

## What the current publisher records establish

The service reported **Reactome release 98** during capture. Its explicit
reference-entity mapping joins UniProt `Q8NCR0` to physical entity
`R-HSA-8878916.1`, then CatalystActivity `8931635` and reaction
`R-HSA-8931648.3`. The reaction records GalNAc transfer onto a DAG1 glycosylation
substrate. It supplies human-event and `isInferred=false` metadata, with ER
compartment modeling. The publisher's ancestor paths connect it through DAG1
and O-linked glycosylation to the two broad annotations above.
[Current reaction](https://reactome.org/content/detail/R-HSA-8931648),
[protein entity](https://reactome.org/content/detail/R-HSA-8878916),
[documented Content Service](https://reactome.org/dev/content-service).

These are current curator statements with exact recorded identifiers. They do
not authenticate the historical contents imported into Pharos319. Canonical
browser links resolve current records; the captured raw objects retain the
reported versions and byte hashes.

## What the primary experiments support

| Evidence | Supported interpretation | Context that must remain visible |
|---|---|---|
| Recombinant transferase assay, Science 2013 Figure 2A | GalNAc transfer onto a defined glycopeptide supports the catalytic interpretation | The assay used a secreted enzyme construct with its transmembrane domain deleted. It does not directly measure intact-ER topology. |
| Earlier biochemical characterization, JBC 2004 | An expressed soluble catalytic domain and product NMR support beta1,3-linkage activity | The tested acceptor differs from the complete DAG1 context. The inspected evidence was the official abstract. |
| Localization study, AJHG 2013 Figure 4 | ER-marker colocalization supports localization of the expressed protein | Human B3GALNT2 carried a V5 detection tag and was expressed in mouse C2C12 cells. This is distinct from native-human-cell membrane or luminal-orientation evidence. |

Sources: [Science 2013, PMID 23929950](https://pubmed.ncbi.nlm.nih.gov/23929950/),
[JBC 2004, PMID 14724282](https://pubmed.ncbi.nlm.nih.gov/14724282/), and
[AJHG 2013, PMID 23453667](https://pmc.ncbi.nlm.nih.gov/articles/PMC3591840/).
The Science paper's SGK196/POMK kinase acts at a separate step; the B3GALNT2
assay concerns sugar transfer. Patient glycosylation observations and purified
catalytic assays also have different scopes. The review did not inspect every
supplement or establish independent replication of each modeled detail.

The qualified conclusion is that the current catalytic interpretation has
primary biochemical support under specified conditions. The inspected
localization experiment alone does not prove every membrane/lumen detail of
the curator model. Missing proof of a modeled detail is not proof that it is
false, and no graph assertion was automatically accepted or pruned.

## Reuse and reproducibility

The workflow uses Reactome, which was already represented in Pharos. Richer
publisher context and the publications it cites must not be counted as new
independent votes merely because they are reached through another interface.
Historical release correspondence, exact assay construct identity and
independent biological validation remain separate questions.

The [sanitized source-and-paper summary](reactome_role_trace_20261113_summary.json)
binds the current identities, primary-paper read scope and interpretation limits.
The complete local source packet is `runs/reactome_role_trace_20261113/`, seal
`98e1132369857c7b96d7daca95ebffc1562e1f0dc4fc45005fa3bb2d628f7b2a`.
It preserves the original failed JSON-Accept version request and the documented
plain-text correction. No custom BioPAX parser, model call, fit or new biological
comparison was added. The accompanying [coverage diagnostic](source_coverage_20261113_summary.json)
remains descriptive and post hoc.

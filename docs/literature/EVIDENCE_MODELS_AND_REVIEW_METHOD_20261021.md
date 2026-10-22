# Evidence models and review method

Reviewed October 21, 2026. This is one component of the [project literature review](../LITERATURE_REVIEW.md). It records primary methods and official specifications, not an implemented standards migration. Source IDs resolve in [cross-cutting sources](cross_cutting_sources_20261021.json).

## What this review is called

The project sits at the intersection of **biomedical semantic integration**, **biocuration**, **scientific claim verification**, **evidence synthesis**, and **knowledge graph maintenance**. These terms describe different tasks. Entity grounding and ontology alignment establish what a record refers to; evidence extraction preserves what was measured; verification assesses whether supplied material supports a claim; synthesis assesses a body of evidence under a defined question. None alone establishes clinical validity.

This is a structured literature and methods review with scoping-review elements. PRISMA-ScR (CROSS01) motivates explicit questions, search reporting, selection rules and evidence charting. We did not register a protocol, independently double-screen a complete database export, or perform a formal systematic review. Parallel AI research tracks are not independent human reviewers. The bibliography is a useful, revisable knowledge base, not proof of exhaustive coverage.

## Established models worth understanding before another schema

| ID and primary source | What it contributes | Boundary and project implication |
|---|---|---|
| CROSS02 — [FAIR principles, 2016](https://www.nature.com/articles/sdata201618) | Machine-actionable discovery, access, interoperability and reuse, including provenance and usage terms. | FAIR metadata does not establish factual correctness. Apply to source manifests, transformations and evaluation artifacts. |
| CROSS03 — [ECO update, 2022](https://doi.org/10.1093/nar/gkab1025); [official ontology](https://evidenceontology.org/) | Controlled vocabulary for evidence types and assertion methods. | Evidence type is not a calibrated probability of truth. Preserve actual source codes; do not infer an experimental code from an aggregator name. Ontology is CC0. |
| CROSS04 — [SEPIO, 2016](https://ceur-ws.org/Vol-1747/IT605_ICBO2016.pdf); [official project](https://github.com/monarch-initiative/SEPIO-ontology) | Separates propositions/assertions, evidence lines, underlying information, activities and contributors. | A useful conceptual crosswalk for our assertions and evidence passports. The repository warns that the information model and OWL implementation have drifted; it is not a version-free drop-in schema. README declares CC BY 3.0. |
| CROSS05 — [GA4GH VA-Spec 1.1.0](https://va-spec.ga4gh.org/en/1.1.0/); [statement model](https://va-spec.ga4gh.org/en/1.1.0/core-information-model/entities/information-entities/statement.html) | Qualified variant propositions, statements, evidence lines, study results, methods and provenance; therapeutic-response profiles are especially relevant. | It is primarily an exchange model. Trial-use/draft maturity and incompatible changes matter. Inspect schema and Python implementation versions together before reuse. Specification repository declares Apache-2.0; transitive artifacts need separate review. |
| CROSS06 — [Micropublications, 2014](https://link.springer.com/article/10.1186/2041-1480-5-28) | Represents arguments, supporting data/methods and challenges beyond a statement plus citation. | Conceptual precedent for context-qualified support and disagreement. The paper does not supply a validated automated cancer-claim judge. |
| CROSS07 — [Nanopublication anatomy, 2010](https://doi.org/10.3233/ISU-2010-0613); [official guidelines](https://nanopub.net/guidelines/working_draft/) | Separates assertion, assertion provenance, and metadata about the published assertion package. | Useful export design, not a reason to replace our storage now. A signed or hash-addressed assertion can still be wrong. Working-draft guidance is not a project certification. |

These models are complementary. Biolink describes biomedical entities and relations; mapping standards describe links between identifiers; PROV describes derivation; ECO describes evidence type; SEPIO/VA-Spec describe how evidence supports an assessment. A compatibility map is a smaller, more defensible first step than adopting every ontology.

## Public annotation reference we had not used

**CROSS08 — [ECO-CollecTF, 2021](https://doi.org/10.3389/frma.2021.674205).** This corpus contains 2,565 evidence annotations from 84 articles, including negation and assertion-related evidence spans. It could inform an evidence-type annotation task. Its restricted one/two-sentence, transcription-regulation setting does not validate full-document cancer treatment synthesis. The paper describes BRAT/BioC releases and document-specific licensing; corpus files and split membership were not downloaded or audited here. Article licensing must not be substituted for the rights to every constituent document.

## A close recent system: useful precedent, limited transfer

**CROSS09 — [EvidenceNet, March 2026 preprint](https://arxiv.org/html/2603.28325v1).** It builds disease-specific evidence graphs, including CRC, with study context and source text. Its component audit is small: 20 extraction cases, 20 selected high-confidence links, 12 fusion cases and 20 semantic relations. Internal graph-derived questions test answer recovery; they do not establish independent scientific accuracy. Its answering prompts allow general-knowledge fallback, which differs from our source-bound verification contract.

The [official code](https://github.com/ZUST-BIT/EvidenceNet-code) is MIT and exposes a pipeline, but excludes raw papers, large normalization resources and generated graphs. The linked Figshare deposit could not be inspected through the research tool. Dataset licensing, paper overlap, full reproducibility and transfer to our task remain unverified. Treat it as a design/reproduction candidate, not as a verified replacement or a gold standard. The preprint has a separate CC BY-NC-SA 4.0 notice.

## Version traps found during this review

- SEPIO's README itself documents model/ontology drift. Referencing the name alone does not specify a compatible implementation.
- [VA-Spec 1.1 release notes](https://va-spec.ga4gh.org/en/stable/releases/1.1.html) describe incompatible changes to trial-use classes. A September ballot page and the 1.1.0 page expose different evidence structures; examples must come from the pinned version.
- The [VA-Spec implementation list](https://va-spec.ga4gh.org/en/1.1.0/appendices/implementations.html) describes adopters using prerelease models. A documentation version is not evidence that every dependent tool already supports it.
- A public repository establishes artifact availability, not successful reproduction. We installed none of these tools in this review.

## Search record and limitations

Search date: October 21, 2026. Used web-index queries, primary publisher pages, arXiv, official ontology/standards sites and linked GitHub repositories. Foundational older work was retained; recent results were checked for artifact and protocol changes. Representative exact queries executed:

1. `biomedical knowledge graph integration evidence provenance limitations scientific claim verification review 2025 2026`
2. `PRISMA ScR scoping reviews checklist explanation Tricco 2018`
3. `SEPIO scientific evidence provenance information ontology evidence assertions ECO nanopublications biomedical`
4. `site.prisma-statement.org scoping reviews PRISMA ScR checklist`
5. `site.github.com monach initiative sepio ontology scientific evidence provenance` (original query contained this spelling)
6. `site.academic.oup.com Evidence Conclusion Ontology ECO 2022 2024`
7. `site.nature.com FAIR Guiding Principles scientific data management stewardship 2016`
8. `"Evidence and Conclusion Ontology" "2022"`
9. `"nanopublications" "anatomy" provenance assertion publication`
10. `"EvidenceNet" "2603.28325" github`
11. `GA4GH Variant Annotation specification evidence strength statement proposition 2025 2026 va spec`
12. `Micropublications semantic model claims evidence arguments biomedical 2014 Clark Ciccarese Goble`
13. `"ECO-CollecTF" "Corpus" "2021"`
14. `site.github.com ga4gh va-spec "1.1.0" "Python"`

Included sources have a direct relationship to our evidence representation or review method. Generic blogs, search snippets unsupported by a primary page, and the unrelated perioperative PHAROS intervention were not used as evidence about the NIH portal. Publisher/official text was used where PMC presented an access challenge. We did not export all database hits, establish a recall estimate, inspect patient-level data or contact authors. The topic reviews record their own searches and access limits. No retained evaluation cases, labels or production outputs were changed.

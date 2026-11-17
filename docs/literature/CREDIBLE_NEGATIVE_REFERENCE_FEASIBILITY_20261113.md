# Credible-negative reference feasibility

The two reviewed resources provide useful evaluation methods, but this bounded
inspection admits **no new scientific negative labels** for the frozen
99-target graph. No graph or model was changed.

The [2026 leakage study](https://doi.org/10.1093/bioinformatics/btag608) separates
split redundancy, structural shortcuts and deployment mismatch. Its
[MIT-licensed author code](https://github.com/galadrielbriere/data_leakage_kge_benchmark/tree/b08dabac07253dfe6bdc10f641a23f3c2c26f57e)
can inform future split diagnostics; its Orphanet inference data are not released
in the repository. Training negatives are sampled corruptions, not experimentally
established nonrelationships. The authors found no evidence that degree alone
explained predictions. Degree-preserving controls therefore test a limited
alternative explanation; their use does not diagnose a degree shortcut in our
graph, and cannot establish study independence or biological accuracy.

The [negative-statements benchmark](https://arxiv.org/abs/2307.11719) distinguishes
GO/HPO negation used as background from target PPI and gene–disease labels. Its
target negatives are random pairs; patients in the disease task are synthetic.
We inspected the [released PPI artifact, v2](https://zenodo.org/records/11282485)
(CC BY 4.0), rather than assuming its target zeros were measured negatives.

Our native-artifact inspection found:

- The 2,048 PPI rows contain 1,024 positives and 1,024 random negatives.
  Twenty-two positives and four random negatives have both accession tokens in
  our cohort. Seventeen unordered pairs have opposite labels across orientations.
  One is our EGFR/PIK3CA pair: positive in one direction and negative in the reverse.
- The OWL contains 8,476 negative GO assertions. Thirteen accession/GO token pairs
  also occur in our graph. Individual OWL annotations omit evidence codes,
  references, taxon, dates and product forms; protein identifiers are relative
  IRIs. This is diagnostic overlap, not full claim identity.
- A bounded lookup of the [original author supplement](https://lab.dessimoz.org/20_not)
  resolves all 13 candidates: twelve are explicitly inferred negatives
  (`type=-1`) from the author's 2018 PAINT/PANTHER construction. The remaining
  MSH6 pair is positive (`type=+1`) in that inferred table and has a separate
  native experimental GO NOT annotation.
- Ten of the thirteen already have positive annotations in the paper-cited
  [January 2021 human GOA release](https://release.geneontology.org/2021-01-01/annotations/goa_human.gaf.gz).
  This exposes source/release/inference disagreement; it does not establish
  which contextual scientific statement is wrong.
- The current MSH6–GO:0043570 NOT row is IMP/BHF-UCL, citing
  [PMID:16388310](https://pubmed.ncbi.nlm.nih.gov/16388310/). Our original Pharos
  projection is IBA/GO_Central. The experimental NOT is eligible for inspection
  but does not match that original evidence tuple. The earlier zero-match
  experimental-NOT gate is therefore consistent with these findings.

[GO's guidance](https://geneontology.org/docs/go-annotations/#the-not-modifier)
allows positive and NOT statements to coexist because of context, product forms
or unresolved evidence. Our stored predicate asserts annotation existence;
missing historical polarity must not become an unqualified positive-function
claim. No Pharos NOT-polarity loss has been proved here. Existing native GAF
inspection and conservative UNKNOWN handling remain appropriate.

For delivery, retain the source-specific context view and pair-orientation
checks. A future explicit function/negation evaluation would require matched
native annotation provenance and qualified claims; these 13 inspected candidates
are now development material. Do not treat random zeros, missing annotations or
inferred negations as fresh experimental truth, or install a replacement learner
merely to reuse a leakage diagnostic.

Detailed byte pins, all candidate rows, failed/provisional captures and the
bounded author-archive ranges are retained locally under
`runs/credible_negative_feasibility_20261113/`. The full 157 MB supplement was
not downloaded; only its directory, three small code files and the selected
28 MB compressed negative-table member were retrieved. No author code was run.

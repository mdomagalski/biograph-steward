# Biological-improvement method reuse: SNOOPPI

October 26, 2026 (America/New_York). This is one bounded methodology and artifact
review, **not dataset adoption, a frozen biological comparison or a new score**.

**Decision:** SNOOPPI is a relevant published method for sequence-aware interaction
qualification. Do not install its pipeline, import its labels, substitute it for
Pharos, or call it an independent validation reference now. It provides a concrete
next reuse candidate rather than a reason to resume unconstrained enrichment or
model experiments. The current reserved IntAct fidelity assessment stays separate.

## Existing method and its actual endpoint

The [primary paper](https://academic.oup.com/bioinformatics/article/42/10/btag736/8866686)
defines interactions between exact sequence/proteoform pairs, requires direct
physical contact, and derives its collection from IntAct release 251. Some
binding-region negatives are designed variants, not the exact experimentally
tested sequences. Its published out-of-the-box classifier comparison reports
poor positive/negative separation. These are published aggregate findings, not
results of our implementation.

The [official dataset card and schema](https://huggingface.co/datasets/ChatterjeeLab/SNOOPPI/blob/45e4f02204a135eeb26158e189bb253d0e677679/README.md)
retain three outcome partitions: positive, negative and unresolved. The unresolved
partition must not become negative interaction evidence. Sequence-pair identity,
protein identifiers, experimental context, feature relationships and provenance
are separate fields. Published cardinalities are 33,625 positive, 5,378 negative
and 835,083 unresolved records; these are metadata, not independently checked
row counts. The three partitions are outcome classes, **not train/dev/test splits**.

The method therefore fits a question about direct interaction of specified
molecular forms. It does not label every gene-level functional association,
co-complex relation or Pharos PPI false when direct-binding evidence is absent.
That distinction matches the existing [IMEx source model](https://www.nature.com/articles/s41467-020-19942-z)
and our [mandatory expansion amendment](../evaluations/intact_fidelity_20261026_semantic_amendment.json).

## What the author artifacts establish

| Artifact inspected | Verified finding | Limit |
| --- | --- | --- |
| [Official repository](https://github.com/sophievincoff/snooppi/tree/5b27ef506caa89d6c43f0e6579382dc901436a6f) | Source, environment files, download/process configuration, reconstruction instructions and clustering code exist at the pinned GitHub ref | No package or runtime was installed or exercised |
| [Reconstruction instructions](https://github.com/sophievincoff/snooppi/blob/5b27ef506caa89d6c43f0e6579382dc901436a6f/interactome/REPRODUCE.md) | Full cleaning/classification includes a notebook; the authors explicitly require saved UniProt mapping dumps for reproduction | The notebook was not fetched because notebooks can embed real output rows; its complete classification implementation is not audited here |
| [Download configuration](https://github.com/sophievincoff/snooppi/blob/5b27ef506caa89d6c43f0e6579382dc901436a6f/configs/download/intact.yaml) | It names an output `all_release251.zip` but retrieves the mutable `intact/current/all.zip` URL | The filename does not freeze historical release bytes; do not execute this download as reproduction of release 251 |
| [Processor](https://github.com/sophievincoff/snooppi/blob/5b27ef506caa89d6c43f0e6579382dc901436a6f/interactome/data/process/intact.py) and [process configuration](https://github.com/sophievincoff/snooppi/blob/5b27ef506caa89d6c43f0e6579382dc901436a6f/configs/process/intact.yaml) | The released processor reads PSI-MI 3.0 files, extracts sequences/features and uses controlled-vocabulary files | Our tested XML helper currently admits only 2.5.4 and does not project full sequences/features; this is not a drop-in replacement |
| [Environment](https://github.com/sophievincoff/snooppi/blob/5b27ef506caa89d6c43f0e6579382dc901436a6f/environment.yaml) | Several dependencies are pinned, but others and a Git dependency are unpinned | It is an environment recipe rather than a complete dependency lock |
| [Zenodo version record](https://zenodo.org/records/22116351) | Concept DOI 22116350 resolves to version 22116351; metadata lists a 3,568,525,998-byte ZIP and CC BY 4.0 | No archive bytes or contents were inspected; identity with the GitHub/Hugging Face artifacts is not established |
| GitHub license metadata and root file inventory | GitHub reports no recognized license; no root license file is listed, and setup metadata declares none | The paper's “open-source” description is not an MIT/Apache permission grant for copying that repository into our MIT code |
| Hugging Face card | The inspected revision has no declared license field | Do not silently apply the separate archive's license to every hosted artifact; resolve scope before redistribution |

This review found a real existing implementation. It did not reproduce it or
establish that all its interpretation choices should be adopted. In particular,
the paper describes assigning an explicit non-expanded label where a Processed
record has no expansion marker. Before adapting that rule, verify what additional
raw-record grouping establishes; our frozen policy does not infer binary origin
from an absent annotation alone. No custom sequence or biological parser was
created to bypass this question.

## Fit with the current product and evaluation

Our graph currently preserves source accessions, roles and qualified observations.
It does not identify each node by the exact experimentally tested sequence and
modification state. Mapping an altered sequence to its parent UniProt accession
would collapse the distinction this method is designed to retain. Sequence- and
feature-resolved evidence would need its own explicit identity projection using
the existing source model before a comparison could be valid.

SNOOPPI's labels are derived from IntAct. Scoring our IntAct-derived interpretation
against those same labels would measure agreement with that derivation; it would
not independently verify biological truth. No exact evidence/study/sequence
overlap audit has been performed. Different releases and publication dates do
not establish independence from consumed material or deployed Pharos providers.
The [existing closed lineage decision](REFERENCE_COMPARATOR_DECISION_20261025.md)
still applies.

The public schema also exposes outcome-derived annotations, including wild-type
labels, label transitions and label-conditioned node degrees. A prediction
experiment must keep these and any derivative reference information outside its
inputs. Exact sequences and close mutant/wild-type families create additional
split dependencies; a random row split would not establish generalization. Use
the [existing leakage review](PUBLIC_REFERENCE_OPTIONS_20261026.md) and the
[published biomedical KG leakage procedure](https://academic.oup.com/bioinformatics/article/42/8/btag608/8767164)
when fixing an actual task, rather than assuming an external file is independent.

## Finite next decision and when biology can run

Prepare the biological-improvement contract in parallel with final fidelity work;
there is no need to finish every architecture feature first. For this candidate,
the next finite step is a **source-code-only audit of the author classification
rules and license scope**, without importing notebook outputs or data labels.
Check actual-tested versus generated negatives, sequence identity, conflicting
outcomes, and missing expansion semantics. Then either adopt the verified portion
under its terms or close the candidate as unsuitable. Do not implement a new
classification protocol merely because the notebook has not yet been inspected.

If adopted, first reproduce the relevant rule on synthetic or already-consumed
development material. Before new evaluation outcomes are accessed, fix a fresh
study/sequence-grouped reference, exposure exclusions, claim-compatible endpoint
and inputs. Compare Pharos, addition of the same information, and Steward's
qualification under matched candidates, learner and budget. Separate measured
source negatives from generated variants and unresolved records. Keep method
reproduction, source interpretation and biological prediction claims distinct.

**Go:** methodology reuse investigation and preparation of that concrete
comparison. **Not ready:** a SNOOPPI score, an independent-reference claim, a new
predictor run or biological pruning. Brev, AWS and a model are unnecessary for
the next code/terms review; paid inference would require a separate stated run.

## Internal development versus independent confirmation

Unknown Pharos import lineage does not prohibit every paired experiment. Once a
literature-supported, task-compatible intervention is justified, a fixed retrospective
comparison on consumed INMC/Lambourne outcomes can measure its internal paired
effect. Match candidates, endpoint, learner, seeds and budget; retain a
same-information simple-addition arm where applicable and every prior result.
Scored labels and derivatives stay outside predictor inputs. Label any outcome
used for fitting as training performance. Do not present consumed data as fresh
validation or tune repeatedly until a favorable result appears.

That narrower result is exploratory/development evidence, with unknown
reference-derived input disclosed. It does not certify external generalization,
source novelty, or new biological knowledge beyond Pharos. Those stronger claims
need suitably independent/fresh evidence. The current no-go concerns lack of a
verified compatible intervention and, for SNOOPPI, missing sequence/proteoform
inputs; it is not a blanket ban on development experiments while lineage is
unknown. This distinction follows the internal-versus-external evaluations in
[Brière et al.](https://academic.oup.com/bioinformatics/article/42/8/btag608/8767164).

## Access scope and receipts

The [machine-readable decision](../evaluations/biological_improvement_reuse_20261026_summary.json)
binds local HTTP receipts. Access was limited to primary papers, public aggregate
findings, repository metadata/file names, explicit source/configuration/docs,
dataset card/schema metadata and archive metadata. No label table, pair list,
sequence table, notebook, archive, checkpoint or experimental source body was
downloaded. No reserved IntAct interaction source was opened, hashed or queried.
No code was installed or executed and no score was generated.

Raw method-review receipts are retained in the ignored directory
`runs/snooppi_method_review_20261026/`. They bind the checked bytes and observed
hosting metadata, not a certification of artifact equivalence or scientific
accuracy. This note changes neither prior results nor the reserved selection.

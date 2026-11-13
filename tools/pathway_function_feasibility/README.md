# PROGENy / decoupleR feasibility decision

**No-go for using PROGENy to establish biological improvement of the current
99-target WikiPathways graph.** This is a source/task qualification result;
no activity inference, fitting, new experimental outcomes or graph changes ran.

PROGENy is an established method for interpreting downstream transcriptomic
responses. Its original paper was accepted in 2017 and published in January
2018. Importantly, responsive genes are a different biological unit from the
signaling-pathway component genes represented by our graph. Predicted activity
is also different from an experimentally measured activity label.
[Original primary paper](https://doi.org/10.1038/s41467-017-02391-6).

The existing quantitative input is PDC000116: **6,422 gene-level total-proteome
rows × 96 tumor/normal samples**, expressed as protein log2 fold changes. It is
not RNA expression or phosphosite measurements. A general matrix interface in
decoupleR does not validate swapping those measurement types. The published
decoupleR benchmark uses transcription-factor perturbations with transcript
readouts and kinase perturbations with phosphosite readouts; these are not
WikiPathways membership labels.
[Primary decoupleR paper](https://doi.org/10.1093/bioadv/vbac016),
[author benchmark](https://github.com/saezlab/decoupleRBench).

The exact input coverage is poor for this particular task. All 99 proteins map
through the existing frozen registry to **98 genes**. Using the observed
official Bioconductor **PROGENy 1.34.0** human model, only **7 cohort genes**
occur in any top-100 footprint and **35** in any top-500 footprint:

| Pathway | Cohort genes in top 100 | Cohort genes in top 500 |
| --- | ---: | ---: |
| Androgen | 2 | 5 |
| EGFR | 0 | 1 |
| Estrogen | 2 | 4 |
| Hypoxia | 0 | 3 |
| JAK-STAT | 0 | 2 |
| MAPK | 0 | 1 |
| NFkB | 0 | 1 |
| p53 | 2 | 10 |
| PI3K | 0 | 1 |
| TGFb | 0 | 2 |
| TNFa | 0 | 2 |
| Trail | 1 | 2 |
| VEGF | 0 | 2 |
| WNT | 1 | 5 |

None of the top-100 pathways and only three top-500 pathways reach the R ULM
default computational minimum of five matching genes. That minimum is **not**
a scientific adequacy threshold. The author's low-coverage benchmark studied
randomly missing transcriptomic genes, down to 500 covered genes, and larger
footprints can help that setting. It does not validate our selected 98-gene
protein panel. We have not invented a universal requirement for every gene in
the transcriptome or a new biological gene-count cutoff.
[Coverage primary paper](https://doi.org/10.1186/s13059-020-1949-z).

There is a second, decisive comparison problem: our Wiki version normalization
and source qualification do not change fixed pretrained PROGENy footprints.
Running that fixed method twice on the same matrix cannot, by itself, measure
the graph intervention. Treating footprint absence as a false component edge
would confuse two different relationships.

The source check also avoids two version traps. The author's older Git master
declares PROGENy 1.17.3; its human model and algorithm bytes match the observed
1.34.0 official release. Current Python `scverse/decoupler` source declares
2.3.1, Python ≥3.12, and uses `dc.op.progeny` with a significance filter; older
`get_progeny(top=500)` examples do not describe that current API. Neither package
was installed to run activities. The native R weights were read with the
existing `rdata` reader in an isolated task directory.

Training independence also remains unqualified. The original author's index
contains 232 non-excluded YAML paths representing 218 series accessions before
final QC/condition filtering, not a complete training-membership certificate
for every current 14-pathway coefficient. Original held-out experiments,
training experiments and TCGA/GDSC evaluations have distinct roles. The
Pharos source stores no explicit GEO/ArrayExpress accessions for a complete
cross-check; that missing lineage does not establish independence. Our CPTAC
matrix and several other references are already consumed development material.

PROGENy is a credible future **transcriptomics interpretation layer** if we
obtain compatible broad expression measurements or an independently validated
targeted transcript panel, qualified experimental perturbation labels, and a
study/condition overlap contract. A future evaluation must identify how the
graph treatment changes its tested input and freeze its endpoint before
outcomes. The author's benchmark should then be reused. Adding this method now
would not supply independent whole-graph accuracy or justify pruning.

The captured licenses remain separate: PROGENy package Apache-2.0; original
`footprints` analysis GPL-3.0; Python decoupler BSD-3-Clause; R decoupleR GPL-3.0;
decoupleRBench MIT. No author analysis code or model was added to core.

Local evidence is under `runs/pathway_function_feasibility_20261113/`:
`feasibility_report.json` binds primary paper passages, source/algorithm/license
captures and the no-go decision; `footprint_coverage.json` preserves every exact
mapping and pathway denominator. The isolated `reproduce_coverage.py` performs
only the mechanical native-data coverage check, mirroring the released
`dplyr::top_n` tie rule. It is not a replacement activity method or new benchmark.

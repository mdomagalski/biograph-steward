# Horlbeck genetic-interaction reference: coverage no-go

The author-released processed maps cover too little of the frozen cohort for
a useful fresh confirmation of the RA result. No new biological comparison,
model fit or graph change was performed.

| Native header | Processed gene labels | Strict cohort symbol matches | Nominal cohort pairs before pairwise QC | Genes overlapping the previous RA92 frame |
| --- | ---: | ---: | ---: | ---: |
| K562 | 448 | 5 | 10 | 4 |
| Jurkat | 388 | 5 | 10 | 4 |

Both headers match AURKA, CDK12, POLE, TAF1 and TRRAP by literal, unique current
Approved HGNC symbols. TAF1 was absent from the earlier RA experimental frame.
Thus only six nominal pairs overlap that frame. Five genes permit at most four
partners per query and cannot support its full N=1…10 readout. Header coverage
does not establish pairwise measurement/QC availability; row identities and
native numerical GI cells were not read. Historical native Entrez/Ensembl
crossrefs were not independently confirmed, and no aliases, forms or compound
labels were collapsed to increase coverage.

[Horlbeck et al.](https://doi.org/10.1016/j.cell.2018.06.010) reports dual
CRISPRi growth perturbations in K562 and Jurkat. Published GI scores compare
measured paired effects with a quadratic expected phenotype, standardized using
non-targeting controls; guide-pair scores are averaged at gene level. Signed
interactions and profile similarity have different meanings. Neither is
physical-binding truth, and a near-zero or absent score is not a general
biological negative. The experiments are distinct from Broad single-gene KO
fitness profiling, but the cell backgrounds and indirect curation may overlap.

The paper-cited [Mendeley v1 deposit](https://doi.org/10.17632/rdzk59n6j4.1)
is CC BY4.0. Its 9.3MB native TreeView archive matches the publisher SHA256.
Only member metadata and the two first matrix-header lines were decoded;
no GI cells were scored. The 94MB and 145MB intermediate archives were not
downloaded. [Official code](https://github.com/mhorlbeck/GImap_tools) is MIT;
its analysis file is unchanged since the original May2018 paper commit. The
legacy Python2 pipeline was not reimplemented or rerun.

No literal Horlbeck PMID/DOI/GSE/author hit was found in the 253 captured exact
Wiki native models. This does not prove independence from indirect references,
unavailable models or STRING/BioGRID aggregation. An initial general search
incidentally exposed four BioGRID example-score snippets; none of their eight
symbols occurs in the frozen cohort, and they were not used for selection.

Receipt: `runs/horlbeck_gi_feasibility_20261113/feasibility_report.json`, seal
`65674f4c…`. Raw source bytes, publisher license, official code, exact headers,
strict mapping rows and the incidental-exposure disclosure are preserved.
This dataset is stopped at the outcome-agnostic coverage gate.

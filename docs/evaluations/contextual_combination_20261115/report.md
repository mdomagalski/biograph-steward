# Context-aware combination: later curator-annotation recovery

**The preselected context stacker establishes a bounded gain over retained LocalPlus in both reference views.** An advantage beyond LocalPlus using complete current-T0 curated annotations is not established by the fixed gate.

This is a bounded human GO function-recovery measurement. It is not a percentage of biologically correct Pharos edges, a clinical assessment, or evidence that unmatched predictions are false.

## Fixed comparison

All **3,300** native target identities were forecast before the new reference was opened. The primary endpoint is **PK biological-process ordinary micro-Fmax**. PK excludes functions already known at T0. All other settings/aspects remain secondary. Native epoch-specific and fixed-T0 ontology views are both required by the gain gate.

| Forecast | Native primary Fmax | Fixed-T0 primary Fmax |
|---|---:|---:|
| Context GCN — evidence/relation features | 0.073431 | 0.210093 |
| Context stacker — eight-layer GCN | 0.059725 | 0.182759 |
| Context stacker — zero-layer MLP | 0.061746 | 0.194713 |
| DeepGO-SE — sequence model | 0.036422 | 0.131391 |
| DeepGO-SE — historical model axis | 0.036422 | 0.131391 |
| DeepGO-SE — same soft processing | 0.037041 | 0.132090 |
| Development-selected global weight | 0.056100 | 0.178030 |
| Fixed 50/50 combination | 0.048155 | 0.164958 |
| Training-label frequency only | 0.032584 | 0.107277 |
| LocalPlus — retained annotations | 0.054732 | 0.171550 |
| LocalPlus — complete current-T0 curated seeds | 0.058838 | 0.182771 |
| LocalPlus — historical model axis | 0.054732 | 0.171550 |
| LocalPlus — same soft processing | 0.054732 | 0.171550 |
| LocalPlus — matched training-label update | 0.055296 | 0.175187 |
| Updated LocalPlus — same soft processing | 0.055296 | 0.175187 |
| Current nonexperimental annotations | 0.025476 | 0.146169 |
| Development-selected context stacker | 0.073431 | 0.210093 |

| Primary view | Full native/bootstrap protein frame | Proteins with residual positive labels |
|---|---:|---:|
| native | 1954 | 322 |
| fixed_T0 | 319 | 319 |

The unchanged native evaluator can retain protein rows whose positive labels are all removed by its known-term and term-of-interest masks. Their predictions can still contribute false positives. Bootstrap draws retain that full native frame. Absolute Fmax values across the two views therefore describe different reference populations; compare methods within each view.

Fmax is threshold-optimized by the fixed evaluator grid; it is not a deployed confidence threshold. Intervals below use 2,000 paired whole-protein resamples with shared draws and seed 20261113. They are conditional, unadjusted descriptive intervals. The point difference and lower interval must both be positive in both views to pass a declared gate.

## Declared gain gates

These statuses copy the completed assessment. The primary question is the selected stacker versus retained LocalPlus. The stricter controls describe what explains that gain; they do not replace a failed primary gate.

| Selected-stacker comparison, required in both views | Stored gate |
|---|---|
| Selected stacker beyond retained LocalPlus | Passed |
| Selected stacker beyond raw and soft retained LocalPlus | Passed |
| Selected stacker beyond current nonexperimental annotations | Passed |
| Selected stacker beyond matched training-label updates | Passed |
| Selected stacker beyond complete current-T0 curated LocalPlus | Not established |
| Selected stacker beyond every declared noncontext control | Not established |

### Separate source-update results

These gates compare the same native LocalPlus algorithm with different legal source annotations. A passed source-update gate supports the value of newer annotations; it does not establish a learned-stacker gain.

| Fixed source update, required in both views | Stored gate |
|---|---|
| Matched training-label update beyond retained LocalPlus, raw and soft | Not established |
| Complete current-T0 annotation update beyond retained LocalPlus | Passed |

## What changed in the inputs

The native ProtBoost stacker combines saved graph and sequence forecasts with existing nonexperimental GOA context. One additional BPO GCN uses source-derived evidence-code/relation channels from the author’s CAFA6 update. Its 40 namespaced channels are views of the same GOA source, not 40 independent resources or studies. Every candidate, checkpoint recipe and feature contract was fixed before new-reference access.

The retained LocalPlus seeds are historical. The matched update adds exactly the allowed full fitting repertoire for 4,040 training proteins, using the same graph and native scorer. A separate practical current-T0 arm replaces the historical seeds with all eligible reviewed-human curated April 10 annotations. That arm is evaluated only on this later window; using it on the older validation would look ahead. The frequency-only arm tests whether prevalence explains a learned gain.

## Development choices

| Aspect | Selected arm | Consumed-validation scores |
|---|---|---|
| biological_process | coded_context_gcn | context_mlp: 0.186163; context_gcn: 0.203548; coded_context_gcn: 0.228355 |
| cellular_component | context_gcn | context_mlp: 0.351675; context_gcn: 0.364653 |
| molecular_function | context_mlp | context_mlp: 0.261104; context_gcn: 0.254305 |

## native primary paired contrasts

| Candidate | Comparator | Fmax difference | Paired 95% interval |
|---|---|---:|---:|
| Development-selected context stacker | Context GCN — evidence/relation features | +0.000000 | [+0.000000, +0.000000] |
| Development-selected context stacker | Context stacker — eight-layer GCN | +0.013706 | [+0.002908, +0.025976] |
| Development-selected context stacker | Context stacker — zero-layer MLP | +0.011685 | [+0.002145, +0.023928] |
| Development-selected context stacker | DeepGO-SE — sequence model | +0.037009 | [+0.024107, +0.055267] |
| Development-selected context stacker | DeepGO-SE — historical model axis | +0.037009 | [+0.024107, +0.055267] |
| Development-selected context stacker | DeepGO-SE — same soft processing | +0.036390 | [+0.023531, +0.055117] |
| Development-selected context stacker | Development-selected global weight | +0.017331 | [+0.002410, +0.033496] |
| Development-selected context stacker | Fixed 50/50 combination | +0.025276 | [+0.011170, +0.042987] |
| Development-selected context stacker | Training-label frequency only | +0.040847 | [+0.024386, +0.062064] |
| Development-selected context stacker | LocalPlus — retained annotations | +0.018700 | [+0.002396, +0.035069] |
| Development-selected context stacker | LocalPlus — complete current-T0 curated seeds | +0.014593 | [-0.001905, +0.032004] |
| Development-selected context stacker | LocalPlus — historical model axis | +0.018700 | [+0.002396, +0.035069] |
| Development-selected context stacker | LocalPlus — same soft processing | +0.018700 | [+0.002396, +0.035069] |
| Development-selected context stacker | LocalPlus — matched training-label update | +0.018135 | [+0.002367, +0.034650] |
| Development-selected context stacker | Updated LocalPlus — same soft processing | +0.018135 | [+0.002367, +0.034650] |
| Development-selected context stacker | Current nonexperimental annotations | +0.047955 | [+0.035253, +0.066741] |

### Fixed source-update contrasts

| Candidate | Comparator | Fmax difference | Paired 95% interval |
|---|---|---:|---:|
| LocalPlus — matched training-label update | LocalPlus — retained annotations | +0.000564 | [-0.001038, +0.002839] |
| Updated LocalPlus — same soft processing | LocalPlus — same soft processing | +0.000564 | [-0.001038, +0.002839] |
| LocalPlus — complete current-T0 curated seeds | LocalPlus — retained annotations | +0.004106 | [+0.000963, +0.007544] |

## fixed_T0 primary paired contrasts

| Candidate | Comparator | Fmax difference | Paired 95% interval |
|---|---|---:|---:|
| Development-selected context stacker | Context GCN — evidence/relation features | +0.000000 | [+0.000000, +0.000000] |
| Development-selected context stacker | Context stacker — eight-layer GCN | +0.027334 | [+0.010237, +0.046230] |
| Development-selected context stacker | Context stacker — zero-layer MLP | +0.015381 | [-0.002592, +0.035150] |
| Development-selected context stacker | DeepGO-SE — sequence model | +0.078702 | [+0.051900, +0.108056] |
| Development-selected context stacker | DeepGO-SE — historical model axis | +0.078702 | [+0.051900, +0.108056] |
| Development-selected context stacker | DeepGO-SE — same soft processing | +0.078003 | [+0.050546, +0.107295] |
| Development-selected context stacker | Development-selected global weight | +0.032064 | [+0.003141, +0.062603] |
| Development-selected context stacker | Fixed 50/50 combination | +0.045136 | [+0.018634, +0.075694] |
| Development-selected context stacker | Training-label frequency only | +0.102816 | [+0.065553, +0.140969] |
| Development-selected context stacker | LocalPlus — retained annotations | +0.038544 | [+0.008030, +0.069139] |
| Development-selected context stacker | LocalPlus — complete current-T0 curated seeds | +0.027322 | [-0.004239, +0.059569] |
| Development-selected context stacker | LocalPlus — historical model axis | +0.038544 | [+0.008030, +0.069139] |
| Development-selected context stacker | LocalPlus — same soft processing | +0.038544 | [+0.008030, +0.069139] |
| Development-selected context stacker | LocalPlus — matched training-label update | +0.034907 | [+0.004885, +0.066213] |
| Development-selected context stacker | Updated LocalPlus — same soft processing | +0.034907 | [+0.004885, +0.066213] |
| Development-selected context stacker | Current nonexperimental annotations | +0.063924 | [+0.043943, +0.085867] |

### Fixed source-update contrasts

| Candidate | Comparator | Fmax difference | Paired 95% interval |
|---|---|---:|---:|
| LocalPlus — matched training-label update | LocalPlus — retained annotations | +0.003637 | [+0.000056, +0.006007] |
| Updated LocalPlus — same soft processing | LocalPlus — same soft processing | +0.003637 | [+0.000056, +0.006007] |
| LocalPlus — complete current-T0 curated seeds | LocalPlus — retained annotations | +0.011222 | [+0.004213, +0.017656] |

## Complete settings and aspects

MF = molecular activity; BP = biological process; CC = cellular location/structure. NK and LK are the native no-knowledge and limited-knowledge settings. Unavailable cells and absent coverage are retained explicitly. Full controls and source slices are in summary.json.

| View / setting / aspect | Cell status | Residual reference proteins | Selected stacker | Retained LocalPlus | Current-T0 LocalPlus |
|---|---|---:|---:|---:|---:|
| native/PK/molecular_function | Evaluated | 229 | 0.245247 | 0.109872 | 0.125798 |
| native/PK/biological_process | Evaluated | 322 | 0.073431 | 0.054732 | 0.058838 |
| native/PK/cellular_component | Evaluated | 1230 | 0.260227 | 0.194680 | 0.167363 |
| native/NK/molecular_function | Evaluated | 7 | 0.387597 | 0.210526 | 0.237037 |
| native/NK/biological_process | Evaluated | 8 | 0.310469 | 0.213650 | 0.237069 |
| native/NK/cellular_component | Evaluated | 32 | 0.484211 | 0.292517 | 0.311037 |
| native/LK/molecular_function | Evaluated | 15 | 0.550898 | 0.230216 | 0.244275 |
| native/LK/biological_process | Evaluated | 59 | 0.390567 | 0.338317 | 0.358277 |
| native/LK/cellular_component | Evaluated | 58 | 0.587646 | 0.471369 | 0.471545 |
| fixed_T0/PK/molecular_function | Evaluated | 228 | 0.299478 | 0.127212 | 0.139747 |
| fixed_T0/PK/biological_process | Evaluated | 319 | 0.210093 | 0.171550 | 0.182771 |
| fixed_T0/PK/cellular_component | Evaluated | 1230 | 0.267299 | 0.197996 | 0.170379 |
| fixed_T0/NK/molecular_function | Evaluated | 7 | 0.387597 | 0.210526 | 0.237037 |
| fixed_T0/NK/biological_process | Evaluated | 8 | 0.312727 | 0.214925 | 0.238213 |
| fixed_T0/NK/cellular_component | Evaluated | 32 | 0.484211 | 0.292517 | 0.311037 |
| fixed_T0/LK/molecular_function | Evaluated | 15 | 0.550898 | 0.230216 | 0.244275 |
| fixed_T0/LK/biological_process | Evaluated | 59 | 0.388728 | 0.340171 | 0.359870 |
| fixed_T0/LK/cellular_component | Evaluated | 58 | 0.587646 | 0.471369 | 0.471545 |

## Scope and limits

The snapshots are April 10–November 4, 2026 human GOA. The corresponding available GO-basic content dates are March 25 and July 26. The fixed-T0 sensitivity holds the ontology fixed and uses the same primary term mask. It is not a purified set of newly performed experiments. Native admission includes eleven experimental codes plus curator inference (IC) and traceable author statements (TAS). Source provenance is assessed separately.

The study is retrospective and not wholly developer-blind. Fit, validation and final accessions, identical full sequences and identical first-1,022-residue sequence inputs were separated. Near-homology, base-checkpoint training and publication independence are not established. Proteins can share studies, families and graph neighborhoods. The author’s original stacker used out-of-fold parent forecasts; this is an explicitly qualified temporal adaptation. GCN versus MLP also changes depth/capacity, so it does not isolate a causal benefit from GO topology.

These results do not replace the separate same-learner enriched-graph link-prediction comparisons. No graph, pruning rule or app default is automatically promoted. Failed controls and all declared cells remain retained.

## Reused methods

- [ProtBoost paper](https://arxiv.org/abs/2412.04529) and [pinned official implementation](https://github.com/btbpanda/CAFA5-protein-function-prediction-2nd-place/tree/52dce6c471337f2820550f779a6a1bb201353b2a).
- [Official CAFA6 source update](https://github.com/btbpanda/CAFA6-updates/tree/0ee85d2f07f724be1721ea39211f1b364535f976).
- [LAFA source](https://github.com/FriedbergLab/CAFA_forever/tree/c3fd5b9a5226348d88b9efadddb3214c803b80c4) and [democafa reference builder](https://github.com/FriedbergLab/democafa_package/tree/0ab84edbaddf5fef11125dc8adbd19167c3cc038).
- [Pinned native evaluator](https://github.com/claradepaolis/CAFA-evaluator-PK/tree/e386b085e204ccfbd75a4f52c1a8b25987d8b465).
- [CAFA4 assessment preprint, June 2026 revision](https://pmc.ncbi.nlm.nih.gov/articles/PMC13174626/): its historical-baseline comparisons distinguish annotation-data growth from methodological progress.
